"""Clasifica, sin aprobar automáticamente, candidatas Bitcarrier -> aristas OSM.

Uso desde la raíz de Proyecto-IA:
    python backend/scripts/ml/clasificar_correspondencias_osm.py

Lee el CSV producido por emparejar_bitcarrier_osm.py y genera archivos de
revisión. No modifica el grafo, el dataset original ni los modelos.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DIR = ROOT / "backend/datos/ml/bitcarrier_mayo_2022_procesado"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--entrada", type=Path, default=DEFAULT_DIR / "candidatos_bitcarrier_osm.csv"
    )
    parser.add_argument("--salida", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--cobertura-minima", type=float, default=0.90)
    parser.add_argument("--angulo-maximo", type=float, default=20.0)
    parser.add_argument("--longitud-minima", type=float, default=20.0)
    args = parser.parse_args()

    if not 0 < args.cobertura_minima <= 1:
        parser.error("--cobertura-minima debe estar entre 0 y 1")
    if not 0 <= args.angulo_maximo <= 180:
        parser.error("--angulo-maximo debe estar entre 0 y 180")

    required = [
        "tid_bitcarrier",
        "indice_osm",
        "id_arista_osm",
        "origen_osm",
        "destino_osm",
        "nombre_via_osm",
        "longitud_osm_m",
        "cobertura_osm",
        "angulo_extremos_grados",
        "orientacion_preliminar",
        "validacion_direccion",
    ]
    df = pd.read_csv(
        args.entrada,
        dtype={"tid_bitcarrier": "string", "indice_osm": "string", "id_arista_osm": "string"},
    )
    missing = sorted(set(required) - set(df.columns))
    if missing:
        raise ValueError(f"Faltan columnas en {args.entrada}: {missing}")
    if df.empty:
        raise ValueError("El CSV de candidatas está vacío")
    if df["indice_osm"].isna().any() or df["tid_bitcarrier"].isna().any():
        raise ValueError("Hay índices OSM o TID vacíos")
    for column in ("longitud_osm_m", "cobertura_osm", "angulo_extremos_grados"):
        df[column] = pd.to_numeric(df[column], errors="coerce")
    if df.duplicated(["indice_osm", "tid_bitcarrier"]).any():
        raise ValueError("Hay pares (indice_osm, tid_bitcarrier) duplicados; revisar el origen")

    df["numero_tid_candidatos"] = df.groupby("indice_osm")["tid_bitcarrier"].transform("nunique")
    df["numero_aristas_por_tid"] = df.groupby("tid_bitcarrier")["indice_osm"].transform("nunique")

    # No declarar correspondencias confirmadas: las geometrías pueden ser de vías paralelas.
    def classify(row: pd.Series) -> tuple[str, str]:
        if (
            pd.isna(row["cobertura_osm"])
            or pd.isna(row["angulo_extremos_grados"])
            or pd.isna(row["longitud_osm_m"])
        ):
            return "REVISAR", "Faltan métricas geométricas"
        if row["orientacion_preliminar"] == "inversa":
            return "DESCARTAR_PRELIMINAR", "Orientación inversa según extremos geométricos"
        if row["orientacion_preliminar"] != "compatible":
            return "REVISAR", "Orientación ambigua o no reconocida"
        if row["angulo_extremos_grados"] > args.angulo_maximo:
            return "REVISAR", "Ángulo superior al umbral"
        if row["cobertura_osm"] < args.cobertura_minima:
            return "REVISAR", "Cobertura geométrica insuficiente"
        if row["longitud_osm_m"] < args.longitud_minima:
            return "REVISAR", "Arista demasiado corta: posible intersección o conector"
        if row["numero_tid_candidatos"] > 1:
            return "REVISAR", "Varios TID candidatos para la misma arista OSM"
        return "PRIORITARIA_PARA_VALIDAR", "Candidato único con geometría y orientación favorables"

    df[["estado", "motivo"]] = pd.DataFrame(df.apply(classify, axis=1).tolist(), index=df.index)
    df["validacion_direccion"] = "PENDIENTE"  # nunca sugerir que esté verificada
    df = df.sort_values(["estado", "indice_osm", "tid_bitcarrier"], kind="stable")

    args.salida.mkdir(parents=True, exist_ok=True)
    completo = args.salida / "correspondencias_clasificadas.csv"
    prioritario = args.salida / "correspondencias_para_revision.csv"
    df.to_csv(completo, index=False, encoding="utf-8-sig")
    df.loc[df["estado"] == "PRIORITARIA_PARA_VALIDAR"].to_csv(
        prioritario, index=False, encoding="utf-8-sig"
    )

    print("ASOCIACIONES ANALIZADAS:", len(df))
    print("ARISTAS OSM DISTINTAS:", df["indice_osm"].nunique())
    print("TID DISTINTOS CON CANDIDATAS:", df["tid_bitcarrier"].nunique())
    print("ESTADOS:")
    for estado, n in df["estado"].value_counts().items():
        print(f"  {estado}: {n}")
    print(
        "ARISTAS EN REVISIÓN PRIORITARIA:",
        df.loc[df["estado"] == "PRIORITARIA_PARA_VALIDAR", "indice_osm"].nunique(),
    )
    print("SALIDAS:", completo, "y", prioritario)
    print(
        "IMPORTANTE: Ninguna asociación ha sido verificada. Falta comprobar nombres, sentidos, conectividad y geometrías paralelas."
    )


if __name__ == "__main__":
    main()
