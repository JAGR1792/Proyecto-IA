"""Endpoints de búsqueda de rutas sobre el grafo de movilidad."""

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.api.rutas_grafo import obtener_grafo
from src.busqueda.base import ResultadoBusqueda
from src.busqueda.comparador import (
    ComparacionAlgoritmos,
)
from src.busqueda.comparador import (
    comparar_algoritmos as comparar_todos,
)
from src.busqueda.registro import crear_algoritmos
from src.congestion.horarios import grafo_en_hora
from src.tarifas.taximetro import ModoRedondeo, calcular_tarifa_taximetro

router = APIRouter()

# Identificadores de algoritmos disponibles en la API
_ID_ALGORITMO = Literal["bfs", "dfs", "ucs", "voraz", "a_estrella"]

# Registro central: BFS y DFS se habilitan al añadirlos en registro.py
_ALGORITMOS = crear_algoritmos()

_INFO_ALGORITMOS = [
    {
        "id": "voraz",
        "nombre": "Voraz (Greedy)",
        "descripcion": "Best-first con heurística euclidiana (no óptimo)",
    },
    {
        "id": "ucs",
        "nombre": "UCS",
        "descripcion": "Búsqueda de costo uniforme (óptima, sin heurística)",
    },
    {
        "id": "a_estrella",
        "nombre": "A*",
        "descripcion": "A estrella con heurística geográfica admisible (óptima)",
    },
    {
        "id": "bfs",
        "nombre": "BFS",
        "descripcion": "Búsqueda en amplitud",
    },
    {
        "id": "dfs",
        "nombre": "DFS",
        "descripcion": "Búsqueda en profundidad",
    },
]


class OpcionesTarifa(BaseModel):
    """Opciones de liquidación de la tarifa de taxi.

    Attributes:
        espera_s: Tiempo detenido (semáforos, recogidas) en segundos.
        nocturno: Aplica el recargo nocturno (20:00 a 5:00).
        domingo_o_festivo: Aplica el recargo dominical o festivo.
        aeropuerto: Aplica el recargo de aeropuerto o Puente Aéreo.
        puerta_a_puerta: Aplica el recargo de servicio puerta a puerta.
        factor_excelencia: Usa la unidad de $172 y recargos de excelencia.
        zona_amarilla: Aplica el recargo ZEO; requiere factor de excelencia.
        redondeo: ``"ceil"`` (por defecto) u ``"oficial"``.
    """

    espera_s: float = Field(0.0, ge=0, description="Tiempo detenido en segundos")
    nocturno: bool = False
    domingo_o_festivo: bool = False
    aeropuerto: bool = False
    puerta_a_puerta: bool = False
    factor_excelencia: bool = False
    zona_amarilla: bool = False
    redondeo: ModoRedondeo = "ceil"


class SolicitudBusqueda(BaseModel):
    """Parámetros para ejecutar una búsqueda de ruta."""

    origen: str
    destino: str
    algoritmo: _ID_ALGORITMO = "voraz"
    criterio: str = "menor_tiempo"
    hora_salida: str | None = Field(
        None,
        pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$",
        description="HH:MM (00:00 a 23:59), tráfico sintético de día hábil típico",
    )
    tarifa: OpcionesTarifa = Field(default_factory=OpcionesTarifa)


class SolicitudComparacion(BaseModel):
    """Parámetros para comparar todos los algoritmos implementados."""

    origen: str
    destino: str
    criterio: str = "menor_tiempo"
    hora_salida: str | None = Field(
        None,
        pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$",
        description="HH:MM (00:00 a 23:59), tráfico sintético de día hábil típico",
    )
    tarifa: OpcionesTarifa = Field(default_factory=OpcionesTarifa)


def _aplicar_tarifa(
    resultado: ResultadoBusqueda,
    opciones: OpcionesTarifa,
) -> ResultadoBusqueda:
    """Liquida la tarifa de taxi y la adjunta al resultado de búsqueda.

    Args:
        resultado: Resultado de la búsqueda con distancia y estado de ruta.
        opciones: Parámetros de liquidación elegidos por el cliente.

    Returns:
        Copia del resultado con ``tarifa_taxi`` diligenciada. Si no se
        encontró ruta, se devuelve el resultado sin cambios.

    Raises:
        ValueError: Si las opciones de tarifa son inconsistentes (por ejemplo,
            zona amarilla sin factor de excelencia).
    """
    if not resultado.ruta_encontrada:
        return resultado

    tarifa = calcular_tarifa_taximetro(
        distancia_m=resultado.distancia_total_m,
        espera_s=opciones.espera_s,
        nocturno=opciones.nocturno,
        domingo_o_festivo=opciones.domingo_o_festivo,
        aeropuerto=opciones.aeropuerto,
        puerta_a_puerta=opciones.puerta_a_puerta,
        factor_excelencia=opciones.factor_excelencia,
        zona_amarilla=opciones.zona_amarilla,
        redondeo=opciones.redondeo,
    )
    return resultado.model_copy(update={"tarifa_taxi": tarifa})


