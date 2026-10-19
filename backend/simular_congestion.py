"""Genera datos SINTÉTICOS de movilidad para el grafo OSM de taxis en Chapinero.

Los datos topológicos vienen de OpenStreetMap. Congestión, incidentes, tiempos
con tráfico y velocidades efectivas son exclusivamente simulados.

Uso (desde backend/):
    python simular_congestion.py --dias 14 --semilla 42
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

HORAS = (6, 8, 12, 17, 19, 22)
INTENSIDAD_HORA = {6: 0.32, 8: 1.05, 12: 0.36, 17: 1.20, 19: 0.79, 22: 0.10}
PESO_VIA = {
    "autopista": 1.35,
    "troncal": 1.25,
    "primaria": 1.24,
    "secundaria": 1.12,
    "terciaria": 1.00,
    "residencial": 0.78,
    "servicio": 0.60,
    "otro": 0.85,
}
COLUMNAS = [
    "fecha", "hora", "dia_semana", "fin_semana", "escenario", "id_arista",
    "origen", "destino", "tipo_via", "distancia_m", "velocidad_libre_kmh",
    "factor_congestion_sintetico", "velocidad_simulada_kmh", "tiempo_viaje_min",
    "congestion", "incidentes", "disponible", "fuente_congestion",
]


def clasificar_congestion(factor: float, disponible: bool) -> str:
    """Clasifica la degradación de velocidad según umbrales *hipotéticos*."""
    if not disponible:
        return "bloqueada"
    if factor < 1.40:
        return "baja"
    if factor < 2.00:
        return "media"
    return "alta"


def generar_observacion(
    arista: dict[str, Any], fecha: date, hora: int, azar: random.Random
) -> dict[str, Any]:
    """Simula UNA observación para una arista y hora, sin mutar la red base."""
    distancia_m = float(arista["distancia"])
    velocidad_libre = float(arista.get("velocidad_promedio") or 40.0)
    if distancia_m < 0 or velocidad_libre <= 0:
        raise ValueError(f"Arista {arista['id']} con distancia o velocidad inválida")

    tipo = arista.get("atributos", {}).get("tipo_via", "otro") or "otro"
    fin_semana = fecha.weekday() >= 5
    intensidad = INTENSIDAD_HORA[hora] * (0.55 if fin_semana else 1.0)
    factor = 1.0 + intensidad * PESO_VIA.get(str(tipo), 0.85) * azar.uniform(0.72, 1.28)
    factor += azar.uniform(-0.10, 0.12)

    prob_incidente = 0.011 if hora in (8, 17, 19) else 0.003
    incidente = int(azar.random() < prob_incidente)
    if incidente:
        factor += azar.uniform(0.35, 0.95)
    cierre = bool(azar.random() < (0.0015 if incidente else 0.00015))
    disponible = bool(arista.get("disponible", True)) and not cierre
    factor = max(1.0, round(factor, 4))
    velocidad_efectiva = round(velocidad_libre / factor, 3)
    tiempo = round((distancia_m / 1000) / velocidad_efectiva * 60, 6) if disponible else None
    congestion = clasificar_congestion(factor, disponible)
    nombre_escenario = (
        "pico_manana" if hora == 8 else "pico_tarde" if hora in (17, 19) else "valle"
    )
    return {
        "fecha": fecha.isoformat(),
        "hora": hora,
        "dia_semana": fecha.weekday(),
        "fin_semana": int(fin_semana),
        "escenario": nombre_escenario,
        "id_arista": arista["id"],
        "origen": arista["origen"],
        "destino": arista["destino"],
        "tipo_via": tipo,
        "distancia_m": distancia_m,
        "velocidad_libre_kmh": velocidad_libre,
        "factor_congestion_sintetico": factor,
        "velocidad_simulada_kmh": velocidad_efectiva,
        "tiempo_viaje_min": tiempo,
        "congestion": congestion,
        "incidentes": incidente,
        "disponible": int(disponible),
        "fuente_congestion": "simulada",
    }


def preparar_grafo_escenario(
    grafo_base: dict[str, Any], observaciones: list[dict[str, Any]],
    fecha: date, hora: int, semilla: int,
) -> dict[str, Any]:
    """Devuelve un snapshot JSON compatible con Grafo Pydantic y RepositorioGrafo."""
    por_id = {str(r["id_arista"]): r for r in observaciones}
    nuevas_aristas = []
    for arista in grafo_base["aristas"]:
        nueva = dict(arista)
        obs = por_id[str(arista["id"])]
        nueva["congestion"] = obs["congestion"]
        nueva["incidentes"] = obs["incidentes"]
        nueva["disponible"] = bool(obs["disponible"])
        nueva["velocidad_promedio"] = obs["velocidad_simulada_kmh"]
        # Las calles bloqueadas mantienen un tiempo base calculado, pero no se recorren.
        nueva["tiempo_estimado"] = (
            obs["tiempo_viaje_min"]
            if obs["tiempo_viaje_min"] is not None
            else round(float(arista["distancia"]) / 1000 / float(arista.get("velocidad_promedio") or 40) * 60, 6)
        )
        nuevas_aristas.append(nueva)
    return {
        "dirigido": grafo_base.get("dirigido", True),
        "metadata": {
            **grafo_base.get("metadata", {}),
            "fuente_congestion": "simulada",
            "datos_trafico_reales": False,
            "fecha_escenario_hipotetico": fecha.isoformat(),
            "hora_escenario_hipotetico": hora,
            "semilla": semilla,
        },
        "nodos": grafo_base["nodos"],
        "aristas": nuevas_aristas,
    }


def generar_dataset(
    entrada: Path, salida: Path, inicio: date, dias: int = 14, semilla: int = 42
) -> dict[str, Any]:
    """Genera CSV temporal y tres instantáneas JSON sin alterar el archivo OSM."""
    if not (1 <= dias <= 365):
        raise ValueError("--dias debe estar entre 1 y 365")
    with entrada.open(encoding="utf-8") as f:
        grafo = json.load(f)
    aristas = grafo.get("aristas", [])
    if not isinstance(aristas, list) or not aristas or not grafo.get("nodos"):
        raise ValueError("El JSON de entrada no contiene nodos y aristas válidos")
    salida.mkdir(parents=True, exist_ok=True)
    rng = random.Random(semilla)
    conteo = Counter()
    instantaneas = {8: "pico_manana", 12: "valle", 17: "pico_tarde"}
    filas = 0
    archivo_csv = salida / "historial_congestion_simulado.csv"
    with archivo_csv.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=COLUMNAS)
        escritor.writeheader()
        for dia in range(dias):
            fecha_actual = inicio + timedelta(days=dia)
            for hora in HORAS:
                observaciones = []
                for arista in aristas:
                    fila = generar_observacion(arista, fecha_actual, hora, rng)
                    escritor.writerow(fila)
                    observaciones.append(fila)
                    conteo[fila["congestion"]] += 1
                    filas += 1
                if dia == 0 and hora in instantaneas:
                    nombre = f"escenario_{instantaneas[hora]}.json"
                    snap = preparar_grafo_escenario(grafo, observaciones, fecha_actual, hora, semilla)
                    with (salida / nombre).open("w", encoding="utf-8") as f:
                        json.dump(snap, f, ensure_ascii=False, indent=2)
    manifiesto = {
        "descripcion": "Datos SINTETICOS para experimentos académicos; no representan tráfico real.",
        "fuente_red_vial": grafo.get("metadata", {}).get("fuente", "OpenStreetMap"),
        "fuente_trafico": "simulacion_controlada",
        "observaciones_reales_trafico": 0,
        "semilla": semilla,
        "fecha_inicio_simulada": inicio.isoformat(),
        "dias": dias,
        "horas": list(HORAS),
        "nodos": len(grafo["nodos"]),
        "aristas": len(aristas),
        "registros": filas,
        "clases": dict(conteo),
        "snapshots": [f"escenario_{nombre}.json" for nombre in instantaneas.values()],
        "etiquetas_objetivo": ["congestion", "tiempo_viaje_min"],
        "advertencia": "No evaluar predicción sobre Bogotá real usando solo este dataset.",
    }
    with (salida / "metadata_simulacion.json").open("w", encoding="utf-8") as f:
        json.dump(manifiesto, f, indent=2, ensure_ascii=False)
    return manifiesto


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entrada", type=Path, default=Path("datos/dataset_osm.json"))
    parser.add_argument("--salida", type=Path, default=Path("datos/simulados"))
    parser.add_argument("--inicio", type=date.fromisoformat, default=date(2026, 10, 19))
    parser.add_argument("--dias", type=int, default=14)
    parser.add_argument("--semilla", type=int, default=42)
    args = parser.parse_args()
    if not args.entrada.is_file():
        parser.error(f"No existe {args.entrada}. Ejecute el script desde backend/ o pase --entrada")
    resultado = generar_dataset(args.entrada, args.salida, args.inicio, args.dias, args.semilla)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
