"""Entrenamiento y comparación de clasificadores de congestión."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.svm import LinearSVC

from src.congestion.horarios import intensidad_en_hora, peso_tipo_via
from src.grafo.modelos import Grafo, NivelCongestion
from src.ml.categorias import CATEGORIAS_CONGESTION
from src.ml.dataset import (
    FEATURE_CATEGORICA,
    FEATURES_NUMERICAS,
    TARGET,
    construir_dataset_clasificacion,
    guardar_dataset,
    resumen_dataset,
)

SEMILLA = 42

NOMBRE_ARCHIVO_MODELO = "modelo_clasificacion_congestion.joblib"
NOMBRE_ARCHIVO_METRICAS = "metricas_clasificacion.json"
NOMBRE_ARCHIVO_CSV = "dataset_clasificacion_congestion.csv"


def directorio_ml(base_datos: Path | None = None) -> Path:
    """Ruta ``backend/datos/ml`` (crea el directorio si no existe)."""
    if base_datos is None:
        base_datos = Path(__file__).resolve().parents[2] / "datos"
    destino = base_datos / "ml"
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def ruta_modelo(base_datos: Path | None = None) -> Path:
    """Ruta del pipeline sklearn persistido con joblib."""
    return directorio_ml(base_datos) / NOMBRE_ARCHIVO_MODELO


def ruta_metricas(base_datos: Path | None = None) -> Path:
    """Ruta del JSON de métricas de comparación de modelos."""
    return directorio_ml(base_datos) / NOMBRE_ARCHIVO_METRICAS


def guardar_modelo(pipeline: Any, destino: Path | str | None = None) -> Path:
    """Persiste el pipeline sklearn del mejor clasificador.

    Args:
        pipeline: Pipeline entrenado (preprocesador + estimador).
        destino: Archivo `.joblib`; por defecto ``datos/ml/modelo_...``.

    Returns:
        Ruta escrita.
    """
    ruta = Path(destino) if destino is not None else ruta_modelo()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, ruta)
    return ruta


def cargar_modelo(origen: Path | str | None = None) -> Any:
    """Carga el pipeline desde joblib.

    Raises:
        FileNotFoundError: Si no existe el archivo del modelo.
    """
    ruta = Path(origen) if origen is not None else ruta_modelo()
    if not ruta.is_file():
        raise FileNotFoundError(f"No hay modelo entrenado en {ruta}")
    return joblib.load(ruta)


def modelo_disponible(origen: Path | str | None = None) -> bool:
    """Indica si existe un `.joblib` entrenado."""
    ruta = Path(origen) if origen is not None else ruta_modelo()
    return ruta.is_file()


def _hora_a_decimal(hora_salida: str) -> float:
    horas, minutos = map(int, hora_salida.split(":"))
    return horas + minutos / 60.0


def construir_features_prediccion(
    grafo: Grafo,
    hora_salida: str,
    arista_ids: list[str] | None = None,
) -> pd.DataFrame:
    """Arma el DataFrame de features para inferencia (sin etiqueta).

    Args:
        grafo: Grafo base OSM (atributos estáticos de aristas).
        hora_salida: Hora HH:MM del contexto temporal.
        arista_ids: Subconjunto de aristas; si es None, todas las predicibles.

    Returns:
        DataFrame con columnas de entrenamiento + ``arista_id`` para mapear salida.
    """
    por_id = {a.id: a for a in grafo.aristas}
    if arista_ids is not None:
        ids = arista_ids
    else:
        ids = [a.id for a in grafo.aristas]

    intensidad = intensidad_en_hora(hora_salida)
    hora_decimal = _hora_a_decimal(hora_salida)
    filas: list[dict[str, Any]] = []

    for aid in ids:
        base = por_id.get(aid)
        if base is None:
            continue
        if not base.disponible or base.congestion == NivelCongestion.BLOQUEADA:
            continue
        tipo = base.atributos.tipo_via.value
        carriles = base.atributos.carriles if base.atributos.carriles is not None else 1
        filas.append(
            {
                "arista_id": aid,
                "hora_decimal": hora_decimal,
                "intensidad_hora": intensidad,
                "distancia_m": base.distancia,
                "tiempo_base_min": base.tiempo_estimado,
                "velocidad_base_kmh": base.velocidad_promedio,
                "carriles": float(carriles),
                "sentido_unico": int(base.atributos.sentido_unico),
                "incidentes": float(base.incidentes),
                "peso_tipo_via": float(peso_tipo_via(tipo)),
                FEATURE_CATEGORICA: tipo,
            }
        )

    return pd.DataFrame(filas)


def predecir_congestion_aristas(
    pipeline: Any,
    grafo: Grafo,
    hora_salida: str,
    arista_ids: list[str] | None = None,
) -> list[dict[str, str]]:
    """Predice la clase de congestión por arista.

    Returns:
        Lista de ``{arista_id, congestion, hora_salida}``.
    """
    features = construir_features_prediccion(grafo, hora_salida, arista_ids)
    if features.empty:
        return []

    columnas_entrada = list(FEATURES_NUMERICAS) + [FEATURE_CATEGORICA]
    predicciones = pipeline.predict(features[columnas_entrada])
    return [
        {
            "arista_id": str(row.arista_id),
            "congestion": str(clase),
            "hora_salida": hora_salida,
        }
        for row, clase in zip(features.itertuples(index=False), predicciones, strict=True)
    ]


def comparacion_a_metricas_json(
    comparacion: ComparacionModelos,
    resumen: dict[str, Any],
) -> dict[str, Any]:
    """Serializa métricas y matrices (sin pipelines) para la API."""
    tabla = comparacion.tabla_metricas()
    return {
        "resumen_dataset": resumen,
        "mejor_modelo": comparacion.mejor_modelo,
        "metricas": tabla.to_dict(orient="records"),
        "matrices_confusion": {
            r.nombre: {
                "matriz": r.matriz_confusion,
                "clases": list(comparacion.clases),
            }
            for r in comparacion.resultados
        },
    }


def reentrenar_y_persistir(
    grafo: Grafo,
    base_datos: Path | None = None,
    test_size: float = 0.25,
    semilla: int = SEMILLA,
) -> dict[str, Any]:
    """Regenera CSV, métricas JSON y joblib del mejor modelo.

    Args:
        grafo: Grafo usado para construir el dataset supervisado.
        base_datos: Directorio ``datos`` del backend.
        test_size: Hold-out estratificado.
        semilla: Semilla de reproducibilidad.

    Returns:
        Payload de métricas (mismo esquema que ``metricas_clasificacion.json``)
        más ``modelo_guardado`` y ``csv_guardado``.
    """
    ml_dir = directorio_ml(base_datos)
    df = construir_dataset_clasificacion(grafo)
    if df.empty:
        raise ValueError("El dataset de clasificación quedó vacío; revise el grafo.")

    csv_path = guardar_dataset(df, ml_dir / NOMBRE_ARCHIVO_CSV)
    resumen = resumen_dataset(df)
    comparacion = entrenar_y_comparar(df, test_size=test_size, semilla=semilla)
    mejor = next(r for r in comparacion.resultados if r.nombre == comparacion.mejor_modelo)
    modelo_path = guardar_modelo(mejor.pipeline, ruta_modelo(base_datos))
    payload = comparacion_a_metricas_json(comparacion, resumen)
    metricas_path = ruta_metricas(base_datos)
    metricas_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        **payload,
        "modelo_guardado": str(modelo_path),
        "csv_guardado": str(csv_path),
        "metricas_guardadas": str(metricas_path),
    }


def cargar_metricas_desde_disco(base_datos: Path | None = None) -> dict[str, Any]:
    """Lee ``metricas_clasificacion.json`` si existe."""
    ruta = ruta_metricas(base_datos)
    if not ruta.is_file():
        raise FileNotFoundError(f"No hay métricas en {ruta}")
    return json.loads(ruta.read_text(encoding="utf-8"))


@dataclass
class ResultadoModelo:
    """Métricas y artefactos de un clasificador evaluado."""

    nombre: str
    accuracy: float
    precision_macro: float
    recall_macro: float
    f1_macro: float
    matriz_confusion: list[list[int]]
    reporte: dict[str, Any]
    pipeline: Any = field(repr=False)


@dataclass
class ComparacionModelos:
    """Resultados agregados de todos los modelos comparados."""

    resultados: list[ResultadoModelo]
    clases: tuple[str, ...]
    mejor_modelo: str
    X_test_shape: tuple[int, int]
    y_test_counts: dict[str, int]

    def tabla_metricas(self) -> pd.DataFrame:
        """Tabla ordenada por F1 macro (descendente)."""
        filas = [
            {
                "modelo": r.nombre,
                "accuracy": r.accuracy,
                "precision_macro": r.precision_macro,
                "recall_macro": r.recall_macro,
                "f1_macro": r.f1_macro,
            }
            for r in self.resultados
        ]
        return pd.DataFrame(filas).sort_values("f1_macro", ascending=False).reset_index(drop=True)


def _construir_preprocesador() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), list(FEATURES_NUMERICAS)),
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                [FEATURE_CATEGORICA],
            ),
        ]
    )


def _definir_modelos(semilla: int = SEMILLA) -> dict[str, Any]:
    """Modelos supervisados a comparar (mismo preprocesado)."""
    return {
        "Regresión logística": LogisticRegression(
            max_iter=2000,
            class_weight="balanced",
            random_state=semilla,
        ),
        "Random Forest": RandomForestClassifier(
            n_estimators=200,
            max_depth=12,
            class_weight="balanced_subsample",
            random_state=semilla,
            n_jobs=-1,
        ),
        "Gradient Boosting": GradientBoostingClassifier(random_state=semilla),
        "KNN (k=7)": KNeighborsClassifier(n_neighbors=7),
        "SVM lineal": LinearSVC(
            dual="auto",
            class_weight="balanced",
            random_state=semilla,
            max_iter=5000,
        ),
    }


def preparar_xy(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Selecciona columnas de entrada y etiqueta."""
    columnas = list(FEATURES_NUMERICAS) + [FEATURE_CATEGORICA]
    faltantes = [c for c in columnas + [TARGET] if c not in df.columns]
    if faltantes:
        raise ValueError(f"Columnas faltantes en el dataset: {faltantes}")
    return df[columnas].copy(), df[TARGET].astype(str).copy()


