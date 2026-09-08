"""Endpoints para mapa y visualización (GeoJSON, GraphML)."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path

from src.grafo.repositorio import RepositorioGrafo, ExcepcionRepositorio

router = APIRouter()

_NOMBRES = ["dataset_osm.json", "transmilenio_grafo.json", "dataset_inicial_pdf.json", "grafo.json"]


def _cargar_grafo() -> "Grafo":
    """Carga el grafo con la misma prioridad que rutas_grafo."""
    from src.grafo.modelos import Grafo
    repo = RepositorioGrafo("datos")
    for nombre in _NOMBRES:
        try:
            return repo.cargar_json(nombre)
        except ExcepcionRepositorio:
            continue
    return repo.generar_dataset_inicial_transmilenio(usar_gtfs_real=False)


@router.get("/geojson/nodos")
async def geojson_nodos():
    """GeoJSON de nodos para visualización en mapa."""
    repo = RepositorioGrafo("datos")
    grafo = _cargar_grafo()
    ruta_nodos, _ = repo.guardar_geojson(grafo, "mapa_nodos.geojson", "mapa_aristas.geojson")
    return FileResponse(ruta_nodos, media_type="application/geo+json", filename="nodos.geojson")


@router.get("/geojson/aristas")
async def geojson_aristas():
    """GeoJSON de aristas para visualización en mapa."""
    repo = RepositorioGrafo("datos")
    grafo = _cargar_grafo()
    _, ruta_aristas = repo.guardar_geojson(grafo, "mapa_nodos.geojson", "mapa_aristas.geojson")
    return FileResponse(ruta_aristas, media_type="application/geo+json", filename="aristas.geojson")


@router.get("/graphml")
async def descargar_graphml():
    """GraphML para Gephi, NetworkX, etc."""
    repo = RepositorioGrafo("datos")
    grafo = _cargar_grafo()
    ruta = repo.guardar_graphml(grafo, "mapa_grafo.graphml")
    return FileResponse(ruta, media_type="application/xml", filename="grafo.graphml")


@router.get("/bbox")
async def bounding_box():
    """Bounding box del grafo para centrar mapa."""
    grafo = _cargar_grafo()

    lats = [n.coordenadas.latitud for n in grafo.nodos.values()]
    lons = [n.coordenadas.longitud for n in grafo.nodos.values()]

    return {
        "min_lat": min(lats),
        "max_lat": max(lats),
        "min_lon": min(lons),
        "max_lon": max(lons),
        "centro_lat": (min(lats) + max(lats)) / 2,
        "centro_lon": (min(lons) + max(lons)) / 2,
    }