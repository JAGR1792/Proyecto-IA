"""Prepara una base de datos histórica y perfiles SIMULADOS para todas las aristas OSM.

Uso desde la raíz del repositorio:
    python backend/scripts/ml/construir_base_hibrida.py
    python backend/scripts/ml/construir_base_hibrida.py --generar-matriz

IMPORTANTE
- HISTORICO: observaciones Bitcarrier; no se afirma matching verificado con OSM.
- SIMULADO: estimación para TODO el grafo con perfiles calibrados por datos históricos.
- Por defecto produce 168 perfiles (7 días x 24 h) y una tabla por arista; evita
  materializar un producto cartesiano grande. --generar-matriz es opcional.
- DISTANCE=m y VEL_PROMEDIO=km/h son SUPUESTOS que deben validarse en la fuente.
- El campo INICIO se interpreta como calendario de la fuente (UTC de representación),
  no se convierte a zona Bogotá, pues HORA/DIA_SEMANA coinciden con ese calendario.
- NO usar filas simuladas como prueba de generalización a tráfico real.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[3]
ENTRADA = RAIZ / "backend/datos/ml/bitcarrier_mayo_2022_procesado/observaciones_limpias.csv.gz"
ARISTAS = RAIZ / "backend/datos/grafo_osm_aristas.csv"
SALIDA = RAIZ / "backend/datos/ml/base_hibrida"
DIAS = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]


def validar_columnas(df: pd.DataFrame, requeridas: set[str], fuente: Path) -> None:
    faltan = requeridas - set(df.columns)
    if faltan:
        raise ValueError(f"Faltan columnas {sorted(faltan)} en {fuente}")


def cargar_historico(path: Path) -> tuple[pd.DataFrame, dict]:
    if not path.exists():
        raise FileNotFoundError(f"No existe el CSV histórico: {path}")
    columnas = ["objectid", "tid", "inicio_original", "dia_semana_original", "hora",
                "distancia_original", "velocidad_original", "num_dispositivos"]
    df = pd.read_csv(path, usecols=columnas)
    validar_columnas(df, set(columnas), path)
    df["fecha_fuente"] = pd.to_datetime(df["inicio_original"], unit="ms", utc=True)
    df["dia_semana"] = df["fecha_fuente"].dt.dayofweek.astype("int8")
    df["hora"] = pd.to_numeric(df["hora"], errors="coerce")
    df["velocidad_original"] = pd.to_numeric(df["velocidad_original"], errors="coerce")
    df["distancia_original"] = pd.to_numeric(df["distancia_original"], errors="coerce")
    df["num_dispositivos"] = pd.to_numeric(df["num_dispositivos"], errors="coerce")
    conteo_original = len(df)
    coherentes = (df["fecha_fuente"].dt.hour == df["hora"]) & (
        df["dia_semana_original"] == df["dia_semana"].map(dict(enumerate(DIAS)))
    )
    if not coherentes.all():
        raise ValueError(f"{int((~coherentes).sum())} registros con calendario inconsistente")
    validos = (
        df["velocidad_original"].gt(0) & df["distancia_original"].gt(0)
        & df["hora"].between(0, 23) & df["num_dispositivos"].ge(1)
    )
    df = df.loc[validos].copy()
    df["hora"] = df["hora"].astype("int8")
    df["tid"] = df["tid"].astype(str)
    df["fuente_dato"] = "HISTORICO_BITCARRIER_2022"
    # Objetivo derivado: su validez depende de confirmar las unidades.
    df["tiempo_referencia_min"] = (
        0.06 * df["distancia_original"] / df["velocidad_original"]
    )
    if df.duplicated(["tid", "inicio_original"]).any():
        raise ValueError("Existen duplicados (tid, inicio_original)")
    estad = {"filas_entrada": conteo_original, "filas_validas": len(df),
             "tid_distintos": int(df["tid"].nunique()),
             "velocidades_mayores_100": int(df["velocidad_original"].gt(100).sum()),
             "intervalos_distintos": int(df["inicio_original"].nunique()),
             "calendario_consistente": bool(coherentes.all())}
    return df, estad


def construir_perfiles(historico: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Perfil normalizado por tramo, para no favorecer segmentos naturalmente rápidos."""
    # Evitar que mediciones extremas dominen el perfil; no alterar observaciones reales.
    percentil_bajo, percentil_alto = historico["velocidad_original"].quantile([0.01, 0.99])
    tmp = historico[["tid", "dia_semana", "hora", "velocidad_original"]].copy()
    tmp["velocidad_para_perfil"] = tmp["velocidad_original"].clip(percentil_bajo, percentil_alto)
    base_tid = tmp.groupby("tid")["velocidad_para_perfil"].median()
    tmp["ratio"] = tmp["velocidad_para_perfil"] / tmp["tid"].map(base_tid)
    # Mediana de observaciones y después mediana entre TID: cada tramo pesa similar.
    por_tramo = (tmp.groupby(["tid", "dia_semana", "hora"], as_index=False)["ratio"].median())
    dia_hora = por_tramo.groupby(["dia_semana", "hora"])["ratio"].median()
    hora_general = por_tramo.groupby("hora")["ratio"].median()
    global_mediana = float(por_tramo["ratio"].median())
    filas = []
    for dia in range(7):
        for hora in range(24):
            valor = dia_hora.get((dia, hora), np.nan)
            if pd.isna(valor):
                valor = hora_general.get(hora, global_mediana)
            filas.append({"dia_semana": dia, "hora": hora,
                          "factor_historico": float(valor),
                          "factor_simulacion": round(float(np.clip(valor, 0.55, 1.35)), 5),
                          "fuente_dato": "PERFIL_CALIBRADO_BITCARRIER_2022"})
    return pd.DataFrame(filas), {
        "velocidad_recorte_percentil_1": round(float(percentil_bajo), 3),
        "velocidad_recorte_percentil_99": round(float(percentil_alto), 3),
        "limites_factor_simulacion": [0.55, 1.35],
        "metodo": "mediana ratio velocidad / mediana de su TID, luego mediana entre TID"
    }


