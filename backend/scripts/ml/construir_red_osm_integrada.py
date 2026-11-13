"""Construye un dataset operativo OSM homogéneo con transferencias Bitcarrier PROVISIONALES.

Ejecutar desde la raíz del repositorio:
    python backend/scripts/ml/construir_red_osm_integrada.py

Requiere que ya se hayan ejecutado construir_dataset_maestro.py y
emparejar_bitcarrier_osm.py. NO modifica el dataset histórico original.

Todos los registros resultantes se refieren a una arista OSM / día tipo / hora.
No existen asociaciones Bitcarrier-OSM verificadas: la transferencia mediante
coincidencias geométricas y de nombre se etiqueta PROVISIONAL, nunca OBSERVADA.
Los perfiles por TID se calibran SOLO en los días 1-21 de mayo de 2022.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import re
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "backend/datos/ml/dataset_maestro_hibrido"
PROCESADO = ROOT / "backend/datos/ml/bitcarrier_mayo_2022_procesado"
SALIDA = ROOT / "backend/datos/ml/red_osm_integrada"

DIAS = {
    "Lunes": 0,
    "Martes": 1,
    "Miercoles": 2,
    "Jueves": 3,
    "Viernes": 4,
    "Sabado": 5,
    "Domingo": 6,
}


def canon(s: str) -> str:
    """Normaliza nombre de corredor sin equiparar calles diferentes."""
    t = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().upper()
    t = re.sub(r"\b(AVENIDA|AV|AVDA|AVEN|DE|LA|EL)\b", " ", t)
    t = re.sub(r"\b(CARRERA|KRA|CRA|CR|KR)\b", " KR ", t)
    t = re.sub(r"\b(CALLE|CLL|CL)\b", " CL ", t)
    t = re.sub(r"\b(AUTOPISTA|AUTO)\b", " AUTO ", t)
    return re.sub(r"\s+", "", t)


def nombres_compatibles(bitcarrier: str, osm: str) -> bool:
    a, b = canon(bitcarrier), canon(osm)
    if not a or not b:
        return False
    # Equivalencias de nombre solo si son plausibles y están documentadas.
    # AUTONORTE y CARACAS NO se equiparan automáticamente a Carrera 20/20B.
    return a == b


def cargar_asociaciones(path_candidatos: Path, path_resumen: Path):
    c = pd.read_csv(
        path_candidatos,
        dtype={"tid_bitcarrier": "str", "id_arista_osm": "str"},
        encoding="utf-8-sig",
    )
    r = pd.read_csv(path_resumen, dtype={"tid_bitcarrier": "str"}, encoding="utf-8-sig")
    campos = [
        "tid_bitcarrier",
        "nombre_origen",
        "geometrias_distintas",
        "frecuencia_geometria_representativa",
    ]
    assert set(campos).issubset(r.columns)
    c = c.merge(r[campos], on="tid_bitcarrier", how="left", validate="many_to_one")
    c["n_tid_candidatos"] = c.groupby("indice_osm")["tid_bitcarrier"].transform("nunique")
    c["nombre_coincide"] = [
        nombres_compatibles(x, y) for x, y in zip(c.nombre_origen, c.nombre_via_osm)
    ]
    c["criterio_estricto"] = (
        (c.cobertura_osm >= 0.90)
        & (c.angulo_extremos_grados <= 20)
        & (c.longitud_osm_m >= 20)
        & (c.orientacion_preliminar == "compatible")
        & (c.n_tid_candidatos == 1)
        & c.nombre_coincide
        & (c.geometrias_distintas == 1)
        & (c.frecuencia_geometria_representativa >= 0.99)
    )
    # Con una sola arista se pueden tener varias filas del mismo TID si el
    # dato de origen estuviera duplicado: no asignar silenciosamente.
    aptas = c.loc[c.criterio_estricto].copy()
    aptas = aptas.loc[~aptas.indice_osm.duplicated(keep=False)]
    return c, aptas


def perfiles_tid_entrenamiento(historico: Path):
    usar = [
        "tid",
        "inicio_original",
        "dia_semana_original",
        "hora",
        "velocidad_original",
        "num_dispositivos",
    ]
    h = pd.read_csv(historico, usecols=usar, dtype={"tid": "str"})
    dt = pd.to_datetime(h["inicio_original"], unit="ms", utc=True)
    h = h.loc[(dt.dt.month == 5) & (dt.dt.day <= 21)].copy()
    h["dia_semana"] = h.dia_semana_original.map(DIAS)
    h["hora"] = pd.to_numeric(h["hora"], errors="coerce")
    h["velocidad_original"] = pd.to_numeric(h["velocidad_original"], errors="coerce")
    h = h.loc[h.velocidad_original.between(4, 100) & h.dia_semana.notna() & h.hora.between(0, 23)]
    if h.empty:
        raise ValueError("No hay filas históricas utilizables del 1 al 21 de mayo de 2022")
    # Mediana robusta, por tramo/día/hora. No se usan muestras futuras.
    tabla = (
        h.groupby(["tid", "dia_semana", "hora"], observed=True)["velocidad_original"]
        .agg(["median", "count"])
        .reset_index()
    )
    return {
        (str(row.tid), int(row.dia_semana), int(row.hora)): (
            float(row["median"]),
            int(row["count"]),
        )
        for _, row in tabla.iterrows()
    }


def ejecutar(base=BASE, procesado=PROCESADO, salida=SALIDA):
    aristas = pd.read_csv(base / "aristas_base.csv")
    perfiles = pd.read_csv(base / "perfiles_entrenamiento.csv")
    candidatos, aptos = cargar_asociaciones(
        procesado / "candidatos_bitcarrier_osm.csv", procesado / "resumen_cruce_bitcarrier_osm.csv"
    )
    historico = perfiles_tid_entrenamiento(procesado / "observaciones_limpias.csv.gz")
    esperadas = {
        "indice_arista_osm",
        "id_arista_osm",
        "distancia_m",
        "velocidad_base_kmh",
        "tipo_via",
        "nombre_via",
    }
    if not esperadas.issubset(aristas.columns):
        raise ValueError(f"Faltan columnas en aristas_base.csv: {esperadas - set(aristas.columns)}")
    if aristas.indice_arista_osm.duplicated().any() or len(aristas) == 0:
        raise ValueError("Los índices de arista OSM deben ser únicos y no vacíos")
    if (aristas.distancia_m <= 0).any():
        raise ValueError("Hay distancias OSM no positivas")
    # Comprobar identidad de aristas contra el archivo OSM realmente utilizado.
    # Un CSV de candidatos generado con otra versión del grafo no es seguro.
    ref_osm = aristas.set_index("indice_arista_osm")
    aptos = aptos.loc[aptos.indice_osm.isin(ref_osm.index)].copy()
    aptos["identidad_osm_coincide"] = [
        str(ref_osm.loc[int(row.indice_osm), "id_arista_osm"]) == str(row.id_arista_osm)
        and nombres_compatibles(
            row.nombre_origen, str(ref_osm.loc[int(row.indice_osm), "nombre_via"])
        )
        for row in aptos.itertuples()
    ]
    aptos = aptos.loc[aptos.identidad_osm_coincide].copy()
    mapa = {int(row.indice_osm): str(row.tid_bitcarrier) for row in aptos.itertuples()}
    salida.mkdir(parents=True, exist_ok=True)
    columnas = [
        "indice_arista_osm",
        "id_arista_osm",
        "origen",
        "destino",
        "nombre_via",
        "tipo_via",
        "dia_semana",
        "hora",
        "distancia_m",
        "velocidad_kmh",
        "tiempo_min",
        "tid_referencia",
        "fuente_dato",
        "estado_match",
        "observaciones_calibracion",
        "particion",
    ]
    temporal = salida / "red_osm_integrada.csv.gz.tmp"
    total = 0
    transferidas = 0
    faltan_perfiles = 0
    try:
        with gzip.open(temporal, "wt", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=columnas)
            w.writeheader()
            for p in perfiles.itertuples(index=False):
                dia, hora = int(p.dia_semana), int(p.hora)
                for a in aristas.itertuples(index=False):
                    idx = int(a.indice_arista_osm)
                    base_v = float(a.velocidad_base_kmh)
                    vel_sim = max(5.0, min(80.0, base_v * float(p.factor_simulacion)))
                    tid = mapa.get(idx)
                    ref = historico.get((tid, dia, hora)) if tid else None
                    if tid and ref and ref[1] >= 3:
                        # Transferencia conservadora: 65% mediana histórica del
                        # corredor + 35% escenario OSM. NO es medición por arista.
                        vel = max(5.0, min(80.0, 0.65 * ref[0] + 0.35 * vel_sim))
                        fuente = "TRANSFERENCIA_BITCARRIER_PROVISIONAL"
                        estado = "NO_VERIFICADO"
                        n = ref[1]
                        transferidas += 1
                    else:
                        vel = vel_sim
                        fuente = "SIMULACION_CALIBRADA_OSM"
                        estado = "SIN_MATCH" if not tid else "PERFIL_INSUFICIENTE"
                        n = 0
                        if tid:
                            faltan_perfiles += 1
                    distancia = float(a.distancia_m)
                    w.writerow(
                        {
                            "indice_arista_osm": idx,
                            "id_arista_osm": a.id_arista_osm,
                            "origen": getattr(a, "origen", ""),
                            "destino": getattr(a, "destino", ""),
                            "nombre_via": getattr(a, "nombre_via", ""),
                            "tipo_via": getattr(a, "tipo_via", ""),
                            "dia_semana": dia,
                            "hora": hora,
                            "distancia_m": round(distancia, 3),
                            "velocidad_kmh": round(vel, 4),
                            "tiempo_min": round(0.06 * distancia / vel, 6),
                            "tid_referencia": tid or "",
                            "fuente_dato": fuente,
                            "estado_match": estado,
                            "observaciones_calibracion": n,
                            "particion": "ESCENARIO_NO_EVALUABLE",
                        }
                    )
                    total += 1
        os.replace(temporal, salida / "red_osm_integrada.csv.gz")
    finally:
        temporal.unlink(missing_ok=True)
    if total != len(aristas) * len(perfiles):
        raise AssertionError("Cobertura incompleta de la red OSM")
    auditoria = candidatos.copy()
    auditoria["resultado"] = "REVISAR_NO_ASIGNADA"
    auditoria.loc[auditoria.indice_osm.isin(aptos.indice_osm), "resultado"] = (
        "PROPUESTA_TRANSFERENCIA_PROVISIONAL"
    )
    auditoria.to_csv(salida / "auditoria_matching.csv", index=False)
    aptos.to_csv(salida / "asociaciones_provisionales.csv", index=False)
    meta = {
        "filas": total,
        "aristas_osm": len(aristas),
        "franjas_semanales": len(perfiles),
        "filas_transferencia_provisional": transferidas,
        "filas_simulacion": total - transferidas,
        "aristas_candidatas_estrictas": len(aptos),
        "perfiles_insuficientes": faltan_perfiles,
        "observaciones_reales_en_red_osm": 0,
        "advertencias": [
            "Los matches son PROVISIONALES. La orientación de extremos no comprueba el sentido legal.",
            "Las horas son horarios tipo, no registros de tiempo real.",
            "Las velocidades transferidas son interpolaciones de perfiles históricos de entrenamiento.",
            "Las unidades metros y km/h siguen pendientes de confirmación documental.",
            "No utilizar este dataset generado como evaluación empírica de precisión del modelo.",
            "Validar continuidad y geometría paralela antes de promover una asociación a verificada.",
        ],
    }
    (salida / "metadatos.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"RED OSM INTEGRADA: {total:,} filas; {len(aristas):,} aristas x {len(perfiles)} horas tipo"
    )
    print(f"Aristas con asociación estricta PROVISIONAL: {len(aptos)}")
    print(f"Escenarios de transferencia PROVISIONAL: {transferidas:,}")
    print(f"Escenarios de simulación: {total - transferidas:,}")
    print("Auditoría:", salida / "auditoria_matching.csv")
    print("NO equivale a matching verificado ni a cobertura observada sobre OSM.")
    return meta


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", type=Path, default=BASE)
    ap.add_argument("--procesado", type=Path, default=PROCESADO)
    ap.add_argument("--salida", type=Path, default=SALIDA)
    args = ap.parse_args()
    ejecutar(args.base, args.procesado, args.salida)
