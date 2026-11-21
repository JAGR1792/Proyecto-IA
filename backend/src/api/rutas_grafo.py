"""Endpoints para gestión del grafo de movilidad."""

import json
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from src.congestion.horarios import grafo_en_hora, invalidar_cache_grafo_en_hora
from src.grafo.modelos import Arista, Grafo, Nodo
from src.grafo.repositorio import ExcepcionRepositorio, RepositorioGrafo

router = APIRouter()

# Repositorio global (en producción usar dependency injection)
_repositorio: RepositorioGrafo | None = None
_grafo_cache: Grafo | None = None


def obtener_repositorio() -> RepositorioGrafo:
    global _repositorio
    if _repositorio is None:
        _repositorio = RepositorioGrafo("datos")
    return _repositorio


def obtener_grafo() -> Grafo:
    global _grafo_cache
    if _grafo_cache is None:
        repo = obtener_repositorio()
        # Prioridad: dataset OSM real (si existe) → sintético PDF
        for nombre in ["dataset_osm.json", "dataset_inicial_pdf.json", "grafo.json"]:
            try:
                _grafo_cache = repo.cargar_json(nombre)
                break
            except ExcepcionRepositorio:
                continue
        if _grafo_cache is None:
            # Generar sintético como fallback
            _grafo_cache = repo.generar_dataset_sintetico_pdf()
    return _grafo_cache


def _serializar_nodo(nodo: Nodo) -> dict:
    """Serializa un nodo para respuestas API."""
    return nodo.model_dump()


def _serializar_arista(arista: Arista, *, incluir_geometria: bool) -> dict:
    """Serializa una arista; omite geometría OSM salvo que se pida explícitamente."""
    data = arista.model_dump()
    if not incluir_geometria and data.get("atributos"):
        atributos = dict(data["atributos"])
        atributos.pop("geometria", None)
        data["atributos"] = atributos
    return data


@router.get("/resumen")
async def resumen_grafo():
    """Totales y metadata del grafo en caché (sin aristas ni geometría)."""
    grafo = obtener_grafo()
    return {
        "total_nodos": len(grafo.nodos),
        "total_aristas": len(grafo.aristas),
        "metadata": grafo.metadata,
        "dirigido": grafo.dirigido,
    }


@router.get("/nodos/indice")
async def indice_nodos():
    """Lista compacta de nodos para autocomplete y clic en mapa."""
    grafo = obtener_grafo()
    return {
        "nodos": [
            {
                "id": nodo.id,
                "nombre": nodo.nombre,
                "lat": nodo.coordenadas.latitud,
                "lon": nodo.coordenadas.longitud,
                "tipo": nodo.tipo.value,
            }
            for nodo in grafo.nodos.values()
        ],
        "total": len(grafo.nodos),
    }


