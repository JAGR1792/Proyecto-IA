"""Endpoints para mapa y visualización (GeoJSON, GraphML)."""

import json
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from src.api.rutas_grafo import obtener_grafo, obtener_repositorio
from src.congestion.horarios import grafo_en_hora

router = APIRouter()

# Tope de seguridad al servir capas por viewport (zoom muy abierto)
LIMITE_FEATURES_GEOJSON = 4000


def _response_geojson(datos: dict[str, Any]) -> Response:
    """Serializa un FeatureCollection a JSON sin tocar disco (compatible Vercel)."""
    return Response(
        content=json.dumps(datos, ensure_ascii=False),
        media_type="application/geo+json",
    )


def _punto_en_bbox(
    lat: float,
    lon: float,
    min_lat: float,
    max_lat: float,
    min_lon: float,
    max_lon: float,
) -> bool:
    return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon


def _feature_intersecta_bbox(
    feature: dict[str, Any],
    min_lat: float,
    max_lat: float,
    min_lon: float,
    max_lon: float,
) -> bool:
    """True si algún vértice del punto o LineString cae dentro del bbox."""
    geometria = feature.get("geometry") or {}
    tipo = geometria.get("type")
    coords = geometria.get("coordinates")
    if tipo == "Point" and coords and len(coords) >= 2:
        lon, lat = coords[0], coords[1]
        return _punto_en_bbox(lat, lon, min_lat, max_lat, min_lon, max_lon)
    if tipo == "LineString" and coords:
        for par in coords:
            if len(par) >= 2:
                lon, lat = par[0], par[1]
                if _punto_en_bbox(lat, lon, min_lat, max_lat, min_lon, max_lon):
                    return True
    return False


def _aplicar_bbox_y_tope(
    coleccion: dict[str, Any],
    *,
    min_lat: float | None,
    min_lon: float | None,
    max_lat: float | None,
    max_lon: float | None,
    limite: int | None = None,
) -> dict[str, Any]:
    """Filtra features por bbox y aplica tope con bandera truncado."""
    features = list(coleccion.get("features") or [])
    bbox_activo = all(v is not None for v in (min_lat, min_lon, max_lat, max_lon))
    if bbox_activo:
        assert (
            min_lat is not None
            and max_lat is not None
            and min_lon is not None
            and max_lon is not None
        )
        features = [
            f for f in features if _feature_intersecta_bbox(f, min_lat, max_lat, min_lon, max_lon)
        ]

    total_filtrado = len(features)
    tope = limite if limite is not None else (LIMITE_FEATURES_GEOJSON if bbox_activo else None)
    truncado = tope is not None and total_filtrado > tope
    if truncado and tope is not None:
        features = features[:tope]

    resultado: dict[str, Any] = {
        "type": "FeatureCollection",
        "features": features,
        "truncado": truncado,
        "total_filtrado": total_filtrado,
        "limite": tope,
    }
    if bbox_activo:
        resultado["bbox"] = {
            "min_lat": min_lat,
            "min_lon": min_lon,
            "max_lat": max_lat,
            "max_lon": max_lon,
        }
    return resultado


def _validar_bbox_parcial(
    min_lat: float | None,
    min_lon: float | None,
    max_lat: float | None,
    max_lon: float | None,
) -> None:
    valores = (min_lat, min_lon, max_lat, max_lon)
    if any(v is not None for v in valores) and not all(v is not None for v in valores):
        raise HTTPException(
            status_code=422,
            detail="Debe enviar los cuatro parámetros de bbox: min_lat, min_lon, max_lat, max_lon",
        )
    if all(v is not None for v in valores):
        assert (
            min_lat is not None
            and max_lat is not None
            and min_lon is not None
            and max_lon is not None
        )
        if min_lat > max_lat or min_lon > max_lon:
            raise HTTPException(status_code=422, detail="BBox inválido: min debe ser menor que max")


@router.get("/geojson/nodos")
async def geojson_nodos(
    min_lat: float | None = None,
    min_lon: float | None = None,
    max_lat: float | None = None,
    max_lon: float | None = None,
    hora_salida: Annotated[str | None, Query(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")] = None,
):
    """GeoJSON de nodos para visualización en mapa (opcionalmente recortado por bbox)."""
    _validar_bbox_parcial(min_lat, min_lon, max_lat, max_lon)
    repo = obtener_repositorio()
    grafo = grafo_en_hora(obtener_grafo(), hora_salida)
    geojson_nodos_data, _ = repo.generar_geojson(grafo)
    coleccion = _aplicar_bbox_y_tope(
        geojson_nodos_data,
        min_lat=min_lat,
        min_lon=min_lon,
        max_lat=max_lat,
        max_lon=max_lon,
    )
    if hora_salida:
        coleccion["hora_salida"] = hora_salida
    return _response_geojson(coleccion)


@router.get("/geojson/aristas")
async def geojson_aristas(
    min_lat: float | None = None,
    min_lon: float | None = None,
    max_lat: float | None = None,
    max_lon: float | None = None,
    hora_salida: Annotated[str | None, Query(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")] = None,
):
    """GeoJSON de aristas para visualización en mapa (opcionalmente recortado por bbox)."""
    _validar_bbox_parcial(min_lat, min_lon, max_lat, max_lon)
    repo = obtener_repositorio()
    grafo = grafo_en_hora(obtener_grafo(), hora_salida)
    _, geojson_aristas_data = repo.generar_geojson(grafo)
    coleccion = _aplicar_bbox_y_tope(
        geojson_aristas_data,
        min_lat=min_lat,
        min_lon=min_lon,
        max_lat=max_lat,
        max_lon=max_lon,
    )
    if hora_salida:
        coleccion["hora_salida"] = hora_salida
    return _response_geojson(coleccion)


@router.get("/graphml")
async def descargar_graphml():
    """GraphML para Gephi, NetworkX, etc."""
    repo = obtener_repositorio()
    grafo = obtener_grafo()
    graphml = repo.generar_graphml(grafo)
    return Response(content=graphml, media_type="application/xml")


@router.get("/bbox")
async def bounding_box():
    """Bounding box del grafo para centrar mapa."""
    grafo = obtener_grafo()

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
