"""Genera el CSV compartido de clasificación de congestión (Persona 2 / Corte 3).

Uso (desde ``backend/`` con el venv activo)::

    python scripts/generar_dataset_clasificacion.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ml.clasificacion import (  # noqa: E402
    comparacion_a_metricas_json,
    entrenar_y_comparar,
    guardar_modelo,
    matriz_a_dataframe,
    ruta_metricas,
)
from src.ml.dataset import (  # noqa: E402
    cargar_grafo_osm,
    construir_dataset_clasificacion,
    guardar_dataset,
    resumen_dataset,
)


def main() -> None:
    datos = ROOT / "datos" / "ml"
    grafo = cargar_grafo_osm()
    df = construir_dataset_clasificacion(grafo)
    csv_path = guardar_dataset(df, datos / "dataset_clasificacion_congestion.csv")
    resumen = resumen_dataset(df)

    comparacion = entrenar_y_comparar(df)
    tabla = comparacion.tabla_metricas()
    mejor = next(r for r in comparacion.resultados if r.nombre == comparacion.mejor_modelo)
    modelo_path = guardar_modelo(mejor.pipeline, datos / "modelo_clasificacion_congestion.joblib")
    metricas_path = ruta_metricas(ROOT / "datos")
    payload = comparacion_a_metricas_json(comparacion, resumen)
    metricas_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Dataset: {csv_path} ({resumen['filas']} filas)")
    print(f"Clases: {resumen['clases']}")
    print(f"Mejor modelo: {comparacion.mejor_modelo}")
    print(tabla.to_string(index=False))
    print("\nMatriz de confusión (mejor modelo):")
    print(matriz_a_dataframe(mejor.matriz_confusion).to_string())
    print(f"\nMétricas JSON: {metricas_path}")
    print(f"Modelo joblib: {modelo_path}")


if __name__ == "__main__":
    main()
