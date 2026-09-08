"""Módulo de percepción del agente - Sensores y estado del ambiente.

Implementa los sensores definidos en el modelo PEAS (PDF Corte 1).
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from ..grafo.modelos import Arista, Grafo, NivelCongestion, Nodo
from .peas import Ambiente, CriterioOptimizacion, Percepcion


class SensorEstaciones:
    """Sensor: detecta estaciones disponibles y sus propiedades."""

    def __init__(self, grafo: Grafo):
        self.grafo = grafo

    def obtener_estacion(self, estacion_id: str) -> Optional[Nodo]:
        return self.grafo.nodos.get(estacion_id)

    def obtener_todas_activas(self) -> List[Nodo]:
        return [n for n in self.grafo.nodos.values() if n.atributos.accesible]

    def es_estacion_operativa(self, estacion_id: str, ambiente: Ambiente) -> bool:
        """Verifica si estación está operativa (no cerrada)."""
        return estacion_id not in ambiente.estaciones_cerradas


class SensorConexiones:
    """Sensor: detecta conexiones disponibles desde una estación."""

    def __init__(self, grafo: Grafo):
        self.grafo = grafo

    def obtener_conexiones_salientes(
        self, estacion_id: str, ambiente: Ambiente
    ) -> List[Arista]:
        """Retorna aristas disponibles desde estación (respeta cierres y horarios)."""
        vecinas = self.grafo.obtener_vecinos(estacion_id)
        disponibles = []
        for arista in vecinas:
            if ambiente.conexion_disponible(arista.origen, arista.destino):
                disponibles.append(arista)
        return disponibles

    def obtener_conexion_directa(
        self, origen: str, destino: str, ambiente: Ambiente
    ) -> Optional[Arista]:
        """Verifica si hay conexión directa disponible."""
        arista = self.grafo.obtener_arista(origen, destino)
        if arista and ambiente.conexion_disponible(origen, destino):
            return arista
        return None

    def detectar_transbordos(
        self, estacion_id: str, servicio_actual: Optional[str], ambiente: Ambiente
    ) -> List[Dict[str, Any]]:
        """Detecta posibles transbordos en una estación de intercambio."""
        transbordos = []
        conexiones = self.obtener_conexiones_salientes(estacion_id, ambiente)

        # Agrupar por servicio (nombre_via)
        servicios_vistos: Set[str] = set()
        if servicio_actual:
            servicios_vistos.add(servicio_actual)

        for arista in conexiones:
            servicio = arista.atributos.nombre_via
            if servicio and servicio not in servicios_vistos:
                transbordos.append(
                    {
                        "estacion": estacion_id,
                        "servicio_nuevo": servicio,
                        "servicio_actual": servicio_actual,
                        "destino": arista.destino,
                        "tiempo_estimado": arista.tiempo_estimado,
                        "tipo": "transbordo",
                    }
                )
                servicios_vistos.add(servicio)

        return transbordos


class SensorHorarios:
    """Sensor: consulta horarios programados (GTFS calendar.txt, stop_times.txt)."""

    def __init__(self):
        # En implementación real, cargaría calendar.txt, calendar_dates.txt, stop_times.txt
        self.horarios_cache: Dict[str, Dict[str, List[str]]] = {}

    def obtener_proximos_horarios(
        self, origen: str, destino: str, servicio: str, hora_actual: str
    ) -> List[str]:
        """Retorna próximos horarios de salida para una conexión."""
        # Placeholder - en implementación real consultar stop_times.txt filtrado por trip_id
        return [hora_actual]  # Simplificado

    def servicio_operativo_en_fecha(self, servicio: str, fecha: datetime) -> bool:
        """Verifica si un servicio opera en la fecha dada (calendar.txt + exceptions)."""
        # Placeholder - consultar calendar.txt y calendar_dates.txt
        return True

    def obtener_franja_horaria(self, hora: str) -> str:
        """Calcula franja de 15 min para consultas de demanda."""
        h, m = map(int, hora.split(":"))
        m_inicio = (m // 15) * 15
        m_fin = m_inicio + 15
        return f"{h:02d}:{m_inicio:02d}-{h:02d}:{m_fin:02d}"


class SensorDemanda:
    """Sensor: nivel histórico de demanda/congestión por franja horaria."""

    def __init__(self, archivo_demanda: Optional[str] = None):
        self.demanda_por_estacion: Dict[str, Dict[str, NivelCongestion]] = {}
        self.demanda_por_arista: Dict[str, Dict[str, NivelCongestion]] = {}
        if archivo_demanda:
            self.cargar_demanda(archivo_demanda)

    def cargar_demanda(self, archivo_csv: str) -> None:
        """Carga demanda desde CSV (formato PDF: fecha, franja_horaria, validaciones, nivel_demanda)."""
        import pandas as pd

        try:
            df = pd.read_csv(archivo_csv)
            for _, row in df.iterrows():
                franja = row.get("franja_horaria", "")
                nivel = NivelCongestion(row.get("nivel_demanda", "baja"))
                estacion = row.get("id_estacion")
                if estacion:
                    if estacion not in self.demanda_por_estacion:
                        self.demanda_por_estacion[estacion] = {}
                    self.demanda_por_estacion[estacion][franja] = nivel
        except Exception:
            pass  # Silencioso si no hay archivo

    def obtener_demanda_estacion(
        self, estacion_id: str, franja: str
    ) -> NivelCongestion:
        return self.demanda_por_estacion.get(estacion_id, {}).get(franja, NivelCongestion.BAJA)

    def obtener_demanda_arista(
        self, arista_id: str, franja: str
    ) -> NivelCongestion:
        return self.demanda_por_arista.get(arista_id, {}).get(franja, NivelCongestion.BAJA)


class SensorIncidentes:
    """Sensor: incidentes activos que afectan la red."""

    def __init__(self):
        self.incidentes_activos: List[Dict[str, Any]] = []

    def actualizar_incidentes(self, incidentes: List[Dict[str, Any]]) -> None:
        self.incidentes_activos = incidentes

    def obtener_incidentes_afectando(
        self, estacion_id: Optional[str] = None, arista_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Filtra incidentes que afectan una estación o conexión específica."""
        relevantes = []
        for inc in self.incidentes_activos:
            if estacion_id and inc.get("estacion") == estacion_id:
                relevantes.append(inc)
            elif arista_id and inc.get("arista") == arista_id:
                relevantes.append(inc)
            elif not estacion_id and not arista_id:
                relevantes.append(inc)
        return relevantes