def construir_aristas(path: Path) -> tuple[pd.DataFrame, dict]:
    if not path.exists():
        raise FileNotFoundError(f"No existe el CSV de aristas OSM: {path}")
    # Leer CSV sin geometrías pesadas; preservar ID original como texto.
    columnas = ["id", "origen", "destino", "distancia", "velocidad_promedio",
                "tipo_via", "nombre_via", "carriles", "sentido_unico"]
    df = pd.read_csv(path, usecols=lambda c: c in columnas, dtype={"id": str,
                                                                    "origen": str, "destino": str})
    validar_columnas(df, {"id", "origen", "destino", "distancia"}, path)
    df = df.rename(columns={"id": "id_arista_osm", "distancia": "distancia_m",
                            "velocidad_promedio": "velocidad_base_kmh"})
    if "velocidad_base_kmh" not in df:
        df["velocidad_base_kmh"] = np.nan
    df["distancia_m"] = pd.to_numeric(df["distancia_m"], errors="coerce")
    df["velocidad_base_kmh"] = pd.to_numeric(df["velocidad_base_kmh"], errors="coerce")
    if df["distancia_m"].isna().any() or df["distancia_m"].le(0).any():
        raise ValueError("Aristas con distancias inválidas")
    # El respaldo por tipo NO es medición. Valores configurables y documentados.
    limites = {"principal": 45.0, "primaria": 45.0, "secundaria": 35.0,
               "terciaria": 30.0, "residencial": 25.0, "local": 25.0}
    tipo = df["tipo_via"].fillna("").astype(str).str.lower() if "tipo_via" in df else pd.Series("", index=df.index)
    respaldo = tipo.map(limites).fillna(30.0)
    tiene_base = df["velocidad_base_kmh"].between(5, 80)
    df["origen_velocidad_base"] = np.where(tiene_base, "OSM_MODELO_EXISTENTE", "SUPUESTO_POR_TIPO_VIA")
    df["velocidad_base_kmh"] = df["velocidad_base_kmh"].where(tiene_base, respaldo).astype(float)
    df["fuente_dato"] = "BASE_OSM_SIN_MEDICION_BITCARRIER_VERIFICADA"
    if df["id_arista_osm"].duplicated().any():
        # Algunos IDs de OSM se repiten si hay multiaristas; usar índice estable.
        df["indice_arista_osm"] = np.arange(len(df), dtype=np.int32)
    else:
        df["indice_arista_osm"] = np.arange(len(df), dtype=np.int32)
    return df, {"total_aristas": len(df), "aristas_base_respaldo": int((~tiene_base).sum()),
                "velocidades_respaldo_por_tipo": limites,
                "nota": "velocidad_promedio proviene del grafo existente, no de Bitcarrier"}


