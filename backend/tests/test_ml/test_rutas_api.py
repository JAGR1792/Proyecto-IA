"""Tests ligeros de los endpoints HTTP de clasificación ML."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from src.api import rutas_ml
from src.ml.clasificacion import reentrenar_y_persistir
from tests.test_ml.test_clasificacion import _grafo_mini


@pytest.fixture
def grafo_ml():
    return _grafo_mini()


@pytest.fixture(autouse=True)
def limpiar_cache_modelo():
    """Evita que un test contamine la caché del pipeline."""
    rutas_ml._invalidar_cache_modelo()
    yield
    rutas_ml._invalidar_cache_modelo()


@pytest.fixture(autouse=True)
def parchear_grafo(monkeypatch, grafo_ml):
    monkeypatch.setattr(rutas_ml, "obtener_grafo", lambda: grafo_ml)


def test_obtener_metricas_incluye_modelo_disponible(monkeypatch, tmp_path: Path):
    ejemplo = {
        "resumen_dataset": {"filas": 12, "aristas_unicas": 3},
        "mejor_modelo": "Gradient Boosting",
        "metricas": [],
        "matrices_confusion": {},
    }
    monkeypatch.setattr(rutas_ml, "cargar_metricas_desde_disco", lambda: ejemplo)
    monkeypatch.setattr(rutas_ml, "modelo_disponible", lambda: True)

    payload = asyncio.run(rutas_ml.obtener_metricas_clasificacion())

    assert payload["mejor_modelo"] == "Gradient Boosting"
    assert payload["modelo_disponible"] is True


def test_obtener_metricas_sin_json_devuelve_404(monkeypatch):
    def _fallar():
        raise FileNotFoundError("sin json")

    monkeypatch.setattr(rutas_ml, "cargar_metricas_desde_disco", _fallar)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(rutas_ml.obtener_metricas_clasificacion())
    assert exc.value.status_code == 404


def test_predecir_forma_respuesta(tmp_path: Path, grafo_ml):
    datos = tmp_path / "datos"
    reentrenar_y_persistir(grafo_ml, base_datos=datos, test_size=0.3)
    from src.ml.clasificacion import cargar_modelo

    ruta_modelo = list((datos / "ml").glob("*.joblib"))[0]
    rutas_ml._modelo_cache = cargar_modelo(ruta_modelo)

    salida = asyncio.run(
        rutas_ml.predecir_clasificacion(
            rutas_ml.PredecirCongestionEntrada(hora_salida="08:00", arista_ids=["a1", "a2"])
        )
    )

    assert salida["hora_salida"] == "08:00"
    assert salida["total"] == 2
    assert len(salida["predicciones"]) == 2
    for fila in salida["predicciones"]:
        assert set(fila.keys()) == {"arista_id", "congestion", "hora_salida"}
        assert fila["hora_salida"] == "08:00"
        assert fila["congestion"] in {"baja", "media", "alta"}


def test_predecir_arista_desconocida_422(monkeypatch, tmp_path: Path, grafo_ml):
    datos = tmp_path / "datos"
    reentrenar_y_persistir(grafo_ml, base_datos=datos, test_size=0.3)
    from src.ml.clasificacion import cargar_modelo

    ruta_modelo = list((datos / "ml").glob("*.joblib"))[0]
    rutas_ml._modelo_cache = cargar_modelo(ruta_modelo)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            rutas_ml.predecir_clasificacion(
                rutas_ml.PredecirCongestionEntrada(hora_salida="12:00", arista_ids=["fantasma"])
            )
        )
    assert exc.value.status_code == 422
    assert "fantasma" in exc.value.detail


def test_predecir_sin_modelo_devuelve_503(monkeypatch):
    def _sin_modelo():
        raise FileNotFoundError("no joblib")

    monkeypatch.setattr(rutas_ml, "cargar_modelo", _sin_modelo)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            rutas_ml.predecir_clasificacion(rutas_ml.PredecirCongestionEntrada(hora_salida="09:30"))
        )
    assert exc.value.status_code == 503


def test_entrada_hora_invalida_rechazada():
    with pytest.raises(ValidationError):
        rutas_ml.PredecirCongestionEntrada(hora_salida="25:99")


def test_router_expone_rutas_regresion_y_clasificacion():
    paths = {route.path for route in rutas_ml.router.routes}
    assert {
        "/estado",
        "/predecir",
        "/ruta",
        "/clasificacion",
        "/clasificacion/predecir",
        "/clasificacion/reentrenar",
    }.issubset(paths)
