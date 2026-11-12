"""Taxi IA — Regresión lineal múltiple sobre la red OSM auditada.

Ejecutar desde la raíz del repositorio:
  python backend/scripts/ml/entrenar_regresion_red_osm.py
  python backend/scripts/ml/entrenar_regresion_red_osm.py --prueba-rapida

Se usa LinearRegression ordinaria (sin regularizacion ni log del objetivo).
La evaluación mide la aproximación de tiempos *estimados* sobre aristas
no vistas; NO demuestra exactitud frente a tiempos de viaje reales.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[3]
INPUT = ROOT / "backend/datos/ml/red_osm_auditada/dataset_red_osm_operativo_auditado.csv.gz"
OUTPUT = ROOT / "backend/datos/ml/modelos_regresion_osm"
FEATURES = ["distancia_m", "hora_sin", "hora_cos", "dia_semana", "tipo_via"]
COLUMNS = [
    "indice_arista_osm",
    "id_arista_osm",
    "dia_semana",
    "hora",
    "tipo_via",
    "distancia_m",
    "velocidad_kmh",
    "tiempo_min",
    "fuente_dato",
]


def validar_y_preparar(df: pd.DataFrame) -> pd.DataFrame:
    faltan = set(COLUMNS) - set(df.columns)
    if faltan:
        raise ValueError(f"Faltan columnas obligatorias: {sorted(faltan)}")
    if df.empty or df[COLUMNS].isna().any().any():
        raise ValueError("Hay nulos en columnas obligatorias o no hay datos")
    if df.duplicated(["indice_arista_osm", "dia_semana", "hora"]).any():
        raise ValueError("Hay aristas con escenarios repetidos")
    if not (
        df["distancia_m"].gt(0).all()
        and df["velocidad_kmh"].gt(0).all()
        and df["tiempo_min"].gt(0).all()
        and df["hora"].between(0, 23).all()
        and df["dia_semana"].between(0, 6).all()
    ):
        raise ValueError("Distancia, velocidad, tiempo o calendario invalidos")
    esperado = df["distancia_m"] * 0.06 / df["velocidad_kmh"]
    if not np.allclose(esperado, df["tiempo_min"], atol=0.01, rtol=0):
        raise ValueError("tiempo_min inconsistente con distancia y velocidad")
    conteo = df.groupby("indice_arista_osm").size()
    if not conteo.eq(168).all():
        raise ValueError("Cada arista debe tener 168 escenarios")
    prepared = df.copy()
    prepared["tipo_via"] = prepared["tipo_via"].astype(str)
    prepared["dia_semana"] = prepared["dia_semana"].astype(str)
    prepared["hora_sin"] = np.sin(2 * np.pi * prepared["hora"] / 24)
    prepared["hora_cos"] = np.cos(2 * np.pi * prepared["hora"] / 24)
    return prepared


def dividir_por_aristas(df: pd.DataFrame, semilla: int = 42):
    ids = np.asarray(sorted(df["indice_arista_osm"].unique()))
    if len(ids) < 15:
        raise ValueError("Se necesitan al menos 15 aristas diferentes")
    trainval_ids, test_ids = train_test_split(ids, test_size=0.2, random_state=semilla)
    train_ids, val_ids = train_test_split(trainval_ids, test_size=0.25, random_state=semilla)
    grupos = {
        "entrenamiento": df[df.indice_arista_osm.isin(train_ids)].copy(),
        "validacion": df[df.indice_arista_osm.isin(val_ids)].copy(),
        "prueba": df[df.indice_arista_osm.isin(test_ids)].copy(),
    }
    for a in grupos:
        for b in grupos:
            if a != b:
                assert set(grupos[a].indice_arista_osm).isdisjoint(grupos[b].indice_arista_osm)
    return grupos


def crear_modelo():
    transform = ColumnTransformer(
        [
            ("numericas", StandardScaler(), ["distancia_m", "hora_sin", "hora_cos"]),
            ("categoricas", OneHotEncoder(handle_unknown="ignore"), ["dia_semana", "tipo_via"]),
        ]
    )
    return Pipeline([("preprocesamiento", transform), ("regresion", LinearRegression())])


def metricas(y, pred):
    return {
        "Loss_MSE_min2": round(float(mean_squared_error(y, pred)), 9),
        "MAE_min": round(float(mean_absolute_error(y, pred)), 6),
        "RMSE_min": round(float(np.sqrt(mean_squared_error(y, pred))), 6),
        "R2": round(float(r2_score(y, pred)), 6),
    }


# Límite operativo aplicado después de predecir: velocidad de 5 a 80 km/h.
# Es una restricción de plausibilidad, NO datos reales ni un cambio de algoritmo.
VELOCIDAD_MAX_KMH = 80.0
VELOCIDAD_MIN_KMH = 5.0


def limitar_tiempos(predicciones, distancias_m):
    """Convierte tiempos en minutos a valores físicamente positivos y plausibles.

    El ajuste es posprocesamiento: no sustituye LinearRegression ni sus coeficientes.
    """
    p = np.asarray(predicciones, dtype=float)
    d = np.asarray(distancias_m, dtype=float)
    if np.any(~np.isfinite(p)) or np.any(~np.isfinite(d)) or np.any(d <= 0):
        raise ValueError("Predicciones y distancias deben ser finitas; distancia > 0")
    return np.clip(p, 0.06 * d / VELOCIDAD_MAX_KMH, 0.06 * d / VELOCIDAD_MIN_KMH)


def referencia_por_tipo_y_distancia(train, eval_df):
    # Baseline independiente de la velocidad de la fila evaluada.
    medianas = train.groupby("tipo_via")["velocidad_kmh"].median()
    global_mediana = train.velocidad_kmh.median()
    velocidades = eval_df.tipo_via.map(medianas).fillna(global_mediana).to_numpy()
    return 0.06 * eval_df.distancia_m.to_numpy() / velocidades


def sha256(archivo: Path):
    h = hashlib.sha256()
    with archivo.open("rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()


def ejecutar(entrada: Path, salida: Path, prueba_rapida: bool = False):
    if not entrada.exists():
        raise FileNotFoundError(f"No existe el dataset auditado: {entrada}")
    df = validar_y_preparar(pd.read_csv(entrada, usecols=COLUMNS))
    grupos = dividir_por_aristas(df)
    # En prueba rapida se reducen filas DENTRO de cada particion manteniendo
    # aristas completamente disjuntas y sin ajustar transformaciones con valid/test.
    if prueba_rapida:
        grupos = {k: g.sample(frac=0.13, random_state=42).copy() for k, g in grupos.items()}
    train, val, test = (grupos[k] for k in ("entrenamiento", "validacion", "prueba"))
    if min(map(len, [train, val, test])) < 3:
        raise ValueError("Particiones insuficientes")
    modelo_validacion = crear_modelo()
    modelo_validacion.fit(train[FEATURES], train.tiempo_min)
    pred_val = limitar_tiempos(modelo_validacion.predict(val[FEATURES]), val.distancia_m)
    met_val = metricas(val.tiempo_min, pred_val)
    print("VALIDACION LinearRegression:", met_val, flush=True)
    baseline_val = metricas(val.tiempo_min, referencia_por_tipo_y_distancia(train, val))
    # Reentrenamiento con train+validation; prueba externa por aristas, una sola vez.
    train_final = pd.concat([train, val], ignore_index=True)
    final = crear_modelo()
    final.fit(train_final[FEATURES], train_final.tiempo_min)
    pred_train_raw = final.predict(train_final[FEATURES])
    pred_test_raw = final.predict(test[FEATURES])
    pred_train = limitar_tiempos(pred_train_raw, train_final.distancia_m)
    pred_test = limitar_tiempos(pred_test_raw, test.distancia_m)
    baseline_test = referencia_por_tipo_y_distancia(train_final, test)
    met_test = metricas(test.tiempo_min, pred_test)
    met_base = metricas(test.tiempo_min, baseline_test)
    salida.mkdir(parents=True, exist_ok=True)
    modelo_path = salida / "modelo_regresion_osm.joblib"
    joblib.dump(final, modelo_path, compress=3)
    resumen = {
        "modelo": "Regresion lineal multiple ordinaria (LinearRegression)",
        "objetivo": "tiempo_min",
        "unidad_objetivo": "minutos derivados",
        "features": FEATURES,
        "version_sklearn_entrenamiento": sklearn.__version__,
        "posprocesamiento": "tiempo limitado usando velocidad entre 5 y 80 km/h",
        "predicciones_crudas_no_positivas_prueba": int(np.sum(pred_test_raw <= 0)),
        "predicciones_ajustadas_prueba": int(
            np.count_nonzero(~np.isclose(pred_test_raw, pred_test, atol=1e-12, rtol=0))
        ),
        "dataset_sha256": sha256(entrada),
        "dataset_archivo": str(entrada),
        "fecha_utc": datetime.now(UTC).isoformat(),
        "filas_dataset": len(df),
        "particiones": {
            k: {"filas": len(v), "aristas": int(v.indice_arista_osm.nunique())}
            for k, v in grupos.items()
        },
        "entrenamiento_final_regresion": metricas(train_final.tiempo_min, pred_train),
        "validacion_regresion": met_val,
        "baseline_validacion": baseline_val,
        "prueba_regresion": met_test,
        "prueba_baseline": met_base,
        "evaluacion": "Prueba sobre ARISTAS OSM no vistas con etiquetas derivadas o simuladas",
        "limitaciones": [
            "La tabla OSM no contiene mediciones directas: no se demuestra precision de trafico real.",
            "tiempo_min procede de distancia/velocidad de cada escenario; no es duracion de viaje medida.",
            "No incluir velocidad_kmh en FEATURES pues causaria fuga de informacion.",
            "Una particion por aristas evalua generalizacion espacial dentro del simulador; no validacion temporal ni empirica.",
            "La asociacion historica Bitcarrier-OSM es provisional.",
            "Para evaluar con trafico observado es necesario un protocolo adicional sobre historico reservado.",
        ],
    }
    (salida / "metricas_regresion_osm.json").write_text(
        json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # Salida corta para graficas y reporte sin exportar dataset a frontend.
    pd.DataFrame(
        {
            "real_estimado_min": test.tiempo_min.to_numpy(),
            "predicho_min": pred_test,
            "indice_arista_osm": test.indice_arista_osm.to_numpy(),
        }
    ).sample(n=min(1500, len(test)), random_state=42).to_csv(
        salida / "muestra_predicciones_prueba.csv", index=False
    )
    print("MODELO:", modelo_path)
    print("PARTICIONES:", resumen["particiones"])
    print("ENTRENAMIENTO FINAL LinearRegression:", resumen["entrenamiento_final_regresion"])
    print("PRUEBA LinearRegression:", met_test)
    print("PRUEBA baseline:", met_base)
    print(
        "PREDICCIONES CRUDAS NO POSITIVAS (prueba):",
        resumen["predicciones_crudas_no_positivas_prueba"],
    )
    print("PREDICCIONES AJUSTADAS (prueba):", resumen["predicciones_ajustadas_prueba"])
    print("VERSION scikit-learn:", sklearn.__version__)
    return resumen


def predecir(
    modelo_path: Path, distancia_m: float, hora: int, dia_semana: int, tipo_via: str
) -> float:
    if distancia_m <= 0 or hora not in range(24) or dia_semana not in range(7):
        raise ValueError("Distancia >0, hora 0..23, dia 0..6")
    x = pd.DataFrame(
        [
            {
                "distancia_m": distancia_m,
                "hora_sin": np.sin(2 * np.pi * hora / 24),
                "hora_cos": np.cos(2 * np.pi * hora / 24),
                "dia_semana": str(dia_semana),
                "tipo_via": tipo_via,
            }
        ]
    )
    model = joblib.load(modelo_path)
    return float(limitar_tiempos(model.predict(x), [distancia_m])[0])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--entrada", type=Path, default=INPUT)
    ap.add_argument("--salida", type=Path, default=OUTPUT)
    ap.add_argument("--prueba-rapida", action="store_true")
    ap.add_argument(
        "--predecir", action="store_true", help="Usar modelo ya entrenado; no reentrena"
    )
    ap.add_argument("--distancia-m", type=float, default=450)
    ap.add_argument("--hora", type=int, default=8)
    ap.add_argument("--dia-semana", type=int, default=0, help="0 lunes, 6 domingo")
    ap.add_argument("--tipo-via", default="residencial")
    args = ap.parse_args()
    if args.predecir:
        ruta = args.salida / "modelo_regresion_osm.joblib"
        print(
            f"PREDICCION: {predecir(ruta, args.distancia_m, args.hora, args.dia_semana, args.tipo_via):.4f} minutos"
        )
    else:
        ejecutar(args.entrada, args.salida, args.prueba_rapida)


if __name__ == "__main__":
    main()
