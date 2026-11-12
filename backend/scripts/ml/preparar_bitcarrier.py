"""Prepara observaciones Bitcarrier mayo 2022 sin cargar todos los JSON en RAM.

Ejecutar desde cualquier carpeta:
  python backend/scripts/ml/preparar_bitcarrier.py

Produce datos tabulares CSV comprimidos, separados de los datos originales, y
un informe JSON de calidad. NO asocia tramos Bitcarrier con aristas OSM.
La distancia y velocidad conservan las unidades originales hasta validarlas.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import statistics
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
ORIGEN = RAIZ / "backend/datos/ml/bitcarrier_mayo_2022_original"
DESTINO = RAIZ / "backend/datos/ml/bitcarrier_mayo_2022_procesado"
COLUMNAS = (
    "objectid",
    "tid",
    "inicio_original",
    "dia_semana_original",
    "hora",
    "distancia_original",
    "velocidad_original",
    "num_dispositivos",
    "nombre_origen",
    "nombre_destino",
    "geometria_disponible",
)


def numerico(valor):
    if valor is None or isinstance(valor, bool):
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return numero if math.isfinite(numero) else None


def entero(valor):
    n = numerico(valor)
    return int(n) if n is not None and n.is_integer() else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limite-lotes", type=int, default=0, help="Para pruebas: 0=todos")
    args = parser.parse_args()
    if args.limite_lotes < 0:
        parser.error("--limite-lotes debe ser >= 0")

    lotes = sorted(ORIGEN.glob("lote_*.json.gz"))
    if not lotes:
        raise SystemExit(f"No se encontraron lotes en {ORIGEN}")
    if args.limite_lotes:
        lotes = lotes[: args.limite_lotes]

    DESTINO.mkdir(parents=True, exist_ok=True)
    salida = DESTINO / (
        "muestra_limpia.csv.gz" if args.limite_lotes else "observaciones_limpias.csv.gz"
    )
    reporte_ruta = DESTINO / (
        "reporte_muestra.json" if args.limite_lotes else "reporte_calidad.json"
    )
    temporal = salida.with_name(salida.name + ".tmp")
    conteo = Counter()
    razones_rechazo = Counter()
    horas = Counter()
    dias = Counter()
    tids = set()
    ids = set()
    velocidades = []
    distancias = []
    dispositivos = []
    inicio_ejemplos = []

    try:
        with gzip.open(temporal, "wt", encoding="utf-8", newline="") as out:
            writer = csv.DictWriter(out, fieldnames=COLUMNAS)
            writer.writeheader()
            for i, ruta in enumerate(lotes, start=1):
                with gzip.open(ruta, "rt", encoding="utf-8") as stream:
                    paquete = json.load(stream)
                features = paquete.get("features")
                if not isinstance(features, list):
                    raise ValueError(f"Formato de lote inválido: {ruta}")
                for feature in features:
                    conteo["leidos"] += 1
                    a = feature.get("attributes") or {}
                    objid = entero(a.get("OBJECTID"))
                    tid = a.get("TID")
                    v = numerico(a.get("VEL_PROMEDIO"))
                    d = numerico(a.get("DISTANCE"))
                    ndev = entero(a.get("NUMDISPOSITIVOS"))
                    hora = entero(a.get("HORA"))
                    dia = a.get("DIA_SEMANA")
                    geo = bool((feature.get("geometry") or {}).get("paths"))
                    fallos = []
                    if objid is None or objid in ids:
                        fallos.append("objectid_ausente_o_repetido")
                    if tid is None or str(tid).strip() == "":
                        fallos.append("tid_ausente")
                    if v is None or v <= 0:
                        fallos.append("velocidad_no_positiva_o_invalida")
                    if d is None or d <= 0:
                        fallos.append("distancia_no_positiva_o_invalida")
                    if hora is None or not 0 <= hora <= 23:
                        fallos.append("hora_fuera_de_0_a_23")
                    if ndev is None or ndev <= 0:
                        fallos.append("dispositivos_invalidos")
                    if dia is None or str(dia).strip() == "":
                        fallos.append("dia_semana_ausente")
                    if not geo:
                        fallos.append("geometria_ausente")
                    if objid is not None:
                        ids.add(objid)
                    if fallos:
                        conteo["rechazados"] += 1
                        razones_rechazo.update(fallos)
                        continue
                    writer.writerow(
                        {
                            "objectid": objid,
                            "tid": tid,
                            "inicio_original": a.get("INICIO"),
                            "dia_semana_original": dia,
                            "hora": hora,
                            "distancia_original": d,
                            "velocidad_original": v,
                            "num_dispositivos": ndev,
                            "nombre_origen": a.get("NAME_FROM"),
                            "nombre_destino": a.get("NAME_TO"),
                            "geometria_disponible": 1,
                        }
                    )
                    conteo["validos"] += 1
                    tids.add(str(tid))
                    horas[hora] += 1
                    dias[str(dia)] += 1
                    velocidades.append(v)
                    distancias.append(d)
                    dispositivos.append(ndev)
                    if len(inicio_ejemplos) < 5:
                        inicio_ejemplos.append(a.get("INICIO"))
                print(
                    f"[{i}/{len(lotes)}] {ruta.name} procesado; válidos: {conteo['validos']:,}",
                    flush=True,
                ) if i % 25 == 0 or i == len(lotes) else None
        temporal.replace(salida)
    finally:
        if temporal.exists():
            temporal.unlink()

    def estadisticas(valores):
        if not valores:
            return None
        ordenados = sorted(valores)
        return {
            "minimo": ordenados[0],
            "mediana": statistics.median(ordenados),
            "p95": ordenados[min(len(ordenados) - 1, int(0.95 * (len(ordenados) - 1)))],
            "maximo": ordenados[-1],
        }

    reporte = {
        "generado_utc": datetime.now(UTC).isoformat(),
        "fuente": "Velocidades Bitcarrier Mayo 2022 (ArcGIS)",
        "lotes_procesados": len(lotes),
        "filas_leidas": conteo["leidos"],
        "filas_validas": conteo["validos"],
        "filas_rechazadas": conteo["rechazados"],
        "razones_rechazo_no_excluyentes": dict(razones_rechazo),
        "tids_distintos": len(tids),
        "conteo_por_hora": {str(k): horas[k] for k in range(24)},
        "conteo_por_dia_original": dict(dias),
        "velocidad_original": estadisticas(velocidades),
        "distancia_original": estadisticas(distancias),
        "num_dispositivos": estadisticas(dispositivos),
        "ejemplos_inicio_original": inicio_ejemplos,
        "archivo_salida": str(salida.relative_to(RAIZ)),
        "notas": [
            "Las unidades de DISTANCE y VEL_PROMEDIO deben confirmarse antes de calcular tiempos.",
            "INICIO y DIA_SEMANA aún no se normalizan; revisar formato y zona horaria.",
            "Datos intersectan el bbox; NO están vinculados a aristas OSM ni validados por sentido.",
            "No se calculan objetivos ni divisiones de entrenamiento/prueba todavía.",
            "El CSV contiene solo atributos; las geometrías originales permanecen en los lotes fuente.",
        ],
    }
    reporte_ruta.write_text(json.dumps(reporte, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nRESUMEN")
    print(
        f"Leídos: {conteo['leidos']:,}; válidos: {conteo['validos']:,}; rechazados: {conteo['rechazados']:,}"
    )
    print(
        f"TID distintos: {len(tids):,}; horas con datos: {sum(bool(horas[h]) for h in range(24))}/24"
    )
    print(f"CSV: {salida}")
    print(f"Reporte: {reporte_ruta}")
    print("PENDIENTE: verificar unidades, fechas, y correspondencia con OSM.")


if __name__ == "__main__":
    main()
