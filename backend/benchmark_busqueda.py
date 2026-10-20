"""Benchmark reproducible de los algoritmos de búsqueda sobre la red vial.

Genera la evidencia experimental del Corte 2: ejecuta todos los algoritmos
registrados sobre los mismos pares origen/destino y criterios, y exporta una
tabla comparativa en CSV, un resumen en JSON y una tabla Markdown lista para
pegar en el informe.

Uso (desde backend/):
    python benchmark_busqueda.py --pares 8 --semilla 42
    python benchmark_busqueda.py --entrada datos/simulados/escenario_pico_manana.json
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from src.busqueda.base import AlgoritmoBusqueda
from src.busqueda.comparador import comparar_algoritmos
from src.busqueda.registro import crear_algoritmos
from src.grafo.modelos import Grafo
from src.grafo.repositorio import RepositorioGrafo

CRITERIOS = ("menor_tiempo", "menor_distancia", "menor_conexiones")
COLUMNAS = [
    "escenario",
    "origen",
    "destino",
    "criterio",
    "algoritmo",
    "ruta_encontrada",
    "costo",
    "distancia_m",
    "tiempo_min",
    "aristas",
    "nodos_explorados",
    "tiempo_ms",
    "brecha_pct",
]


def seleccionar_pares(
    grafo: Grafo,
    cantidad: int,
    semilla: int,
    distancia_min_m: float = 400.0,
) -> list[tuple[str, str]]:
    """Selecciona pares origen/destino reproducibles para el benchmark.

    Solo considera orígenes con al menos una arista saliente y descarta pares
    separados por menos de ``distancia_min_m`` en línea recta, para que las
    rutas sean representativas de un viaje urbano.

    Args:
        grafo: Red vial sobre la que se eligen los pares.
        cantidad: Número de pares deseados.
        semilla: Semilla para que la selección sea reproducible.
        distancia_min_m: Separación mínima en línea recta entre los nodos.

    Returns:
        Lista de tuplas ``(origen, destino)``.

    Raises:
        ValueError: Si el grafo no tiene al menos dos nodos con salidas.
    """
    candidatos = sorted(nodo_id for nodo_id in grafo.nodos if grafo.obtener_vecinos(nodo_id))
    if len(candidatos) < 2:
        raise ValueError("El grafo no tiene suficientes nodos con aristas salientes")

    azar = random.Random(semilla)
    pares: list[tuple[str, str]] = []
    vistos: set[tuple[str, str]] = set()
    intentos = 0

    while len(pares) < cantidad and intentos < cantidad * 200:
        intentos += 1
        origen, destino = azar.sample(candidatos, 2)
        clave = tuple(sorted((origen, destino)))
        if clave in vistos:
            continue
        separacion = grafo.nodos[origen].coordenadas.distancia_a(grafo.nodos[destino].coordenadas)
        if separacion < distancia_min_m:
            continue
        vistos.add(clave)
        pares.append((origen, destino))

    return pares


def ejecutar_benchmark(
    grafo: Grafo,
    pares: list[tuple[str, str]],
    criterios: tuple[str, ...],
    algoritmos: dict[str, AlgoritmoBusqueda],
    escenario: str,
) -> list[dict[str, Any]]:
    """Ejecuta la matriz de algoritmos, pares y criterios.

    Args:
        grafo: Red vial del escenario.
        pares: Pares origen/destino a evaluar.
        criterios: Criterios de optimización a comparar.
        algoritmos: Diccionario ``id -> algoritmo``.
        escenario: Nombre del escenario (por ejemplo, el archivo de entrada).

    Returns:
        Filas del benchmark con métricas y brecha porcentual frente al mejor
        costo de cada consulta.
    """
    filas: list[dict[str, Any]] = []

    for origen, destino in pares:
        for criterio in criterios:
            comparacion = comparar_algoritmos(grafo, origen, destino, criterio, algoritmos)
            for resultado in comparacion.resultados:
                filas.append(
                    {
                        "escenario": escenario,
                        "origen": origen,
                        "destino": destino,
                        "criterio": criterio,
                        "algoritmo": resultado.algoritmo,
                        "ruta_encontrada": resultado.ruta_encontrada,
                        "costo": resultado.costo_total,
                        "distancia_m": resultado.distancia_total_m,
                        "tiempo_min": resultado.tiempo_total_min,
                        "aristas": resultado.detalle.get("num_aristas", 0),
                        "nodos_explorados": resultado.nodos_explorados,
                        "tiempo_ms": resultado.tiempo_ejecucion_ms,
                        "brecha_pct": None,
                    }
                )

    mejores: dict[tuple[str, str, str], float] = {}
    for fila in filas:
        if not fila["ruta_encontrada"]:
            continue
        clave = (fila["origen"], fila["destino"], fila["criterio"])
        mejores[clave] = min(mejores.get(clave, fila["costo"]), fila["costo"])

    for fila in filas:
        if not fila["ruta_encontrada"]:
            continue
        mejor = mejores[(fila["origen"], fila["destino"], fila["criterio"])]
        if mejor > 0:
            fila["brecha_pct"] = round((fila["costo"] - mejor) / mejor * 100, 3)

    return filas


def resumir(filas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Agrega las filas por algoritmo y criterio.

    Args:
        filas: Filas producidas por :func:`ejecutar_benchmark`.

    Returns:
        Una fila de resumen por combinación algoritmo/criterio con promedios
        de costo, brecha, nodos explorados y milisegundos.
    """
    grupos: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for fila in filas:
        grupos[(fila["algoritmo"], fila["criterio"])].append(fila)

    resumen: list[dict[str, Any]] = []
    for (algoritmo, criterio), grupo in sorted(grupos.items()):
        encontradas = [fila for fila in grupo if fila["ruta_encontrada"]]
        resumen.append(
            {
                "algoritmo": algoritmo,
                "criterio": criterio,
                "ejecuciones": len(grupo),
                "encontradas": len(encontradas),
                "costo_promedio": round(statistics.mean(fila["costo"] for fila in encontradas), 3)
                if encontradas
                else None,
                "brecha_promedio_pct": round(
                    statistics.mean(fila["brecha_pct"] for fila in encontradas), 3
                )
                if encontradas
                else None,
                "nodos_promedio": round(
                    statistics.mean(fila["nodos_explorados"] for fila in encontradas), 1
                )
                if encontradas
                else None,
                "aristas_promedio": round(
                    statistics.mean(fila["aristas"] for fila in encontradas), 1
                )
                if encontradas
                else None,
                "ms_promedio": round(statistics.mean(fila["tiempo_ms"] for fila in encontradas), 3)
                if encontradas
                else None,
            }
        )
    return resumen


