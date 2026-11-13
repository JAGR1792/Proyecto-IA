"""Exporta métricas reales de LinearRegression al centro de análisis de Nuxt.

Ejecutar desde la raíz del repositorio: python backend/scripts/ml/exportar_metricas_front.py
No modifica el modelo ni el dataset; solo produce frontend/public/datos/ml_regresion_resumen.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
ORIGEN = ROOT / "backend" / "datos" / "ml" / "modelos_regresion_osm"
DESTINO = ROOT / "frontend" / "public" / "datos" / "ml_regresion_resumen.json"


def metricas(data: dict, *nombres: str) -> dict:
    for nombre in nombres:
        m = data.get(nombre)
        if isinstance(m, dict) and "MAE_min" in m and "R2" in m:
            return m
    raise ValueError(f"No hay métricas para {nombres}. Reentrena y evalúa el modelo.")


def filas_resumen(csv_path: Path, columna: str) -> list[dict]:
    if not csv_path.exists():
        return []
    df = pd.read_csv(csv_path)
    esperadas = {columna, "n", "MAE_min", "MSE_min2"}
    if not esperadas.issubset(df.columns):
        raise ValueError(f"{csv_path.name} sin columnas {esperadas - set(df.columns)}")
    return [
        {
            "etiqueta": str(r[columna]),
            "n": int(r["n"]),
            "mae": float(r["MAE_min"]),
            "mse": float(r["MSE_min2"]),
        }
        for _, r in df.iterrows()
        if pd.notna(r[columna]) and pd.notna(r["MAE_min"])
    ]


def muestreo_predicciones(csv_path: Path) -> tuple[list[dict], list[dict], int]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Falta {csv_path}; ejecuta evaluar_regresion_red_osm.py")
    df = pd.read_csv(csv_path)
    if not {"real_estimado_min", "predicho_min"}.issubset(df.columns):
        raise ValueError("La muestra no tiene real_estimado_min y predicho_min")
    df = df[["real_estimado_min", "predicho_min"]].replace([np.inf, -np.inf], np.nan).dropna()
    if df.empty:
        raise ValueError("La muestra de prueba está vacía")
    df["residuo"] = df["real_estimado_min"] - df["predicho_min"]
    muestra = df.sample(n=min(800, len(df)), random_state=42) if len(df) > 800 else df
    puntos = [
        {
            "real": round(float(r.real_estimado_min), 6),
            "predicho": round(float(r.predicho_min), 6),
            "residuo": round(float(r.residuo), 6),
        }
        for r in muestra.itertuples(index=False)
    ]
    hist, edges = np.histogram(df["residuo"].to_numpy(), bins=24)
    histogram = [
        {"desde": round(float(a), 6), "hasta": round(float(b), 6), "n": int(n)}
        for a, b, n in zip(edges[:-1], edges[1:], hist)
    ]
    return puntos, histogram, len(df)


def main() -> None:
    ruta_metricas = ORIGEN / "metricas_regresion_osm.json"
    ruta_eval = ORIGEN / "evaluacion_detallada"
    if not ruta_metricas.exists():
        raise FileNotFoundError(f"No existe {ruta_metricas}")
    d = json.loads(ruta_metricas.read_text(encoding="utf-8"))
    # Seguridad contra resultados viejos del modelo regularizado.
    nombre = str(d.get("modelo", ""))
    if "LinearRegression" not in nombre or "Ridge" in nombre:
        raise ValueError("Las métricas no corresponden a LinearRegression ordinaria.")
    reg = metricas(d, "prueba_regresion")
    base = metricas(d, "prueba_baseline", "prueba_referencia")
    puntos, hist, n_muestra = muestreo_predicciones(ORIGEN / "muestra_predicciones_prueba.csv")
    payload = {
        "schema_version": 1,
        "modelo": nombre,
        "fecha_generacion": d.get("fecha_utc", ""),
        "metricas": {
            "regresion": reg,
            "referencia": base,
            "entrenamiento": d.get("entrenamiento_final_regresion"),
        },
        "totales": {
            "filas_prueba": int(d.get("particiones", {}).get("prueba", {}).get("filas", n_muestra)),
            "predicciones_crudas_no_positivas": int(
                d.get("predicciones_crudas_no_positivas_prueba", 0)
            ),
            "predicciones_ajustadas": int(d.get("predicciones_ajustadas_prueba", 0)),
        },
        "muestra": puntos,
        "histograma_residuos": hist,
        "por_hora": filas_resumen(ruta_eval / "errores_por_hora.csv", "hora"),
        "por_tipo_via": filas_resumen(ruta_eval / "errores_por_tipo_via.csv", "tipo_via"),
    }
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )
    print(f"Resumen frontend generado: {DESTINO}")
    print(
        f"MSE: {reg.get('Loss_MSE_min2', reg.get('MSE_min2'))}, R2: {reg['R2']}; puntos para gráfica: {len(puntos)}"
    )
    if not payload["por_hora"] or not payload["por_tipo_via"]:
        print(
            "Aviso: faltan errores_por_hora.csv o errores_por_tipo_via.csv; ejecuta la evaluación detallada."
        )


if __name__ == "__main__":
    main()