class PercepcionCompleta:
    """Agrupa todos los sensores y genera percepción completa para el agente."""

    def __init__(self, grafo: Grafo, archivo_demanda: Optional[str] = None):
        self.sensor_estaciones = SensorEstaciones(grafo)
        self.sensor_conexiones = SensorConexiones(grafo)
        self.sensor_horarios = SensorHorarios()
        self.sensor_demanda = SensorDemanda(archivo_demanda)
        self.sensor_incidentes = SensorIncidentes()

    def generar_percepcion(
        self,
        origen: str,
        destino: str,
        criterio: CriterioOptimizacion,
        fecha: datetime,
        hora: str,
        estacion_actual: str,
        servicio_actual: Optional[str] = None,
        ruta_construida: Optional[List[str]] = None,
        transbordos_realizados: int = 0,
        ambiente: Optional[Ambiente] = None,
    ) -> Percepcion:
        """Genera percepción completa del estado actual."""

        franja = self.sensor_horarios.obtener_franja_horaria(hora)

        # Conexiones disponibles desde estación actual
        conexiones = self.sensor_conexiones.obtener_conexiones_salientes(estacion_actual, ambiente) if ambiente else []
        ids_conexiones = [f"{c.origen}-{c.destino}" for c in conexiones]

        # Transbordos posibles
        transbordos = []
        if ambiente:
            transbordos = self.sensor_conexiones.detectar_transbordos(
                estacion_actual, servicio_actual, ambiente
            )

        # Demanda actual
        demanda = {}
        for c in conexiones:
            demanda[f"{c.origen}-{c.destino}"] = self.sensor_demanda.obtener_demanda_arista(
                c.id, franja
            )

        # Incidentes cercanos
        incidentes = self.sensor_incidentes.obtener_incidentes_afectando(estacion_id=estacion_actual)

        # Horarios siguientes (simplificado)
        horarios = {}
        for c in conexiones:
            horarios[f"{c.origen}-{c.destino}"] = self.sensor_horarios.obtener_proximos_horarios(
                c.origen, c.destino, c.atributos.nombre_via or "", hora
            )[0]

        return Percepcion(
            estacion_origen=origen,
            estacion_destino=destino,
            fecha=fecha,
            hora=hora,
            criterio=criterio,
            estacion_actual=estacion_actual,
            servicio_actual=servicio_actual,
            ruta_construida=ruta_construida or [],
            transbordos_realizados=transbordos_realizados,
            conexiones_disponibles=ids_conexiones,
            horarios_siguientes=horarios,
            transbordos_posibles=transbordos,
            nivel_demanda_actual=demanda,
            incidentes_cercanos=incidentes,
        )