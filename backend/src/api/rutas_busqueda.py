"""Endpoints para algoritmos de búsqueda (Corte 2 - stubs)."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

router = APIRouter()


class AlgoritmoBusqueda(str, Enum):
    BFS = "bfs"
    DFS = "dfs"
    UCS = "ucs"
    VORAZ = "voraz"
    A_ESTRELLA = "a_estrella"


class SolicitudBusqueda(BaseModel):
    origen: str
    destino: str
    algoritmo: AlgoritmoBusqueda = AlgoritmoBusqueda.A_ESTRELLA
    criterio: str = "tiempo"  # tiempo, distancia, costo


class ResultadoBusqueda(BaseModel):
    algoritmo: str
    ruta_encontrada: bool
    camino: List[str]
    costo_total: float
    tiempo_ejecucion_ms: float
    nodos_explorados: int
    detalle: dict


@router.post("/buscar", response_model=ResultadoBusqueda)
async def buscar_ruta(solicitud: SolicitudBusqueda):
    """Ejecuta algoritmo de búsqueda (placeholder Corte 2)."""
    # TODO Corte 2: Implementar BFS, DFS, UCS, Voraz, A*
    raise HTTPException(
        status_code=501,
        detail=f"Algoritmo {solicitud.algoritmo.value} no implementado aún (Corte 2)"
    )


@router.get("/algoritmos")
async def listar_algoritmos():
    """Lista algoritmos disponibles."""
    return {
        "algoritmos": [
            {"id": "bfs", "nombre": "BFS", "descripcion": "Búsqueda en amplitud"},
            {"id": "dfs", "nombre": "DFS", "descripcion": "Búsqueda en profundidad"},
            {"id": "ucs", "nombre": "UCS", "descripcion": "Búsqueda de costo uniforme"},
            {"id": "voraz", "nombre": "Voraz", "descripcion": "Búsqueda voraz (greedy)"},
            {"id": "a_estrella", "nombre": "A*", "descripcion": "A estrella con heurística"},
        ],
        "nota": "Implementación en Corte 2"
    }


@router.post("/comparar")
async def comparar_algoritmos(origen: str, destino: str):
    """Compara todos los algoritmos (placeholder Corte 2)."""
    raise HTTPException(status_code=501, detail="Comparación en Corte 2")