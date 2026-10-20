"""Clase base y utilidades comunes para los algoritmos de búsqueda de rutas."""

import time
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from src.grafo.modelos import CRITERIOS_OPTIMIZACION, Arista, Grafo
from src.tarifas.taximetro import TarifaTaxi

# Criterios de optimización soportados (PDF 5.2)
CRITERIOS_VALIDOS: tuple[str, ...] = CRITERIOS_OPTIMIZACION


def validar_criterio(criterio: str) -> None:
    """Valida que el criterio pertenezca a los soportados por el proyecto.

    Args:
        criterio: Identificador del criterio de optimización.

    Raises:
        ValueError: Si el criterio no es ``menor_tiempo``, ``menor_distancia``
            o ``menor_conexiones``.
    """
    if criterio not in CRITERIOS_VALIDOS:
        raise ValueError(f"Criterio '{criterio}' inválido. Válidos: {', '.join(CRITERIOS_VALIDOS)}")


def costo_arista(arista: Arista, criterio: str) -> float:
    """Calcula el costo de recorrer una arista según el criterio activo.

    Args:
        arista: Arista a evaluar.
        criterio: Criterio de optimización (``menor_tiempo``,
            ``menor_distancia`` o ``menor_conexiones``).

    Returns:
        Costo en la unidad del criterio: minutos, metros o número de
        conexiones (1 por arista).

    Raises:
        ValueError: Si el criterio no está soportado.
    """
    if criterio == "menor_distancia":
        return arista.distancia
    if criterio == "menor_tiempo":
        return arista.tiempo_estimado
    if criterio == "menor_conexiones":
        return 1.0
    raise ValueError(f"Criterio '{criterio}' inválido")


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
        tarifa_taxi: Tarifa de taxi liquidada para la ruta, si se solicitó.
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
    tarifa_taxi: TarifaTaxi | None = Field(
        None,
        description="Tarifa de taxi liquidada para la ruta (si se solicitó)",
    )


def construir_resultado(
    *,
    algoritmo: str,
    criterio: str,
    camino: list[str],
    aristas: list[Arista],
    encontrada: bool,
    nodos_explorados: int,
    detalle: dict[str, Any] | None = None,
) -> ResultadoBusqueda:
    """Construye el resultado homogéneo de una búsqueda a partir del camino.

    Centraliza el cálculo de métricas (costo, distancia, tiempo y número de
    aristas) para que todos los algoritmos reporten las mismas magnitudes.

    Args:
        algoritmo: Nombre del algoritmo ejecutado.
        criterio: Criterio de optimización aplicado.
        camino: IDs de los nodos del camino encontrado (vacío si no hay ruta).
        aristas: Aristas recorridas, en el mismo orden que ``camino``.
        encontrada: True si se alcanzó el destino.
        nodos_explorados: Cantidad de nodos expandidos durante la búsqueda.
        detalle: Información adicional opcional.

    Returns:
        Resultado de búsqueda con las métricas acumuladas.
    """
    detalle_resultado = dict(detalle or {})
    detalle_resultado.setdefault("num_aristas", len(aristas))
    return ResultadoBusqueda(
        algoritmo=algoritmo,
        ruta_encontrada=encontrada,
        camino=camino,
        aristas_camino=[arista.id for arista in aristas],
        criterio=criterio,
        costo_total=round(sum(costo_arista(arista, criterio) for arista in aristas), 3),
        distancia_total_m=round(sum(arista.distancia for arista in aristas), 3),
        tiempo_total_min=round(sum(arista.tiempo_estimado for arista in aristas), 3),
        nodos_explorados=nodos_explorados,
        detalle=detalle_resultado,
    )


def reconstruir_camino(
    origen: str,
    destino: str,
    predecesores: dict[str, tuple[str, Arista]],
) -> tuple[list[str], list[Arista]]:
    """Reconstruye el camino y sus aristas siguiendo los predecesores.

    Args:
        origen: Nodo inicial de la búsqueda.
        destino: Nodo final alcanzado.
        predecesores: Mapa ``nodo -> (nodo_anterior, arista)``.

    Returns:
        Tupla ``(camino, aristas)`` en orden origen → destino.
    """
    camino = [destino]
    aristas: list[Arista] = []
    while camino[-1] != origen:
        anterior, arista = predecesores[camino[-1]]
        aristas.append(arista)
        camino.append(anterior)
    camino.reverse()
    aristas.reverse()
    return camino, aristas


class AlgoritmoBusqueda(ABC):
    """Contrato común para los algoritmos de búsqueda de rutas.

    Los algoritmos implementan la lógica en `_buscar` y la clase base
    se encarga de validar la entrada y medir el tiempo de ejecución.
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

        Raises:
            ValueError: Si origen o destino no existen en el grafo, o si el
                criterio no está soportado.
        """
        if origen not in grafo.nodos or destino not in grafo.nodos:
            raise ValueError(f"Nodo origen '{origen}' o destino '{destino}' no existe en el grafo")
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
