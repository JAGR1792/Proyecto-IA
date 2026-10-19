"""Helpers y fixtures compartidas por toda la suite de tests."""

import pytest

from src.grafo.modelos import Arista, Coordenadas, Grafo, Nodo, TipoNodo


def crear_nodo(nid: str, lat: float, lon: float) -> Nodo:
    """Crea un nodo de intersección para los tests."""
    return Nodo(
        id=nid,
        nombre=f"Nodo {nid}",
        coordenadas=Coordenadas(latitud=lat, longitud=lon),
        tipo=TipoNodo.INTERSECCION,
    )


def crear_arista(
    oid: str,
    did: str,
    tiempo: float,
    dist: float,
    arista_id: str | None = None,
    velocidad: float = 40.0,
    disponible: bool = True,
) -> Arista:
    """Crea una arista con los valores mínimos que usan los tests."""
    return Arista(
        id=arista_id or f"{oid}-{did}",
        origen=oid,
        destino=did,
        distancia=dist,
        tiempo_estimado=tiempo,
        velocidad_promedio=velocidad,
        disponible=disponible,
    )


def construir_grafo(nodos: dict[str, tuple[float, float]], aristas: list[Arista]) -> Grafo:
    """Construye un grafo dirigido a partir de coordenadas y aristas."""
    grafo = Grafo()
    for nid, (lat, lon) in nodos.items():
        grafo.agregar_nodo(crear_nodo(nid, lat, lon))
    for arista in aristas:
        grafo.agregar_arista(arista)
    return grafo


@pytest.fixture
def grafo_lineal() -> Grafo:
    """N1 → N2 → N3 en línea recta (1 km + 0.8 km)."""
    return construir_grafo(
        {"N1": (4.60, -74.00), "N2": (4.61, -74.00), "N3": (4.62, -74.00)},
        [
            crear_arista("N1", "N2", tiempo=10.0, dist=1000.0),
            crear_arista("N2", "N3", tiempo=8.0, dist=800.0),
        ],
    )


@pytest.fixture
def grafo_diamante() -> Grafo:
    """O→A→D es rápida pero larga; O→D es lenta pero corta y directa.

    Permite comprobar que cada criterio elige una ruta distinta:
    tiempo → O→A→D, distancia → O→D, conexiones → O→D.
    """
    return construir_grafo(
        {"O": (4.600, -74.008), "A": (4.600, -74.004), "D": (4.600, -74.000)},
        [
            crear_arista("O", "A", tiempo=2.0, dist=600.0, arista_id="rapida-1"),
            crear_arista("A", "D", tiempo=2.0, dist=600.0, arista_id="rapida-2"),
            crear_arista("O", "D", tiempo=9.0, dist=900.0, arista_id="directa"),
        ],
    )


@pytest.fixture
def grafo_inconexo() -> Grafo:
    """O→A desconectado de X→Y (destino)."""
    return construir_grafo(
        {"O": (4.60, -74.00), "A": (4.61, -74.00), "X": (4.60, -73.50), "Y": (4.61, -73.50)},
        [
            crear_arista("O", "A", tiempo=5.0, dist=500.0),
            crear_arista("X", "Y", tiempo=5.0, dist=500.0),
        ],
    )


@pytest.fixture
def grafo_con_bloqueo() -> Grafo:
    """La conexión directa O→D está cortada: solo queda el desvío O→A→D."""
    return construir_grafo(
        {"O": (4.600, -74.008), "A": (4.600, -74.004), "D": (4.600, -74.000)},
        [
            crear_arista("O", "D", tiempo=1.0, dist=100.0, arista_id="cortada", disponible=False),
            crear_arista("O", "A", tiempo=5.0, dist=600.0, arista_id="desvio-1"),
            crear_arista("A", "D", tiempo=5.0, dist=600.0, arista_id="desvio-2"),
        ],
    )


@pytest.fixture
def grafo_ramal_largo() -> Grafo:
    """Cadena hacia el destino (11 min) con un ramal largo que se aleja.

    El ramal Z avanza hacia el norte, en dirección opuesta al destino, y no
    vuelve a conectarse: UCS lo explora por su bajo costo acumulado, mientras
    A* lo descarta gracias a la heurística geográfica.
    """
    nodos: dict[str, tuple[float, float]] = {"M0": (4.60, -74.000)}
    for k in range(1, 11):
        nodos[f"M{k}"] = (4.60, -74.000 + 0.001 * k)
    nodos["D"] = (4.60, -74.000 + 0.001 * 11)
    for k in range(1, 11):
        nodos[f"Z{k}"] = (4.60 + 0.002 * k, -74.000)

    aristas: list[Arista] = []
    for k in range(11):
        origen = f"M{k}"
        destino = "D" if k == 10 else f"M{k + 1}"
        aristas.append(crear_arista(origen, destino, tiempo=1.0, dist=111.19, velocidad=5.0))
    aristas.append(crear_arista("M0", "Z1", tiempo=2.0, dist=222.39, velocidad=5.0))
    for k in range(1, 10):
        aristas.append(crear_arista(f"Z{k}", f"Z{k + 1}", tiempo=2.0, dist=222.39, velocidad=5.0))
    return construir_grafo(nodos, aristas)
