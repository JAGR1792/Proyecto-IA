"""Entrena el agrupamiento K-Means de patrones de movilidad (Persona 3, Corte 3).

Ejecutar desde la raíz del repositorio::

    python backend/scripts/ml/entrenar_agrupamiento.py          # k automático
    python backend/scripts/ml/entrenar_agrupamiento.py --k 5    # forzar k

Produce:

* ``backend/datos/ml/agrupamiento/metricas_agrupamiento.json``
* ``backend/datos/ml/agrupamiento/asignaciones_clusters.csv``
* ``backend/datos/ml/agrupamiento/evaluacion_k.csv``
* ``backend/datos/ml/agrupamiento/modelo_kmeans_movilidad.joblib``
* ``frontend/public/datos/ml_agrupamiento_resumen.json`` (respaldo estático del dashboard)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from src.ml.agrupamiento import ejecutar_pipeline_completo  # noqa: E402

DESTINO_FRONT = ROOT / "frontend" / "public" / "datos" / "ml_agrupamiento_resumen.json"


def main() -> None:
    """Punto de entrada CLI."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--k", type=int, default=None, help="Número de grupos (por defecto automático)"
    )
    args = parser.parse_args()

    res, payload = ejecutar_pipeline_completo(k=args.k)
    DESTINO_FRONT.parent.mkdir(parents=True, exist_ok=True)
    DESTINO_FRONT.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )

    print(f"k elegido: {res.k}")
    for linea in res.justificacion:
        print(f"  - {linea}")
    print("Métricas:", {k: round(v, 4) for k, v in res.metricas.items()})
    for g in payload["grupos"]:
        print(f"  [{g['cluster']}] {g['nombre']}: {g['aristas']} aristas ({g['porcentaje']:.1f} %)")
    print(f"Respaldo frontend: {DESTINO_FRONT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
