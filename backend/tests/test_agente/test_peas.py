"""Tests unitarios para src/agente/peas.py"""

import pytest
from datetime import datetime
from src.agente.peas import (
    MedidaDesempeno, Ambiente, Percepcion, Accion, ModeloPEAS,
    CriterioOptimizacion, crear_peas_inicial, _calcular_franja,
    PESOS_COSTO_EQUILIBRADO,
)
from src.grafo.modelos import Grafo, Nodo, Arista, Coordenadas, TipoNodo, NivelCongestion


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _hacer_nodo(nid: str, lat: float = 4.6, lon: float = -74.0) -> Nodo:
    return Nodo(
        id=nid, nombre=f"Estación {nid}",
        coordenadas=Coordenadas(latitud=lat, longitud=lon),
        tipo=TipoNodo.ESTACION,
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

    def test_costo_menor_estaciones(self):
        m = MedidaDesempeno(criterio=CriterioOptimizacion.MENOR_ESTACIONES)
        m.num_estaciones = 4
        assert m.calcular_costo() == 4

    def test_costo_menos_transbordos(self):
        m = MedidaDesempeno(criterio=CriterioOptimizacion.MENOS_TRANSBORDOS)
        m.num_transbordos = 2
        assert m.calcular_costo() == 2

    def test_costo_menor_demanda(self):
        m = MedidaDesempeno(criterio=CriterioOptimizacion.MENOR_DEMANDA)
        m.demanda_promedio = 5000.0
        assert m.calcular_costo() == pytest.approx(5000.0)

    def test_costo_ruta_equilibrada_es_float(self):
        m = MedidaDesempeno(criterio=CriterioOptimizacion.RUTA_EQUILIBRADA)
        m.tiempo_total_min = 30.0
        m.num_transbordos = 1
        m.demanda_promedio = 3000.0
        costo = m.calcular_costo()
        assert isinstance(costo, float)
        assert 0.0 <= costo <= 1.0

    def test_es_mejor_que_con_menor_costo(self):
        m1 = MedidaDesempeno(criterio=CriterioOptimizacion.MENOR_TIEMPO)
        m1.tiempo_total_min = 10.0
        m2 = MedidaDesempeno(criterio=CriterioOptimizacion.MENOR_TIEMPO)
        m2.tiempo_total_min = 20.0
        assert m1.es_mejor_que(m2) is True
        assert m2.es_mejor_que(m1) is False


# ─── Tests Ambiente ───────────────────────────────────────────────────────────

class TestAmbiente:
    def test_obtener_estaciones_disponibles(self, grafo_lineal):
        amb = Ambiente(grafo=grafo_lineal, fecha=datetime.now(), hora="08:00", franja_horaria="08:00-08:15")
        estaciones = amb.obtener_estaciones_disponibles()
        assert len(estaciones) == 3

    def test_obtener_estaciones_excluye_cerradas(self, grafo_lineal):
        amb = Ambiente(
            grafo=grafo_lineal, fecha=datetime.now(), hora="08:00", franja_horaria="08:00-08:15",
            estaciones_cerradas={"N2"},
        )
        disponibles = amb.obtener_estaciones_disponibles()
        ids = [e.id for e in disponibles]
        assert "N2" not in ids

    def test_conexion_disponible_existente(self, grafo_lineal):
        amb = Ambiente(grafo=grafo_lineal, fecha=datetime.now(), hora="08:00", franja_horaria="08:00-08:15")
        assert amb.conexion_disponible("N1", "N2") is True

    def test_conexion_disponible_no_existente(self, grafo_lineal):
        amb = Ambiente(grafo=grafo_lineal, fecha=datetime.now(), hora="08:00", franja_horaria="08:00-08:15")
        assert amb.conexion_disponible("N3", "N1") is False

    def test_conexion_bloqueada_no_disponible(self, grafo_lineal):
        amb = Ambiente(
            grafo=grafo_lineal, fecha=datetime.now(), hora="08:00", franja_horaria="08:00-08:15",
            conexiones_bloqueadas={"N1-N2"},
        )
        assert amb.conexion_disponible("N1", "N2") is False

    def test_congestion_default_baja(self, grafo_lineal):
        amb = Ambiente(grafo=grafo_lineal, fecha=datetime.now(), hora="08:00", franja_horaria="08:00-08:15")
        assert amb.obtener_congestion("N1-N2") == NivelCongestion.BAJA


# ─── Tests ModeloPEAS ─────────────────────────────────────────────────────────

class TestModeloPEAS:
    def test_crear_peas_inicial(self, grafo_lineal):
        modelo = crear_peas_inicial(grafo=grafo_lineal, origen="N1", destino="N3")
        assert modelo.percepcion.estacion_actual == "N1"
        assert modelo.percepcion.estacion_destino == "N3"
        assert not modelo.objetivo_cumplido()

    def test_objetivo_cumplido_falso_al_inicio(self, modelo_peas):
        assert modelo_peas.objetivo_cumplido() is False

    def test_registrar_accion_actualiza_ruta(self, modelo_peas):
        accion = Accion(tipo="avanzar", estacion_origen="N1", estacion_destino="N2", tiempo_estimado=10.0)
        modelo_peas.registrar_accion(accion)
        assert "N1" in modelo_peas.percepcion.ruta_construida

    def test_registrar_transbordo_incrementa_contador(self, modelo_peas):
        accion = Accion(
            tipo="transbordar", estacion_origen="N2",
            estacion_destino="N2", servicio="Ruta-B",
            es_transbordo=True,
        )
        inicial = modelo_peas.percepcion.transbordos_realizados
        modelo_peas.registrar_accion(accion)
        assert modelo_peas.percepcion.transbordos_realizados == inicial + 1

    def test_evaluar_desempeno(self, modelo_peas):
        # Registrar 2 acciones para que ruta_construida tenga >1 elemento
        accion1 = Accion(tipo="avanzar", estacion_origen="N1", estacion_destino="N2", tiempo_estimado=10.0)
        accion2 = Accion(tipo="avanzar", estacion_origen="N2", estacion_destino="N3", tiempo_estimado=8.0)
        modelo_peas.registrar_accion(accion1)
        modelo_peas.registrar_accion(accion2)
        medida = modelo_peas.evaluar_desempeno(destino_alcanzado=True)
        assert medida.destino_alcanzado is True
        # ruta_valida: destino_alcanzado AND len(ruta_construida) > 1
        assert len(modelo_peas.percepcion.ruta_construida) > 1
        assert medida.ruta_valida is True


# ─── Tests helpers ────────────────────────────────────────────────────────────

class TestHelpers:
    @pytest.mark.parametrize("hora,esperado", [
        ("08:00", "08:00-08:15"),
        ("08:14", "08:00-08:15"),
        ("08:15", "08:15-08:30"),
        ("23:59", "23:45-24:00"),
        ("12:30", "12:30-12:45"),
    ])
    def test_calcular_franja(self, hora, esperado):
        assert _calcular_franja(hora) == esperado

    def test_pesos_costo_equilibrado_suman_uno(self):
        total = sum(PESOS_COSTO_EQUILIBRADO.values())
        assert total == pytest.approx(1.0)
