"""Módulo de percepción del agente - Sensores y estado del ambiente.

Implementa los sensores definidos en el modelo PEAS (PDF Corte 1):
ubicación actual, origen, destino, hora, conexiones disponibles, distancia,
tiempo, congestión e incidentes.
"""

from datetime import datetime
from typing import Any

from ..grafo.modelos import Arista, Grafo, NivelCongestion, Nodo
from .peas import Ambiente, CriterioOptimizacion, Percepcion


class SensorNodos:
    """Sensor: detecta nodos (intersecciones) y sus propiedades."""

    def __init__(self, grafo: Grafo):
        self.grafo = grafo

    def obtener_nodo(self, nodo_id: str) -> Nodo | None:
        """Retorna un nodo del grafo."""
        return self.grafo.nodos.get(nodo_id)

    def obtener_todos_disponibles(self) -> list[Nodo]:
        """Retorna todos los nodos accesibles de la red."""
        return [n for n in self.grafo.nodos.values() if n.atributos.accesible]


class SensorConexiones:
    """Sensor: detecta conexiones (segmentos viales) disponibles desde un nodo."""

    def __init__(self, grafo: Grafo):
        self.grafo = grafo

    def obtener_conexiones_salientes(
        self, nodo_id: str, ambiente: Ambiente
    ) -> list[Arista]:
        """Retorna aristas disponibles desde el nodo (respeta bloqueos)."""
        vecinas = self.grafo.obtener_vecinos(nodo_id)
        disponibles = []
        for arista in vecinas:
            if ambiente.conexion_disponible(arista.origen, arista.destino):
                disponibles.append(arista)
        return disponibles

    def obtener_conexion_directa(
        self, origen: str, destino: str, ambiente: Ambiente
    ) -> Arista | None:
        """Verifica si hay conexión directa disponible."""
        arista = self.grafo.obtener_arista(origen, destino)
        if arista and ambiente.conexion_disponible(origen, destino):
            return arista
        return None


class SensorCongestion:
    """Sensor: nivel de congestión por conexión (segmento vial)."""

    def obtener_congestion_conexiones(
        self, conexiones: list[Arista]
    ) -> dict[str, NivelCongestion]:
        """Retorna congestión actual de cada conexión."""
        return {
            f"{c.origen}-{c.destino}": c.congestion
            for c in conexiones
        }


class SensorIncidentes:
    """Sensor: incidentes activos que afectan la red."""

    def __init__(self):
        self.incidentes_activos: list[dict[str, Any]] = []

    def actualizar_incidentes(self, incidentes: list[dict[str, Any]]) -> None:
        self.incidentes_activos = incidentes

    def obtener_incidentes_afectando(
        self, nodo_id: str | None = None, arista_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Filtra incidentes que afectan un nodo o conexión específica."""
        relevantes = []
        for inc in self.incidentes_activos:
            if nodo_id and inc.get("nodo") == nodo_id:
                relevantes.append(inc)
            elif arista_id and inc.get("arista") == arista_id:
                relevantes.append(inc)
            elif not nodo_id and not arista_id:
                relevantes.append(inc)
        return relevantes


class PercepcionCompleta:
    """Agrupa todos los sensores y genera percepción completa para el agente."""

    def __init__(self, grafo: Grafo):
        self.sensor_nodos = SensorNodos(grafo)
        self.sensor_conexiones = SensorConexiones(grafo)
        self.sensor_congestion = SensorCongestion()
        self.sensor_incidentes = SensorIncidentes()

    def generar_percepcion(
        self,
        origen: str,
        destino: str,
        criterio: CriterioOptimizacion,
        fecha: datetime,
        hora: str,
        nodo_actual: str,
        ruta_construida: list[str] | None = None,
        ambiente: Ambiente | None = None,
    ) -> Percepcion:
        """Genera percepción completa del estado actual."""

        # Conexiones disponibles desde nodo actual
        conexiones = self.sensor_conexiones.obtener_conexiones_salientes(nodo_actual, ambiente) if ambiente else []
        ids_conexiones = [f"{c.origen}-{c.destino}" for c in conexiones]
        congestion = self.sensor_congestion.obtener_congestion_conexiones(conexiones) if ambiente else {}

        # Incidentes cercanos
        incidentes = self.sensor_incidentes.obtener_incidentes_afectando(nodo_id=nodo_actual)

        return Percepcion(
            nodo_origen=origen,
            nodo_destino=destino,
            fecha=fecha,
            hora=hora,
            criterio=criterio,
            nodo_actual=nodo_actual,
            ruta_construida=ruta_construida or [],
            conexiones_disponibles=ids_conexiones,
            congestion_conexiones=congestion,
            incidentes_cercanos=incidentes,
        )
