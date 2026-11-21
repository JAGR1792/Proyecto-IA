"""Tests de categorías, dataset y comparación de clasificadores."""

from __future__ import annotations

import pandas as pd
import pytest

from src.grafo.modelos import (
    Arista,
    AtributosArista,
    Coordenadas,
    Grafo,
    NivelCongestion,
    Nodo,
    TipoNodo,
    TipoVia,
)
from src.ml.categorias import CATEGORIAS_CONGESTION, umbral_factor_a_categoria
from src.ml.clasificacion import entrenar_y_comparar, matriz_a_dataframe, preparar_xy
from src.ml.dataset import TARGET, construir_dataset_clasificacion, resumen_dataset


def _grafo_mini() -> Grafo:
    grafo = Grafo()
    for i, (lat, lon) in enumerate([(4.65, -74.06), (4.66, -74.06), (4.67, -74.05)], start=1):
        grafo.agregar_nodo(
            Nodo(
                id=f"n{i}",
                nombre=f"Nodo {i}",
                coordenadas=Coordenadas(latitud=lat, longitud=lon),
                tipo=TipoNodo.INTERSECCION,
            )
        )
    vias = [
        ("a1", "n1", "n2", TipoVia.PRIMARIA, 3),
        ("a2", "n2", "n3", TipoVia.RESIDENCIAL, 1),
        ("a3", "n1", "n3", TipoVia.SECUNDARIA, 2),
    ]
    for aid, o, d, tipo, carriles in vias:
        grafo.agregar_arista(
            Arista(
                id=aid,
                origen=o,
                destino=d,
                distancia=400.0,
                tiempo_estimado=1.2,
                velocidad_promedio=40.0,
                congestion=NivelCongestion.BAJA,
                atributos=AtributosArista(tipo_via=tipo, carriles=carriles, sentido_unico=True),
            )
        )
    return grafo


def test_umbral_factor_a_categoria() -> None:
    assert umbral_factor_a_categoria(1.0) == "baja"
    assert umbral_factor_a_categoria(1.39) == "baja"
    assert umbral_factor_a_categoria(1.40) == "media"
    assert umbral_factor_a_categoria(1.99) == "media"
    assert umbral_factor_a_categoria(2.0) == "alta"


def test_construir_dataset_tiene_clases_validas() -> None:
    df = construir_dataset_clasificacion(
        _grafo_mini(),
        horas=("08:00", "12:00", "17:00", "22:00"),
    )
    assert not df.empty
    assert set(df[TARGET].unique()).issubset(set(CATEGORIAS_CONGESTION))
    assert "tipo_via" in df.columns
    assert "hora_decimal" in df.columns
    resumen = resumen_dataset(df)
    assert resumen["filas"] == len(df)
    assert resumen["aristas_unicas"] == 3


def test_entrenar_y_comparar_sobre_dataset_sintetico() -> None:
    # Dataset tabular suficiente para split estratificado sin grafo OSM.
    filas = []
    for hora, intensidad, etiqueta in [
        (6.0, 0.3, "baja"),
        (8.0, 1.0, "alta"),
        (12.0, 0.4, "baja"),
        (17.0, 1.2, "alta"),
        (19.0, 0.8, "media"),
        (22.0, 0.1, "baja"),
    ]:
        for i in range(40):
            filas.append(
                {
                    "hora_decimal": hora,
                    "intensidad_hora": intensidad,
                    "distancia_m": 100 + i,
                    "tiempo_base_min": 0.5 + i * 0.01,
                    "velocidad_base_kmh": 30 + (i % 5),
                    "carriles": 1 + (i % 3),
                    "sentido_unico": i % 2,
                    "incidentes": 0,
                    "peso_tipo_via": 1.0 + (i % 3) * 0.1,
                    "tipo_via": ["residencial", "secundaria", "primaria"][i % 3],
                    "congestion": etiqueta,
                }
            )
    df = pd.DataFrame(filas)
    comparacion = entrenar_y_comparar(df, test_size=0.3)
    assert comparacion.mejor_modelo
    assert len(comparacion.resultados) == 5
    tabla = comparacion.tabla_metricas()
    assert set(tabla.columns) >= {"modelo", "accuracy", "f1_macro"}
    mejor = next(r for r in comparacion.resultados if r.nombre == comparacion.mejor_modelo)
    cm = matriz_a_dataframe(mejor.matriz_confusion)
    assert cm.shape == (3, 3)
    assert mejor.accuracy >= 0.5


def test_preparar_xy_falla_sin_columnas() -> None:
    with pytest.raises(ValueError, match="faltantes"):
        preparar_xy(pd.DataFrame({"x": [1]}))
