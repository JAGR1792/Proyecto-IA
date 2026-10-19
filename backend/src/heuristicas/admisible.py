"""Heurísticas admisibles para la búsqueda A* sobre la red vial.

Una heurística ``h(n)`` es **admisible** cuando nunca sobreestima el costo
real de llegar al destino; con una heurística admisible A* garantiza la ruta
de costo mínimo. Además, las heurísticas de este módulo son **consistentes**
(monótonas), lo que evita reabrir nodos ya expandidos.

La estimación se deriva de la distancia geográfica en línea recta (haversine)
y del criterio activo:

- ``menor_distancia``: distancia en línea recta, que nunca supera la
  distancia recorrida por las vías.
- ``menor_tiempo``: distancia en línea recta dividida por la velocidad
  máxima efectiva de la red, que nunca supera el tiempo real.
- ``menor_conexiones``: 1 si el nodo no es el destino (todo camino necesita
  al menos una arista), 0 en el destino.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.grafo.modelos import CRITERIOS_OPTIMIZACION

if TYPE_CHECKING:
    from src.grafo.modelos import Grafo

NOMBRE_HEURISTICA = "admisible_geografica"


@dataclass(frozen=True)
class ContextoHeuristico:
    """Parámetros constantes de una búsqueda A* que la heurística necesita.

    Se calcula una sola vez por búsqueda para no recorrer el grafo en cada
    evaluación de ``h(n)``.

    Attributes:
        destino: ID del nodo destino.
        criterio: Criterio de optimización activo.
        velocidad_maxima_ms: Cota superior de la velocidad efectiva, en m/s.
        nombre: Identificador de la heurística usada.
    """

    destino: str
    criterio: str
    velocidad_maxima_ms: float
    nombre: str = NOMBRE_HEURISTICA


def velocidad_maxima_ms(grafo: "Grafo") -> float:
    """Calcula una cota superior de la velocidad efectiva de la red, en m/s.

    Se toma el máximo entre la velocidad declarada de cada arista y la
    velocidad implícita en su costo (``distancia / tiempo``). Así la
    heurística de tiempo nunca sobreestima el costo real aunque los datos
    de velocidad y tiempo no sean perfectamente coherentes.

    Args:
        grafo: Red vial de la que se extrae la cota.

    Returns:
        Velocidad en metros por segundo. Si el grafo no tiene aristas
        utilizables devuelve ``1.0`` para evitar divisiones por cero.
    """
    maxima = 0.0
    for arista in grafo.aristas:
        if not arista.disponible:
            continue
        maxima = max(maxima, arista.velocidad_promedio / 3.6)
        if arista.tiempo_estimado > 0:
            maxima = max(maxima, arista.distancia / (arista.tiempo_estimado * 60.0))
    return maxima if maxima > 0 else 1.0


def preparar_contexto(grafo: "Grafo", destino: str, criterio: str) -> ContextoHeuristico:
    """Precalcula los parámetros que la heurística necesita.

    Args:
        grafo: Red vial sobre la que se buscará.
        destino: ID del nodo destino.
        criterio: Criterio de optimización activo.

    Returns:
        Contexto heurístico listo para evaluar ``h(n)``.

    Raises:
        ValueError: Si el criterio no está soportado.
    """
    if criterio not in CRITERIOS_OPTIMIZACION:
        raise ValueError(
            f"Criterio '{criterio}' inválido. Válidos: {', '.join(CRITERIOS_OPTIMIZACION)}"
        )
    velocidad = velocidad_maxima_ms(grafo) if criterio == "menor_tiempo" else 1.0
    return ContextoHeuristico(
        destino=destino,
        criterio=criterio,
        velocidad_maxima_ms=velocidad,
    )


def estimar_costo_restante(grafo: "Grafo", nodo_id: str, contexto: ContextoHeuristico) -> float:
    """Estima el costo restante desde ``nodo_id`` hasta el destino.

    Args:
        grafo: Red vial con las coordenadas de los nodos.
        nodo_id: Nodo desde el que se estima.
        contexto: Parámetros precalculados de la búsqueda.

    Returns:
        Estimación ``h(nodo_id)`` en la unidad del criterio activo
        (metros, minutos o conexiones). Es 0 en el destino.
    """
    if nodo_id == contexto.destino:
        return 0.0
    if contexto.criterio == "menor_conexiones":
        return 1.0

    distancia = grafo.nodos[nodo_id].coordenadas.distancia_a(
        grafo.nodos[contexto.destino].coordenadas
    )
    if contexto.criterio == "menor_distancia":
        return distancia
    # menor_tiempo: tiempo mínimo teórico a la velocidad máxima efectiva.
    return distancia / contexto.velocidad_maxima_ms / 60.0
