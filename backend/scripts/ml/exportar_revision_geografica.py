"""Prepara dos capas GeoJSON para inspeccion visual en QGIS.

- candidatos_osm_revision.geojson: aristas dirigidas con propuestas estrictas.
- tramos_bitcarrier_revision.geojson: 46 geometrías representativas.

Requiere geopandas y shapely instalados en el entorno del backend. El archivo
GeoJSON NO prueba sentidos legales de circulacion; se revisan por separado.
"""

from __future__ import annotations

import gzip
import json
from collections import Counter
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, MultiLineString

ROOT = Path(__file__).resolve().parents[3]
PROCESADO = ROOT / "backend/datos/ml/bitcarrier_mayo_2022_procesado"
OSM = ROOT / "backend/datos/grafo_osm_aristas.geojson"
ORIGINAL = ROOT / "backend/datos/ml/bitcarrier_mayo_2022_original"
SALIDA = ROOT / "backend/datos/ml/red_osm_auditada"


def ejecutar(procesado=PROCESADO, osm_path=OSM, original=ORIGINAL, salida=SALIDA):
    salida.mkdir(parents=True, exist_ok=True)
    archivo = salida / "auditoria_geografica_direccional.csv"
    if not archivo.exists():
        raise FileNotFoundError("Ejecuta antes auditar_y_cerrar_red_osm.py")
    audit = pd.read_csv(archivo, dtype={"id_arista_osm": str, "tid_bitcarrier": str})
    audit = audit.loc[audit.propuesta_estricta_vigente].copy()
    calles = gpd.read_file(osm_path)
    if calles.crs is None:
        raise ValueError("Grafo OSM sin CRS")
    # El script de origen reinicia índices tras descartar geometrías no válidas.
    # Replicar exactamente ese orden para que indice_osm sea interpretable.
    calles = calles.to_crs("EPSG:32618")
    calles = calles.loc[calles.geometry.notna() & ~calles.geometry.is_empty].reset_index(drop=True)
    calles = calles.loc[
        calles.geometry.geom_type.isin(["LineString", "MultiLineString"])
    ].reset_index(drop=True)
    valid = audit.loc[audit.indice_osm.isin(calles.index)].copy()
    if len(valid) != len(audit):
        raise ValueError("Candidato fuera de indices del grafo: regenerate matching")
    capas = calles.iloc[valid.indice_osm.astype(int).to_numpy()].copy().reset_index(drop=True)
    # Comparar identidades no solo índices: evita revisar una versión equivocada.
    if (
        "id" not in capas.columns
        or not (capas.id.astype(str).to_numpy() == valid.id_arista_osm.astype(str).to_numpy()).all()
    ):
        raise ValueError(
            "Los ID del grafo OSM no corresponden con los candidatos. Rehacer matching"
        )
    for col in [
        "tid_bitcarrier",
        "cobertura_osm",
        "angulo_extremos_grados",
        "orientacion_preliminar",
    ]:
        capas[col] = valid[col].to_numpy()
    capas["indice_osm"] = valid.indice_osm.to_numpy()
    capas.to_crs("EPSG:4326").to_file(salida / "candidatos_osm_revision.geojson", driver="GeoJSON")
    datos = {}
    for lote in sorted(original.glob("lote_*.json.gz")):
        with gzip.open(lote, "rt", encoding="utf8") as f:
            features = json.load(f).get("features", [])
        for feat in features:
            attr = feat.get("attributes") or {}
            geom = feat.get("geometry") or {}
            paths = geom.get("paths") or []
            if not paths or any(len(p) < 2 for p in paths):
                continue
            tid = str(attr.get("TID"))
            if tid == "None":
                continue
            try:
                line = LineString(paths[0]) if len(paths) == 1 else MultiLineString(paths)
            except (ValueError, TypeError):
                continue
            info = datos.setdefault(
                tid, {"n": Counter(), "geom": {}, "via": str(attr.get("NAME_FROM", ""))}
            )
            key = line.wkb_hex
            info["n"][key] += 1
            info["geom"][key] = line
    if not datos:
        raise FileNotFoundError("No hay geometrías originales Bitcarrier: faltan lote_*.json.gz")
    items = []
    for tid, info in sorted(datos.items()):
        key, n = info["n"].most_common(1)[0]
        items.append(
            {
                "tid_bitcarrier": tid,
                "via": info["via"],
                "n_registros": sum(info["n"].values()),
                "frecuencia_geom": n / sum(info["n"].values()),
                "geometry": info["geom"][key],
            }
        )
    gpd.GeoDataFrame(items, geometry="geometry", crs="EPSG:4326").to_file(
        salida / "tramos_bitcarrier_revision.geojson", driver="GeoJSON"
    )
    print(f"Capas QGIS listas: {len(capas)} aristas candidatas y {len(items)} tramos Bitcarrier")
    print("REQUIERE REVISION MANUAL DE SENTIDO LEGAL Y GEOMETRIA")


if __name__ == "__main__":
    ejecutar()