@router.get("/")
async def obtener_grafo_completo(
    hora_salida: Annotated[str | None, Query(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")] = None,
    incluir_geometria: bool = Query(
        False,
        description="Incluir coordenadas LineString OSM en atributos de cada arista",
    ),
):
    """Retorna el grafo con la congestión sintética para HH:MM, si se solicita."""
    grafo = grafo_en_hora(obtener_grafo(), hora_salida)
    return {
        "dirigido": grafo.dirigido,
        "metadata": grafo.metadata,
        "nodos": {nid: _serializar_nodo(nodo) for nid, nodo in grafo.nodos.items()},
        "aristas": [
            _serializar_arista(arista, incluir_geometria=incluir_geometria)
            for arista in grafo.aristas
        ],
        "total_nodos": len(grafo.nodos),
        "total_aristas": len(grafo.aristas),
        "incluir_geometria": incluir_geometria,
    }


@router.get("/nodos")
async def listar_nodos():
    """Lista todos los nodos del grafo."""
    grafo = obtener_grafo()
    return {
        "nodos": {nid: nodo.model_dump() for nid, nodo in grafo.nodos.items()},
        "total": len(grafo.nodos),
    }


@router.get("/nodos/{nodo_id}")
async def obtener_nodo(nodo_id: str):
    """Obtiene un nodo específico por ID."""
    grafo = obtener_grafo()
    if nodo_id not in grafo.nodos:
        raise HTTPException(status_code=404, detail=f"Nodo '{nodo_id}' no encontrado")
    return grafo.nodos[nodo_id].model_dump()


@router.get("/aristas")
async def listar_aristas():
    """Lista todas las aristas del grafo."""
    grafo = obtener_grafo()
    return {
        "aristas": [arista.model_dump() for arista in grafo.aristas],
        "total": len(grafo.aristas),
    }


@router.get("/vecinos/{nodo_id}")
async def obtener_vecinos(nodo_id: str):
    """Obtiene nodos vecinos (aristas salientes) de un nodo."""
    grafo = obtener_grafo()
    if nodo_id not in grafo.nodos:
        raise HTTPException(status_code=404, detail=f"Nodo '{nodo_id}' no encontrado")
    vecinos = grafo.obtener_vecinos(nodo_id)
    return {
        "nodo": nodo_id,
        "vecinos": [arista.model_dump() for arista in vecinos],
        "total": len(vecinos),
    }


@router.get("/geojson/nodos")
async def geojson_nodos():
    """Descarga nodos como GeoJSON."""
    repo = obtener_repositorio()
    grafo = obtener_grafo()
    geojson_nodos_data, _ = repo.generar_geojson(grafo)
    return Response(
        content=json.dumps(geojson_nodos_data, ensure_ascii=False),
        media_type="application/geo+json",
    )


@router.get("/geojson/aristas")
async def geojson_aristas():
    """Descarga aristas como GeoJSON."""
    repo = obtener_repositorio()
    grafo = obtener_grafo()
    _, geojson_aristas_data = repo.generar_geojson(grafo)
    return Response(
        content=json.dumps(geojson_aristas_data, ensure_ascii=False),
        media_type="application/geo+json",
    )


@router.get("/graphml")
async def descargar_graphml():
    """Descarga grafo como GraphML."""
    repo = obtener_repositorio()
    grafo = obtener_grafo()
    return Response(content=repo.generar_graphml(grafo), media_type="application/xml")


@router.post("/recargar")
async def recargar_grafo(
    usar_sintetico: bool = Query(
        True, description="Usar dataset sintético (False = OSM en vivo o desde disco)"
    ),
    desde_archivo: bool = Query(
        False,
        description="Si true, recarga dataset_osm.json del disco (sin descarga OSMnx)",
    ),
    radio_metros: int = Query(
        1200,
        ge=500,
        le=50_000,
        description="Radio de descarga OSM en metros (modo point/mosaico; descarga en vivo)",
    ),
    lugar: str | None = Query(
        None,
        description="Lugar OSM; por defecto Universidad Sergio Arboleda (Chapinero)",
    ),
    modo: str = Query(
        "point",
        pattern="^(mosaico|place|point)$",
        description="point (Chapinero); mosaico (Bogotá tiled); place (descarga en vivo)",
    ),
    reentrenar_ml: bool = Query(
        False,
        description="Regenerar CSV y modelo ML tras recargar (puede tardar en grafos grandes)",
    ),
):
    """Recarga el grafo desde archivo en disco, sintético o descarga OSM (uso offline preferido)."""
    global _grafo_cache
    repo = obtener_repositorio()
    invalidar_cache_grafo_en_hora()
    try:
        if usar_sintetico:
            _grafo_cache = repo.generar_dataset_sintetico_pdf()
            return {
                "mensaje": "Grafo recargado (sintético)",
                "nodos": len(_grafo_cache.nodos),
                "aristas": len(_grafo_cache.aristas),
            }

        if desde_archivo:
            _grafo_cache = repo.cargar_dataset_osm_desde_disco()
            respuesta_archivo: dict = {
                "mensaje": "Grafo recargado desde dataset OSM en disco",
                "nodos": len(_grafo_cache.nodos),
                "aristas": len(_grafo_cache.aristas),
                "metadata": _grafo_cache.metadata,
            }
            if reentrenar_ml:
                from src.api.rutas_ml import reentrenar_tras_grafo_nuevo

                try:
                    respuesta_archivo["ml"] = reentrenar_tras_grafo_nuevo()
                except Exception as ml_err:
                    respuesta_archivo["ml"] = {"error": str(ml_err)}
            return respuesta_archivo

        kwargs: dict = {
            "radio_metros": radio_metros,
            "modo": modo,
            "lugar": lugar or "Universidad Sergio Arboleda, Bogotá, Colombia",
        }
        _grafo_cache = repo.generar_dataset_osm(**kwargs)

        from src.api.rutas_ml import reentrenar_tras_grafo_nuevo

        ml_info: dict | None = None
        try:
            ml_info = reentrenar_tras_grafo_nuevo()
        except Exception as ml_err:
            ml_info = {"error": str(ml_err)}

        respuesta: dict = {
            "mensaje": "Grafo descargado desde OSM (OSMnx) y guardado en datos/",
            "nodos": len(_grafo_cache.nodos),
            "aristas": len(_grafo_cache.aristas),
            "modo": modo,
            "lugar": kwargs["lugar"],
            "radio_metros": radio_metros if modo == "point" else None,
            "metadata": _grafo_cache.metadata,
        }
        if ml_info is not None:
            respuesta["ml"] = ml_info
        return respuesta
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error recargando grafo: {e}")


@router.get("/estadisticas")
async def estadisticas_grafo():
    """Estadísticas descriptivas del grafo."""
    from src.grafo.validadores import calcular_estadisticas, validar_grafo_completo

    grafo = obtener_grafo()
    stats = calcular_estadisticas(grafo)
    valido, errores = validar_grafo_completo(grafo)
    return {
        "valido": valido,
        "errores": errores,
        "estadisticas": stats,
    }
