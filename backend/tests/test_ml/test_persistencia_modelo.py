"""Persistencia joblib y predicción sobre grafo mini."""

from __future__ import annotations

from pathlib import Path

from src.ml.clasificacion import (
    cargar_modelo,
    construir_features_prediccion,
    predecir_congestion_aristas,
    reentrenar_y_persistir,
)
from tests.test_ml.test_clasificacion import _grafo_mini


def test_guardar_cargar_joblib(tmp_path: Path) -> None:
    """Round-trip joblib con pipeline entrenado en grafo mini."""
    datos = tmp_path / "datos"
    resultado = reentrenar_y_persistir(_grafo_mini(), base_datos=datos, test_size=0.3)
    assert resultado["mejor_modelo"]
    assert Path(resultado["modelo_guardado"]).is_file()
    pipeline = cargar_modelo(Path(resultado["modelo_guardado"]))
    preds = predecir_congestion_aristas(pipeline, _grafo_mini(), "08:00", ["a1"])
    assert len(preds) == 1
    assert preds[0]["congestion"] in {"baja", "media", "alta"}


def test_construir_features_sin_arista_desconocida() -> None:
    df = construir_features_prediccion(_grafo_mini(), "12:00", ["no_existe", "a1"])
    assert len(df) == 1
    assert df.iloc[0]["arista_id"] == "a1"
