"""Compara un recorrido ML con los objetivos del dataset, sin inventar observaciones.

El tiempo de referencia es tiempo_min DERIVADO en el dataset auditado, no
un tiempo real observado. Requiere correspondencia única por origen/destino,
distancia, día y hora. Un emparejamiento parcial no permite calcular loss.
"""

from __future__ import annotations

import math
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import pandas as pd

COLUMNAS_REFERENCIA = ["origen", "destino", "distancia_m", "dia_semana", "hora", "tiempo_min"]


@lru_cache(maxsize=2)
def cargar_referencias(ruta: str):
    """Indexa únicamente columnas necesarias. No depende del ID de arista."""
    df = pd.read_csv(Path(ruta), usecols=COLUMNAS_REFERENCIA, dtype={"origen": str, "destino": str})
    if df[COLUMNAS_REFERENCIA].isna().any().any():
        raise ValueError("Dataset con referencias incompletas")
    indice = defaultdict(list)
    for r in df.itertuples(index=False):
        distancia, tiempo = float(r.distancia_m), float(r.tiempo_min)
        if not (
            math.isfinite(distancia) and distancia > 0 and math.isfinite(tiempo) and tiempo > 0
        ):
            raise ValueError("El dataset tiene distancias o tiempos de referencia inválidos")
        indice[(str(r.origen), str(r.destino), int(r.dia_semana), int(r.hora))].append(
            (distancia, tiempo)
        )
    return dict(indice)


def comparar_ruta(grafo_ml, resultado, indice: dict, dia: int, hora: int) -> dict:
    """Compara exactamente las aristas recorridas por UCS con el dataset.

    Nunca reasigna una arista por cercanía geográfica ni usa el tiempo base
    del grafo como si fuera una observación empírica.
    """
    if not resultado.ruta_encontrada:
        return {
            "disponible": False,
            "motivo": "No se encontró una ruta dirigida para comparar.",
            "tramos_total": 0,
            "tramos_con_referencia": 0,
            "fuente": "Dataset operativo: objetivos derivados, no observaciones reales",
        }

    ids = [str(x) for x in resultado.aristas_camino]
    mapa = {str(a.id): a for a in grafo_ml.aristas}
    caminos = [str(x) for x in resultado.camino]
    if len(caminos) != len(ids) + 1:
        raise ValueError("La ruta no conserva la cantidad de aristas y nodos esperada")
    estimado, referencia, cubiertos = 0.0, 0.0, 0
    for i, edge_id in enumerate(ids):
        arista = mapa.get(edge_id)
        if (
            arista is None
            or str(arista.origen) != caminos[i]
            or str(arista.destino) != caminos[i + 1]
        ):
            raise ValueError("El resultado de UCS no se corresponde con el grafo ML")
        estimado += float(arista.tiempo_estimado)
        opciones = indice.get((str(arista.origen), str(arista.destino), dia, hora), [])
        compatibles = [
            (dist, t)
            for dist, t in opciones
            if abs(dist - float(arista.distancia)) <= max(0.5, 0.01 * float(arista.distancia))
        ]
        # Repetidos exactos de la misma arista o aristas paralelas ambiguas se descartan.
        if len(compatibles) == 1:
            referencia += compatibles[0][1]
            cubiertos += 1

    base = {
        "disponible": cubiertos == len(ids) and bool(ids),
        "tramos_total": len(ids),
        "tramos_con_referencia": cubiertos,
        "tiempo_predicho_min": round(estimado, 8),
        "fuente": "Tiempo derivado del dataset operativo; no observado en un viaje real",
        "tipo_comparacion": "Mismo recorrido de UCS, día y hora",
    }
    if not base["disponible"]:
        base["motivo"] = (
            "No existe una correspondencia única en el dataset para todos los tramos. "
            "No se calcula un valor de referencia ni una pérdida parcial."
        )
        return base
    error = estimado - referencia
    base.update(
        tiempo_referencia_min=round(referencia, 8),
        error_firmado_min=round(error, 8),
        error_absoluto_min=round(abs(error), 8),
        loss_cuadratica_min2=round(error**2, 10),
    )
    return base


def comparar_con_grafo_base(grafo_original, grafo_ml, resultado) -> dict:
    """Comparación de respaldo con los tiempos *estimados* del grafo activo.

    No son observaciones reales. Exige mismas aristas, dirección y nodos.
    Solo si el objetivo del CSV no se puede determinar de modo inequívoco.
    """
    if not resultado.ruta_encontrada:
        return {"disponible": False, "motivo": "No se encontró ruta para comparar."}
    aristas_base = {str(a.id): a for a in grafo_original.aristas}
    aristas_ml = {str(a.id): a for a in grafo_ml.aristas}
    camino = list(map(str, resultado.camino))
    ids = list(map(str, resultado.aristas_camino))
    if not ids or len(camino) != len(ids) + 1:
        return {"disponible": False, "motivo": "Camino incompleto para comparar."}
    predicho = 0.0
    base = 0.0
    for i, aid in enumerate(ids):
        a = aristas_base.get(aid)
        b = aristas_ml.get(aid)
        if (
            a is None
            or b is None
            or any(str(x.origen) != camino[i] or str(x.destino) != camino[i + 1] for x in (a, b))
        ):
            return {
                "disponible": False,
                "motivo": "Aristas del recorrido no coinciden con el grafo original.",
            }
        tbase = float(a.tiempo_estimado)
        tp = float(b.tiempo_estimado)
        if not all(math.isfinite(t) and t > 0 for t in (tbase, tp)):
            return {"disponible": False, "motivo": "Tiempo base inválido."}
        base += tbase
        predicho += tp
    error = predicho - base
    return {
        "disponible": True,
        "tiempo_predicho_min": round(predicho, 8),
        "tiempo_referencia_min": round(base, 8),
        "error_absoluto_min": round(abs(error), 8),
        "error_firmado_min": round(error, 8),
        "loss_cuadratica_min2": round(error * error, 10),
        "tramos_total": len(ids),
        "tramos_con_referencia": len(ids),
        "fuente": "Tiempo base estimado del grafo activo (simulado; no observado)",
        "tipo_comparacion": "Mismo recorrido, comparación contra el tiempo base del grafo",
        "tipo_referencia": "grafo_base_simulado",
    }
