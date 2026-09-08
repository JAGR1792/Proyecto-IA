"""Módulo de acciones del agente inteligente - Corte 1.

Define el catálogo de acciones posibles y la lógica de selección de
siguiente acción basada en la percepción actual (sin algoritmo de búsqueda).
El motor de búsqueda se implementará en Corte 2.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ..grafo.modelos import Arista, Grafo, NivelCongestion
from .peas import Accion, Ambiente, Percepcion


class TipoAccion(str, Enum):
    """Catálogo de acciones posibles del agente."""

    AVANZAR = "avanzar"
    TRANSBORDAR = "transbordar"
    ESPERAR = "esperar"
    RECALCULAR = "recalcular"
    FINALIZAR = "finalizar"
    ERROR = "error"


@dataclass
class ContextoAccion:
    """Contexto para seleccionar y ejecutar una acción.

    Attributes:
        percepcion: Estado perceptual actual del agente.
        ambiente: Ambiente del agente con el grafo y estado dinámico.
        historial: Nodos ya visitados (para evitar ciclos).
        max_espera: Máximo de pasos en espera antes de recalcular.
        pasos_espera: Contador de pasos esperando.
    """

    percepcion: Percepcion
    ambiente: Ambiente
    historial: List[str] = field(default_factory=list)
    max_espera: int = 3
    pasos_espera: int = 0


def construir_accion_avanzar(arista: Arista) -> Accion:
    """Construye una acción de avance por una arista.

    Args:
        arista: La arista (conexión) por la que avanzar.

    Returns:
        Acción de tipo AVANZAR configurada con los datos de la arista.
    """
    servicio = arista.atributos.nombre_via or "línea desconocida"
    return Accion(
        tipo=TipoAccion.AVANZAR.value,
        estacion_origen=arista.origen,
        estacion_destino=arista.destino,
        servicio=servicio,
        tiempo_estimado=arista.tiempo_estimado,
        es_transbordo=False,
        descripcion=(
            f"Avanzar de '{arista.origen}' a '{arista.destino}' "
            f"por {servicio} (~{arista.tiempo_estimado:.1f} min, "
            f"{arista.distancia:.0f} m)"
        ),
    )


def construir_accion_transbordo(
    estacion: str, servicio_nuevo: str, servicio_actual: Optional[str]
) -> Accion:
    """Construye una acción de transbordo de línea.

    Args:
        estacion: Estación donde se realiza el transbordo.
        servicio_nuevo: Nombre del servicio/línea al que se cambia.
        servicio_actual: Nombre del servicio/línea actual (puede ser None).

    Returns:
        Acción de tipo TRANSBORDAR.
    """
    descripcion = f"Transbordar en '{estacion}' "
    if servicio_actual:
        descripcion += f"de '{servicio_actual}' a '{servicio_nuevo}'"
    else:
        descripcion += f"hacia línea '{servicio_nuevo}'"

    return Accion(
        tipo=TipoAccion.TRANSBORDAR.value,
        estacion_origen=estacion,
        estacion_destino=estacion,
        servicio=servicio_nuevo,
        tiempo_estimado=3.0,  # Tiempo promedio de transbordo en min
        es_transbordo=True,
        descripcion=descripcion,
    )


def construir_accion_esperar(estacion: str, razon: str = "") -> Accion:
    """Construye una acción de espera en la estación actual.

    Args:
        estacion: Estación donde esperar.
        razon: Motivo de la espera (opcional).

    Returns:
        Acción de tipo ESPERAR.
    """
    descripcion = f"Esperar en '{estacion}'"
    if razon:
        descripcion += f": {razon}"
    return Accion(
        tipo=TipoAccion.ESPERAR.value,
        estacion_origen=estacion,
        tiempo_estimado=5.0,  # Espera promedio 5 min
        descripcion=descripcion,
    )


def construir_accion_recalcular(estacion: str, razon: str = "") -> Accion:
    """Construye una acción de recalcular ruta.

    Args:
        estacion: Estación actual desde donde recalcular.
        razon: Motivo por el que se recalcula.

    Returns:
        Acción de tipo RECALCULAR.
    """
    descripcion = f"Recalcular ruta desde '{estacion}'"
    if razon:
        descripcion += f": {razon}"
    return Accion(
        tipo=TipoAccion.RECALCULAR.value,
        estacion_origen=estacion,
        descripcion=descripcion,
    )


def construir_accion_finalizar(estacion: str) -> Accion:
    """Construye una acción de finalización (destino alcanzado).

    Args:
        estacion: Estación final (destino).

    Returns:
        Acción de tipo FINALIZAR.
    """
    return Accion(
        tipo=TipoAccion.FINALIZAR.value,
        estacion_origen=estacion,
        descripcion=f"¡Destino alcanzado! Llegada a '{estacion}'.",
    )


def seleccionar_arista_criterio(
    aristas: List[Arista],
    criterio: str,
    historial: List[str],
) -> Optional[Arista]:
    """Selecciona la mejor arista según el criterio de optimización.

    Filtra aristas que llevan a nodos ya visitados (evita ciclos triviales)
    y ordena según el criterio.

    Args:
        aristas: Lista de aristas disponibles desde la estación actual.
        criterio: Criterio de optimización (menor_tiempo, menor_estaciones, etc.).
        historial: IDs de nodos ya visitados en la ruta actual.

    Returns:
        La arista seleccionada, o None si no hay opciones válidas.

    Example:
        >>> arista = seleccionar_arista_criterio(vecinas, "menor_tiempo", ["A"])
    """
    # Filtrar aristas que no llevan a nodos ya visitados
    candidatas = [a for a in aristas if a.destino not in historial]

    if not candidatas:
        # Si todas llevan a nodos visitados, intentar con todas (último recurso)
        candidatas = aristas

    if not candidatas:
        return None

    # Ordenar según criterio
    if criterio == "menor_tiempo":
        return min(candidatas, key=lambda a: a.tiempo_estimado)
    elif criterio == "menor_estaciones":
        # Cualquier arista suma 1 estación; elegir la más rápida como desempate
        return min(candidatas, key=lambda a: a.tiempo_estimado)
    elif criterio == "menos_transbordos":
        # Preferir continuar en la misma línea
        return min(candidatas, key=lambda a: (0 if a.atributos.nombre_via else 1, a.tiempo_estimado))
    elif criterio == "menor_demanda":
        # Ordenar por nivel de congestión
        orden_congestion = {
            NivelCongestion.BAJA: 0,
            NivelCongestion.MEDIA: 1,
            NivelCongestion.ALTA: 2,
            NivelCongestion.BLOQUEADA: 3,
        }
        return min(candidatas, key=lambda a: (orden_congestion[a.congestion], a.tiempo_estimado))
    else:
        # ruta_equilibrada: fórmula C(r) = 0.5*T + 0.3*Tr + 0.2*D (normalizado)
        def costo_equilibrado(arista: Arista) -> float:
            t_norm = min(arista.tiempo_estimado / 60.0, 1.0)
            congestion_val = {
                NivelCongestion.BAJA: 0.0,
                NivelCongestion.MEDIA: 0.5,
                NivelCongestion.ALTA: 1.0,
                NivelCongestion.BLOQUEADA: 2.0,
            }.get(arista.congestion, 0.0)
            return 0.5 * t_norm + 0.2 * congestion_val

        return min(candidatas, key=costo_equilibrado)


def decidir_accion(contexto: ContextoAccion) -> Accion:
    """Selecciona la acción a ejecutar dada la percepción actual (Corte 1).

    Lógica de decisión simple (greedy local) — sin algoritmo de búsqueda global.
    El algoritmo de búsqueda completo se implementa en Corte 2.

    Orden de prioridad:
        1. FINALIZAR si ya estamos en el destino.
        2. AVANZAR si hay conexiones disponibles sin ciclo.
        3. ESPERAR si hay incidentes temporales (máx `max_espera` pasos).
        4. RECALCULAR si se superó el límite de espera o hay bloqueos.
        5. ERROR si no hay ninguna opción.

    Args:
        contexto: Estado completo del agente (percepción + ambiente + historial).

    Returns:
        La acción seleccionada para ejecutar.
    """
    percep = contexto.percepcion
    amb = contexto.ambiente
    estacion = percep.estacion_actual
    destino = percep.estacion_destino
    criterio = percep.criterio.value

    # 1. ¿Llegamos?
    if estacion == destino:
        return construir_accion_finalizar(estacion)

    # 2. Obtener conexiones disponibles
    vecinas = amb.grafo.obtener_vecinos(estacion)
    disponibles = [
        a for a in vecinas
        if amb.conexion_disponible(a.origen, a.destino)
        and a.congestion != NivelCongestion.BLOQUEADA
    ]

    if not disponibles:
        # Sin conexiones: esperar o recalcular
        if contexto.pasos_espera < contexto.max_espera:
            contexto.pasos_espera += 1
            return construir_accion_esperar(estacion, "sin conexiones disponibles")
        else:
            contexto.pasos_espera = 0
            return construir_accion_recalcular(estacion, "tiempo máximo de espera superado")

    # 3. Seleccionar mejor arista según criterio
    mejor = seleccionar_arista_criterio(disponibles, criterio, contexto.historial)

    if mejor is None:
        return construir_accion_recalcular(estacion, "todas las rutas llevan a ciclos")

    # Registrar en historial
    contexto.historial.append(estacion)
    contexto.pasos_espera = 0

    return construir_accion_avanzar(mejor)


def obtener_acciones_posibles(
    estacion_actual: str,
    ambiente: Ambiente,
    historial: List[str],
) -> List[Dict[str, Any]]:
    """Retorna todas las acciones posibles desde la estación actual.

    Útil para visualización en el frontend y para el algoritmo de búsqueda
    en Corte 2.

    Args:
        estacion_actual: ID de la estación desde donde generar acciones.
        ambiente: Estado actual del ambiente.
        historial: Nodos ya visitados.

    Returns:
        Lista de diccionarios describiendo cada acción posible.

    Example:
        >>> acciones = obtener_acciones_posibles("N1", ambiente, [])
    """
    acciones: List[Dict[str, Any]] = []

    vecinas = ambiente.grafo.obtener_vecinos(estacion_actual)
    for arista in vecinas:
        if not ambiente.conexion_disponible(arista.origen, arista.destino):
            continue

        estado = "disponible"
        if arista.destino in historial:
            estado = "visitado"
        if arista.congestion == NivelCongestion.BLOQUEADA:
            estado = "bloqueado"

        accion = construir_accion_avanzar(arista)
        acciones.append({
            "tipo": accion.tipo,
            "destino": arista.destino,
            "tiempo_estimado": arista.tiempo_estimado,
            "distancia": arista.distancia,
            "congestion": arista.congestion.value,
            "servicio": arista.atributos.nombre_via,
            "estado": estado,
            "descripcion": accion.descripcion,
        })

    return acciones
