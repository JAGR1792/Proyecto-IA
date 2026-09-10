"""Modelo PEAS del agente inteligente para planificación de rutas de taxis (Chapinero).

Basado en la Primera Entrega del proyecto (PDF de taxis) - Corte 1.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from ..grafo.modelos import Grafo, NivelCongestion, Nodo


class CriterioOptimizacion(str, Enum):
    """Criterios de optimización que el usuario puede seleccionar (PDF 5.2)."""

    MENOR_DISTANCIA = "menor_distancia"
    MENOR_TIEMPO = "menor_tiempo"
    MENOR_CONEXIONES = "menor_conexiones"


@dataclass
class MedidaDesempeno:
    """Medida de desempeño del agente (componente P del PEAS).

    Evalúa qué tan bien el agente cumple su objetivo según el criterio
    seleccionado: menor distancia, menor tiempo estimado o menor cantidad
    de conexiones (PDF 5.2).
    """

    criterio: CriterioOptimizacion
    destino_alcanzado: bool = False
    distancia_total: float = 0.0
    tiempo_total_min: float = 0.0
    num_conexiones: int = 0
    ruta_valida: bool = False
    costo_total: float = 0.0

    def calcular_costo(self) -> float:
        """Calcula función de costo según criterio (PDF 5.2)."""
        if self.criterio == CriterioOptimizacion.MENOR_DISTANCIA:
            self.costo_total = self.distancia_total
        elif self.criterio == CriterioOptimizacion.MENOR_TIEMPO:
            self.costo_total = self.tiempo_total_min
        elif self.criterio == CriterioOptimizacion.MENOR_CONEXIONES:
            self.costo_total = float(self.num_conexiones)

        return self.costo_total

    def es_mejor_que(self, otra: "MedidaDesempeno") -> bool:
        """Compara si esta medida es mejor que otra (menor costo = mejor)."""
        return self.calcular_costo() < otra.calcular_costo()


@dataclass
class Ambiente:
    """Ambiente del agente (componente E del PEAS).

    Representa la red vial dirigida de la zona de estudio (Chapinero):
    intersecciones, calles, sentidos, velocidades, congestión, incidentes,
    fecha y hora (PDF 5.1).
    """

    grafo: Grafo
    fecha: datetime
    hora: str  # Formato HH:MM

    # Estados dinámicos
    conexiones_bloqueadas: set[str] = field(default_factory=set)
    incidentes_activos: list[dict[str, Any]] = field(default_factory=list)

    def obtener_nodos_disponibles(self) -> list[Nodo]:
        """Retorna los nodos (intersecciones) disponibles de la red."""
        return [n for n in self.grafo.nodos.values() if n.atributos.accesible]

    def conexion_disponible(self, origen: str, destino: str) -> bool:
        """Verifica si una conexión (segmento vial) está disponible."""
        arista = self.grafo.obtener_arista(origen, destino)
        if not arista or not arista.disponible:
            return False
        if arista.id in self.conexiones_bloqueadas:
            return False
        return True

    def obtener_congestion(self, arista_id: str) -> NivelCongestion:
        """Obtiene nivel de congestión actual de una conexión."""
        arista = next((a for a in self.grafo.aristas if a.id == arista_id), None)
        return arista.congestion if arista else NivelCongestion.BAJA


@dataclass
class Percepcion:
    """Lo que el agente percibe del ambiente (componente S del PEAS).

    Sensores: ubicación actual, origen, destino, hora, conexiones disponibles,
    distancia, tiempo, congestión e incidentes (PDF 5.1).
    """

    # Entrada del usuario
    nodo_origen: str
    nodo_destino: str
    fecha: datetime
    hora: str
    criterio: CriterioOptimizacion

    # Estado actual del agente
    nodo_actual: str
    ruta_construida: list[str] = field(default_factory=list)

    # Información del ambiente (desde sensores/datos)
    conexiones_disponibles: list[str] = field(default_factory=list)
    congestion_conexiones: dict[str, NivelCongestion] = field(default_factory=dict)
    incidentes_cercanos: list[dict[str, Any]] = field(default_factory=list)

    def obtener_estado_actual(self) -> dict[str, Any]:
        """Retorna estado completo para toma de decisiones."""
        return {
            "origen": self.nodo_origen,
            "destino": self.nodo_destino,
            "actual": self.nodo_actual,
            "ruta": self.ruta_construida,
            "criterio": self.criterio.value,
            "conexiones": self.conexiones_disponibles,
            "congestion": {k: v.value for k, v in self.congestion_conexiones.items()},
            "incidentes": self.incidentes_cercanos,
        }


@dataclass
class Accion:
    """Acción que el agente puede ejecutar (componente A del PEAS).

    Catálogo del PDF: avanzar al siguiente nodo, esperar, recalcular y
    finalizar el recorrido.
    """

    tipo: str  # "avanzar", "esperar", "recalcular", "finalizar"
    nodo_origen: str
    nodo_destino: str | None = None
    tiempo_estimado: float = 0.0
    distancia: float = 0.0
    descripcion: str = ""

    def __str__(self) -> str:
        if self.tipo == "avanzar":
            return (
                f"Avanzar a {self.nodo_destino} "
                f"(~{self.tiempo_estimado:.0f} min, {self.distancia:.0f} m)"
            )
        elif self.tipo == "finalizar":
            return f"Llegada a destino: {self.nodo_origen}"
        return f"{self.tipo}: {self.descripcion}"


@dataclass
class ModeloPEAS:
    """Modelo PEAS completo del agente.

    Integra Performance, Environment, Actuators, Sensors.
    """

    # Componentes
    medida: MedidaDesempeno
    ambiente: Ambiente
    percepcion: Percepcion

    # Historial para aprendizaje futuro
    historial_acciones: list[Accion] = field(default_factory=list)
    historial_estados: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        """Inicializa medida con criterio de la percepción."""
        self.medida = MedidaDesempeno(criterio=self.percepcion.criterio)

    def actualizar_percepcion(self, nueva: Percepcion) -> None:
        """Actualiza percepción y registra estado anterior."""
        self.historial_estados.append(self.percepcion.obtener_estado_actual())
        self.percepcion = nueva

    def registrar_accion(self, accion: Accion) -> None:
        """Registra acción ejecutada."""
        self.historial_acciones.append(accion)
        self.percepcion.ruta_construida.append(accion.nodo_origen)

    def evaluar_desempeno(self, destino_alcanzado: bool = False) -> MedidaDesempeno:
        """Evalúa desempeño actual y actualiza métricas."""
        self.medida.destino_alcanzado = destino_alcanzado
        avanzar = [a for a in self.historial_acciones if a.tipo == "avanzar"]
        self.medida.num_conexiones = len(avanzar)
        self.medida.distancia_total = sum(a.distancia for a in avanzar)
        self.medida.tiempo_total_min = sum(
            a.tiempo_estimado for a in self.historial_acciones
        )
        self.medida.ruta_valida = (
            destino_alcanzado and len(self.percepcion.ruta_construida) > 1
        )

        return self.medida

    def objetivo_cumplido(self) -> bool:
        """Verifica si se alcanzó el destino."""
        return self.percepcion.nodo_actual == self.percepcion.nodo_destino


def crear_peas_inicial(
    grafo: Grafo,
    origen: str,
    destino: str,
    criterio: CriterioOptimizacion = CriterioOptimizacion.MENOR_TIEMPO,
    fecha: datetime | None = None,
    hora: str = "08:00",
) -> ModeloPEAS:
    """Factory para crear modelo PEAS inicial."""
    ahora = fecha or datetime.now()

    ambiente = Ambiente(
        grafo=grafo,
        fecha=ahora,
        hora=hora,
    )

    percepcion = Percepcion(
        nodo_origen=origen,
        nodo_destino=destino,
        fecha=ahora,
        hora=hora,
        criterio=criterio,
        nodo_actual=origen,
    )

    medida = MedidaDesempeno(criterio=criterio)

    return ModeloPEAS(medida=medida, ambiente=ambiente, percepcion=percepcion)
