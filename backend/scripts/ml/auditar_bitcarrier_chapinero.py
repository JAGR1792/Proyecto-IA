"""Auditoría preliminar de emparejamiento geométrico Bitcarrier ↔ grafo OSM.

Ejecutar desde la raíz de Proyecto-IA con el entorno backend/.venv activado:
    python auditar_bitcarrier_chapinero.py

No guarda datos ni modifica archivos. Usa muestras espaciadas del servicio, no
una descarga completa. La coincidencia espacial NO acredita sentido vial ni
correspondencia exacta de los segmentos.
"""
import json
import urllib.parse
import urllib.request
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString, MultiLineString, shape

BASE = "https://services2.arcgis.com/NEwhEo9GGSHXcRXV/ArcGIS/rest/services/Velocidades_Bitcarrier_Mayo_2022/FeatureServer/0"
NODOS = Path("backend/datos/grafo_osm_nodos.csv")
ARISTAS = Path("backend/datos/grafo_osm_aristas.geojson")
TAMANO = 150
MARGEN_METROS = 25  # Exploratorio: no equivale a un emparejamiento validado


def consultar(path, params):
    url = BASE + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Taxi-IA-academico/1.0"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.load(resp)
    if "error" in data:
        raise RuntimeError(data["error"])
    return data


def geometria_arcgis(geom):
    if not geom:
        return None
    if "paths" in geom:
        paths = [p for p in geom["paths"] if len(p) >= 2]
        if not paths:
            return None
        return LineString(paths[0]) if len(paths) == 1 else MultiLineString(paths)
    if "rings" in geom:
        return shape({"type": "Polygon", "coordinates": geom["rings"]})
    return None


def main():
    if not NODOS.exists() or not ARISTAS.exists():
        raise SystemExit("Ejecuta desde la carpeta raíz Proyecto-IA (faltan archivos OSM).")
    import csv
    with NODOS.open(encoding="utf-8-sig", newline="") as f:
        filas = list(csv.DictReader(f))
    xs = [float(n["longitud"]) for n in filas]
    ys = [float(n["latitud"]) for n in filas]
    envelope = json.dumps({"xmin": min(xs), "ymin": min(ys), "xmax": max(xs), "ymax": max(ys), "spatialReference": {"wkid": 4326}})
    parametros = {"where": "1=1", "geometry": envelope, "geometryType": "esriGeometryEnvelope", "inSR": 4326, "spatialRel": "esriSpatialRelIntersects", "f": "json"}
    cantidad = consultar("/query", dict(parametros, returnCountOnly="true"))["count"]
    print(f"Registros que intersectan el rectángulo: {cantidad:,}")
    print("Nota: son observaciones, no necesariamente tramos únicos.")
    offsets = sorted(set(max(0, min(cantidad - TAMANO, round((cantidad - TAMANO) * f))) for f in (0.05, 0.5, 0.95)))
    observaciones = []
    for offset in offsets:
        datos = consultar("/query", dict(parametros, outFields="*", returnGeometry="true", outSR=4326, orderByFields="OBJECTID ASC", resultOffset=str(offset), resultRecordCount=str(TAMANO)))
        features = datos.get("features", [])
        print(f"Muestra desde offset {offset:,}: {len(features)} registros")
        for feat in features:
            geom = geometria_arcgis(feat.get("geometry"))
            if geom and not geom.is_empty and geom.length > 0:
                observaciones.append({**feat.get("attributes", {}), "geometry": geom})
    if not observaciones:
        raise SystemExit("Sin geometrías en la muestra; comprobar respuesta ArcGIS.")

    muestra = gpd.GeoDataFrame(observaciones, geometry="geometry", crs="EPSG:4326").to_crs("EPSG:32618")
    calles = gpd.read_file(ARISTAS).to_crs("EPSG:32618")
    calles = calles.loc[calles.geometry.notna() & ~calles.geometry.is_empty].copy()
    idx = calles.sindex
    encontrados = 0
    solapes_altos = 0
    mejores = []
    for geom in muestra.geometry:
        if geom.geom_type not in ("LineString", "MultiLineString") or geom.length <= 0:
            continue
        candidatos = list(idx.query(geom.buffer(MARGEN_METROS), predicate="intersects"))
        puntuacion = max((geom.intersection(calles.geometry.iloc[int(i)].buffer(MARGEN_METROS)).length / geom.length for i in candidatos), default=0.0)
        mejores.append(puntuacion)
        if puntuacion >= 0.50:
            encontrados += 1
        if puntuacion >= 0.80:
            solapes_altos += 1
    import pandas as pd
    print(f"Muestra con geometría: {len(muestra)}; aristas OSM geométricas: {len(calles)}")
    print(f"Coincidencias geométricas preliminares (>=50 % en corredor de 25 m): {encontrados}/{len(mejores)}")
    print(f"Coincidencias geométricas fuertes (>=80 %): {solapes_altos}/{len(mejores)}")
    print("ADVERTENCIA: proximidad NO valida dirección, identificación ni granularidad del tramo.")
    for campo in ["VEL_PROMEDIO", "VEL_MEDIA_MIXTO", "DISTANCE", "HORA", "INICIO", "DIA_SEMANA", "NUMDISPOSITIVOS", "TID"]:
        if campo in muestra:
            valores = pd.to_numeric(muestra[campo], errors="coerce") if campo in ("VEL_PROMEDIO", "VEL_MEDIA_MIXTO", "DISTANCE", "NUMDISPOSITIVOS") else muestra[campo]
            print(f"  {campo}: {int(valores.notna().sum())}/{len(muestra)} no nulos", end="")
            if campo in ("VEL_PROMEDIO", "DISTANCE"):
                print(f"; >0: {int((valores > 0).sum())}; min/mediana/max: {valores.min():.2f}/{valores.median():.2f}/{valores.max():.2f}", end="")
            print()
    print("Conclusión: la muestra permite decidir si vale la pena descargar el dataset completo y hacer matching espacial/direccional reproducible.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        raise SystemExit(f"Fallo en auditoría: {type(exc).__name__}: {exc}") from exc
