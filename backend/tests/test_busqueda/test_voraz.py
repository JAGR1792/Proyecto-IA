"""Tests unitarios para src/busqueda/voraz.py"""

import pytest

from src.busqueda.voraz import BusquedaVoraz
from src.grafo.modelos import Arista, Coordenadas, Grafo, Nodo, TipoNodo


def _hacer_nodo(nid: str, lat: float, lon: float) -> Nodo:
    return Nodo(
        id=nid,
        nombre=f"Nodo {nid}",
        coordenadas=Coordenadas(latitud=lat, longitud=lon),
        tipo=TipoNodo.INTERSECCION,
    )


def _hacer_arista(oid: str, did: str, tiempo: float, dist: float, arista_id: str = None) -> Arista:
    return Arista(
        id=arista_id or f"{oid}-{did}",
        origen=oid,
        destino=did,
        distancia=dist,
        tiempo_estimado=tiempo,
    )


@pytest.fixture
def busqueda_voraz() -> BusquedaVoraz:
    return BusquedaVoraz()


@pytest.fixture
def grafo_lineal() -> Grafo:
    """N1 → N2 → N3 en línea recta."""
    g = Grafo()
    for nid, lat, lon in [("N1", 4.60, -74.00), ("N2", 4.61, -74.00), ("N3", 4.62, -74.00)]:
        g.agregar_nodo(_hacer_nodo(nid, lat, lon))
    g.agregar_arista(_hacer_arista("N1", "N2", tiempo=10.0, dist=1000.0))
    g.agregar_arista(_hacer_arista("N2", "N3", tiempo=8.0, dist=800.0))
    return g


@pytest.fixture
def grafo_con_callejon() -> Grafo:
    """Greedy cae en un callejón sin salida y debe retroceder.

    O conecta a A→C (sin salida) y a B→D; D es el destino y queda
    más cerca de A que de B, forzando el retroceso.
    """
    g = Grafo()
    coordenadas = {
        "O": (4.6000, -74.0000),
        "A": (4.6005, -74.0005),
        "C": (4.6010, -74.0010),
        "B": (4.6000, -74.0020),
        "D": (4.6010, -74.0005),
    }
    for nid, (lat, lon) in coordenadas.items():
        g.agregar_nodo(_hacer_nodo(nid, lat, lon))
    g.agregar_arista(_hacer_arista("O", "A", tiempo=5.0, dist=500.0))
    g.agregar_arista(_hacer_arista("A", "C", tiempo=5.0, dist=500.0))
    g.agregar_arista(_hacer_arista("O", "B", tiempo=10.0, dist=1000.0))
    g.agregar_arista(_hacer_arista("B", "D", tiempo=10.0, dist=1000.0))
    return g


@pytest.fixture
def grafo_inconexo() -> Grafo:
    """O→A desconectado de X→Y (destino)."""
    g = Grafo()
    for nid, lat, lon in [("O", 4.60, -74.00), ("A", 4.61, -74.00), ("X", 4.60, -73.50), ("Y", 4.61, -73.50)]:
        g.agregar_nodo(_hacer_nodo(nid, lat, lon))
    g.agregar_arista(_hacer_arista("O", "A", tiempo=5.0, dist=500.0))
    g.agregar_arista(_hacer_arista("X", "Y", tiempo=5.0, dist=500.0))
    return g


class TestBusquedaVoraz:
    def test_encuentra_ruta_lineal(self, busqueda_voraz, grafo_lineal):
        resultado = busqueda_voraz.buscar(grafo_lineal, "N1", "N3")
        assert resultado.ruta_encontrada
        assert resultado.camino == ["N1", "N2", "N3"]
        assert resultado.aristas_camino == ["N1-N2", "N2-N3"]
        assert resultado.distancia_total_m == 1800.0
        assert resultado.tiempo_total_min == 18.0
        assert resultado.costo_total == 18.0  # criterio por defecto: menor_tiempo

    def test_retrocede_en_callejon(self, busqueda_voraz, grafo_con_callejon):
        resultado = busqueda_voraz.buscar(grafo_con_callejon, "O", "D")
        assert resultado.ruta_encontrada
        assert resultado.camino == ["O", "B", "D"]

    def test_menor_conexiones_cuesta_un_por_arista(self, busqueda_voraz, grafo_lineal):
        resultado = busqueda_voraz.buscar(grafo_lineal, "N1", "N3", criterio="menor_conexiones")
        assert resultado.ruta_encontrada
        assert resultado.costo_total == 2  # dos aristas

    def test_grafo_inconexo_no_encuentra_ruta(self, busqueda_voraz, grafo_inconexo):
        resultado = busqueda_voraz.buscar(grafo_inconexo, "O", "Y")
        assert not resultado.ruta_encontrada
        assert resultado.camino == ["O"]
        assert resultado.detalle["mensaje"]

    def test_origen_igual_destino(self, busqueda_voraz, grafo_lineal):
        resultado = busqueda_voraz.buscar(grafo_lineal, "N2", "N2")
        assert resultado.ruta_encontrada
        assert resultado.camino == ["N2"]

    def test_criterio_invalido_lanza_error(self, busqueda_voraz, grafo_lineal):
        with pytest.raises(ValueError):
            busqueda_voraz.buscar(grafo_lineal, "N1", "N3", criterio="ruta_equilibrada")

    def test_aristas_paralelas_elige_la_mas_barata(self, busqueda_voraz):
        g = Grafo()
        g.agregar_nodo(_hacer_nodo("O", 4.60, -74.00))
        g.agregar_nodo(_hacer_nodo("D", 4.61, -74.00))
        g.agregar_arista(_hacer_arista("O", "D", tiempo=1.0, dist=100.0, arista_id="rapida"))
        g.agregar_arista(_hacer_arista("O", "D", tiempo=10.0, dist=1000.0, arista_id="lenta"))
        resultado = busqueda_voraz.buscar(g, "O", "D", criterio="menor_tiempo")
        assert resultado.ruta_encontrada
        assert resultado.aristas_camino == ["rapida"]
        assert resultado.costo_total == 1.0

    def test_reporta_metricas_de_ejecucion(self, busqueda_voraz, grafo_lineal):
        resultado = busqueda_voraz.buscar(grafo_lineal, "N1", "N3")
        assert resultado.tiempo_ejecucion_ms >= 0
        assert resultado.nodos_explorados >= 1
        assert resultado.algoritmo == "voraz"
