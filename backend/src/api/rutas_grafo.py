"""Endpoints para gestión del grafo de movilidad."""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from src.grafo.modelos import Grafo, Nodo, Arista
from src.grafo.repositorio import RepositorioGrafo, ExcepcionRepositorio

router = APIRouter()

# Repositorio global (en producción usar dependency injection)
_repositorio: Optional[RepositorioGrafo] = None
_grafo_cache: Optional[Grafo] = None


def obtener_repositorio() -> RepositorioGrafo:
    global _repositorio
    if _repositorio is None:
        _repositorio = RepositorioGrafo("datos")
    return _repositorio


def obtener_grafo() -> Grafo:
    global _grafo_cache
    if _grafo_cache is None:
        repo = obtener_repositorio()
        # Intentar cargar grafo existente
        for nombre in ["transmilenio_grafo.json", "dataset_inicial_pdf.json", "grafo.json"]:
            try:
                _grafo_cache = repo.cargar_json(nombre)
                break
            except ExcepcionRepositorio:
                continue
        if _grafo_cache is None:
            # Generar sintético como fallback
            _grafo_cache = repo.generar_dataset_inicial_transmilenio(usar_gtfs_real=False)
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
    ruta_nodos, _ = repo.guardar_geojson(grafo, "temp_nodos.geojson", "temp_aristas.geojson")
    return FileResponse(ruta_nodos, media_type="application/geo+json", filename="nodos.geojson")


@router.get("/geojson/aristas")
async def geojson_aristas():
    """Descarga aristas como GeoJSON."""
    repo = obtener_repositorio()
    grafo = obtener_grafo()
    _, ruta_aristas = repo.guardar_geojson(grafo, "temp_nodos.geojson", "temp_aristas.geojson")
    return FileResponse(ruta_aristas, media_type="application/geo+json", filename="aristas.geojson")


@router.get("/graphml")
async def descargar_graphml():
    """Descarga grafo como GraphML."""
    repo = obtener_repositorio()
    grafo = obtener_grafo()
    ruta = repo.guardar_graphml(grafo, "temp_grafo.graphml")
    return FileResponse(ruta, media_type="application/xml", filename="grafo.graphml")


@router.post("/recargar")
async def recargar_grafo(usar_sintetico: bool = Query(True, description="Usar dataset sintético (False = intentar GTFS real)")):
    """Recarga el grafo desde archivo o regenera."""
    global _grafo_cache
    repo = obtener_repositorio()
    try:
        if usar_sintetico:
            _grafo_cache = repo.generar_dataset_inicial_transmilenio(usar_gtfs_real=False)
        else:
            _grafo_cache = repo.generar_dataset_inicial_transmilenio(usar_gtfs_real=True)
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