"""Endpoints para el agente inteligente (Corte 1)."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.agente.acciones import obtener_acciones_posibles
from src.agente.decision import EstadoDecision, MotorDecision
from src.agente.peas import (
    CriterioOptimizacion,
)
from src.grafo.repositorio import RepositorioGrafo

router = APIRouter()

# Estado del motor en memoria (en producción usar sesión/BD)
_motor_actual: MotorDecision | None = None


class SolicitudIniciar(BaseModel):
    """Entrada para inicializar el agente."""
    origen: str
    destino: str
    criterio: str = "menor_tiempo"
    fecha: str | None = None
    hora: str = "08:00"


class RespuestaPaso(BaseModel):
    """Salida de un paso del agente."""
    accion: str
    descripcion: str
    estado: str
    paso: int
    mensaje: str
    estado_actual: dict[str, Any]
    medida_desempeno: dict[str, Any]
    acciones_posibles: list[dict[str, Any]]
    objetivo_cumplido: bool


class RespuestaResumen(BaseModel):
    """Resumen completo del estado del agente."""
    paso_actual: int
    nodo_actual: str
    nodo_destino: str
    ruta_construida: list[str]
    distancia_total: float
    historial_acciones: list[str]
    medida_desempeno: dict[str, Any]
    objetivo_cumplido: bool


def _cargar_grafo():
    """Carga el grafo del dataset inicial."""
    repo = RepositorioGrafo("datos")
    return repo.cargar_json("dataset_inicial_pdf.json")


@router.post("/iniciar", response_model=RespuestaPaso)
async def iniciar_agente(solicitud: SolicitudIniciar):
    """Inicializa el agente con origen, destino y criterio.

    Crea el modelo PEAS, configura los sensores y genera la percepción inicial.
    """
    global _motor_actual

    try:
        grafo = _cargar_grafo()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cargando grafo: {str(e)}")

    if solicitud.origen not in grafo.nodos:
        raise HTTPException(status_code=404, detail=f"Nodo origen '{solicitud.origen}' no existe")
    if solicitud.destino not in grafo.nodos:
        raise HTTPException(status_code=404, detail=f"Nodo destino '{solicitud.destino}' no existe")
    if solicitud.origen == solicitud.destino:
        raise HTTPException(status_code=422, detail="Origen y destino deben ser diferentes")

    try:
        criterio = CriterioOptimizacion(solicitud.criterio)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Criterio '{solicitud.criterio}' inválido. "
                   f"Válidos: {[c.value for c in CriterioOptimizacion]}"
        )

    fecha = datetime.fromisoformat(solicitud.fecha) if solicitud.fecha else datetime.now()

    _motor_actual = MotorDecision.desde_parametros(
        grafo=grafo,
        origen=solicitud.origen,
        destino=solicitud.destino,
        criterio=criterio,
        hora=solicitud.hora,
        fecha=fecha,
    )

    percepcion = _motor_actual.modelo.percepcion
    acciones_pos = obtener_acciones_posibles(
        solicitud.origen,
        _motor_actual.modelo.ambiente,
        [],
    )

    return RespuestaPaso(
        accion="iniciar",
        descripcion=f"Agente iniciado en '{solicitud.origen}' → '{solicitud.destino}'",
        estado=EstadoDecision.LISTO.value,
        paso=0,
        mensaje=f"Listo para planificar ruta con criterio '{criterio.value}'",
        estado_actual=percepcion.obtener_estado_actual(),
        medida_desempeno={},
        acciones_posibles=acciones_pos,
        objetivo_cumplido=False,
    )


@router.post("/paso", response_model=RespuestaPaso)
async def ejecutar_paso():
    """Ejecuta un paso del agente: percibir → decidir → actuar.

    Implementa el ciclo básico del agente racional (Corte 1).
    En Corte 2 se conectará con los algoritmos de búsqueda.
    """
    global _motor_actual

    if _motor_actual is None:
        raise HTTPException(status_code=400, detail="Agente no iniciado. Llame a POST /iniciar primero.")

    resultado = _motor_actual.ejecutar_paso()

    return RespuestaPaso(
        accion=resultado.accion.tipo,
        descripcion=resultado.accion.descripcion,
        estado=resultado.estado.value,
        paso=resultado.paso,
        mensaje=resultado.mensaje,
        estado_actual=resultado.percepcion.obtener_estado_actual(),
        medida_desempeno={
            "criterio": resultado.medida.criterio.value,
            "costo": resultado.medida.calcular_costo(),
            "destino_alcanzado": resultado.medida.destino_alcanzado,
            "distancia_total": resultado.medida.distancia_total,
            "tiempo_total_min": resultado.medida.tiempo_total_min,
            "num_conexiones": resultado.medida.num_conexiones,
            "ruta_valida": resultado.medida.ruta_valida,
        },
        acciones_posibles=resultado.acciones_posibles,
        objetivo_cumplido=resultado.estado == EstadoDecision.DESTINO_ALCANZADO,
    )


@router.post("/ejecutar-completo", response_model=list[RespuestaPaso])
async def ejecutar_completo(max_pasos: int = 30):
    """Ejecuta todos los pasos del agente hasta llegar al destino o agotar pasos.

    Args:
        max_pasos: Límite máximo de pasos (default 30, máx 100).
    """
    global _motor_actual

    if _motor_actual is None:
        raise HTTPException(status_code=400, detail="Agente no iniciado. Llame a POST /iniciar primero.")

    if max_pasos > 100:
        raise HTTPException(status_code=422, detail="max_pasos no puede superar 100")

    resultados = _motor_actual.ejecutar_completo(max_pasos=max_pasos)

    return [
        RespuestaPaso(
            accion=r.accion.tipo,
            descripcion=r.accion.descripcion,
            estado=r.estado.value,
            paso=r.paso,
            mensaje=r.mensaje,
            estado_actual=r.percepcion.obtener_estado_actual(),
            medida_desempeno={
                "criterio": r.medida.criterio.value,
                "costo": r.medida.calcular_costo(),
                "destino_alcanzado": r.medida.destino_alcanzado,
                "distancia_total": r.medida.distancia_total,
                "tiempo_total_min": r.medida.tiempo_total_min,
                "num_conexiones": r.medida.num_conexiones,
                "ruta_valida": r.medida.ruta_valida,
            },
            acciones_posibles=r.acciones_posibles,
            objetivo_cumplido=r.estado == EstadoDecision.DESTINO_ALCANZADO,
        )
        for r in resultados
    ]


@router.get("/estado", response_model=RespuestaResumen)
async def estado_agente():
    """Obtiene el estado completo actual del agente."""
    global _motor_actual
    if _motor_actual is None:
        raise HTTPException(status_code=404, detail="Agente no iniciado")

    resumen = _motor_actual.obtener_resumen()
    return RespuestaResumen(**resumen)


@router.post("/reiniciar")
async def reiniciar_agente():
    """Reinicia el agente (borra estado actual)."""
    global _motor_actual
    _motor_actual = None
    return {"mensaje": "Agente reiniciado correctamente"}


@router.get("/acciones-posibles/{nodo_id}")
async def acciones_posibles(nodo_id: str):
    """Retorna las acciones posibles desde un nodo (sin agente activo).

    Útil para exploración del grafo desde el frontend.
    """
    try:
        grafo = _cargar_grafo()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if nodo_id not in grafo.nodos:
        raise HTTPException(status_code=404, detail=f"Nodo '{nodo_id}' no existe")

    from datetime import datetime

    from src.agente.peas import Ambiente
    ambiente = Ambiente(grafo=grafo, fecha=datetime.now(), hora="08:00")
    acciones = obtener_acciones_posibles(nodo_id, ambiente, [])

    return {
        "nodo": nodo_id,
        "nombre": grafo.nodos[nodo_id].nombre,
        "acciones_posibles": acciones,
        "total": len(acciones),
    }
