"""Endpoints para gestión del grafo de movilidad."""

import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from src.grafo.modelos import Grafo
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


@router.get("/")
async def obtener_grafo_completo():
    """Retorna el grafo completo (nodos + aristas)."""
    grafo = obtener_grafo()
    return {
        "dirigido": grafo.dirigido,
        "metadata": grafo.metadata,
        "nodos": {nid: nodo.model_dump() for nid, nodo in grafo.nodos.items()},
        "aristas": [arista.model_dump() for arista in grafo.aristas],
        "total_nodos": len(grafo.nodos),
        "total_aristas": len(grafo.aristas),
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
    return Response(content=json.dumps(geojson_nodos_data, ensure_ascii=False), media_type="application/geo+json")


@router.get("/geojson/aristas")
async def geojson_aristas():
    """Descarga aristas como GeoJSON."""
    repo = obtener_repositorio()
    grafo = obtener_grafo()
    _, geojson_aristas_data = repo.generar_geojson(grafo)
    return Response(content=json.dumps(geojson_aristas_data, ensure_ascii=False), media_type="application/geo+json")


@router.get("/graphml")
async def descargar_graphml():
    """Descarga grafo como GraphML."""
    repo = obtener_repositorio()
    grafo = obtener_grafo()
    return Response(content=repo.generar_graphml(grafo), media_type="application/xml")


@router.post("/recargar")
async def recargar_grafo(usar_sintetico: bool = Query(True, description="Usar dataset sintético (False = descargar red OSM con OSMnx)")):
    """Recarga el grafo desde archivo o regenera."""
    global _grafo_cache
    repo = obtener_repositorio()
    try:
        if usar_sintetico:
            _grafo_cache = repo.generar_dataset_sintetico_pdf()
        else:
            _grafo_cache = repo.generar_dataset_osm()
        return {
            "mensaje": "Grafo recargado",
            "nodos": len(_grafo_cache.nodos),
            "aristas": len(_grafo_cache.aristas),
        }
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
