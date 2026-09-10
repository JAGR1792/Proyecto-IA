"""Endpoints para mapa y visualización (GeoJSON, GraphML)."""

import json
from typing import TYPE_CHECKING

from fastapi import APIRouter
from fastapi.responses import Response

from src.grafo.repositorio import ExcepcionRepositorio, RepositorioGrafo

if TYPE_CHECKING:
    from src.grafo.modelos import Grafo

router = APIRouter()

_NOMBRES = ["dataset_osm.json", "taxis_grafo.json", "dataset_inicial_pdf.json", "grafo.json"]


def _cargar_grafo() -> "Grafo":
    """Carga el grafo con la misma prioridad que rutas_grafo."""
    repo = RepositorioGrafo("datos")
    for nombre in _NOMBRES:
        try:
            return repo.cargar_json(nombre)
        except ExcepcionRepositorio:
            continue
    return repo.generar_dataset_inicial_taxis(usar_gtfs_real=False)


def _response_geojson(datos: dict) -> Response:
    """Serializa un FeatureCollection a JSON sin tocar disco (compatible Vercel)."""
    return Response(
        content=json.dumps(datos, ensure_ascii=False),
        media_type="application/geo+json",
    )


@router.get("/geojson/nodos")
async def geojson_nodos():
    """GeoJSON de nodos para visualización en mapa."""
    repo = RepositorioGrafo("datos")
    grafo = _cargar_grafo()
    geojson_nodos_data, _ = repo.generar_geojson(grafo)
    return _response_geojson(geojson_nodos_data)


@router.get("/geojson/aristas")
async def geojson_aristas():
    """GeoJSON de aristas para visualización en mapa."""
    repo = RepositorioGrafo("datos")
    grafo = _cargar_grafo()
    _, geojson_aristas_data = repo.generar_geojson(grafo)
    return _response_geojson(geojson_aristas_data)


@router.get("/graphml")
async def descargar_graphml():
    """GraphML para Gephi, NetworkX, etc."""
    repo = RepositorioGrafo("datos")
    grafo = _cargar_grafo()
    graphml = repo.generar_graphml(grafo)
    return Response(content=graphml, media_type="application/xml")


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