"""Módulo de decisión del agente inteligente - Corte 1 (stub/interfaz).

Define la interfaz base del módulo de decisión. La implementación completa
con algoritmos de búsqueda (BFS, DFS, UCS, Voraz, A*) se realiza en Corte 2.

Este módulo actúa como capa de orquestación entre percepción y acción.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ..grafo.modelos import Grafo
from .peas import (
    Accion,
    Ambiente,
    CriterioOptimizacion,
    MedidaDesempeno,
    ModeloPEAS,
    Percepcion,
    crear_peas_inicial,
)
from .acciones import (
    ContextoAccion,
    TipoAccion,
    decidir_accion,
    obtener_acciones_posibles,
)
from .percepcion import PercepcionCompleta
from datetime import datetime


class EstadoDecision(str, Enum):
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
    acciones_posibles: List[Dict[str, Any]] = field(default_factory=list)
    paso: int = 0
    mensaje: str = ""


class MotorDecision:
    """Motor de decisión del agente inteligente (Corte 1).

    Orquesta el ciclo percepción → decisión → acción del agente.
    En Corte 1 usa lógica greedy local. En Corte 2 se reemplaza por
    algoritmos de búsqueda informados/no informados.

    Attributes:
        modelo: Modelo PEAS completo del agente.
        sensores: Módulo de percepción con todos los sensores.
        contexto: Contexto de la acción actual (historial, pasos).
        _paso_actual: Contador de pasos ejecutados.
    """

    def __init__(self, modelo: ModeloPEAS, sensores: PercepcionCompleta):
        """Inicializa el motor con el modelo PEAS y los sensores.

        Args:
            modelo: Modelo PEAS ya inicializado (via crear_peas_inicial).
            sensores: Instancia de PercepcionCompleta con el grafo cargado.
        """
        self.modelo = modelo
        self.sensores = sensores
        self.contexto = ContextoAccion(
            percepcion=modelo.percepcion,
            ambiente=modelo.ambiente,
        )
        self._paso_actual = 0

    @classmethod
    def desde_parametros(
        cls,
        grafo: Grafo,
        origen: str,
        destino: str,
        criterio: CriterioOptimizacion = CriterioOptimizacion.RUTA_EQUILIBRADA,
        hora: str = "08:00",
        fecha: Optional[datetime] = None,
    ) -> "MotorDecision":
        """Factory: crea el motor desde parámetros básicos.

        Args:
            grafo: Grafo de la red de movilidad.
            origen: ID de la estación de origen.
            destino: ID de la estación de destino.
            criterio: Criterio de optimización.
            hora: Hora de inicio en formato HH:MM.
            fecha: Fecha del viaje (None = ahora).

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
        return cls(modelo, sensores)

    def _actualizar_percepcion(self) -> Percepcion:
        """Genera y actualiza la percepción completa del agente.

        Returns:
            Percepción actualizada desde los sensores.
        """
        percep = self.modelo.percepcion
        nueva = self.sensores.generar_percepcion(
            origen=percep.estacion_origen,
            destino=percep.estacion_destino,
            criterio=percep.criterio,
            fecha=percep.fecha,
            hora=percep.hora,
            estacion_actual=percep.estacion_actual,
            servicio_actual=percep.servicio_actual,
            ruta_construida=list(percep.ruta_construida),
            transbordos_realizados=percep.transbordos_realizados,
            ambiente=self.modelo.ambiente,
        )
        self.modelo.actualizar_percepcion(nueva)
        self.contexto.percepcion = nueva
        return nueva

    def ejecutar_paso(self) -> ResultadoDecision:
        """Ejecuta un ciclo de decisión: percibir → decidir → actuar.

        Implementa el bucle básico del agente racional (Corte 1).
        En Corte 2 este método invocará el algoritmo de búsqueda seleccionado.

        Returns:
            ResultadoDecision con la acción tomada y el estado actualizado.
        """
        self._paso_actual += 1
        percepcion = self._actualizar_percepcion()

        # Determinar acciones posibles (para visualización)
        acciones_pos = obtener_acciones_posibles(
            percepcion.estacion_actual,
            self.modelo.ambiente,
            self.contexto.historial,
        )

        # Seleccionar acción
        accion = decidir_accion(self.contexto)

        # Registrar acción en el modelo
        self.modelo.registrar_accion(accion)

        # Avanzar posición si la acción lo requiere
        if accion.tipo == TipoAccion.AVANZAR.value and accion.estacion_destino:
            self.modelo.percepcion.estacion_actual = accion.estacion_destino
            if accion.servicio:
                self.modelo.percepcion.servicio_actual = accion.servicio

        # Evaluar desempeño
        destino_alcanzado = accion.tipo == TipoAccion.FINALIZAR.value
        medida = self.modelo.evaluar_desempeno(destino_alcanzado=destino_alcanzado)

        # Determinar estado del proceso
        if destino_alcanzado:
            estado = EstadoDecision.DESTINO_ALCANZADO
            mensaje = f"✅ Destino '{percepcion.estacion_destino}' alcanzado en {self._paso_actual} pasos."
        elif accion.tipo == TipoAccion.ERROR.value:
            estado = EstadoDecision.ERROR
            mensaje = f"❌ Error: {accion.descripcion}"
        elif accion.tipo == TipoAccion.RECALCULAR.value and not acciones_pos:
            estado = EstadoDecision.SIN_RUTA
            mensaje = "⚠️ No se encontró ruta disponible."
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

    def ejecutar_completo(self, max_pasos: int = 50) -> List[ResultadoDecision]:
        """Ejecuta todos los pasos hasta llegar al destino o agotar pasos.

        Args:
            max_pasos: Límite de pasos para evitar bucles infinitos.

        Returns:
            Lista de ResultadoDecision con el historial completo.

        Example:
            >>> resultados = motor.ejecutar_completo(max_pasos=20)
            >>> print(resultados[-1].estado)
        """
        historial: List[ResultadoDecision] = []

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

    def obtener_resumen(self) -> Dict[str, Any]:
        """Retorna resumen del estado actual del motor de decisión.

        Returns:
            Diccionario con estado, historial de acciones y métricas.
        """
        return {
            "paso_actual": self._paso_actual,
            "estacion_actual": self.modelo.percepcion.estacion_actual,
            "estacion_destino": self.modelo.percepcion.estacion_destino,
            "ruta_construida": self.modelo.percepcion.ruta_construida,
            "transbordos": self.modelo.percepcion.transbordos_realizados,
            "historial_acciones": [str(a) for a in self.modelo.historial_acciones],
            "medida_desempeno": {
                "criterio": self.modelo.medida.criterio.value,
                "costo": self.modelo.medida.calcular_costo(),
                "destino_alcanzado": self.modelo.medida.destino_alcanzado,
                "tiempo_total_min": self.modelo.medida.tiempo_total_min,
                "num_estaciones": self.modelo.medida.num_estaciones,
                "num_transbordos": self.modelo.medida.num_transbordos,
            },
            "objetivo_cumplido": self.modelo.objetivo_cumplido(),
        }
