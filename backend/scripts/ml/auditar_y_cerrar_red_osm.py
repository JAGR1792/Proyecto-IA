"""Audita unidad Bitcarrier, revisa matching OSM y genera una red operacional trazable.

Ejecutar desde la raiz: python backend/scripts/ml/auditar_y_cerrar_red_osm.py

No verifica automaticamente el sentido legal: sin aprobacion documentada, las
transferencias siguen marcadas PROVISIONALES. El generador conserva el dataset
original y escribe la version auditada en una carpeta nueva.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
PROCESADO = ROOT / "backend/datos/ml/bitcarrier_mayo_2022_procesado"
BASE = ROOT / "backend/datos/ml/dataset_maestro_hibrido"
RED = ROOT / "backend/datos/ml/red_osm_integrada"
DESTINO = ROOT / "backend/datos/ml/red_osm_auditada"

DICT_URL = "https://sig.simur.gov.co/DatosAbiertosDoc/DiccionarioDatos_V1.2_SDM.pdf"

COLUMNAS_REVISION = [
    "indice_osm",
    "id_arista_osm",
    "tid_bitcarrier",
    "nombre_origen",
    "nombre_via_osm",
    "cobertura_osm",
    "angulo_extremos_grados",
    "orientacion_preliminar",
    "n_tid_candidatos",
    "nombre_coincide",
    "criterio_estricto",
    "decision",
    "geometria_confirmada",
    "sentido_legal_confirmado",
    "evidencia",
    "revisor",
    "observaciones_revision",
]


def huella(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(b)
    return digest.hexdigest()


def auditar_unidades(historico: pd.DataFrame, resumen: pd.DataFrame):
    esperado = {"tid", "distancia_original", "velocidad_original"}
    if not esperado.issubset(historico.columns):
        raise ValueError(f"Historico sin columnas: {esperado - set(historico.columns)}")
    if not {"tid_bitcarrier", "longitud_bitcarrier_geom_m"}.issubset(resumen.columns):
        raise ValueError("Falta la auditoria de geometria representativa por TID.")
    s = (
        historico.groupby("tid", observed=True)["distancia_original"]
        .agg(["median", "min", "max", "count"])
        .reset_index()
    )
    s = s.merge(
        resumen[
            [
                "tid_bitcarrier",
                "longitud_bitcarrier_geom_m",
                "geometrias_distintas",
                "frecuencia_geometria_representativa",
            ]
        ],
        left_on="tid",
        right_on="tid_bitcarrier",
        validate="one_to_one",
        how="left",
    )
    if s.longitud_bitcarrier_geom_m.isna().any():
        raise ValueError("Hay TID sin geometria: no es posible cerrar la auditoria")
    s["ratio_distancia_geometria"] = s["median"] / s.longitud_bitcarrier_geom_m
    s["desviacion_porcentual"] = (s.ratio_distancia_geometria - 1).abs() * 100
    s["unidad_distancia_compatible"] = s.ratio_distancia_geometria.between(0.75, 1.25)
    s["distancia_constante_por_tid"] = s["min"] == s["max"]
    vel = pd.to_numeric(historico.velocidad_original, errors="coerce")
    reporte = {
        "documentacion_oficial": DICT_URL,
        "DISTANCE": "metros (documentacion SDM + contraste longitud geometrica)",
        "VEL_PROMEDIO": "km/h (documentacion SDM)",
        "tramos": len(s),
        "tramos_distancia_compatible_25pct": int(s.unidad_distancia_compatible.sum()),
        "mediana_ratio": float(s.ratio_distancia_geometria.median()),
        "tramos_con_distancia_variable": int((~s.distancia_constante_por_tid).sum()),
        "velocidad_no_positiva": int((vel <= 0).sum()),
        "velocidad_mayor_100_kmh": int((vel > 100).sum()),
        "registros_velocidad_nula": int(vel.isna().sum()),
        "regla_tiempo_min": "distancia_m * 0.06 / velocidad_kmh",
        "advertencia": "La distancia entre sensores no equivale necesariamente a la distancia de cada arista OSM.",
    }
    return s, reporte


def candidatos_con_auditoria(procesado: Path, base: Path):
    # Reutiliza exactamente los criterios conservadores del constructor previo.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from construir_red_osm_integrada import cargar_asociaciones

    c, aptas = cargar_asociaciones(
        procesado / "candidatos_bitcarrier_osm.csv", procesado / "resumen_cruce_bitcarrier_osm.csv"
    )
    aristas = pd.read_csv(base / "aristas_base.csv", dtype={"id_arista_osm": str})
    if aristas.indice_arista_osm.duplicated().any():
        raise ValueError("Indices OSM duplicados en aristas_base.csv")
    actual = aristas.set_index("indice_arista_osm")
    c["identidad_arista_vigente"] = [
        int(r.indice_osm) in actual.index
        and str(actual.loc[int(r.indice_osm), "id_arista_osm"]) == str(r.id_arista_osm)
        for r in c.itertuples(index=False)
    ]
    c["nombre_vigente_coincide"] = [
        (
            int(r.indice_osm) in actual.index
            and __import__("construir_red_osm_integrada").nombres_compatibles(
                r.nombre_origen, str(actual.loc[int(r.indice_osm), "nombre_via"])
            )
        )
        for r in c.itertuples(index=False)
    ]
    c["propuesta_estricta_vigente"] = (
        c.criterio_estricto
        & c.identidad_arista_vigente
        & c.nombre_vigente_coincide
        & c.indice_osm.isin(aptas.indice_osm)
    )
    # Nunca se equipara el angulo de los extremos con autorizacion de circulacion.
    c["advertencia_sentido"] = (
        "La direccion legal debe confirmarse en OSM/regulacion vial; angulo insuficiente"
    )
    return c, aristas


def construir_plantilla(c: pd.DataFrame, destino: Path):
    cols = [
        x
        for x in COLUMNAS_REVISION
        if x
        not in (
            "decision",
            "geometria_confirmada",
            "sentido_legal_confirmado",
            "evidencia",
            "revisor",
            "observaciones_revision",
        )
    ]
    d = c.loc[c.propuesta_estricta_vigente, cols].copy()
    # CSV inicial es plantilla de propuestas; no contiene autorizaciones.
    for col in [
        "decision",
        "geometria_confirmada",
        "sentido_legal_confirmado",
        "evidencia",
        "revisor",
        "observaciones_revision",
    ]:
        d[col] = "PENDIENTE" if col == "decision" else ""
    d.to_csv(destino, index=False, encoding="utf-8-sig")
    return d


def cargar_aprobaciones(path: Path, candidatos: pd.DataFrame):
    if not path.exists():
        return pd.DataFrame(columns=["indice_osm", "tid_bitcarrier"])
    r = pd.read_csv(
        path, dtype={"id_arista_osm": str, "tid_bitcarrier": str}, keep_default_na=False
    )
    required = {
        "indice_osm",
        "id_arista_osm",
        "tid_bitcarrier",
        "decision",
        "geometria_confirmada",
        "sentido_legal_confirmado",
        "evidencia",
        "revisor",
    }
    if not required.issubset(r.columns):
        raise ValueError(f"Revision incompleta: {required - set(r.columns)}")
    aprobadas = r.loc[r.decision.str.strip().str.upper() == "APROBADO"].copy()
    if aprobadas.empty:
        return aprobadas
    for col in ["geometria_confirmada", "sentido_legal_confirmado"]:
        if not aprobadas[col].astype(str).str.strip().str.upper().eq("SI").all():
            raise ValueError(f"Toda fila APROBADO debe tener {col}=SI")
    for col in ["evidencia", "revisor"]:
        if (
            aprobadas[col].astype(str).str.strip().str.len() < 8
            if col == "evidencia"
            else aprobadas[col].astype(str).str.strip().str.len() < 3
        ).any():
            raise ValueError(f"Falta {col} documentado en una fila APROBADO")
    if aprobadas.indice_osm.duplicated().any():
        raise ValueError("La misma arista tiene multiples aprobaciones")
    keys = ["indice_osm", "id_arista_osm", "tid_bitcarrier"]
    validos = candidatos.loc[candidatos.propuesta_estricta_vigente, keys].copy()
    validos["tid_bitcarrier"] = validos.tid_bitcarrier.astype(str)
    validos["id_arista_osm"] = validos.id_arista_osm.astype(str)
    check = aprobadas.merge(validos.assign(_valido=True), on=keys, how="left")
    if not check._valido.fillna(False).all() or len(check) != len(aprobadas):
        raise ValueError("Aprobacion no pertenece a candidatos estrictos del grafo actual")
    return aprobadas


def verificar_red(red: pd.DataFrame, aristas: pd.DataFrame):
    claves = ["indice_arista_osm", "dia_semana", "hora"]
    necesarias = set(
        claves + ["distancia_m", "velocidad_kmh", "tiempo_min", "fuente_dato", "estado_match"]
    )
    if not necesarias.issubset(red.columns):
        raise ValueError(f"Faltan columnas en red: {necesarias - set(red.columns)}")
    if red[claves].isna().any().any() or red.duplicated(claves).any():
        raise ValueError("Hay claves vacias o duplicadas")
    if len(red) != len(aristas) * 168 or red.indice_arista_osm.nunique() != len(aristas):
        raise ValueError("Faltan aristas u horarios en la red")
    if not red.hora.between(0, 23).all() or not red.dia_semana.between(0, 6).all():
        raise ValueError("Hora o dia fuera de rango")
    if (red.distancia_m <= 0).any() or (red.velocidad_kmh <= 0).any():
        raise ValueError("Distancias o velocidades no positivas")
    if red[["distancia_m", "velocidad_kmh", "tiempo_min"]].isna().any().any():
        raise ValueError("Hay valores numericos nulos")
    esperado = 0.06 * red.distancia_m / red.velocidad_kmh
    diferencia = (esperado - red.tiempo_min).abs()
    if diferencia.max() > 0.001:
        raise ValueError(f"Tiempo incoherente con metros/kmh: error max {diferencia.max():.6f}")
    if not red.groupby("indice_arista_osm").size().eq(168).all():
        raise ValueError("Algunas aristas no tienen 168 horarios")
    if (
        red.groupby("indice_arista_osm")[["dia_semana", "hora"]].apply(
            lambda d: len(d.drop_duplicates())
        )
        != 168
    ).any():
        raise ValueError("Una arista no cubre 168 horarios distintos")
    return {
        "registros": int(len(red)),
        "aristas": int(len(aristas)),
        "duplicados": int(red.duplicated(claves).sum()),
        "error_max_tiempo_min": float(diferencia.max()),
    }


def ejecutar(
    procesado=PROCESADO, base=BASE, red_dir=RED, salida=DESTINO, revision: Path | None = None
):
    salida.mkdir(parents=True, exist_ok=True)
    h = pd.read_csv(
        procesado / "observaciones_limpias.csv.gz",
        usecols=["tid", "distancia_original", "velocidad_original"],
    )
    s = pd.read_csv(procesado / "resumen_cruce_bitcarrier_osm.csv")
    tabla, unidades = auditar_unidades(h, s)
    tabla.to_csv(salida / "auditoria_unidades_por_tid.csv", index=False)
    (salida / "unidades_verificadas.json").write_text(
        json.dumps(unidades, indent=2, ensure_ascii=False), encoding="utf8"
    )
    if unidades["tramos_distancia_compatible_25pct"] != unidades["tramos"]:
        raise ValueError("Distancias no compatibles para todos los TID; revisar antes de continuar")
    c, aristas = candidatos_con_auditoria(procesado, base)
    c.to_csv(salida / "auditoria_geografica_direccional.csv", index=False)
    plantilla = salida / "PLANTILLA_revision_direcciones.csv"
    construir_plantilla(c, plantilla)
    aceptadas = (
        cargar_aprobaciones(revision, c)
        if revision
        else pd.DataFrame(columns=["indice_osm", "tid_bitcarrier"])
    )
    aceptadas.to_csv(salida / "aprobaciones_documentadas.csv", index=False)
    origen_red = red_dir / "red_osm_integrada.csv.gz"
    if not origen_red.exists():
        raise FileNotFoundError(
            "Falta red_osm_integrada.csv.gz. Ejecuta construir_red_osm_integrada.py"
        )
    d = pd.read_csv(origen_red, dtype={"id_arista_osm": str, "tid_referencia": str})
    quality = verificar_red(d, aristas)
    # La transferencia del modelo previo permanece identificada como PROVISIONAL.
    ids = set(aceptadas.indice_osm.astype(int)) if len(aceptadas) else set()
    if ids:
        referencias = d.loc[
            d.indice_arista_osm.isin(ids), ["indice_arista_osm", "tid_referencia"]
        ].drop_duplicates()
        m = aceptadas[["indice_osm", "tid_bitcarrier"]].merge(
            referencias, left_on="indice_osm", right_on="indice_arista_osm", how="left"
        )
        if (
            m.tid_referencia.isna().any()
            or not m.tid_bitcarrier.astype(str).eq(m.tid_referencia.astype(str)).all()
        ):
            raise ValueError("TID aprobado no coincide con el TID asignado en la red existente")
    es_transferencia = d.fuente_dato.eq("TRANSFERENCIA_BITCARRIER_PROVISIONAL")
    es_aprobado = d.indice_arista_osm.isin(ids) & es_transferencia
    d["fuente_dato"] = np.where(es_aprobado, "TRANSFERENCIA_BITCARRIER_REVISADA", d.fuente_dato)
    d["estado_match"] = np.where(es_aprobado, "REVISADO_CON_EVIDENCIA", d.estado_match)
    d["unidad_espacial"] = "ARISTA_OSM_DIRIGIDA"
    d["unidad_temporal"] = "DIA_TIPO_HORA"
    d["version_unidades"] = "SDM_METROS_KMH"
    d["es_observacion_directa"] = False
    d["uso_evaluacion_empirica"] = "NO; evaluar en historico reservado, nunca en esta tabla"
    out = salida / "dataset_red_osm_operativo_auditado.csv.gz"
    d.to_csv(out, index=False, compression="gzip")
    meta = {
        **quality,
        "transferencias_provisionales": int(
            (d.fuente_dato == "TRANSFERENCIA_BITCARRIER_PROVISIONAL").sum()
        ),
        "transferencias_revisadas": int(es_aprobado.sum()),
        "aristas_revisadas": len(ids),
        "aristas_con_propuesta_estricta": int(
            c.loc[c.propuesta_estricta_vigente, "indice_osm"].nunique()
        ),
        "simuladas": int((d.fuente_dato == "SIMULACION_CALIBRADA_OSM").sum()),
        "observaciones_directas": 0,
        "unidades": "m, km/h y minutos",
        "estado_geografico": "PENDIENTE_REVISION_EXTERNA" if not ids else "PARCIALMENTE_REVISADO",
        "advertencia": "Ni las propuestas estrictas ni las aprobaciones documentales prueban por si solas un aforo medido por arista. Las aprobaciones necesitan verificacion de regulacion vial.",
        "sha256_red_original": huella(origen_red),
        "archivo_dataset": str(out),
    }
    (salida / "informe_cierre.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf8"
    )
    print("UNIDADES OFICIALES: DISTANCE=metros; VEL_PROMEDIO=km/h")
    print(
        f"AUDITORIA GEOMETRIA: {unidades['tramos_distancia_compatible_25pct']}/{unidades['tramos']} tramos compatibles; ratio mediano={unidades['mediana_ratio']:.5f}"
    )
    print(
        f"RED AUDITADA: {meta['registros']:,} filas; {meta['aristas']:,} aristas; duplicados={meta['duplicados']}"
    )
    print(
        f"PROVISIONALES: {meta['transferencias_provisionales']:,}; REVISADAS: {meta['transferencias_revisadas']:,}; SIMULADAS: {meta['simuladas']:,}"
    )
    print("ESTADO DIRECCIONAL:", meta["estado_geografico"])
    print("Dataset:", out)
    print("Revision:", plantilla)
    return meta


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--procesado", type=Path, default=PROCESADO)
    p.add_argument("--base", type=Path, default=BASE)
    p.add_argument("--red", type=Path, default=RED)
    p.add_argument("--salida", type=Path, default=DESTINO)
    p.add_argument(
        "--revision",
        type=Path,
        default=None,
        help="CSV aprobado manualmente, diferente a la plantilla",
    )
    args = p.parse_args()
    ejecutar(args.procesado, args.base, args.red, args.salida, args.revision)
