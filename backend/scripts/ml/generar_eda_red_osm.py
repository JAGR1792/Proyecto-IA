"""Audita y resume la RED OSM INTEGRADA (no la tabla híbrida intermedia).

Desde la raíz de Proyecto-IA:
    python backend/scripts/ml/generar_eda_red_osm.py

Fuente operacional única: una arista OSM × día tipo × hora (168 escenarios).
Las velocidades son MODELOS/SIMULACIÓN; transferencia Bitcarrier PROVISIONAL.
Los tiempos son derivados, NO tiempos de viaje medidos directamente.
No se entrenan modelos ni se estima precisión con esta tabla sintética.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[3]
ENTRADA = RAIZ / "backend/datos/ml/red_osm_auditada/dataset_red_osm_operativo_auditado.csv.gz"
METADATOS = RAIZ / "backend/datos/ml/red_osm_auditada/informe_cierre.json"
SALIDA = RAIZ / "frontend/public/datos/eda_red_osm.json"
FUENTES = ("TRANSFERENCIA_BITCARRIER_PROVISIONAL", "SIMULACION_CALIBRADA_OSM")
DIAS = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
BINS_VELOCIDAD = np.array(
    [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 100, 120, 160, 200], dtype=float
)
BINS_TIEMPO = np.array(
    [0, 0.15, 0.3, 0.5, 0.75, 1, 1.5, 2, 3, 4, 6, 10, 20, 40, 90, 180], dtype=float
)
REQUERIDAS = {
    "indice_arista_osm",
    "id_arista_osm",
    "dia_semana",
    "hora",
    "distancia_m",
    "velocidad_kmh",
    "tiempo_min",
    "fuente_dato",
    "tipo_via",
    "nombre_via",
    "estado_match",
    "observaciones_calibracion",
}


def valor(v, precision=3):
    try:
        f = float(v)
        return round(f, precision) if math.isfinite(f) else None
    except (ValueError, TypeError):
        return None


def stats(s):
    x = s.dropna()
    if x.empty:
        return {
            "min": None,
            "p25": None,
            "mediana": None,
            "media": None,
            "p75": None,
            "p95": None,
            "max": None,
        }
    q = x.quantile([0, 0.25, 0.5, 0.75, 0.95, 1])
    return {
        "min": valor(q.loc[0]),
        "p25": valor(q.loc[0.25]),
        "mediana": valor(q.loc[0.5]),
        "media": valor(x.mean()),
        "p75": valor(q.loc[0.75]),
        "p95": valor(q.loc[0.95]),
        "max": valor(q.loc[1]),
    }


def histograma(s, limites):
    conteo, bordes = np.histogram(s.dropna(), bins=limites)
    return [
        {"desde": valor(bordes[i]), "hasta": valor(bordes[i + 1]), "n": int(n)}
        for i, n in enumerate(conteo)
    ]


def describir(v):
    por_hora = v.groupby("hora")["velocidad_kmh"].agg(["size", "median"])
    por_dia = v.groupby("dia_semana")["velocidad_kmh"].agg(["size", "median"])
    mapa = v.groupby(["dia_semana", "hora"])["velocidad_kmh"].agg(["size", "median"])
    tipos = (
        v.groupby("tipo_via", dropna=False)
        .agg(
            n=("velocidad_kmh", "size"),
            v_med=("velocidad_kmh", "median"),
            t_med=("tiempo_min", "median"),
            aristas=("indice_arista_osm", "nunique"),
        )
        .sort_values("n", ascending=False)
        .head(12)
    )
    return {
        "n": int(len(v)),
        "aristas": int(v.indice_arista_osm.nunique()),
        "velocidad": stats(v.velocidad_kmh),
        "tiempo": stats(v.tiempo_min),
        "distancia": stats(v.distancia_m),
        "hist_velocidad": histograma(v.velocidad_kmh, BINS_VELOCIDAD),
        "hist_tiempo": histograma(v.tiempo_min, BINS_TIEMPO),
        "horas": [
            {
                "hora": h,
                "n": int(por_hora.loc[h, "size"]) if h in por_hora.index else 0,
                "mediana": valor(por_hora.loc[h, "median"]) if h in por_hora.index else None,
            }
            for h in range(24)
        ],
        "dias": [
            {
                "dia": DIAS[d],
                "n": int(por_dia.loc[d, "size"]) if d in por_dia.index else 0,
                "mediana": valor(por_dia.loc[d, "median"]) if d in por_dia.index else None,
            }
            for d in range(7)
        ],
        "calor": [
            {
                "dia": DIAS[d],
                "hora": h,
                "n": int(mapa.loc[(d, h), "size"]) if (d, h) in mapa.index else 0,
                "mediana": valor(mapa.loc[(d, h), "median"]) if (d, h) in mapa.index else None,
            }
            for d in range(7)
            for h in range(24)
        ],
        "tipos": [
            {
                "tipo": str(tipo) if pd.notna(tipo) and str(tipo).strip() else "Sin categoría",
                "n": int(x.n),
                "aristas": int(x.aristas),
                "velocidad_mediana": valor(x.v_med),
                "tiempo_mediano": valor(x.t_med),
            }
            for tipo, x in tipos.iterrows()
        ],
        "velocidad_mayor_100": int((v.velocidad_kmh > 100).sum()),
    }


def generar(entrada=ENTRADA, salida=SALIDA, metadatos=METADATOS):
    entrada = Path(entrada)
    salida = Path(salida)
    metadatos = Path(metadatos)
    df = pd.read_csv(
        entrada,
        low_memory=False,
        dtype={
            "id_arista_osm": "str",
            "fuente_dato": "str",
            "tipo_via": "str",
            "nombre_via": "str",
        },
    )
    faltan = REQUERIDAS.difference(df.columns)
    if faltan:
        raise ValueError("Faltan columnas: " + ", ".join(sorted(faltan)))
    if df.empty:
        raise ValueError("Dataset vacío")
    for c in (
        "indice_arista_osm",
        "dia_semana",
        "hora",
        "distancia_m",
        "velocidad_kmh",
        "tiempo_min",
        "observaciones_calibracion",
    ):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    if (
        df[
            [
                "indice_arista_osm",
                "dia_semana",
                "hora",
                "distancia_m",
                "velocidad_kmh",
                "tiempo_min",
            ]
        ]
        .isna()
        .any()
        .any()
    ):
        raise ValueError("Nulos en campos esenciales")
    if not df.dia_semana.between(0, 6).all() or not df.hora.between(0, 23).all():
        raise ValueError("Día u hora inválidos")
    if (df[["distancia_m", "velocidad_kmh", "tiempo_min"]] <= 0).any().any():
        raise ValueError("Distancias, velocidades o tiempos no positivos")
    fuentes = set(df.fuente_dato.dropna().unique())
    if not fuentes.issubset(set(FUENTES)):
        raise ValueError("Fuente inesperada: " + str(fuentes))
    duplicados = int(df.duplicated(["indice_arista_osm", "dia_semana", "hora"]).sum())
    if duplicados:
        raise ValueError(f"Hay {duplicados} combinaciones duplicadas")
    cobertura = df.groupby("indice_arista_osm").size()
    incompletas = int((cobertura != 168).sum())
    if incompletas:
        raise ValueError(f"{incompletas} aristas no tienen 168 escenarios")
    total_aristas = int(df.indice_arista_osm.nunique())
    if len(df) != total_aristas * 168:
        raise ValueError("Tamaño incompatible con 168 escenarios por arista")
    # Redondeos a 6 decimales durante la generación crean diferencias pequeñas.
    t_calculado = 0.06 * df.distancia_m / df.velocidad_kmh
    discrepancias = int(((t_calculado - df.tiempo_min).abs() > 0.00015).sum())
    if discrepancias:
        raise ValueError(f"{discrepancias} tiempos incoherentes con distancia/velocidad")
    transferidos = df.loc[df.fuente_dato == FUENTES[0]]
    simulados = df.loc[df.fuente_dato == FUENTES[1]]
    cobertura_transfer = transferidos.groupby("indice_arista_osm").size()
    # Mediana por arista para representación y resumen; no son muestras independientes del tráfico.
    ranking = (
        df.groupby(["indice_arista_osm", "id_arista_osm"], dropna=False)
        .agg(
            nombre=("nombre_via", "first"),
            tipo=("tipo_via", "first"),
            velocidad_mediana=("velocidad_kmh", "median"),
            tiempo_mediano=("tiempo_min", "median"),
            distancia=("distancia_m", "first"),
            transferencias=("fuente_dato", lambda s: int((s == FUENTES[0]).sum())),
        )
        .reset_index()
        .sort_values("tiempo_mediano", ascending=False)
        .head(12)
    )
    # Relaciones distancia-tiempo: rangos sobre 1.741 aristas, no sobre 292k filas replicadas.
    por_arista = (
        df.groupby("indice_arista_osm")
        .agg(distancia=("distancia_m", "first"), tiempo_mediano=("tiempo_min", "median"))
        .reset_index()
    )
    bins = np.unique(np.quantile(por_arista.distancia, np.linspace(0, 1, 9)))
    if len(bins) < 2:
        bins = np.array([por_arista.distancia.min() - 1, por_arista.distancia.max() + 1])
    por_arista["rango_distancia"] = pd.cut(
        por_arista.distancia, bins=bins, include_lowest=True, duplicates="drop"
    )
    rel = por_arista.groupby("rango_distancia", observed=True).agg(
        distancia_mediana=("distancia", "median"),
        tiempo_mediano=("tiempo_mediano", "median"),
        n=("tiempo_mediano", "size"),
    )
    met = json.loads(metadatos.read_text(encoding="utf-8")) if metadatos.exists() else {}
    resultado = {
        "schema_version": 3,
        "tipo": "red_osm_integrada",
        "titulo": "Análisis exploratorio · Red vial OSM integrada",
        "total": int(len(df)),
        "aristas_osm": total_aristas,
        "horarios": 168,
        "procedencia": {
            "transferencia_provisional": int(len(transferidos)),
            "simulacion_calibrada": int(len(simulados)),
            "aristas_con_transferencia": int(len(cobertura_transfer)),
            "aristas_transferencia_parcial": int((cobertura_transfer < 168).sum()),
            "escenarios_respaldo_en_aristas_transferidas": int((168 - cobertura_transfer).sum())
            if len(cobertura_transfer)
            else 0,
        },
        "calidad": {
            "duplicados": duplicados,
            "aristas_incompletas": incompletas,
            "tiempos_inconsistentes": discrepancias,
            "horas_por_arista_min": int(cobertura.min()),
            "horas_por_arista_max": int(cobertura.max()),
            "velocidades_no_positivas": 0,
            "tiempos_no_positivos": 0,
            "observaciones_reales_sobre_osm": 0,
        },
        "segmentos": {
            "todos": describir(df),
            "transferencia": describir(transferidos),
            "simulacion": describir(simulados),
        },
        "aristas_tiempo_mayor": [
            {
                "id": str(r.id_arista_osm),
                "nombre": str(r.nombre) if pd.notna(r.nombre) else "Sin nombre",
                "tipo": str(r.tipo) if pd.notna(r.tipo) else "Sin categoría",
                "distancia_m": valor(r.distancia, 1),
                "tiempo_mediano": valor(r.tiempo_mediano, 3),
                "velocidad_mediana": valor(r.velocidad_mediana, 2),
                "transferencias": int(r.transferencias),
            }
            for r in ranking.itertuples(index=False)
        ],
        "distancia_vs_tiempo": [
            {
                "distancia_m": valor(r.distancia_mediana, 1),
                "tiempo_min": valor(r.tiempo_mediano, 3),
                "n_aristas": int(r.n),
            }
            for r in rel.itertuples()
        ],
        "metadatos_generacion": {
            "aristas_candidatas_estrictas": met.get("aristas_candidatas_estrictas"),
            "perfiles_insuficientes": met.get("perfiles_insuficientes"),
        },
        "advertencias": [
            "Unidad espacial homogénea: una arista OSM dirigida por día tipo y hora (168 escenarios por arista).",
            "Ninguna fila es observación directa de tráfico en una arista OSM; las transferencias Bitcarrier son PROVISIONALES.",
            "Los 168 escenarios semanales por arista son estimaciones relacionadas; no equivalen a 168 mediciones independientes.",
            "Tiempo derivado: 0,06 × distancia_m / velocidad_kmh; DISTANCE en metros y VEL_PROMEDIO en km/h, según auditoría de unidades.",
            "Los factores simulados usan solo datos Bitcarrier históricos de entrenamiento (mayo de 2022, días 1 a 21).",
            "El EDA describe la red operativa; no demuestra exactitud predictiva sobre tráfico real.",
            "Para evaluar regresión/clasificación usar observaciones Bitcarrier reservadas, no esta matriz de escenarios.",
        ],
    }
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )
    print(
        f"EDA RED OSM: {resultado['total']:,} escenarios | {total_aristas:,} aristas | 168 horarios"
    )
    print(
        "Transferencia provisional:",
        f"{len(transferidos):,}",
        "| Simulación:",
        f"{len(simulados):,}",
    )
    print(
        "Aristas con transferencia:",
        len(cobertura_transfer),
        "| parciales:",
        resultado["procedencia"]["aristas_transferencia_parcial"],
    )
    print("Validaciones: 0 duplicados; 0 aristas incompletas; 0 tiempos inconsistentes")
    print("JSON:", salida)
    return resultado


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, default=ENTRADA)
    p.add_argument("--output", type=Path, default=SALIDA)
    p.add_argument("--metadata", type=Path, default=METADATOS)
    a = p.parse_args()
    generar(a.input, a.output, a.metadata)
