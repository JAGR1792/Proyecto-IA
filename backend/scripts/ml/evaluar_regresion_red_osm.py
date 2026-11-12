"""Diagnostico de LinearRegression guardado: NO reentrena y NO reemplaza el modelo.

Desde raiz: python backend/scripts/ml/evaluar_regresion_red_osm.py
Genera metrica MSE, tablas por hora/via, residuos y graficas PNG.
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

import joblib
import matplotlib
import numpy as np
import pandas as pd
import sklearn

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent))
from entrenar_regresion_red_osm import (  # noqa: E402
    COLUMNS,
    FEATURES,
    INPUT,
    OUTPUT,
    dividir_por_aristas,
    limitar_tiempos,
    referencia_por_tipo_y_distancia,
    validar_y_preparar,
)


def calcular_metricas(y, p):
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    if len(y) == 0:
        raise ValueError("No hay observaciones")
    return {
        "MSE_min2": float(mean_squared_error(y, p)),
        "MAE_min": float(mean_absolute_error(y, p)),
        "RMSE_min": float(np.sqrt(mean_squared_error(y, p))),
        "R2": float(r2_score(y, p)) if len(y) > 1 else None,
        "error_medio_firmado_min": float(np.mean(p - y)),
        "error_absoluto_p95_min": float(np.percentile(abs(p - y), 95)),
        "predicciones_no_positivas": int(np.sum(p <= 0)),
    }


def generar(
    entrada: Path = INPUT,
    model_path: Path = OUTPUT / "modelo_regresion_osm.joblib",
    salida: Path = OUTPUT / "evaluacion_detallada",
):
    if not entrada.exists():
        raise FileNotFoundError(f"Dataset no existe: {entrada}")
    if not model_path.exists():
        raise FileNotFoundError(f"Modelo no existe: {model_path}")
    from sklearn.exceptions import InconsistentVersionWarning

    with warnings.catch_warnings():
        warnings.simplefilter("error", InconsistentVersionWarning)
        try:
            modelo = joblib.load(model_path)  # cargar solo modelos propios y confiables
        except InconsistentVersionWarning as e:
            raise RuntimeError(
                "Modelo guardado con scikit-learn de otra version. "
                "Vuelve a entrenar con el entorno actual antes de evaluar: "
                "python .\\backend\\scripts\\ml\\entrenar_regresion_red_osm.py"
            ) from e
    if not isinstance(modelo.named_steps["regresion"], LinearRegression):
        raise ValueError("El modelo cargado NO es LinearRegression ordinaria")
    df = validar_y_preparar(pd.read_csv(entrada, usecols=COLUMNS))
    grupos = dividir_por_aristas(df)
    train = pd.concat([grupos["entrenamiento"], grupos["validacion"]], ignore_index=True)
    test = grupos["prueba"].copy()
    # El pipeline guardado ya contiene preprocesamiento entrenado; NO se hace fit aquí.
    pred_train_raw = modelo.predict(train[FEATURES])
    pred_test_raw = modelo.predict(test[FEATURES])
    pred_train = limitar_tiempos(pred_train_raw, train.distancia_m)
    pred_test = limitar_tiempos(pred_test_raw, test.distancia_m)
    base = referencia_por_tipo_y_distancia(train, test)
    mt_train = calcular_metricas(train.tiempo_min, pred_train)
    mt_test = calcular_metricas(test.tiempo_min, pred_test)
    mt_base = calcular_metricas(test.tiempo_min, base)
    test["predicho_min"] = pred_test
    test["residuo_min"] = test["tiempo_min"] - pred_test
    test["error_absoluto_min"] = np.abs(test["residuo_min"])
    test["prediccion_cruda_negativa"] = pred_test_raw < 0
    test["prediccion_ajustada_por_limite"] = ~np.isclose(
        pred_test_raw, pred_test, rtol=0, atol=1e-12
    )
    salida.mkdir(parents=True, exist_ok=True)
    tabla_via = []
    for via, g in test.groupby("tipo_via"):
        m = calcular_metricas(g.tiempo_min, g.predicho_min)
        tabla_via.append({"tipo_via": str(via), "n": len(g), **m})
    tabla_hora = []
    for hora, g in test.groupby("hora"):
        m = calcular_metricas(g.tiempo_min, g.predicho_min)
        tabla_hora.append({"hora": int(hora), "n": len(g), **m})
    pd.DataFrame(tabla_via).sort_values("MAE_min", ascending=False).to_csv(
        salida / "errores_por_tipo_via.csv", index=False
    )
    pd.DataFrame(tabla_hora).to_csv(salida / "errores_por_hora.csv", index=False)
    test[
        [
            "indice_arista_osm",
            "dia_semana",
            "hora",
            "tipo_via",
            "distancia_m",
            "tiempo_min",
            "predicho_min",
            "residuo_min",
            "error_absoluto_min",
            "prediccion_cruda_negativa",
        ]
    ].to_csv(salida / "predicciones_prueba_completas.csv.gz", index=False, compression="gzip")
    # Fig 1: valores objetivo frente a valores predichos
    muestra = test.sample(n=min(3500, len(test)), random_state=42)
    fig, ax = plt.subplots(figsize=(7.4, 5.5))
    ax.scatter(muestra.tiempo_min, muestra.predicho_min, s=8, alpha=0.28, rasterized=True)
    minlim = min(muestra.tiempo_min.min(), muestra.predicho_min.min(), 0)
    maxlim = max(muestra.tiempo_min.max(), muestra.predicho_min.max()) * 1.03
    ax.plot([minlim, maxlim], [minlim, maxlim], linestyle="--", label="Predicción perfecta")
    ax.set(
        xlabel="Tiempo objetivo del escenario (min)",
        ylabel="Tiempo predicho (min)",
        title="Regresión lineal: objetivo vs. predicción",
    )
    ax.legend()
    ax.grid(alpha=0.18)
    fig.tight_layout()
    fig.savefig(salida / "01_objetivo_vs_predicho.png", dpi=160)
    plt.close(fig)
    # Fig 2: distribución de residuos
    fig, ax = plt.subplots(figsize=(7.4, 4.5))
    ax.hist(test.residuo_min, bins=75)
    ax.axvline(0, linestyle="--", label="Error cero")
    ax.set(
        xlabel="Residuo: objetivo − predicho (min)",
        ylabel="Frecuencia",
        title="Distribución de residuos (prueba)",
    )
    ax.legend()
    ax.grid(alpha=0.18)
    fig.tight_layout()
    fig.savefig(salida / "02_residuos.png", dpi=160)
    plt.close(fig)
    # Fig 3: MAE por hora
    horas = pd.DataFrame(tabla_hora)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(horas.hora, horas.MAE_min, marker="o")
    ax.set(
        xlabel="Hora del día",
        ylabel="MAE (min)",
        title="Error absoluto medio por hora",
        xticks=list(range(0, 24, 2)),
    )
    ax.grid(alpha=0.22)
    fig.tight_layout()
    fig.savefig(salida / "03_mae_por_hora.png", dpi=160)
    plt.close(fig)
    # Fig 4: comparación loss
    fig, ax = plt.subplots(figsize=(7.4, 4.5))
    ax.bar(["LinearRegression", "Referencia"], [mt_test["MSE_min2"], mt_base["MSE_min2"]])
    ax.set(ylabel="MSE (min²)", title="Loss en prueba: regresión vs. referencia")
    ax.grid(axis="y", alpha=0.20)
    fig.tight_layout()
    fig.savefig(salida / "04_loss_mse.png", dpi=160)
    plt.close(fig)
    resumen = {
        "modelo": "LinearRegression ordinaria (sin RNA, sin Ridge)",
        "sin_reentrenamiento": True,
        "entrenamiento_final": mt_train,
        "prueba": mt_test,
        "referencia_prueba": mt_base,
        "n_aristas_prueba": int(test.indice_arista_osm.nunique()),
        "n_filas_prueba": len(test),
        "predicciones_crudas_negativas": int((pred_test_raw < 0).sum()),
        "predicciones_crudas_no_positivas": int((pred_test_raw <= 0).sum()),
        "predicciones_ajustadas_por_limites": int(
            (~np.isclose(pred_test_raw, pred_test, rtol=0, atol=1e-12)).sum()
        ),
        "version_sklearn_evaluacion": sklearn.__version__,
        "posprocesamiento": "Limites operativos de velocidad 5-80 km/h, aplicados a cada arista",
        "nota": "Los valores objetivo son tiempos DERIVADOS del dataset operacional, no duraciones de viajes observados directamente. El loss se reporta en min².",
        "uso": "Diagnóstico en prueba por aristas; no evaluación empírica de tráfico real.",
    }
    (salida / "resumen_evaluacion.json").write_text(
        json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("ENTRENAMIENTO FINAL:", mt_train)
    print("PRUEBA LinearRegression:", mt_test)
    print("PRUEBA referencia:", mt_base)
    print("Predicciones crudas negativas:", resumen["predicciones_crudas_negativas"])
    print("PREDICCIONES AJUSTADAS POR LIMITES:", resumen["predicciones_ajustadas_por_limites"])
    print("VERSION scikit-learn:", sklearn.__version__)
    print("Gráficas y reportes:", salida)
    return resumen


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--entrada", type=Path, default=INPUT)
    p.add_argument("--modelo", type=Path, default=OUTPUT / "modelo_regresion_osm.joblib")
    p.add_argument("--salida", type=Path, default=OUTPUT / "evaluacion_detallada")
    a = p.parse_args()
    generar(a.entrada, a.modelo, a.salida)


if __name__ == "__main__":
    main()
