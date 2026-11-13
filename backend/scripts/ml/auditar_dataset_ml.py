"""Audita estructura temporal y distribución de tramos de Bitcarrier limpio.

Ejecutar desde cualquier directorio:
    python backend/scripts/ml/auditar_dataset_ml.py

Solo lee el CSV.gz procesado. No modifica datos, no calcula objetivos ni entrena.
"""

from __future__ import annotations

import csv
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
ARCHIVO = RAIZ / "backend/datos/ml/bitcarrier_mayo_2022_procesado/observaciones_limpias.csv.gz"
REPORTE = RAIZ / "backend/datos/ml/bitcarrier_mayo_2022_procesado/reporte_calidad.json"


def main() -> None:
    if not ARCHIVO.is_file():
        raise SystemExit(f"No se encuentra el CSV procesado: {ARCHIVO}")
    n = 0
    por_tid = Counter()
    por_hora = Counter()
    por_dia = Counter()
    inicios = Counter()
    por_tid_hora = defaultdict(set)
    ejemplos_tid = defaultdict(list)
    muestras = []
    with gzip.open(ARCHIVO, "rt", encoding="utf-8", newline="") as stream:
        for fila in csv.DictReader(stream):
            n += 1
            tid = fila["tid"]
            hora = fila["hora"]
            dia = fila["dia_semana_original"]
            inicio = fila["inicio_original"]
            por_tid[tid] += 1
            por_hora[hora] += 1
            por_dia[dia] += 1
            inicios[inicio] += 1
            por_tid_hora[tid].add(hora)
            if len(ejemplos_tid[tid]) < 1:
                ejemplos_tid[tid].append(
                    (fila["nombre_origen"], fila["nombre_destino"], fila["distancia_original"])
                )
            if len(muestras) < 8:
                muestras.append(
                    {
                        k: fila[k]
                        for k in (
                            "tid",
                            "inicio_original",
                            "dia_semana_original",
                            "hora",
                            "distancia_original",
                            "velocidad_original",
                        )
                    }
                )

    print(f"FILAS: {n:,} | TID distintos: {len(por_tid)} | INICIO distintos: {len(inicios)}")
    print("Ejemplos de formato (sin interpretar aún fecha ni unidades):")
    for fila in muestras:
        print(" ", fila)
    print("\nDIA_SEMANA original (valor: cantidad):")
    print(" ", dict(por_dia.most_common()))
    print(
        "\nTID con mayor cantidad de observaciones (TID, registros, horas cubiertas, ejemplo de vía):"
    )
    for tid, count in por_tid.most_common(12):
        print(" ", tid, count, f"{len(por_tid_hora[tid])}/24", ejemplos_tid[tid][0])
    print("\nRango de observaciones por tramo:", min(por_tid.values()), "a", max(por_tid.values()))
    print(
        "TID con cobertura de 24 horas:",
        sum(len(h) == 24 for h in por_tid_hora.values()),
        "/",
        len(por_tid),
    )
    print("INICIO más repetidos:", inicios.most_common(5))
    if REPORTE.is_file():
        reporte = json.loads(REPORTE.read_text(encoding="utf-8"))
        for campo in ("velocidad_original", "distancia_original", "num_dispositivos"):
            print(f"{campo}:", reporte.get(campo))
    print("\nAviso: INICIO/DIA_SEMANA/velocidad/distancia conservan formato y unidades originales.")
    print(
        "No se infiere que 46 TID sean 46 aristas OSM; hay que hacer cruce geográfico y direccional."
    )


if __name__ == "__main__":
    main()
