"""Tests ligeros de los endpoints HTTP de agrupamiento (K-Means)."""

from __future__ import annotations

import asyncio

import pandas as pd
import pytest
from fastapi import HTTPException

from src.api import rutas_ml


def test_obtener_agrupamiento_devuelve_json(monkeypatch):
    ejemplo = {"k": 6, "metricas": {"silueta": 0.27}, "grupos": []}
    monkeypatch.setattr(rutas_ml.agrupamiento, "cargar_metricas_desde_disco", lambda: ejemplo)

    payload = asyncio.run(rutas_ml.obtener_agrupamiento())

    assert payload["k"] == 6


def test_obtener_agrupamiento_sin_json_devuelve_404(monkeypatch):
    def _fallar():
        raise FileNotFoundError("sin json")

    monkeypatch.setattr(rutas_ml.agrupamiento, "cargar_metricas_desde_disco", _fallar)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(rutas_ml.obtener_agrupamiento())
    assert exc.value.status_code == 404


def test_aristas_agrupadas_filtra_por_cluster(monkeypatch):
    tabla = pd.DataFrame(
        {
            "arista_id": ["a", "b", "c"],
            "cluster": [0, 1, 1],
            "nombre_cluster": ["Corredores rápidos", "Malla local densa", "Malla local densa"],
            "nombre_via": ["Av 1", "Calle 2", "Calle 3"],
            "tipo_via": ["primaria", "residencial", "residencial"],
            "silueta": [0.5, 0.31234, 0.2],
        }
    )
    monkeypatch.setattr(rutas_ml.agrupamiento, "cargar_asignaciones", lambda: tabla)

    todo = asyncio.run(rutas_ml.obtener_aristas_agrupadas())
    solo_uno = asyncio.run(rutas_ml.obtener_aristas_agrupadas(cluster=1))

    assert todo["total"] == 3
    assert solo_uno["total"] == 2
    assert {a["arista_id"] for a in solo_uno["aristas"]} == {"b", "c"}


def test_reentrenar_rechaza_k_fuera_de_rango():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(rutas_ml.reentrenar_agrupamiento(k=1))
    assert exc.value.status_code == 422
