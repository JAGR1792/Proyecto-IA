"""Módulo de acciones del agente inteligente - Corte 1.

Define el catálogo de acciones posibles y la lógica de selección de
siguiente acción basada en la percepción actual (sin algoritmo de búsqueda).
El motor de búsqueda se implementará en Corte 2.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..grafo.modelos import Arista, NivelCongestion
from .peas import Accion, Ambiente, Percepcion


class TipoAccion(str, Enum):
    """Catálogo de acciones posibles del agente (PDF 5.1)."""

    AVANZAR = "avanzar"
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
    historial: list[str] = field(default_factory=list)
    max_espera: int = 3
    pasos_espera: int = 0


def construir_accion_avanzar(arista: Arista) -> Accion:
    """Construye una acción de avance por una arista.

    Args:
        arista: La arista (conexión vial) por la que avanzar.

    Returns:
        Acción de tipo AVANZAR configurada con los datos de la arista.
    """
    via = arista.atributos.nombre_via or "vía desconocida"
    return Accion(
        tipo=TipoAccion.AVANZAR.value,
        nodo_origen=arista.origen,
        nodo_destino=arista.destino,
        tiempo_estimado=arista.tiempo_estimado,
        distancia=arista.distancia,
        descripcion=(
            f"Avanzar de '{arista.origen}' a '{arista.destino}' "
            f"por {via} (~{arista.tiempo_estimado:.1f} min, "
            f"{arista.distancia:.0f} m)"
        ),
    )


def construir_accion_esperar(nodo: str, razon: str = "") -> Accion:
    """Construye una acción de espera en el nodo actual.

    Args:
        nodo: Nodo donde esperar.
        razon: Motivo de la espera (opcional).

    Returns:
        Acción de tipo ESPERAR.
    """
    descripcion = f"Esperar en '{nodo}'"
    if razon:
        descripcion += f": {razon}"
    return Accion(
        tipo=TipoAccion.ESPERAR.value,
        nodo_origen=nodo,
        tiempo_estimado=5.0,  # Espera promedio 5 min
        descripcion=descripcion,
    )


def construir_accion_recalcular(nodo: str, razon: str = "") -> Accion:
    """Construye una acción de recalcular ruta.

    Args:
        nodo: Nodo actual desde donde recalcular.
        razon: Motivo por el que se recalcula.

    Returns:
        Acción de tipo RECALCULAR.
    """
    descripcion = f"Recalcular ruta desde '{nodo}'"
    if razon:
        descripcion += f": {razon}"
    return Accion(
        tipo=TipoAccion.RECALCULAR.value,
        nodo_origen=nodo,
        descripcion=descripcion,
    )


def construir_accion_finalizar(nodo: str) -> Accion:
    """Construye una acción de finalización (destino alcanzado).

    Args:
        nodo: Nodo final (destino).

    Returns:
        Acción de tipo FINALIZAR.
    """
    return Accion(
        tipo=TipoAccion.FINALIZAR.value,
        nodo_origen=nodo,
        descripcion=f"Destino alcanzado. Llegada a '{nodo}'.",
    )


def seleccionar_arista_criterio(
    aristas: list[Arista],
    criterio: str,
    historial: list[str],
) -> Arista | None:
    """Selecciona la mejor arista según el criterio de optimización.

    Filtra aristas que llevan a nodos ya visitados (evita ciclos triviales)
    y ordena según el criterio.

    Args:
        aristas: Lista de aristas disponibles desde el nodo actual.
        criterio: Criterio de optimización (menor_distancia, menor_tiempo,
            menor_conexiones).
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

    # Ordenar según criterio (PDF 5.2)
    if criterio == "menor_distancia":
        return min(candidatas, key=lambda a: a.distancia)
    elif criterio == "menor_tiempo":
        return min(candidatas, key=lambda a: a.tiempo_estimado)
    else:
        # menor_conexiones: cualquier arista suma una conexión; usar la más
        # rápida como desempate
        return min(candidatas, key=lambda a: a.tiempo_estimado)


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
    nodo = percep.nodo_actual
    destino = percep.nodo_destino
    criterio = percep.criterio.value

    # 1. ¿Llegamos?
    if nodo == destino:
        return construir_accion_finalizar(nodo)

    # 2. Obtener conexiones disponibles
    vecinas = amb.grafo.obtener_vecinos(nodo)
    disponibles = [
        a for a in vecinas
        if amb.conexion_disponible(a.origen, a.destino)
        and a.congestion != NivelCongestion.BLOQUEADA
    ]

    if not disponibles:
        # Sin conexiones: esperar o recalcular
        if contexto.pasos_espera < contexto.max_espera:
            contexto.pasos_espera += 1
            return construir_accion_esperar(nodo, "sin conexiones disponibles")
        else:
            contexto.pasos_espera = 0
            return construir_accion_recalcular(nodo, "tiempo máximo de espera superado")

    # 3. Seleccionar mejor arista según criterio
    mejor = seleccionar_arista_criterio(disponibles, criterio, contexto.historial)

    if mejor is None:
        return construir_accion_recalcular(nodo, "todas las rutas llevan a ciclos")

    # Registrar en historial
    contexto.historial.append(nodo)
    contexto.pasos_espera = 0

    return construir_accion_avanzar(mejor)


def obtener_acciones_posibles(
    nodo_actual: str,
    ambiente: Ambiente,
    historial: list[str],
) -> list[dict[str, Any]]:
    """Retorna todas las acciones posibles desde el nodo actual.

    Útil para visualización en el frontend y para el algoritmo de búsqueda
    en Corte 2.

    Args:
        nodo_actual: ID del nodo desde donde generar acciones.
        ambiente: Estado actual del ambiente.
        historial: Nodos ya visitados.

    Returns:
        Lista de diccionarios describiendo cada acción posible.

    Example:
        >>> acciones = obtener_acciones_posibles("N1", ambiente, [])
    """
    acciones: list[dict[str, Any]] = []

    vecinas = ambiente.grafo.obtener_vecinos(nodo_actual)
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
            "via": arista.atributos.nombre_via,
            "estado": estado,
            "descripcion": accion.descripcion,
        })

    return acciones
