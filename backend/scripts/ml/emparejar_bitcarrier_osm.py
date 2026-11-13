"""Auditoría local y reproducible de correspondencia Bitcarrier <-> OSM.

Desde la raíz de Proyecto-IA:
  python backend/scripts/ml/emparejar_bitcarrier_osm.py
  python backend/scripts/ml/emparejar_bitcarrier_osm.py --buffer-m 15

No altera grafo ni datos fuente. Produce candidatos geométricos para revisión,
NO un matching validado de sentido vial. Las observaciones se leen por lotes.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
from collections import Counter
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString, MultiLineString
from shapely.ops import unary_union

RAIZ = Path(__file__).resolve().parents[3]
ORIGEN = RAIZ / "backend/datos/ml/bitcarrier_mayo_2022_original"
OSM = RAIZ / "backend/datos/grafo_osm_aristas.geojson"
SALIDA = RAIZ / "backend/datos/ml/bitcarrier_mayo_2022_procesado"
CRS_METRICO = "EPSG:32618"  # UTM 18N, Bogotá


def geom_arcgis(g):
    if not isinstance(g, dict):
        return None
    paths = [p for p in g.get("paths", []) if isinstance(p, list) and len(p) >= 2]
    try:
        if not paths:
            return None
        return LineString(paths[0]) if len(paths) == 1 else MultiLineString(paths)
    except (ValueError, TypeError):
        return None


def extremos(linea):
    """Extremos del trazado; MultiLineString supone partes ordenadas por proveedor."""
    partes = list(linea.geoms) if linea.geom_type == "MultiLineString" else [linea]
    return partes[0].coords[0], partes[-1].coords[-1]


def angulo_orientado(a, b):
    """Ángulo entre vectores de extremos: 0º paralelo, 180º inverso."""
    ap, aq = extremos(a)
    bp, bq = extremos(b)
    va = (aq[0] - ap[0], aq[1] - ap[1])
    vb = (bq[0] - bp[0], bq[1] - bp[1])
    na, nb = math.hypot(*va), math.hypot(*vb)
    if na < 0.001 or nb < 0.001:
        return None
    c = max(-1.0, min(1.0, (va[0] * vb[0] + va[1] * vb[1]) / (na * nb)))
    return math.degrees(math.acos(c))


def leer_tramos():
    """Conserva una geometría representativa por TID; detecta inconsistencias."""
    datos = {}
    for lote in sorted(ORIGEN.glob("lote_*.json.gz")):
        with gzip.open(lote, "rt", encoding="utf-8") as f:
            features = json.load(f).get("features", [])
        for feat in features:
            a = feat.get("attributes") or {}
            tid = a.get("TID")
            geom = geom_arcgis(feat.get("geometry"))
            if tid is None or geom is None or geom.is_empty:
                continue
            tid = str(tid)
            firma = geom.wkb_hex
            if tid not in datos:
                datos[tid] = {
                    "geoms": Counter(),
                    "representantes": {},
                    "n": 0,
                    "origen": str(a.get("NAME_FROM", "")),
                    "destino": str(a.get("NAME_TO", "")),
                }
            d = datos[tid]
            d["n"] += 1
            d["geoms"][firma] += 1
            if firma not in d["representantes"]:
                d["representantes"][firma] = geom
    return datos


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--buffer-m",
        type=float,
        default=15.0,
        help="Tolerancia espacial en metros (por defecto 15)",
    )
    parser.add_argument(
        "--min-cobertura",
        type=float,
        default=0.50,
        help="Cobertura mínima de una arista OSM para listarla",
    )
    args = parser.parse_args()
    if not 0 < args.buffer_m <= 100 or not 0 < args.min_cobertura <= 1:
        parser.error("buffer-m debe ser (0,100] y min-cobertura (0,1]")
    if not OSM.exists():
        raise SystemExit(f"No se encuentra {OSM}")
    datos = leer_tramos()
    if not datos:
        raise SystemExit(f"No se encontraron geometrías Bitcarrier en {ORIGEN}")
    calles = gpd.read_file(OSM)
    if calles.crs is None:
        raise SystemExit("GeoJSON OSM sin CRS declarado: no se puede medir en metros")
    calles = calles.to_crs(CRS_METRICO)
    calles = calles.loc[calles.geometry.notna() & ~calles.geometry.is_empty].reset_index(drop=True)
    calles = calles.loc[
        calles.geometry.geom_type.isin(["LineString", "MultiLineString"])
    ].reset_index(drop=True)
    if calles.empty:
        raise SystemExit("GeoJSON OSM sin líneas válidas")
    aristas_idx = calles.sindex
    salida_detalle = []
    salida_resumen = []

    for i, (tid, info) in enumerate(sorted(datos.items()), 1):
        firma, ocurrencias = info["geoms"].most_common(1)[0]
        geom_original = info["representantes"][firma]
        geom = gpd.GeoSeries([geom_original], crs="EPSG:4326").to_crs(CRS_METRICO).iloc[0]
        longitud = float(geom.length)
        if longitud <= 0:
            continue
        corredor = geom.buffer(args.buffer_m)
        idx_candidatos = list(aristas_idx.query(corredor, predicate="intersects"))
        contribuciones = []
        compatibles = []
        inversas = []
        for idx in idx_candidatos:
            idx = int(idx)
            osm = calles.geometry.iloc[idx]
            if osm.length <= 0:
                continue
            fraccion = float(osm.intersection(corredor).length / osm.length)
            if fraccion < args.min_cobertura:
                continue
            ang = angulo_orientado(geom, osm)
            # La geometría dirigida puede contener múltiples curvas.
            # El ángulo de extremos es SOLO un indicador, no prueba circulación.
            orientacion = (
                "indeterminada"
                if ang is None
                else "compatible"
                if ang <= 60
                else "inversa"
                if ang >= 120
                else "ambigua"
            )
            fila = {
                "tid_bitcarrier": tid,
                "indice_osm": idx,
                "id_arista_osm": str(calles.iloc[idx].get("id", "")),
                "origen_osm": str(calles.iloc[idx].get("origen", "")),
                "destino_osm": str(calles.iloc[idx].get("destino", "")),
                "nombre_via_osm": str(calles.iloc[idx].get("nombre_via", "")),
                "longitud_osm_m": round(osm.length, 2),
                "cobertura_osm": round(fraccion, 4),
                "angulo_extremos_grados": "" if ang is None else round(ang, 2),
                "orientacion_preliminar": orientacion,
                "validacion_direccion": "PENDIENTE",
            }
            salida_detalle.append(fila)
            contribuciones.append(osm)
            if orientacion == "compatible":
                compatibles.append(osm)
            if orientacion == "inversa":
                inversas.append(osm)
        # Unión de corredores de múltiples aristas: no exige que una sola
        # arista OSM cubra toda la geometría Bitcarrier.
        cobertura_total = (
            geom.intersection(unary_union([g.buffer(args.buffer_m) for g in contribuciones])).length
            / longitud
            if contribuciones
            else 0.0
        )
        cobertura_comp = (
            geom.intersection(unary_union([g.buffer(args.buffer_m) for g in compatibles])).length
            / longitud
            if compatibles
            else 0.0
        )
        salida_resumen.append(
            {
                "tid_bitcarrier": tid,
                "nombre_origen": info["origen"],
                "nombre_destino": info["destino"],
                "observaciones": info["n"],
                "geometrias_distintas": len(info["geoms"]),
                "frecuencia_geometria_representativa": round(ocurrencias / info["n"], 4),
                "longitud_bitcarrier_geom_m": round(longitud, 2),
                "aristas_osm_candidatas": len(contribuciones),
                "aristas_orientacion_compatible": len(compatibles),
                "aristas_orientacion_inversa": len(inversas),
                "cobertura_espacial_total": round(cobertura_total, 4),
                "cobertura_orientacion_compatible": round(cobertura_comp, 4),
                "estado": "REVISION_MANUAL",  # Nunca aceptar automáticamente el sentido
            }
        )
        print(
            f"[{i}/{len(datos)}] TID={tid}: {len(contribuciones)} aristas candidatas; "
            f"cobertura={cobertura_total:.1%}; orientacion compatible={cobertura_comp:.1%}",
            flush=True,
        )

    SALIDA.mkdir(parents=True, exist_ok=True)
    archivos = [
        (SALIDA / "candidatos_bitcarrier_osm.csv", salida_detalle),
        (SALIDA / "resumen_cruce_bitcarrier_osm.csv", salida_resumen),
    ]
    for path, filas in archivos:
        if not filas:
            print(f"Sin filas para {path.name}")
            continue
        temporal = path.with_suffix(".csv.tmp")
        with temporal.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(filas[0]))
            writer.writeheader()
            writer.writerows(filas)
        temporal.replace(path)
        print(f"Escrito: {path} ({len(filas):,} filas)")
    print("\nIMPORTANTE: Son CANDIDATOS geométricos, NO correspondencias verificadas.")
    print(
        "Revisar visualmente tramos, sentidos, geometrías y unidades antes de crear el dataset maestro."
    )


if __name__ == "__main__":
    main()