def tabla_markdown(resumen: list[dict[str, Any]]) -> str:
    """Construye una tabla Markdown del resumen para el informe.

    Args:
        resumen: Filas producidas por :func:`resumir`.

    Returns:
        Tabla Markdown con una fila por algoritmo y criterio.
    """
    lineas = [
        "| Algoritmo | Criterio | Ejecuciones | Costo prom. | Brecha prom. (%) | "
        "Nodos prom. | Aristas prom. | ms prom. |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for fila in resumen:
        lineas.append(
            "| {algoritmo} | {criterio} | {ejecuciones} | {costo_promedio} | "
            "{brecha_promedio_pct} | {nodos_promedio} | {aristas_promedio} | "
            "{ms_promedio} |".format(**fila)
        )
    return "\n".join(lineas)


def bloquear_aristas(grafo: Grafo, porcentaje: float, semilla: int) -> int:
    """Marca un porcentaje de aristas como no disponibles (cierre simulado).

    La modificación es solo en memoria: el archivo de entrada no se toca.

    Args:
        grafo: Red vial a modificar.
        porcentaje: Porcentaje de aristas a cerrar (0-100).
        semilla: Semilla para que el cierre sea reproducible.

    Returns:
        Número de aristas cerradas.

    Raises:
        ValueError: Si el porcentaje está fuera de [0, 100).
    """
    if not 0 <= porcentaje < 100:
        raise ValueError("El porcentaje de cierre debe estar entre 0 y 100")
    cantidad = int(len(grafo.aristas) * porcentaje / 100)
    if cantidad == 0:
        return 0
    azar = random.Random(semilla)
    elegidas = azar.sample(grafo.aristas, cantidad)
    for arista in elegidas:
        arista.disponible = False
    return cantidad


def cargar_grafo(entrada: Path) -> Grafo:
    """Carga el grafo desde un JSON compatible con el repositorio.

    Args:
        entrada: Ruta del archivo JSON.

    Returns:
        Grafo validado.
    """
    repositorio = RepositorioGrafo(entrada.parent)
    return repositorio.cargar_json(entrada.name)


def main() -> None:
    """Punto de entrada del benchmark."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--entrada",
        type=Path,
        default=Path("datos/dataset_osm.json"),
        help="JSON del grafo (por defecto datos/dataset_osm.json)",
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=Path("datos/resultados"),
        help="Directorio de salida para CSV/JSON/Markdown",
    )
    parser.add_argument("--pares", type=int, default=8, help="Número de pares OD")
    parser.add_argument("--semilla", type=int, default=42, help="Semilla reproducible")
    parser.add_argument(
        "--criterios",
        default=",".join(CRITERIOS),
        help="Criterios separados por coma",
    )
    parser.add_argument(
        "--algoritmos",
        default="",
        help="Algoritmos separados por coma (vacío = todos los registrados)",
    )
    parser.add_argument(
        "--bloquear-pct",
        type=float,
        default=0.0,
        help="Porcentaje de aristas a cerrar para simular un escenario de cierre",
    )
    args = parser.parse_args()

    if not args.entrada.is_file():
        parser.error(f"No existe {args.entrada}. Ejecuta el script desde backend/")

    grafo = cargar_grafo(args.entrada)
    criterios = tuple(c.strip() for c in args.criterios.split(",") if c.strip())
    registrados = crear_algoritmos()
    nombres = [a.strip() for a in args.algoritmos.split(",") if a.strip()]
    algoritmos = {nombre: registrados[nombre] for nombre in nombres} if nombres else registrados

    pares = seleccionar_pares(grafo, args.pares, args.semilla)
    aristas_bloqueadas = bloquear_aristas(grafo, args.bloquear_pct, args.semilla)
    escenario = args.entrada.stem
    if aristas_bloqueadas:
        escenario = f"{escenario}_cierre_{args.bloquear_pct:g}pct"

    filas = ejecutar_benchmark(grafo, pares, criterios, algoritmos, escenario)
    resumen = resumir(filas)

    args.salida.mkdir(parents=True, exist_ok=True)
    ruta_csv = args.salida / f"benchmark_{escenario}.csv"
    with ruta_csv.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=COLUMNAS)
        escritor.writeheader()
        escritor.writerows(filas)

    manifiesto = {
        "escenario": escenario,
        "entrada": str(args.entrada),
        "fecha_ejecucion": datetime.now().isoformat(timespec="seconds"),
        "semilla": args.semilla,
        "pares": len(pares),
        "criterios": list(criterios),
        "algoritmos": list(algoritmos),
        "nodos": len(grafo.nodos),
        "aristas": len([a for a in grafo.aristas if a.disponible]),
        "aristas_bloqueadas": aristas_bloqueadas,
        "resumen": resumen,
    }
    with (args.salida / f"resumen_{escenario}.json").open("w", encoding="utf-8") as archivo:
        json.dump(manifiesto, archivo, ensure_ascii=False, indent=2)

    markdown = tabla_markdown(resumen)
    (args.salida / f"benchmark_{escenario}.md").write_text(
        f"# Benchmark de búsqueda — {escenario}\n\n{markdown}\n", encoding="utf-8"
    )

    print(json.dumps(manifiesto, ensure_ascii=False, indent=2))
    print()
    print(markdown)


if __name__ == "__main__":
    main()
