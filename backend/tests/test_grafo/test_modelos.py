"""Tests unitarios para src/grafo/modelos.py"""

import pytest
from src.grafo.modelos import (
    Nodo, Arista, Grafo, Coordenadas,
    TipoNodo, NivelCongestion, TipoVia,
    AtributosNodo, AtributosArista,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def coord_bogota():
    return Coordenadas(latitud=4.6097, longitud=-74.0817)


@pytest.fixture
def coord_suba():
    return Coordenadas(latitud=4.7439, longitud=-74.1001)


@pytest.fixture
def nodo_portal_norte(coord_bogota):
    return Nodo(
        id="PN",
        nombre="Portal Norte",
        coordenadas=coord_bogota,
        tipo=TipoNodo.ESTACION,
    )


@pytest.fixture
def nodo_calle_72(coord_suba):
    return Nodo(
        id="C72",
        nombre="Calle 72",
        coordenadas=coord_suba,
        tipo=TipoNodo.INTERSECCION,
    )


@pytest.fixture
def arista_pn_c72(nodo_portal_norte, nodo_calle_72):
    return Arista(
        id="PN-C72",
        origen="PN",
        destino="C72",
        distancia=5000.0,
        tiempo_estimado=12.5,
        congestion=NivelCongestion.BAJA,
    )


@pytest.fixture
def grafo_simple(nodo_portal_norte, nodo_calle_72, arista_pn_c72):
    g = Grafo()
    g.agregar_nodo(nodo_portal_norte)
    g.agregar_nodo(nodo_calle_72)
    g.agregar_arista(arista_pn_c72)
    return g


# ─── Tests Coordenadas ────────────────────────────────────────────────────────

class TestCoordenadas:
    def test_crear_coordenadas_validas(self):
        c = Coordenadas(latitud=4.6097, longitud=-74.0817)
        assert c.latitud == 4.6097
        assert c.longitud == -74.0817

    def test_latitud_fuera_rango_falla(self):
        with pytest.raises(Exception):
            Coordenadas(latitud=91.0, longitud=0.0)

    def test_longitud_fuera_rango_falla(self):
        with pytest.raises(Exception):
            Coordenadas(latitud=0.0, longitud=181.0)

    def test_distancia_a_misma_coord_es_cero(self, coord_bogota):
        assert coord_bogota.distancia_a(coord_bogota) == pytest.approx(0.0, abs=1e-3)

    def test_distancia_a_otro_punto_positiva(self, coord_bogota, coord_suba):
        dist = coord_bogota.distancia_a(coord_suba)
        assert dist > 0

    def test_distancia_es_simetrica(self, coord_bogota, coord_suba):
        d1 = coord_bogota.distancia_a(coord_suba)
        d2 = coord_suba.distancia_a(coord_bogota)
        assert d1 == pytest.approx(d2, rel=1e-5)


# ─── Tests Nodo ───────────────────────────────────────────────────────────────

class TestNodo:
    def test_crear_nodo_valido(self, coord_bogota):
        nodo = Nodo(id="N1", nombre="Test", coordenadas=coord_bogota)
        assert nodo.id == "N1"
        assert nodo.tipo == TipoNodo.INTERSECCION  # default

    def test_id_vacio_falla(self, coord_bogota):
        with pytest.raises(Exception):
            Nodo(id="", nombre="Test", coordenadas=coord_bogota)

    def test_id_con_espacios_se_limpia(self, coord_bogota):
        nodo = Nodo(id="  N1  ", nombre="Test", coordenadas=coord_bogota)
        assert nodo.id == "N1"

    def test_tipo_estacion(self, coord_bogota):
        nodo = Nodo(id="E1", nombre="Estación", coordenadas=coord_bogota, tipo=TipoNodo.ESTACION)
        assert nodo.tipo == TipoNodo.ESTACION

    def test_atributos_default(self, coord_bogota):
        nodo = Nodo(id="N1", nombre="Test", coordenadas=coord_bogota)
        assert nodo.atributos.accesible is True


# ─── Tests Arista ─────────────────────────────────────────────────────────────

class TestArista:
    def test_crear_arista_valida(self):
        a = Arista(id="A1", origen="N1", destino="N2", distancia=1000.0, tiempo_estimado=5.0)
        assert a.id == "A1"
        assert a.disponible is True
        assert a.congestion == NivelCongestion.BAJA

    def test_distancia_negativa_falla(self):
        with pytest.raises(Exception):
            Arista(id="A1", origen="N1", destino="N2", distancia=-1.0, tiempo_estimado=5.0)

    def test_tiempo_negativo_falla(self):
        with pytest.raises(Exception):
            Arista(id="A1", origen="N1", destino="N2", distancia=100.0, tiempo_estimado=-1.0)

    def test_velocidad_fuera_rango_falla(self):
        with pytest.raises(Exception):
            Arista(id="A1", origen="N1", destino="N2", distancia=100.0, tiempo_estimado=1.0, velocidad_promedio=250.0)

    def test_nivel_congestion_bloqueada(self):
        a = Arista(
            id="A1", origen="N1", destino="N2",
            distancia=100.0, tiempo_estimado=1.0,
            congestion=NivelCongestion.BLOQUEADA, disponible=False
        )
        assert a.congestion == NivelCongestion.BLOQUEADA
        assert a.disponible is False


# ─── Tests Grafo ──────────────────────────────────────────────────────────────

class TestGrafo:
    def test_grafo_vacio(self):
        g = Grafo()
        assert len(g.nodos) == 0
        assert len(g.aristas) == 0

    def test_agregar_nodo(self, nodo_portal_norte):
        g = Grafo()
        g.agregar_nodo(nodo_portal_norte)
        assert "PN" in g.nodos

    def test_agregar_arista_con_nodos_existentes(self, grafo_simple, arista_pn_c72):
        assert len(grafo_simple.aristas) == 1
        assert grafo_simple.aristas[0].id == "PN-C72"

    def test_agregar_arista_sin_nodo_origen_falla(self, nodo_calle_72, arista_pn_c72):
        g = Grafo()
        g.agregar_nodo(nodo_calle_72)  # solo destino, falta origen
        with pytest.raises(ValueError, match="origen"):
            g.agregar_arista(arista_pn_c72)

    def test_agregar_arista_sin_nodo_destino_falla(self, nodo_portal_norte, arista_pn_c72):
        g = Grafo()
        g.agregar_nodo(nodo_portal_norte)
        with pytest.raises(ValueError, match="destino"):
            g.agregar_arista(arista_pn_c72)

    def test_obtener_vecinos(self, grafo_simple):
        vecinos = grafo_simple.obtener_vecinos("PN")
        assert len(vecinos) == 1
        assert vecinos[0].destino == "C72"

    def test_obtener_vecinos_nodo_sin_salidas(self, grafo_simple):
        vecinos = grafo_simple.obtener_vecinos("C72")
        assert len(vecinos) == 0

    def test_obtener_arista_existente(self, grafo_simple):
        arista = grafo_simple.obtener_arista("PN", "C72")
        assert arista is not None
        assert arista.id == "PN-C72"

    def test_obtener_arista_no_existente(self, grafo_simple):
        arista = grafo_simple.obtener_arista("C72", "PN")
        assert arista is None

    def test_validar_conectividad_sin_errores(self, grafo_simple):
        errores = grafo_simple.validar_conectividad()
        assert len(errores) == 0

    def test_validar_conectividad_con_arista_huerfana(self):
        g = Grafo()
        g.nodos["N1"] = Nodo(
            id="N1", nombre="Uno",
            coordenadas=Coordenadas(latitud=4.6, longitud=-74.0)
        )
        # Agregar arista directamente sin validación (para test)
        a = Arista(id="A1", origen="N1", destino="NOEXISTE", distancia=100.0, tiempo_estimado=1.0)
        g.aristas.append(a)
        errores = g.validar_conectividad()
        assert len(errores) > 0

    def test_conversion_networkx_dirigido(self, grafo_simple):
        import networkx as nx
        G = grafo_simple.a_networkx()
        assert isinstance(G, nx.DiGraph)
        assert "PN" in G.nodes
        assert "C72" in G.nodes
        assert G.has_edge("PN", "C72")

    def test_conversion_networkx_no_dirigido(self, nodo_portal_norte, nodo_calle_72, arista_pn_c72):
        import networkx as nx
        g = Grafo(dirigido=False)
        g.agregar_nodo(nodo_portal_norte)
        g.agregar_nodo(nodo_calle_72)
        g.agregar_arista(arista_pn_c72)
        G = g.a_networkx()
        assert isinstance(G, nx.Graph)
