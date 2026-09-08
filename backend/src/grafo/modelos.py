"""Modelos de datos para la red de movilidad (grafo).

Define Nodo, Arista, Grafo y tipos de apoyo usando Pydantic para validación.
Compatible con NetworkX para algoritmos de búsqueda.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class TipoNodo(str, Enum):
    """Tipos de nodos en la red de movilidad."""

    EDIFICIO = "edificio"
    INTERSECCION = "interseccion"
    ESTACION = "estacion"
    ZONA = "zona"
    OTRO = "otro"


class NivelCongestion(str, Enum):
    """Niveles de congestión en las aristas."""

    BAJA = "baja"
    MEDIA = "media"
    ALTA = "alta"
    BLOQUEADA = "bloqueada"


class TipoVia(str, Enum):
    """Tipos de vía según clasificación OSM."""

    AUTOPATIA = "autopista"
    TRONCAL = "troncal"
    PRIMARIA = "primaria"
    SECUNDARIA = "secundaria"
    TERCIARIA = "terciaria"
    RESIDENCIAL = "residencial"
    SERVICIO = "servicio"
    PEATONAL = "peatonal"
    CICLOVIA = "ciclovia"
    OTRO = "otro"


class Coordenadas(BaseModel):
    """Coordenadas geográficas en grados decimales (WGS84)."""

    latitud: float = Field(..., ge=-90, le=90, description="Latitud en grados decimales")
    longitud: float = Field(..., ge=-180, le=180, description="Longitud en grados decimales")

    def distancia_a(self, otra: "Coordenadas") -> float:
        """Calcula distancia euclidiana aproximada en metros (para heurísticas)."""
        import math

        R = 6371000  # Radio Tierra en metros
        lat1, lon1 = math.radians(self.latitud), math.radians(self.longitud)
        lat2, lon2 = math.radians(otra.latitud), math.radians(otra.longitud)

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c


class AtributosNodo(BaseModel):
    """Atributos opcionales de un nodo."""

    capacidad: Optional[int] = Field(None, ge=0, description="Capacidad máxima (personas/vehículos)")
    horario_apertura: Optional[str] = Field(None, description="Horario formato HH:MM")
    horario_cierre: Optional[str] = Field(None, description="Horario formato HH:MM")
    accesible: bool = Field(True, description="Accesible para movilidad reducida")
    descripcion: Optional[str] = None


class AtributosArista(BaseModel):
    """Atributos opcionales extendidos de una arista."""

    tipo_via: TipoVia = Field(TipoVia.OTRO, description="Clasificación de la vía")
    nombre_via: Optional[str] = Field(None, description="Nombre de la calle/vía")
    superficie: Optional[str] = Field(None, description="Tipo de pavimento")
    carriles: Optional[int] = Field(None, ge=1, description="Número de carriles")
    sentido_unico: bool = Field(False, description="Vía de un solo sentido")
    peaje: bool = Field(False, description="Tiene peaje")
    costo_peaje: Optional[float] = Field(None, ge=0, description="Costo del peaje")
    restricciones: List[str] = Field(default_factory=list, description="Restricciones (ej: solo_bus, peso_max)")


class Nodo(BaseModel):
    """Representa un nodo (lugar) en la red de movilidad.

    Attributes:
        id: Identificador único del nodo.
        nombre: Nombre legible del lugar.
        coordenadas: Posición geográfica.
        tipo: Categoría del nodo.
        atributos: Propiedades adicionales opcionales.
    """

    id: str = Field(..., min_length=1, description="Identificador único")
    nombre: str = Field(..., min_length=1, description="Nombre del lugar")
    coordenadas: Coordenadas
    tipo: TipoNodo = Field(TipoNodo.INTERSECCION, description="Tipo de nodo")
    atributos: AtributosNodo = Field(default_factory=AtributosNodo)

    @field_validator("id")
    @classmethod
    def validar_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El ID no puede estar vacío")
        return v.strip()


class Arista(BaseModel):
    """Representa una conexión entre dos nodos.

    Attributes:
        id: Identificador único de la arista.
        origen: ID del nodo origen.
        destino: ID del nodo destino.
        distancia: Longitud en metros.
        tiempo_estimado: Tiempo en minutos.
        costo: Costo monetario (ej: peaje, combustible).
        velocidad_promedio: Velocidad típica en km/h.
        congestion: Nivel de congestión actual.
        disponible: Si la conexión está transitable.
        incidentes: Número de incidentes reportados.
        atributos: Propiedades adicionales de la vía.
    """

    id: str = Field(..., min_length=1)
    origen: str = Field(..., min_length=1)
    destino: str = Field(..., min_length=1)
    distancia: float = Field(..., ge=0, description="Distancia en metros")
    tiempo_estimado: float = Field(..., ge=0, description="Tiempo en minutos")
    costo: float = Field(0.0, ge=0, description="Costo monetario")
    velocidad_promedio: float = Field(50.0, ge=0, le=200, description="km/h")
    congestion: NivelCongestion = Field(NivelCongestion.BAJA, description="Nivel de congestión")
    disponible: bool = Field(True, description="Conexión transitable")
    incidentes: int = Field(0, ge=0, description="Incidentes reportados")
    atributos: AtributosArista = Field(default_factory=AtributosArista)

    @field_validator("id")
    @classmethod
    def validar_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El ID no puede estar vacío")
        return v.strip()

    @field_validator("origen", "destino")
    @classmethod
    def validar_nodos(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Referencia a nodo no puede estar vacía")
        return v.strip()


class Grafo(BaseModel):
    """Contenedor del grafo completo de movilidad.

    Attributes:
        nodos: Diccionario id -> Nodo.
        aristas: Lista de aristas.
        dirigido: Si el grafo es dirigido (True) o no dirigido (False).
        metadata: Información adicional (fuente, fecha, versión).
    """

    nodos: Dict[str, Nodo] = Field(default_factory=dict)
    aristas: List[Arista] = Field(default_factory=list)
    dirigido: bool = Field(True, description="Grafo dirigido")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def agregar_nodo(self, nodo: Nodo) -> None:
        """Agrega un nodo al grafo."""
        self.nodos[nodo.id] = nodo

    def agregar_arista(self, arista: Arista) -> None:
        """Agrega una arista al grafo."""
        if arista.origen not in self.nodos:
            raise ValueError(f"Nodo origen '{arista.origen}' no existe")
        if arista.destino not in self.nodos:
            raise ValueError(f"Nodo destino '{arista.destino}' no existe")
        self.aristas.append(arista)

    def obtener_vecinos(self, nodo_id: str) -> List[Arista]:
        """Retorna aristas salientes desde un nodo."""
        return [a for a in self.aristas if a.origen == nodo_id and a.disponible]

    def obtener_arista(self, origen: str, destino: str) -> Optional[Arista]:
        """Busca arista directa entre dos nodos."""
        for arista in self.aristas:
            if arista.origen == origen and arista.destino == destino:
                return arista
        return None

    def a_networkx(self) -> "networkx.Graph":
        """Convierte a grafo NetworkX para algoritmos."""
        import networkx as nx

        G = nx.DiGraph() if self.dirigido else nx.Graph()

        for nodo in self.nodos.values():
            G.add_node(
                nodo.id,
                nombre=nodo.nombre,
                lat=nodo.coordenadas.latitud,
                lon=nodo.coordenadas.longitud,
                tipo=nodo.tipo.value,
            )

        for arista in self.aristas:
            if arista.disponible:
                G.add_edge(
                    arista.origen,
                    arista.destino,
                    id=arista.id,
                    distancia=arista.distancia,
                    tiempo=arista.tiempo_estimado,
                    costo=arista.costo,
                    velocidad=arista.velocidad_promedio,
                    congestion=arista.congestion.value,
                    incidentes=arista.incidentes,
                )

        return G

    @classmethod
    def desde_networkx(cls, G: "networkx.Graph", dirigido: bool = True) -> "Grafo":
        """Crea Grafo desde NetworkX."""
        grafo = cls(dirigido=dirigido)

        for nodo_id, data in G.nodes(data=True):
            grafo.agregar_nodo(
                Nodo(
                    id=nodo_id,
                    nombre=data.get("nombre", f"Nodo {nodo_id}"),
                    coordenadas=Coordenadas(
                        latitud=data.get("lat", 0.0), longitud=data.get("lon", 0.0)
                    ),
                    tipo=TipoNodo(data.get("tipo", "interseccion")),
                )
            )

        for u, v, data in G.edges(data=True):
            grafo.agregar_arista(
                Arista(
                    id=data.get("id", f"{u}-{v}"),
                    origen=u,
                    destino=v,
                    distancia=data.get("distancia", 100.0),
                    tiempo_estimado=data.get("tiempo", 1.0),
                    costo=data.get("costo", 0.0),
                    velocidad_promedio=data.get("velocidad", 50.0),
                    congestion=NivelCongestion(data.get("congestion", "baja")),
                    incidentes=data.get("incidentes", 0),
                )
            )

        return grafo

    def validar_conectividad(self) -> List[str]:
        """Valida que todos los nodos referenciados existan."""
        errores = []
        ids_nodos = set(self.nodos.keys())
        for arista in self.aristas:
            if arista.origen not in ids_nodos:
                errores.append(f"Arista {arista.id}: origen {arista.origen} no existe")
            if arista.destino not in ids_nodos:
                errores.append(f"Arista {arista.id}: destino {arista.destino} no existe")
        return errores