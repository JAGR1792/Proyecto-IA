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
from src.busqueda.bfs import BusquedaAmplitud
from src.busqueda.comparador import ComparacionAlgoritmos, comparar_algoritmos
from src.busqueda.registro import crear_algoritmos
from src.busqueda.ucs import BusquedaCostoUniforme
from src.busqueda.voraz import BusquedaVoraz

__all__ = [
    "CRITERIOS_VALIDOS",
    "AlgoritmoBusqueda",
    "ResultadoBusqueda",
    "BusquedaAEstrella",
    "BusquedaAmplitud",
    "BusquedaCostoUniforme",
    "BusquedaVoraz",
    "ComparacionAlgoritmos",
    "comparar_algoritmos",
    "construir_resultado",
    "costo_arista",
    "crear_algoritmos",
    "reconstruir_camino",
    "validar_criterio",
]