def entrenar_y_comparar(
    df: pd.DataFrame,
    test_size: float = 0.25,
    semilla: int = SEMILLA,
) -> ComparacionModelos:
    """Entrena varios clasificadores y calcula métricas + matrices de confusión.

    Args:
        df: Dataset con features y ``congestion``.
        test_size: Fracción de hold-out estratificado.
        semilla: Reproducibilidad del split y de los modelos.

    Returns:
        ``ComparacionModelos`` con pipelines entrenados y métricas.
    """
    X, y = preparar_xy(df)
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=semilla,
        stratify=y,
    )

    resultados: list[ResultadoModelo] = []
    for nombre, estimador in _definir_modelos(semilla).items():
        pipe = Pipeline(
            steps=[
                ("preprocesador", _construir_preprocesador()),
                ("modelo", estimador),
            ]
        )
        pipe.fit(X_train, y_train)
        y_pred = pipe.predict(X_test)

        cm = confusion_matrix(y_test, y_pred, labels=list(CATEGORIAS_CONGESTION))
        resultados.append(
            ResultadoModelo(
                nombre=nombre,
                accuracy=float(accuracy_score(y_test, y_pred)),
                precision_macro=float(
                    precision_score(y_test, y_pred, average="macro", zero_division=0)
                ),
                recall_macro=float(recall_score(y_test, y_pred, average="macro", zero_division=0)),
                f1_macro=float(f1_score(y_test, y_pred, average="macro", zero_division=0)),
                matriz_confusion=cm.astype(int).tolist(),
                reporte=classification_report(
                    y_test,
                    y_pred,
                    labels=list(CATEGORIAS_CONGESTION),
                    output_dict=True,
                    zero_division=0,
                ),
                pipeline=pipe,
            )
        )

    mejor = max(resultados, key=lambda r: r.f1_macro)
    counts = {c: int((y_test == c).sum()) for c in CATEGORIAS_CONGESTION}
    return ComparacionModelos(
        resultados=resultados,
        clases=CATEGORIAS_CONGESTION,
        mejor_modelo=mejor.nombre,
        X_test_shape=(int(X_test.shape[0]), int(X_test.shape[1])),
        y_test_counts=counts,
    )


def matriz_a_dataframe(
    matriz: list[list[int]],
    clases: tuple[str, ...] = CATEGORIAS_CONGESTION,
) -> pd.DataFrame:
    """Convierte la matriz de confusión a DataFrame etiquetado."""
    arr = np.asarray(matriz)
    return pd.DataFrame(
        arr,
        index=[f"real_{c}" for c in clases],
        columns=[f"pred_{c}" for c in clases],
    )
