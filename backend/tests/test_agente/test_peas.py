"""Tests unitarios para src/agente/peas.py"""

from datetime import datetime

import pytest

from src.agente.peas import (
    Accion,
    Ambiente,
    CriterioOptimizacion,
    MedidaDesempeno,
    crear_peas_inicial,
)
from src.grafo.modelos import Arista, Coordenadas, Grafo, NivelCongestion, Nodo, TipoNodo

# ─── Fixtures ────────────────────────────────────────────────────────────────

def _hacer_nodo(nid: str, lat: float = 4.6, lon: float = -74.0) -> Nodo:
    return Nodo(
        id=nid, nombre=f"Intersección {nid}",
        coordenadas=Coordenadas(latitud=lat, longitud=lon),
        tipo=TipoNodo.INTERSECCION,
    )


def _hacer_arista(oid: str, did: str, tiempo: float = 5.0, dist: float = 1000.0) -> Arista:
    return Arista(
        id=f"{oid}-{did}", origen=oid, destino=did,
        distancia=dist, tiempo_estimado=tiempo,
    )


@pytest.fixture
def grafo_lineal():
    """Grafo N1 → N2 → N3."""
    g = Grafo()
    for nid in ["N1", "N2", "N3"]:
        g.agregar_nodo(_hacer_nodo(nid))
    g.agregar_arista(_hacer_arista("N1", "N2", tiempo=10.0))
    g.agregar_arista(_hacer_arista("N2", "N3", tiempo=8.0))
    return g


@pytest.fixture
def modelo_peas(grafo_lineal):
    return crear_peas_inicial(
        grafo=grafo_lineal,
        origen="N1",
        destino="N3",
        criterio=CriterioOptimizacion.MENOR_TIEMPO,
        hora="08:00",
    )


# ─── Tests MedidaDesempeno ────────────────────────────────────────────────────

class TestMedidaDesempeno:
    def test_costo_menor_tiempo(self):
        m = MedidaDesempeno(criterio=CriterioOptimizacion.MENOR_TIEMPO)
        m.tiempo_total_min = 25.0
        assert m.calcular_costo() == pytest.approx(25.0)

    def test_costo_menor_distancia(self):
        m = MedidaDesempeno(criterio=CriterioOptimizacion.MENOR_DISTANCIA)
        m.distancia_total = 1200.0
        assert m.calcular_costo() == pytest.approx(1200.0)

    def test_costo_menor_conexiones(self):
        m = MedidaDesempeno(criterio=CriterioOptimizacion.MENOR_CONEXIONES)
        m.num_conexiones = 3
        assert m.calcular_costo() == pytest.approx(3.0)

    def test_es_mejor_que_con_menor_costo(self):
        m1 = MedidaDesempeno(criterio=CriterioOptimizacion.MENOR_TIEMPO)
        m1.tiempo_total_min = 10.0
        m2 = MedidaDesempeno(criterio=CriterioOptimizacion.MENOR_TIEMPO)
        m2.tiempo_total_min = 20.0
        assert m1.es_mejor_que(m2) is True
        assert m2.es_mejor_que(m1) is False


# ─── Tests Ambiente ───────────────────────────────────────────────────────────

class TestAmbiente:
    def test_obtener_nodos_disponibles(self, grafo_lineal):
        amb = Ambiente(grafo=grafo_lineal, fecha=datetime.now(), hora="08:00")
        nodos = amb.obtener_nodos_disponibles()
        assert len(nodos) == 3

    def test_conexion_disponible_existente(self, grafo_lineal):
        amb = Ambiente(grafo=grafo_lineal, fecha=datetime.now(), hora="08:00")
        assert amb.conexion_disponible("N1", "N2") is True

    def test_conexion_disponible_no_existente(self, grafo_lineal):
        amb = Ambiente(grafo=grafo_lineal, fecha=datetime.now(), hora="08:00")
        assert amb.conexion_disponible("N3", "N1") is False

    def test_conexion_bloqueada_no_disponible(self, grafo_lineal):
        amb = Ambiente(
            grafo=grafo_lineal, fecha=datetime.now(), hora="08:00",
            conexiones_bloqueadas={"N1-N2"},
        )
        assert amb.conexion_disponible("N1", "N2") is False

    def test_congestion_default_usando_arista(self, grafo_lineal):
        amb = Ambiente(grafo=grafo_lineal, fecha=datetime.now(), hora="08:00")
        assert amb.obtener_congestion("N1-N2") == NivelCongestion.BAJA


# ─── Tests ModeloPEAS ─────────────────────────────────────────────────────────

class TestModeloPEAS:
    def test_crear_peas_inicial(self, grafo_lineal):
        modelo = crear_peas_inicial(grafo=grafo_lineal, origen="N1", destino="N3")
        assert modelo.percepcion.nodo_actual == "N1"
        assert modelo.percepcion.nodo_destino == "N3"
        assert not modelo.objetivo_cumplido()

    def test_objetivo_cumplido_falso_al_inicio(self, modelo_peas):
        assert modelo_peas.objetivo_cumplido() is False

    def test_registrar_accion_actualiza_ruta(self, modelo_peas):
        accion = Accion(tipo="avanzar", nodo_origen="N1", nodo_destino="N2", tiempo_estimado=10.0, distancia=500.0)
        modelo_peas.registrar_accion(accion)
        assert "N1" in modelo_peas.percepcion.ruta_construida

    def test_evaluar_desempeno(self, modelo_peas):
        # Registrar 2 acciones para que ruta_construida tenga >1 elemento
        accion1 = Accion(tipo="avanzar", nodo_origen="N1", nodo_destino="N2", tiempo_estimado=10.0, distancia=500.0)
        accion2 = Accion(tipo="avanzar", nodo_origen="N2", nodo_destino="N3", tiempo_estimado=8.0, distancia=700.0)
        modelo_peas.registrar_accion(accion1)
        modelo_peas.registrar_accion(accion2)
        medida = modelo_peas.evaluar_desempeno(destino_alcanzado=True)
        assert medida.destino_alcanzado is True
        assert medida.num_conexiones == 2
        assert medida.distancia_total == pytest.approx(1200.0)
        assert medida.tiempo_total_min == pytest.approx(18.0)
        # ruta_valida: destino_alcanzado AND len(ruta_construida) > 1
        assert len(modelo_peas.percepcion.ruta_construida) > 1
        assert medida.ruta_valida is True
