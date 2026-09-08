"""Modelo PEAS del agente inteligente para planificación de rutas TransMilenio.

Basado en la Primera Entrega del proyecto (PDF) - Corte 1.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from ..grafo.modelos import Grafo, NivelCongestion, Nodo


class CriterioOptimizacion(str, Enum):
    """Criterios de optimización que el usuario puede seleccionar."""

    MENOR_ESTACIONES = "menor_estaciones"
    MENOR_TIEMPO = "menor_tiempo"
    MENOS_TRANSBORDOS = "menos_transbordos"
    MENOR_DEMANDA = "menor_demanda"
    RUTA_EQUILIBRADA = "ruta_equilibrada"


class EstadoOperativo(str, Enum):
    """Estado operativo de una estación según fuentes oficiales."""

    ACTIVA = "activa"
    TEMPORAL_ACTIVA = "temporal_activa"
    CERRADA_TEMPORALMENTE = "cerrada_temporalmente"
    CERRADA_DEFINITIVAMENTE = "cerrada_definitivamente"


@dataclass
class MedidaDesempeno:
    """Medida de desempeño del agente (componente P del PEAS).

    Evalúa qué tan bien el agente cumple su objetivo según el criterio seleccionado.
    """

    criterio: CriterioOptimizacion
    destino_alcanzado: bool = False
    tiempo_total_min: float = 0.0
    num_estaciones: int = 0
    num_transbordos: int = 0
    demanda_promedio: float = 0.0
    ruta_valida: bool = False
    costo_total: float = 0.0

    def calcular_costo(self) -> float:
        """Calcula función de costo según criterio (fórmula del PDF)."""
        if self.criterio == CriterioOptimizacion.RUTA_EQUILIBRADA:
            # C(r) = 0.5*T(r) + 0.3*Tr(r) + 0.2*D(r) - normalizado
            t_norm = min(self.tiempo_total_min / 60.0, 1.0)  # normalizar a 1h max
            tr_norm = min(self.num_transbordos / 5.0, 1.0)    # normalizar a 5 transbordos max
            d_norm = min(self.demanda_promedio / 10000.0, 1.0)  # normalizar demanda
            self.costo_total = 0.5 * t_norm + 0.3 * tr_norm + 0.2 * d_norm
        elif self.criterio == CriterioOptimizacion.MENOR_TIEMPO:
            self.costo_total = self.tiempo_total_min
        elif self.criterio == CriterioOptimizacion.MENOR_ESTACIONES:
            self.costo_total = self.num_estaciones
        elif self.criterio == CriterioOptimizacion.MENOS_TRANSBORDOS:
            self.costo_total = self.num_transbordos
        elif self.criterio == CriterioOptimizacion.MENOR_DEMANDA:
            self.costo_total = self.demanda_promedio

        return self.costo_total

    def es_mejor_que(self, otra: "MedidaDesempeno") -> bool:
        """Compara si esta medida es mejor que otra (menor costo = mejor)."""
        return self.calcular_costo() < otra.calcular_costo()


@dataclass
class Ambiente:
    """Ambiente del agente (componente E del PEAS).

    Representa la red troncal de TransMilenio operativa.
    """

    grafo: Grafo
    fecha: datetime
    hora: str  # Formato HH:MM
    franja_horaria: str  # ej: "06:00-07:00"

    # Estados dinámicos
    estaciones_cerradas: set[str] = field(default_factory=set)
    conexiones_bloqueadas: set[str] = field(default_factory=set)
    demanda_actual: Dict[str, NivelCongestion] = field(default_factory=dict)
    incidentes_activos: List[Dict[str, Any]] = field(default_factory=list)

    def obtener_estaciones_disponibles(self) -> List[Nodo]:
        """Retorna solo estaciones operativas (activas y no cerradas)."""
        disponibles = []
        for nodo in self.grafo.nodos.values():
            if nodo.id not in self.estaciones_cerradas:
                disponibles.append(nodo)
        return disponibles

    def conexion_disponible(self, origen: str, destino: str) -> bool:
        """Verifica si una conexión está disponible en la fecha/hora actual."""
        arista = self.grafo.obtener_arista(origen, destino)
        if not arista or not arista.disponible:
            return False
        if arista.id in self.conexiones_bloqueadas:
            return False
        if origen in self.estaciones_cerradas or destino in self.estaciones_cerradas:
            return False
        # TODO: Verificar calendar.txt y calendar_dates.txt para servicio en esta fecha
        return True

    def obtener_congestion(self, arista_id: str) -> NivelCongestion:
        """Obtiene nivel de congestión actual (histórico + tiempo real)."""
        return self.demanda_actual.get(arista_id, NivelCongestion.BAJA)


@dataclass
class Percepcion:
    """Lo que el agente percibe del ambiente (componente S del PEAS).

    Sensores: entrada usuario + estado actual del ambiente.
    """

    # Entrada del usuario
    estacion_origen: str
    estacion_destino: str
    fecha: datetime
    hora: str
    criterio: CriterioOptimizacion

    # Estado actual del agente
    estacion_actual: str
    servicio_actual: Optional[str] = None
    ruta_construida: List[str] = field(default_factory=list)
    transbordos_realizados: int = 0

    # Información del ambiente (desde sensores/datos)
    conexiones_disponibles: List[str] = field(default_factory=list)
    horarios_siguientes: Dict[str, str] = field(default_factory=dict)
    transbordos_posibles: List[Dict[str, Any]] = field(default_factory=list)
    nivel_demanda_actual: Dict[str, NivelCongestion] = field(default_factory=dict)
    incidentes_cercanos: List[Dict[str, Any]] = field(default_factory=list)

    def obtener_estado_actual(self) -> Dict[str, Any]:
        """Retorna estado completo para toma de decisiones."""
        return {
            "origen": self.estacion_origen,
            "destino": self.estacion_destino,
            "actual": self.estacion_actual,
            "servicio": self.servicio_actual,
            "ruta": self.ruta_construida,
            "transbordos": self.transbordos_realizados,
            "criterio": self.criterio.value,
            "conexiones": self.conexiones_disponibles,
            "horarios": self.horarios_siguientes,
            "transbordos_posibles": self.transbordos_posibles,
            "demanda": {k: v.value for k, v in self.nivel_demanda_actual.items()},
            "incidentes": self.incidentes_cercanos,
        }


@dataclass
class Accion:
    """Acción que el agente puede ejecutar (componente A del PEAS)."""

    tipo: str  # "avanzar", "transbordar", "esperar", "recalcular", "finalizar"
    estacion_origen: str
    estacion_destino: Optional[str] = None
    servicio: Optional[str] = None
    tiempo_estimado: float = 0.0
    es_transbordo: bool = False
    descripcion: str = ""

    def __str__(self) -> str:
        if self.tipo == "avanzar":
            return f"Avanzar a {self.estacion_destino} (línea {self.servicio}, ~{self.tiempo_estimado:.0f} min)"
        elif self.tipo == "transbordar":
            return f"Transbordar a {self.servicio} en {self.estacion_origen}"
        elif self.tipo == "finalizar":
            return f"Llegada a destino: {self.estacion_origen}"
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
    historial_acciones: List[Accion] = field(default_factory=list)
    historial_estados: List[Dict[str, Any]] = field(default_factory=list)

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
        self.percepcion.ruta_construida.append(accion.estacion_origen)
        if accion.es_transbordo:
            self.percepcion.transbordos_realizados += 1
            self.percepcion.servicio_actual = accion.servicio

    def evaluar_desempeno(self, destino_alcanzado: bool = False) -> MedidaDesempeno:
        """Evalúa desempeño actual y actualiza métricas."""
        self.medida.destino_alcanzado = destino_alcanzado
        self.medida.num_estaciones = len(self.percepcion.ruta_construida)
        self.medida.num_transbordos = self.percepcion.transbordos_realizados
        self.medida.ruta_valida = destino_alcanzado and len(self.percepcion.ruta_construida) > 1

        # Calcular tiempo y demanda acumulados (simplificado)
        self.medida.tiempo_total_min = sum(a.tiempo_estimado for a in self.historial_acciones)
        self.medida.demanda_promedio = 1000  # Placeholder - conectar con datos reales

        return self.medida

    def objetivo_cumplido(self) -> bool:
        """Verifica si se alcanzó el destino."""
        return self.percepcion.estacion_actual == self.percepcion.estacion_destino


def crear_peas_inicial(
    grafo: Grafo,
    origen: str,
    destino: str,
    criterio: CriterioOptimizacion = CriterioOptimizacion.RUTA_EQUILIBRADA,
    fecha: Optional[datetime] = None,
    hora: str = "08:00",
) -> ModeloPEAS:
    """Factory para crear modelo PEAS inicial."""
    ahora = fecha or datetime.now()

    ambiente = Ambiente(
        grafo=grafo,
        fecha=ahora,
        hora=hora,
        franja_horaria=_calcular_franja(hora),
    )

    percepcion = Percepcion(
        estacion_origen=origen,
        estacion_destino=destino,
        fecha=ahora,
        hora=hora,
        criterio=criterio,
        estacion_actual=origen,
    )

    medida = MedidaDesempeno(criterio=criterio)

    return ModeloPEAS(medida=medida, ambiente=ambiente, percepcion=percepcion)


def _calcular_franja(hora: str) -> str:
    """Calcula franja horaria de 15 min (formato GTFS validaciones)."""
    h, m = map(int, hora.split(":"))
    m_inicio = (m // 15) * 15
    m_fin = m_inicio + 15
    if m_fin >= 60:
        # Ej: 23:45 → 23:45-24:00
        h_fin = h + 1
        m_fin = m_fin - 60
        return f"{h:02d}:{m_inicio:02d}-{h_fin:02d}:{m_fin:02d}"
    return f"{h:02d}:{m_inicio:02d}-{h:02d}:{m_fin:02d}"


# Pesos para función de costo equilibrada (del PDF)
PESOS_COSTO_EQUILIBRADO = {
    "tiempo": 0.5,
    "transbordos": 0.3,
    "demanda": 0.2,
}