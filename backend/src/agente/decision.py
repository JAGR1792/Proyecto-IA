"""Módulo de decisión del agente inteligente.

Orquesta el ciclo percepción → decisión → acción. La ruta se planifica con
los algoritmos de búsqueda del paquete ``busqueda`` (A* por defecto) y el
agente ejecuta la acción de avance que corresponda a esa ruta.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from ..busqueda.base import AlgoritmoBusqueda, ResultadoBusqueda
from ..busqueda.registro import crear_algoritmos
from ..grafo.modelos import Arista, Grafo
from .acciones import (
    ContextoAccion,
    TipoAccion,
    construir_accion_avanzar,
    construir_accion_finalizar,
    construir_accion_recalcular,
    obtener_acciones_posibles,
)
from .peas import (
    Accion,
    CriterioOptimizacion,
    MedidaDesempeno,
    ModeloPEAS,
    Percepcion,
    crear_peas_inicial,
)
from .percepcion import PercepcionCompleta


class EstadoDecision(StrEnum):
    """Estado del proceso de decisión del agente."""

    LISTO = "listo"
    EN_CURSO = "en_curso"
    DESTINO_ALCANZADO = "destino_alcanzado"
    SIN_RUTA = "sin_ruta"
    ERROR = "error"


@dataclass
class ResultadoDecision:
    """Resultado de un ciclo de decisión del agente.

    Attributes:
        accion: La acción seleccionada.
        estado: Estado actual del proceso de decisión.
        percepcion: Percepción actual del agente.
        medida: Medida de desempeño actualizada.
        acciones_posibles: Alternativas consideradas (para visualización).
        paso: Número de paso en la secuencia de decisiones.
        mensaje: Mensaje descriptivo para el usuario.
    """

    accion: Accion
    estado: EstadoDecision
    percepcion: Percepcion
    medida: MedidaDesempeno
    acciones_posibles: list[dict[str, Any]] = field(default_factory=list)
    paso: int = 0
    mensaje: str = ""


class MotorDecision:
    """Motor de decisión del agente inteligente.

    Orquesta el ciclo percepción → decisión → acción. La ruta se calcula una
    vez con el algoritmo de búsqueda elegido y se sigue paso a paso; si el
    agente queda fuera de la ruta planificada, se recalcula.

    Attributes:
        modelo: Modelo PEAS completo del agente.
        sensores: Módulo de percepción con todos los sensores.
        contexto: Contexto de la acción actual (historial, pasos).
        algoritmo: ID del algoritmo de búsqueda usado para planificar.
        ruta_planificada: Camino óptimo desde el nodo actual hasta el destino.
    """

    def __init__(
        self,
        modelo: ModeloPEAS,
        sensores: PercepcionCompleta,
        algoritmo: str = "a_estrella",
    ):
        """Inicializa el motor con el modelo PEAS, los sensores y el algoritmo.

        Args:
            modelo: Modelo PEAS ya inicializado (via crear_peas_inicial).
            sensores: Instancia de PercepcionCompleta con el grafo cargado.
            algoritmo: ID del algoritmo de búsqueda (``a_estrella`` por
                defecto, ``ucs`` o ``voraz``).

        Raises:
            ValueError: Si el algoritmo no está registrado.
        """
        self.modelo = modelo
        self.sensores = sensores
        self.contexto = ContextoAccion(
            percepcion=modelo.percepcion,
            ambiente=modelo.ambiente,
        )
        self._paso_actual = 0
        self.algoritmo = algoritmo
        self._buscador: AlgoritmoBusqueda = self._resolver_algoritmo(algoritmo)
        self.ruta_planificada: list[str] = []
        self._resultado_ruta: ResultadoBusqueda | None = None
        self._planificar_ruta()

    @staticmethod
    def _resolver_algoritmo(algoritmo: str) -> AlgoritmoBusqueda:
        """Obtiene la instancia del algoritmo registrado.

        Args:
            algoritmo: ID del algoritmo.

        Returns:
            Instancia del algoritmo de búsqueda.

        Raises:
            ValueError: Si el ID no corresponde a un algoritmo registrado.
        """
        algoritmos = crear_algoritmos()
        if algoritmo not in algoritmos:
            raise ValueError(f"Algoritmo '{algoritmo}' inválido. Válidos: {', '.join(algoritmos)}")
        return algoritmos[algoritmo]

    @classmethod
    def desde_parametros(
        cls,
        grafo: Grafo,
        origen: str,
        destino: str,
        criterio: CriterioOptimizacion = CriterioOptimizacion.MENOR_TIEMPO,
        hora: str = "08:00",
        fecha: datetime | None = None,
        algoritmo: str = "a_estrella",
    ) -> "MotorDecision":
        """Factory: crea el motor desde parámetros básicos.

        Args:
            grafo: Grafo de la red de movilidad.
            origen: ID del nodo de origen.
            destino: ID del nodo de destino.
            criterio: Criterio de optimización.
            hora: Hora de inicio en formato HH:MM.
            fecha: Fecha del viaje (None = ahora).
            algoritmo: ID del algoritmo de búsqueda a usar.

        Returns:
            Instancia de MotorDecision lista para ejecutar.

        Example:
            >>> motor = MotorDecision.desde_parametros(grafo, "N1", "N6")
        """
        modelo = crear_peas_inicial(
            grafo=grafo,
            origen=origen,
            destino=destino,
            criterio=criterio,
            fecha=fecha,
            hora=hora,
        )
        sensores = PercepcionCompleta(grafo)
        return cls(modelo, sensores, algoritmo=algoritmo)

    def _actualizar_percepcion(self) -> Percepcion:
        """Genera y actualiza la percepción completa del agente.

        Returns:
            Percepción actualizada desde los sensores.
        """
        percep = self.modelo.percepcion
        nueva = self.sensores.generar_percepcion(
            origen=percep.nodo_origen,
            destino=percep.nodo_destino,
            criterio=percep.criterio,
            fecha=percep.fecha,
            hora=percep.hora,
            nodo_actual=percep.nodo_actual,
            ruta_construida=list(percep.ruta_construida),
            ambiente=self.modelo.ambiente,
        )
        self.modelo.actualizar_percepcion(nueva)
        self.contexto.percepcion = nueva
        return nueva

    def _planificar_ruta(self) -> ResultadoBusqueda:
        """Calcula la ruta óptima desde el nodo actual con el buscador elegido.

        Returns:
            Resultado de la búsqueda, también almacenado para seguir la ruta.
        """
        percepcion = self.modelo.percepcion
        self._resultado_ruta = self._buscador.buscar(
            self.modelo.ambiente.grafo,
            percepcion.nodo_actual,
            percepcion.nodo_destino,
            percepcion.criterio.value,
        )
        self.ruta_planificada = (
            list(self._resultado_ruta.camino) if self._resultado_ruta.ruta_encontrada else []
        )
        return self._resultado_ruta

    def _siguiente_arista(self) -> Arista | None:
        """Retorna la arista que sigue en la ruta planificada.

        Returns:
            La arista a recorrer, o None si no hay ruta o ya se llegó.
        """
        if not self._resultado_ruta or not self.ruta_planificada:
            return None

        actual = self.modelo.percepcion.nodo_actual
        if actual not in self.ruta_planificada:
            return None

        indice = self.ruta_planificada.index(actual)
        if indice >= len(self._resultado_ruta.aristas_camino):
            return None

        arista_id = self._resultado_ruta.aristas_camino[indice]
        return next(
            (arista for arista in self.modelo.ambiente.grafo.aristas if arista.id == arista_id),
            None,
        )

    def ejecutar_paso(self) -> ResultadoDecision:
        """Ejecuta un ciclo de decisión: percibir → decidir → actuar.

        Si el nodo actual está en la ruta planificada, avanza por la siguiente
        arista; si no, replanifica. Si no existe ruta, devuelve RECALCULAR y
        el estado SIN_RUTA.

        Returns:
            ResultadoDecision con la acción tomada y el estado actualizado.
        """
        self._paso_actual += 1
        percepcion = self._actualizar_percepcion()

        # Determinar acciones posibles (para visualización)
        acciones_pos = obtener_acciones_posibles(
            percepcion.nodo_actual,
            self.modelo.ambiente,
            self.contexto.historial,
        )

        # Planificar si hace falta o si el agente quedó fuera de la ruta
        if not self.ruta_planificada or percepcion.nodo_actual not in self.ruta_planificada:
            self._planificar_ruta()

        # Seleccionar acción según la ruta planificada
        if percepcion.nodo_actual == percepcion.nodo_destino:
            accion = construir_accion_finalizar(percepcion.nodo_actual)
        else:
            arista = self._siguiente_arista()
            if arista is None:
                accion = construir_accion_recalcular(
                    percepcion.nodo_actual,
                    "no hay ruta transitable hacia el destino",
                )
            else:
                accion = construir_accion_avanzar(arista)
                self.contexto.historial.append(percepcion.nodo_actual)

        # Registrar acción en el modelo
        self.modelo.registrar_accion(accion)

        # Avanzar posición si la acción lo requiere
        if accion.tipo == TipoAccion.AVANZAR.value and accion.nodo_destino:
            self.modelo.percepcion.nodo_actual = accion.nodo_destino

        # Evaluar desempeño
        destino_alcanzado = accion.tipo == TipoAccion.FINALIZAR.value
        medida = self.modelo.evaluar_desempeno(destino_alcanzado=destino_alcanzado)

        # Determinar estado del proceso
        if destino_alcanzado:
            estado = EstadoDecision.DESTINO_ALCANZADO
            mensaje = f"Destino '{percepcion.nodo_destino}' alcanzado en {self._paso_actual} pasos."
        elif accion.tipo == TipoAccion.ERROR.value:
            estado = EstadoDecision.ERROR
            mensaje = f"Error: {accion.descripcion}"
        elif accion.tipo == TipoAccion.RECALCULAR.value:
            estado = (
                EstadoDecision.SIN_RUTA if not self.ruta_planificada else EstadoDecision.EN_CURSO
            )
            mensaje = (
                "No se encontró una ruta transitable hacia el destino."
                if estado == EstadoDecision.SIN_RUTA
                else str(accion)
            )
        else:
            estado = EstadoDecision.EN_CURSO
            mensaje = str(accion)

        return ResultadoDecision(
            accion=accion,
            estado=estado,
            percepcion=self.modelo.percepcion,
            medida=medida,
            acciones_posibles=acciones_pos,
            paso=self._paso_actual,
            mensaje=mensaje,
        )

    def ejecutar_completo(self, max_pasos: int = 50) -> list[ResultadoDecision]:
        """Ejecuta todos los pasos hasta llegar al destino o agotar pasos.

        Args:
            max_pasos: Límite de pasos para evitar bucles infinitos.

        Returns:
            Lista de ResultadoDecision con el historial completo.

        Example:
            >>> resultados = motor.ejecutar_completo(max_pasos=20)
            >>> print(resultados[-1].estado)
        """
        historial: list[ResultadoDecision] = []

        for _ in range(max_pasos):
            resultado = self.ejecutar_paso()
            historial.append(resultado)

            if resultado.estado in (
                EstadoDecision.DESTINO_ALCANZADO,
                EstadoDecision.SIN_RUTA,
                EstadoDecision.ERROR,
            ):
                break

        return historial

    def obtener_resumen(self) -> dict[str, Any]:
        """Retorna resumen del estado actual del motor de decisión.

        Returns:
            Diccionario con estado, algoritmo, ruta planificada, historial de
            acciones y métricas de desempeño.
        """
        resultado = self._resultado_ruta
        return {
            "paso_actual": self._paso_actual,
            "nodo_actual": self.modelo.percepcion.nodo_actual,
            "nodo_destino": self.modelo.percepcion.nodo_destino,
            "algoritmo": self.algoritmo,
            "ruta_planificada": list(self.ruta_planificada),
            "ruta_construida": self.modelo.percepcion.ruta_construida,
            "distancia_total": self.modelo.medida.distancia_total,
            "planificacion": {
                "costo": resultado.costo_total if resultado else None,
                "distancia_m": resultado.distancia_total_m if resultado else None,
                "tiempo_min": resultado.tiempo_total_min if resultado else None,
                "nodos_explorados": resultado.nodos_explorados if resultado else None,
                "tiempo_ms": resultado.tiempo_ejecucion_ms if resultado else None,
            },
            "historial_acciones": [str(a) for a in self.modelo.historial_acciones],
            "medida_desempeno": {
                "criterio": self.modelo.medida.criterio.value,
                "costo": self.modelo.medida.calcular_costo(),
                "destino_alcanzado": self.modelo.medida.destino_alcanzado,
                "tiempo_total_min": self.modelo.medida.tiempo_total_min,
                "distancia_total": self.modelo.medida.distancia_total,
                "num_conexiones": self.modelo.medida.num_conexiones,
                "ruta_valida": self.modelo.medida.ruta_valida,
            },
            "objetivo_cumplido": self.modelo.objetivo_cumplido(),
        }
