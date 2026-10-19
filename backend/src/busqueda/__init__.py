"""Paquete de algoritmos de búsqueda de rutas sobre la red vial."""

from src.busqueda.a_estrella import BusquedaAEstrella
from src.busqueda.base import (
    CRITERIOS_VALIDOS,
    AlgoritmoBusqueda,
    ResultadoBusqueda,
    construir_resultado,
    costo_arista,
    reconstruir_camino,
    validar_criterio,
)
from src.busqueda.ucs import BusquedaCostoUniforme
from src.busqueda.voraz import BusquedaVoraz

__all__ = [
    "CRITERIOS_VALIDOS",
    "AlgoritmoBusqueda",
    "ResultadoBusqueda",
    "BusquedaAEstrella",
    "BusquedaCostoUniforme",
    "BusquedaVoraz",
    "construir_resultado",
    "costo_arista",
    "reconstruir_camino",
    "validar_criterio",
]
