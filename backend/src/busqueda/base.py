"""Clase base y tipos comunes para algoritmos de búsqueda de rutas."""

import time
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from src.grafo.modelos import Grafo


class ResultadoBusqueda(BaseModel):
    """Resultado de una búsqueda de ruta entre dos nodos.

    Attributes:
        algoritmo: Nombre del algoritmo ejecutado.
        ruta_encontrada: True si se halló un camino origen → destino.
        camino: Lista ordenada de IDs de nodos (vacía si no hay ruta).
        aristas_camino: Lista ordenada de IDs de aristas usadas.
        criterio: Criterio de optimización utilizado.
        costo_total: Costo acumulado según el criterio seleccionado.
        distancia_total_m: Distancia acumulada en metros.
        tiempo_total_min: Tiempo acumulado en minutos.
        nodos_explorados: Cantidad de nodos expandidos.
        tiempo_ejecucion_ms: Milisegundos de ejecución del algoritmo.
        detalle: Información adicional del proceso.
    """

    algoritmo: str
    ruta_encontrada: bool = False
    camino: list[str] = Field(default_factory=list)
    aristas_camino: list[str] = Field(default_factory=list)
    criterio: str = "menor_tiempo"
    costo_total: float = 0.0
    distancia_total_m: float = 0.0
    tiempo_total_min: float = 0.0
    nodos_explorados: int = 0
    tiempo_ejecucion_ms: float = 0.0
    detalle: dict[str, Any] = Field(default_factory=dict)


class AlgoritmoBusqueda(ABC):
    """Contrato común para los algoritmos de búsqueda de rutas.

    Los algoritmos implementan la lógica en `_buscar` y la clase base
    se encarga de medir el tiempo de ejecución.
    """

    nombre: str = "base"

    def buscar(
        self,
        grafo: Grafo,
        origen: str,
        destino: str,
        criterio: str = "menor_tiempo",
    ) -> ResultadoBusqueda:
        """Ejecuta la búsqueda y mide el tiempo de ejecución.

        Args:
            grafo: Red vial donde buscar la ruta.
            origen: ID del nodo de origen.
            destino: ID del nodo de destino.
            criterio: Criterio de optimización (menor_tiempo, menor_distancia,
                menor_conexiones).

        Returns:
            Resultado de la búsqueda con métricas de ejecución.
        """
        inicio = time.perf_counter()
        resultado = self._buscar(grafo, origen, destino, criterio)
        resultado.tiempo_ejecucion_ms = round((time.perf_counter() - inicio) * 1000, 3)
        return resultado

    @abstractmethod
    def _buscar(
        self,
        grafo: Grafo,
        origen: str,
        destino: str,
        criterio: str,
    ) -> ResultadoBusqueda:
        """Implementa la búsqueda concreta del algoritmo."""
