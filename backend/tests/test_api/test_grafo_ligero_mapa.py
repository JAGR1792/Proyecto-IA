"""Endpoints ligeros de grafo y mapa por bbox."""

import asyncio
import json

from src.api import rutas_grafo, rutas_mapa
from src.congestion.horarios import grafo_en_hora, invalidar_cache_grafo_en_hora


async def _body(resp):
    return json.loads(resp.body.decode("utf-8"))


def test_resumen_e_indice(monkeypatch, grafo_lineal):
    monkeypatch.setattr(rutas_grafo, "obtener_grafo", lambda: grafo_lineal)
    resumen = asyncio.run(rutas_grafo.resumen_grafo())
    assert resumen["total_nodos"] == 3
    assert resumen["total_aristas"] == 2
    assert "metadata" in resumen

    indice = asyncio.run(rutas_grafo.indice_nodos())
    assert indice["total"] == 3
    assert indice["nodos"][0] == {
        "id": "N1",
        "nombre": "Nodo N1",
        "lat": 4.60,
        "lon": -74.00,
        "tipo": "interseccion",
    }
    assert set(indice["nodos"][0]) == {"id", "nombre", "lat", "lon", "tipo"}


def test_grafo_completo_sin_geometria_por_defecto(monkeypatch, grafo_lineal):
    monkeypatch.setattr(rutas_grafo, "obtener_grafo", lambda: grafo_lineal)
    body = asyncio.run(
        rutas_grafo.obtener_grafo_completo(hora_salida="17:00", incluir_geometria=False)
    )
    assert body["incluir_geometria"] is False
    for arista in body["aristas"]:
        assert "geometria" not in (arista.get("atributos") or {})


def test_geojson_mapa_usa_cache_compartida(monkeypatch, grafo_lineal):
    llamadas = {"n": 0}

    def _grafo():
        llamadas["n"] += 1
        return grafo_lineal

    monkeypatch.setattr(rutas_mapa, "obtener_grafo", _grafo)

    resp = asyncio.run(rutas_mapa.geojson_nodos())
    data = asyncio.run(_body(resp))
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 3
    assert data["truncado"] is False
    assert llamadas["n"] >= 1


def test_geojson_filtra_bbox(monkeypatch, grafo_lineal):
    monkeypatch.setattr(rutas_mapa, "obtener_grafo", lambda: grafo_lineal)
    resp = asyncio.run(
        rutas_mapa.geojson_nodos(
            min_lat=4.615,
            max_lat=4.625,
            min_lon=-74.01,
            max_lon=-73.99,
        )
    )
    data = asyncio.run(_body(resp))
    assert data["truncado"] is False
    assert data["total_filtrado"] == 1
    assert data["features"][0]["properties"]["id"] == "N3"


def test_geojson_truncado(monkeypatch, grafo_lineal):
    monkeypatch.setattr(rutas_mapa, "obtener_grafo", lambda: grafo_lineal)
    monkeypatch.setattr(rutas_mapa, "LIMITE_FEATURES_GEOJSON", 1)
    resp = asyncio.run(
        rutas_mapa.geojson_nodos(
            min_lat=4.59,
            max_lat=4.63,
            min_lon=-74.01,
            max_lon=-73.99,
        )
    )
    data = asyncio.run(_body(resp))
    assert data["truncado"] is True
    assert len(data["features"]) == 1
    assert data["total_filtrado"] == 3


def test_geojson_sin_bbox_no_trunca(monkeypatch, grafo_lineal):
    monkeypatch.setattr(rutas_mapa, "obtener_grafo", lambda: grafo_lineal)
    monkeypatch.setattr(rutas_mapa, "LIMITE_FEATURES_GEOJSON", 1)
    resp = asyncio.run(rutas_mapa.geojson_nodos())
    data = asyncio.run(_body(resp))
    assert data["truncado"] is False
    assert len(data["features"]) == 3
    assert data["total_filtrado"] == 3
    assert data["limite"] is None


def test_grafo_en_hora_memoizado(grafo_lineal):
    invalidar_cache_grafo_en_hora()
    a = grafo_en_hora(grafo_lineal, "08:00")
    b = grafo_en_hora(grafo_lineal, "08:00")
    assert a is b
    invalidar_cache_grafo_en_hora()
    c = grafo_en_hora(grafo_lineal, "08:00")
    assert c is not a