def _validar_nodos(origen: str, destino: str) -> None:
    """Valida que origen y destino existan en el grafo activo.

    Args:
        origen: ID del nodo de origen.
        destino: ID del nodo de destino.

    Raises:
        HTTPException 404: Si alguno de los nodos no existe.
    """
    grafo = obtener_grafo()
    if origen not in grafo.nodos or destino not in grafo.nodos:
        raise HTTPException(
            status_code=404,
            detail=f"Nodo origen '{origen}' o destino '{destino}' no existe en el grafo",
        )


@router.post("/buscar", response_model=ResultadoBusqueda)
async def buscar_ruta(solicitud: SolicitudBusqueda):
    """Busca la mejor ruta entre dos nodos según el algoritmo indicado.

    Args:
        solicitud: Origen, destino, algoritmo, criterio y opciones de tarifa.

    Returns:
        Ruta encontrada con sus métricas (camino, costo, tiempo, distancia) y
        la tarifa de taxi liquidada.

    Raises:
        HTTPException 404: si origen o destino no existen en el grafo.
        HTTPException 422: si el criterio o las opciones de tarifa no son
            válidos.
        HTTPException 501: si el algoritmo aún no está implementado.
    """
    grafo = grafo_en_hora(obtener_grafo(), solicitud.hora_salida)
    origen, destino = solicitud.origen, solicitud.destino
    _validar_nodos(origen, destino)

    algoritmo = _ALGORITMOS.get(solicitud.algoritmo)
    if algoritmo is None:
        raise HTTPException(
            status_code=501,
            detail=f"Algoritmo '{solicitud.algoritmo}' no implementado aún (Corte 2)",
        )

    try:
        resultado = algoritmo.buscar(grafo, origen, destino, solicitud.criterio)
        if solicitud.hora_salida is not None:
            resultado.detalle["hora_salida"] = solicitud.hora_salida
            resultado.detalle["fuente_trafico"] = "sintetico"
        return _aplicar_tarifa(resultado, solicitud.tarifa)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/comparar", response_model=ComparacionAlgoritmos)
async def comparar_ruta(solicitud: SolicitudComparacion):
    """Ejecuta todos los algoritmos implementados sobre la misma ruta.

    Sirve de base para la tabla comparativa del Corte 2: cada algoritmo
    reporta costo, distancia, tiempo, aristas, nodos explorados y milisegundos.

    Args:
        solicitud: Origen, destino, criterio y opciones de tarifa compartidos.

    Returns:
        Comparación con un resultado por algoritmo, la tarifa de taxi de cada
        uno y el mejor global.

    Raises:
        HTTPException 404: si origen o destino no existen.
        HTTPException 422: si el criterio o las opciones de tarifa no son
            válidos.
    """
    grafo = grafo_en_hora(obtener_grafo(), solicitud.hora_salida)
    origen, destino = solicitud.origen, solicitud.destino
    _validar_nodos(origen, destino)

    try:
        comparacion = comparar_todos(
            grafo,
            origen,
            destino,
            solicitud.criterio,
            _ALGORITMOS,
        )
        if solicitud.hora_salida is not None:
            for resultado in comparacion.resultados:
                resultado.detalle["hora_salida"] = solicitud.hora_salida
                resultado.detalle["fuente_trafico"] = "sintetico"
        resultados = [
            _aplicar_tarifa(resultado, solicitud.tarifa) for resultado in comparacion.resultados
        ]
        return comparacion.model_copy(update={"resultados": resultados})
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/algoritmos")
async def listar_algoritmos():
    """Lista algoritmos disponibles y su estado de implementación."""
    return {
        "algoritmos": [
            {**info, "implementado": info["id"] in _ALGORITMOS} for info in _INFO_ALGORITMOS
        ],
        "nota": "BFS y DFS quedan a cargo del equipo; el comparador los incluye al registrarlos",
    }
