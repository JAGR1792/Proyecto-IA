"""Paquete de algoritmos de búsqueda de rutas sobre la red vial."""

from src.busqueda.base import AlgoritmoBusqueda, ResultadoBusqueda
from src.busqueda.voraz import BusquedaVoraz

__all__ = [
    "AlgoritmoBusqueda",
    "ResultadoBusqueda",
    "BusquedaVoraz",
]
