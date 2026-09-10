"""Endpoints de búsqueda de rutas sobre el grafo de movilidad."""

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.api.rutas_grafo import obtener_grafo
from src.busqueda.base import AlgoritmoBusqueda, ResultadoBusqueda
from src.busqueda.voraz import BusquedaVoraz

router = APIRouter()

# Identificadores de algoritmos disponibles en la API
_ID_ALGORITMO = Literal["bfs", "dfs", "ucs", "voraz", "a_estrella"]


class SolicitudBusqueda(BaseModel):
    """Parámetros para ejecutar una búsqueda de ruta."""

    origen: str
    destino: str
    algoritmo: _ID_ALGORITMO = "voraz"
    criterio: str = "menor_tiempo"


# Registro de algoritmos implementados (Corte 2, incremental)
_ALGORITMOS: dict[str, AlgoritmoBusqueda] = {
    "voraz": BusquedaVoraz(),
}


@router.post("/buscar", response_model=ResultadoBusqueda)
async def buscar_ruta(solicitud: SolicitudBusqueda):
    """Busca la mejor ruta entre dos nodos según el algoritmo indicado.

    Args:
        solicitud: Origen, destino, algoritmo y criterio de optimización.

    Returns:
        Ruta encontrada con sus métricas (camino, costo, tiempo, distancia).

    Raises:
        HTTPException 404: si origen o destino no existen en el grafo.
        HTTPException 422: si el criterio no es válido.
        HTTPException 501: si el algoritmo aún no está implementado.
    """
    grafo = obtener_grafo()
    origen, destino = solicitud.origen, solicitud.destino

    if origen not in grafo.nodos or destino not in grafo.nodos:
        raise HTTPException(
            status_code=404,
            detail=f"Nodo origen '{origen}' o destino '{destino}' no existe en el grafo",
        )

    algoritmo = _ALGORITMOS.get(solicitud.algoritmo)
    if algoritmo is None:
        raise HTTPException(
            status_code=501,
            detail=f"Algoritmo '{solicitud.algoritmo}' no implementado aún (Corte 2)",
        )

    try:
        return algoritmo.buscar(grafo, origen, destino, solicitud.criterio)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/algoritmos")
async def listar_algoritmos():
    """Lista algoritmos disponibles y su estado de implementación."""
    return {
        "algoritmos": [
            {"id": "voraz", "nombre": "Voraz (Greedy)", "descripcion": "Best-first con heurística euclidiana", "implementado": True},
            {"id": "bfs", "nombre": "BFS", "descripcion": "Búsqueda en amplitud", "implementado": False},
            {"id": "dfs", "nombre": "DFS", "descripcion": "Búsqueda en profundidad", "implementado": False},
            {"id": "ucs", "nombre": "UCS", "descripcion": "Búsqueda de costo uniforme", "implementado": False},
            {"id": "a_estrella", "nombre": "A*", "descripcion": "A estrella con heurística", "implementado": False},
        ],
        "nota": "Implementación incremental en Corte 2",
    }


@router.post("/comparar")
async def comparar_algoritmos(origen: str, destino: str):
    """Compara los algoritmos implementados (placeholder Corte 2)."""
    raise HTTPException(status_code=501, detail="Comparación de algoritmos en Corte 2")
