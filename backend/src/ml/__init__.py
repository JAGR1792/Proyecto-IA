"""Aprendizaje automático del Corte 3 (clasificación de congestión)."""

from src.ml.categorias import CATEGORIAS_CONGESTION, umbral_factor_a_categoria
from src.ml.clasificacion import ComparacionModelos, entrenar_y_comparar
from src.ml.dataset import FEATURES_NUMERICAS, TARGET, construir_dataset_clasificacion

__all__ = [
    "CATEGORIAS_CONGESTION",
    "ComparacionModelos",
    "FEATURES_NUMERICAS",
    "TARGET",
    "construir_dataset_clasificacion",
    "entrenar_y_comparar",
    "umbral_factor_a_categoria",
]
