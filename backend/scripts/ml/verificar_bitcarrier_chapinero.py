"""Diagnóstico de cobertura de Bitcarrier en la red OSM de Taxi IA Chapinero.

Uso desde la raíz del repositorio:
    python verificar_bitcarrier_chapinero.py

Necesita conexión a Internet. No descarga el dataset completo ni modifica archivos.
"""

import csv
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://services2.arcgis.com/NEwhEo9GGSHXcRXV/ArcGIS/rest/services/Velocidades_Bitcarrier_Mayo_2022/FeatureServer/0"
NODOS = Path("backend/datos/grafo_osm_nodos.csv")


def solicitar(url, params=None):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Taxi-IA-Universidad/1.0"})
    with urllib.request.urlopen(req, timeout=45) as response:
        return json.load(response)


def main():
    if not NODOS.is_file():
        raise SystemExit(
            "Ejecuta este script desde la raíz del repositorio (no se encontró backend/datos/grafo_osm_nodos.csv)."
        )
    with NODOS.open(encoding="utf-8-sig", newline="") as f:
        nodos = list(csv.DictReader(f))
    lat = [float(n["latitud"]) for n in nodos]
    lon = [float(n["longitud"]) for n in nodos]
    xmin, ymin, xmax, ymax = min(lon), min(lat), max(lon), max(lat)
    print("Nodos OSM:", len(nodos))
    print("Bounding box:", [xmin, ymin, xmax, ymax])
    envelope = json.dumps(
        {"xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax, "spatialReference": {"wkid": 4326}}
    )
    common = {
        "where": "1=1",
        "geometry": envelope,
        "geometryType": "esriGeometryEnvelope",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "f": "json",
    }
    try:
        meta = solicitar(BASE, {"f": "json"})
        if "error" in meta:
            raise RuntimeError(meta["error"])
        print("Servicio:", meta.get("name"))
        print("Capacidad por página:", meta.get("maxRecordCount"))
        count = solicitar(BASE + "/query", dict(common, returnCountOnly="true"))
        if "error" in count:
            raise RuntimeError(count["error"])
        print("Registros que intersectan el rectángulo:", count.get("count", "no disponible"))
        sample = solicitar(
            BASE + "/query",
            dict(
                common,
                outFields="OBJECTID,TID,INICIO,HORA,CUARTO_HORA,DIA_SEMANA,DISTANCE,VEL_PROMEDIO,VEL_MEDIA_MIXTO,NUMDISPOSITIVOS,NAME_FROM,NAME_TO",
                returnGeometry="true",
                resultRecordCount="100",
                outSR=4326,
            ),
        )
        if "error" in sample:
            raise RuntimeError(sample["error"])
        feats = sample.get("features", [])
        print("Registros muestra:", len(feats))
        for name in [
            "VEL_PROMEDIO",
            "VEL_MEDIA_MIXTO",
            "DISTANCE",
            "HORA",
            "INICIO",
            "NUMDISPOSITIVOS",
        ]:
            valid = sum(1 for f in feats if f.get("attributes", {}).get(name) is not None)
            print(f"  {name}: {valid}/{len(feats)} no nulos")
        for f in feats[:5]:
            a = f.get("attributes", {})
            print(
                "  Ejemplo:",
                {k: a.get(k) for k in ["NAME_FROM", "NAME_TO", "HORA", "VEL_PROMEDIO", "DISTANCE"]},
            )
        print(
            "\nIMPORTANTE: intersección del rectángulo no equivale a asociación exacta con las aristas OSM."
        )
        print(
            "Siguiente paso: emparejamiento geométrico de tramos, dirección y revisión de unidades."
        )
    except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
        raise SystemExit(f"No se pudo consultar Bitcarrier: {exc}")


if __name__ == "__main__":
    main()
