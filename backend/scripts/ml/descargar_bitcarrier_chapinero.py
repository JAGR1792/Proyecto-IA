"""Descarga reanudable de observaciones históricas Bitcarrier para Taxi IA.

Ejecutar desde la raíz del repositorio Proyecto-IA:
    python descargar_bitcarrier_chapinero.py
    python descargar_bitcarrier_chapinero.py --limite 2000   # prueba pequeña
    python descargar_bitcarrier_chapinero.py --resumen        # auditar lo descargado

Solo descarga registros cuyas geometrías intersectan el RECTÁNGULO del grafo OSM.
Usa POST para los lotes de objectIds a fin de evitar URLs demasiado largas.
NO prueba correspondencia exacta con las vías ni sus sentidos. No entrena ML.
Conserva los atributos y geometrías sin transformar (JSON gzip por lote).
"""

import argparse
import csv
import gzip
import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

BASE = (
    "https://services2.arcgis.com/NEwhEo9GGSHXcRXV/ArcGIS/rest/services/"
    "Velocidades_Bitcarrier_Mayo_2022/FeatureServer/0"
)
RAIZ = Path(__file__).resolve().parents[3]
NODOS = RAIZ / "backend/datos/grafo_osm_nodos.csv"
SALIDA = RAIZ / "backend/datos/ml/bitcarrier_mayo_2022_original"
AGENTE = "Taxi-IA-Chapinero-academico/1.0"
CAMPOS_CLAVE = (
    "OBJECTID",
    "TID",
    "VEL_PROMEDIO",
    "VEL_MEDIA_MIXTO",
    "DISTANCE",
    "HORA",
    "INICIO",
    "DIA_SEMANA",
    "NUMDISPOSITIVOS",
    "NAME_FROM",
    "NAME_TO",
)