def generar_matriz(aristas: pd.DataFrame, perfiles: pd.DataFrame, destino: Path) -> int:
    """Escribe producto cartesiano en streaming (un día/hora por vez)."""
    n = 0
    with gzip.open(destino, "wt", encoding="utf-8", newline="") as f:
        campos = ["indice_arista_osm", "id_arista_osm", "dia_semana", "hora",
                  "distancia_m", "velocidad_simulada_kmh", "tiempo_simulado_min", "fuente_dato"]
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        for perfil in perfiles.itertuples(index=False):
            for arista in aristas.itertuples(index=False):
                vel = float(np.clip(arista.velocidad_base_kmh * perfil.factor_simulacion, 5, 80))
                writer.writerow({"indice_arista_osm": arista.indice_arista_osm,
                                 "id_arista_osm": arista.id_arista_osm,
                                 "dia_semana": perfil.dia_semana, "hora": perfil.hora,
                                 "distancia_m": round(arista.distancia_m, 4),
                                 "velocidad_simulada_kmh": round(vel, 4),
                                 "tiempo_simulado_min": round(0.06 * arista.distancia_m / vel, 6),
                                 "fuente_dato": "SIMULADO_CALIBRADO_HISTORICO"})
                n += 1
    return n


def ejecutar(historico_path: Path, osm_path: Path, salida: Path, matriz: bool) -> dict:
    salida.mkdir(parents=True, exist_ok=True)
    historial, calidad = cargar_historico(historico_path)
    perfiles, metod = construir_perfiles(historial)
    aristas, config = construir_aristas(osm_path)
    # Historial: mantener separado; no copiarlo artificialmente 1:1 a las aristas.
    real = historial[["objectid", "tid", "inicio_original", "fecha_fuente", "dia_semana",
                      "hora", "distancia_original", "velocidad_original", "num_dispositivos",
                      "tiempo_referencia_min", "fuente_dato"]]
    real.to_csv(salida / "regresion_historica.csv.gz", index=False, compression="gzip")
    perfiles.to_csv(salida / "perfiles_dia_hora.csv", index=False)
    aristas.to_csv(salida / "aristas_base.csv", index=False)
    filas_matriz = generar_matriz(aristas, perfiles, salida / "escenarios_simulados.csv.gz") if matriz else 0
    info = {
        "generado_utc": datetime.now(timezone.utc).isoformat(),
        "fuente_historica": "Bitcarrier mayo 2022", "calidad": calidad,
        "perfil": metod, "grafo": config, "filas_perfil": len(perfiles),
        "filas_simuladas_materializadas": filas_matriz,
        "etiqueta_datos_reales": "HISTORICO_BITCARRIER_2022",
        "etiqueta_datos_simulados": "SIMULADO_CALIBRADO_HISTORICO",
        "unidades_asumidas_sin_verificacion_documental": {"DISTANCE": "metros", "VEL_PROMEDIO": "km/h"},
        "zona_horaria": "Calendario fuente coincide con UTC representado; no convertir a America/Bogota sin confirmar metadatos",
        "limites": [
            "NO hay correspondencias verificadas entre TID y aristas OSM",
            "NO se atribuyen mediciones reales a aristas OSM",
            "El perfil general se transfiere a vías sin tráfico observado (suposición)",
            "El tiempo de referencia se deriva de distancia y velocidad, no es duración medida",
            "Los datos simulados NO se usan para evaluar desempeño sobre datos reales",
            "El conjunto de observaciones reales se debe dividir cronológicamente antes de ajustar modelos"
        ],
        "salidas": ["regresion_historica.csv.gz", "perfiles_dia_hora.csv", "aristas_base.csv"] +
                   (["escenarios_simulados.csv.gz"] if matriz else [])
    }
    (salida / "metadatos.json").write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    print("DATOS HISTORICOS:",len(real),"filas;",calidad["tid_distintos"],"TID")
    print("PERFILES:",len(perfiles),"(7 dias x 24 horas)")
    print("ARISTAS OSM:",len(aristas),"(sin afirmar matching histórico)")
    print("MATRIZ MATERIALIZADA:",filas_matriz,"filas")
    print("SALIDA:",salida)
    print("IMPORTANTE: perfiles calibrados son simulados para OSM; NO son observaciones reales por arista.")
    return info


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--generar-matriz", action="store_true", help="Crear también escenarios_simulados.csv.gz")
    p.add_argument("--historico", type=Path, default=ENTRADA)
    p.add_argument("--osm", type=Path, default=ARISTAS)
    p.add_argument("--salida", type=Path, default=SALIDA)
    args = p.parse_args()
    ejecutar(args.historico, args.osm, args.salida, args.generar_matriz)


if __name__ == "__main__":
    main()