def solicitar(endpoint, parametros, intentos=5):
    """Consulta ArcGIS con POST para lotes grandes y reintentos solo transitorios.

    GET se reserva para metadatos y conteos, mientras POST evita URLs largas
    con centenares de objectIds, que pueden ser rechazadas por intermediarios.
    """
    url = BASE + endpoint
    codificados = urllib.parse.urlencode(parametros).encode("utf-8")
    usar_post = endpoint == "/query" and "objectIds" in parametros
    if usar_post:
        req = urllib.request.Request(
            url,
            data=codificados,
            headers={
                "User-Agent": AGENTE,
                "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                "Accept": "application/json",
            },
            method="POST",
        )
    else:
        req = urllib.request.Request(
            url + "?" + codificados.decode("utf-8"),
            headers={"User-Agent": AGENTE, "Accept": "application/json"},
        )
    for intento in range(intentos):
        try:
            with urllib.request.urlopen(req, timeout=120) as respuesta:
                datos = json.load(respuesta)
            if "error" in datos:
                error = datos["error"]
                codigo = error.get("code")
                raise RuntimeError(
                    f"ArcGIS respondió código {codigo}: {error.get('message')}; "
                    f"detalles: {error.get('details')}"
                )
            return datos
        except urllib.error.HTTPError as exc:
            # 404/400/401/403 no se resuelven esperando: mostrar diagnóstico.
            if exc.code not in (408, 429, 500, 502, 503, 504):
                raise RuntimeError(
                    f"ArcGIS HTTP {exc.code} en {endpoint or '/'} "
                    f"(método {'POST' if usar_post else 'GET'}). "
                    "Verificar endpoint y compatibilidad del servicio."
                ) from exc
            error = exc
        except (TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
            error = exc
        if intento == intentos - 1:
            raise RuntimeError(
                f"No se pudo consultar ArcGIS tras {intentos} intentos: {error}"
            ) from error
        pausa = min(30, 2**intento) + random.random()
        print(f"   Reintentando solicitud en {pausa:.1f}s: {error}", flush=True)
        time.sleep(pausa)
    raise RuntimeError("Solicitud sin respuesta")


def limites_grafo():
    if not NODOS.is_file():
        raise SystemExit(f"No encuentro {NODOS}; verifica la carpeta del proyecto.")
    with NODOS.open("r", encoding="utf-8-sig", newline="") as archivo:
        filas = list(csv.DictReader(archivo))
    if not filas:
        raise SystemExit("El CSV de nodos OSM está vacío.")
    lon = [float(f["longitud"]) for f in filas]
    lat = [float(f["latitud"]) for f in filas]
    return [min(lon), min(lat), max(lon), max(lat)], len(filas)


def parametros_espaciales(bbox):
    return {
        "where": "1=1",
        "geometry": json.dumps(
            {
                "xmin": bbox[0],
                "ymin": bbox[1],
                "xmax": bbox[2],
                "ymax": bbox[3],
                "spatialReference": {"wkid": 4326},
            }
        ),
        "geometryType": "esriGeometryEnvelope",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "f": "json",
    }


def escribir_json_atomico(ruta, objeto, comprimir=False):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(ruta.name + ".tmp")
    if comprimir:
        with gzip.open(temporal, "wt", encoding="utf-8") as archivo:
            json.dump(objeto, archivo, ensure_ascii=False)
    else:
        with temporal.open("w", encoding="utf-8") as archivo:
            json.dump(objeto, archivo, ensure_ascii=False, indent=2)
    temporal.replace(ruta)


def cargar_lote(ruta):
    with gzip.open(ruta, "rt", encoding="utf-8") as archivo:
        return json.load(archivo)


def resumen(ruta_salida):
    lotes = sorted(ruta_salida.glob("lote_*.json.gz"))
    if not lotes:
        print("No hay lotes descargados todavía.")
        return
    total = 0
    campos_no_nulos = Counter()
    campos_positivos = Counter()
    ids = set()
    duplicados = 0
    tipos_geom = Counter()
    for ruta in lotes:
        datos = cargar_lote(ruta)
        for elemento in datos.get("features", []):
            attrs = elemento.get("attributes") or {}
            oid = attrs.get("OBJECTID")
            if oid in ids:
                duplicados += 1
            ids.add(oid)
            total += 1
            for campo in CAMPOS_CLAVE:
                valor = attrs.get(campo)
                if valor is not None:
                    campos_no_nulos[campo] += 1
                if campo in ("VEL_PROMEDIO", "DISTANCE", "NUMDISPOSITIVOS"):
                    try:
                        if float(valor) > 0:
                            campos_positivos[campo] += 1
                    except (TypeError, ValueError):
                        pass
            geometria = elemento.get("geometry") or {}
            tipos_geom["paths" if geometria.get("paths") else "sin_paths"] += 1
    reporte = {
        "generado_utc": datetime.now(UTC).isoformat(),
        "observaciones_descargadas": total,
        "ids_unicos": len(ids),
        "ids_duplicados": duplicados,
        "lotes": len(lotes),
        "no_nulos": dict(campos_no_nulos),
        "positivos": dict(campos_positivos),
        "geometria": dict(tipos_geom),
        "advertencia": "Intersección con bounding box; no equivale a matching OSM ni valida dirección.",
    }
    escribir_json_atomico(ruta_salida / "resumen_calidad.json", reporte)
    print("\nRESUMEN DE CALIDAD")
    print(f"Observaciones: {total:,}; IDs únicos: {len(ids):,}; duplicados: {duplicados:,}")
    print(f"Lotes: {len(lotes)}; registros con geometría paths: {tipos_geom['paths']:,}")
    for campo in CAMPOS_CLAVE:
        print(f"  {campo}: {campos_no_nulos[campo]:,}/{total:,} no nulos", end="")
        if campo in campos_positivos:
            print(f"; positivos: {campos_positivos[campo]:,}", end="")
        print()
    print(f"Reporte: {ruta_salida / 'resumen_calidad.json'}")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--limite",
        type=int,
        default=0,
        help="Máximo de observaciones seleccionadas; 0=todas (predeterminado)",
    )
    parser.add_argument(
        "--lote",
        type=int,
        default=500,
        help="Registros por solicitud (1 a 2000; predeterminado 500)",
    )
    parser.add_argument("--resumen", action="store_true", help="Solo auditar los lotes descargados")
    args = parser.parse_args()
    if args.limite < 0 or not 1 <= args.lote <= 2000:
        parser.error("--limite debe ser >= 0 y --lote entre 1 y 2000")
    if args.resumen:
        resumen(SALIDA)
        return

    bbox, total_nodos = limites_grafo()
    consulta = parametros_espaciales(bbox)
    print(f"Nodos OSM: {total_nodos}; bbox: {bbox}")
    meta = solicitar("", {"f": "json"})
    print(f"Servicio: {meta.get('name')}; máximo por página: {meta.get('maxRecordCount')}")
    cantidad = solicitar("/query", dict(consulta, returnCountOnly="true"))["count"]
    print(f"Registros que intersectan el rectángulo: {cantidad:,}")

    # ArcGIS permite consultar todos los IDs aunque limite el número de entidades devueltas.
    datos_ids = solicitar("/query", dict(consulta, returnIdsOnly="true", returnGeometry="false"))
    identificadores = sorted(set(datos_ids.get("objectIds") or []))
    if len(identificadores) != cantidad:
        raise SystemExit(
            f"ERROR: conteo={cantidad:,}, IDs={len(identificadores):,}; "
            "no descargaremos datos potencialmente incompletos."
        )
    if args.limite:
        identificadores = identificadores[: args.limite]
    print(f"Registros seleccionados: {len(identificadores):,}")

    SALIDA.mkdir(parents=True, exist_ok=True)
    ruta_manifest = SALIDA / "manifiesto.json"
    config = {
        "servicio": BASE,
        "bbox_wgs84": bbox,
        "nodos_osm": total_nodos,
        "total_intersecciones_bbox": cantidad,
        "limite": args.limite,
        "lote": args.lote,
        "object_id_field": meta.get("objectIdField", "OBJECTID"),
        "criterio": "esriSpatialRelIntersects con rectángulo de nodos OSM",
    }
    if ruta_manifest.exists():
        anterior = json.loads(ruta_manifest.read_text(encoding="utf-8"))
        if any(anterior.get(k) != config[k] for k in ("servicio", "bbox_wgs84", "limite", "lote")):
            raise SystemExit(
                "Ya existe una descarga con otros parámetros en esta carpeta. "
                "Conserva esos archivos y muévelos a otra carpeta antes de comenzar otra modalidad."
            )
    else:
        escribir_json_atomico(ruta_manifest, config)

    numero_lotes = (len(identificadores) + args.lote - 1) // args.lote
    for n, inicio in enumerate(range(0, len(identificadores), args.lote), 1):
        subset = identificadores[inicio : inicio + args.lote]
        destino = SALIDA / f"lote_{n:05d}.json.gz"
        if destino.exists():
            data = cargar_lote(destino)
            almacenados = {
                f.get("attributes", {}).get("OBJECTID") for f in data.get("features", [])
            }
            if almacenados == set(subset):
                print(f"[{n}/{numero_lotes}] Ya existe y está verificado: {destino.name}")
                continue
            raise SystemExit(
                f"El lote {destino.name} no coincide con los IDs esperados. No se sobrescribe."
            )
        datos = solicitar(
            "/query",
            {
                "objectIds": ",".join(map(str, subset)),
                "outFields": "*",
                "returnGeometry": "true",
                "outSR": 4326,
                "f": "json",
            },
        )
        feats = datos.get("features") or []
        recibidos = {f.get("attributes", {}).get("OBJECTID") for f in feats}
        if recibidos != set(subset) or datos.get("exceededTransferLimit"):
            raise SystemExit(
                f"Lote {n}: solicitados {len(subset)}, recibidos {len(recibidos)} IDs distintos. "
                "Detenido para evitar un dataset incompleto; prueba con --lote 200 en una carpeta vacía."
            )
        escribir_json_atomico(destino, {"features": feats}, comprimir=True)
        print(f"[{n}/{numero_lotes}] Guardados {len(feats)} registros → {destino.name}", flush=True)
    resumen(SALIDA)
    print("\nDescarga terminada. NO es aún el dataset maestro vinculado a OSM.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit("\nInterrumpido. Vuelve a ejecutar el mismo comando para reanudar.")
