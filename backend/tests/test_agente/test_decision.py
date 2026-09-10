"""Tests unitarios para src/agente/acciones.py y decision.py"""

from datetime import datetime

import pytest

from src.agente.acciones import (
    ContextoAccion,
    TipoAccion,
    construir_accion_avanzar,
    construir_accion_esperar,
    construir_accion_finalizar,
    construir_accion_recalcular,
    decidir_accion,
    obtener_acciones_posibles,
    seleccionar_arista_criterio,
)
from src.agente.decision import EstadoDecision, MotorDecision
from src.agente.peas import Ambiente, CriterioOptimizacion, Percepcion
from src.grafo.modelos import (
    Arista,
    AtributosArista,
    Coordenadas,
    Grafo,
    NivelCongestion,
    Nodo,
)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _nodo(nid: str, lat: float = 4.6) -> Nodo:
    return Nodo(
        id=nid, nombre=f"Int. {nid}",
        coordenadas=Coordenadas(latitud=lat, longitud=-74.0),
    )


def _arista(oid: str, did: str, tiempo: float = 5.0, dist: float = 1000.0, congestion=NivelCongestion.BAJA, via: str = "Calle 1") -> Arista:
    atrib = AtributosArista(nombre_via=via)
    return Arista(
        id=f"{oid}-{did}", origen=oid, destino=did,
        distancia=dist, tiempo_estimado=tiempo,
        congestion=congestion, atributos=atrib,
    )


@pytest.fixture
def grafo_basico():
    """N1 → N2 → N3, N1 → N3 (directa lenta)."""
    g = Grafo()
    for nid in ["N1", "N2", "N3"]:
        g.agregar_nodo(_nodo(nid))
    g.agregar_arista(_arista("N1", "N2", tiempo=5.0, dist=500.0))
    g.agregar_arista(_arista("N2", "N3", tiempo=5.0, dist=700.0))
    g.agregar_arista(_arista("N1", "N3", tiempo=20.0, dist=2000.0))
    return g


@pytest.fixture
def ambiente_basico(grafo_basico):
    return Ambiente(grafo=grafo_basico, fecha=datetime.now(), hora="08:00")


@pytest.fixture
def percepcion_basica(ambiente_basico):
    return Percepcion(
        nodo_origen="N1",
        nodo_destino="N3",
        fecha=datetime.now(),
        hora="08:00",
        criterio=CriterioOptimizacion.MENOR_TIEMPO,
        nodo_actual="N1",
    )


@pytest.fixture
def contexto_basico(percepcion_basica, ambiente_basico):
    return ContextoAccion(percepcion=percepcion_basica, ambiente=ambiente_basico)


# ─── Tests constructores de acciones ─────────────────────────────────────────

class TestConstructoresAccion:
    def test_construir_avanzar(self, grafo_basico):
        arista = grafo_basico.obtener_arista("N1", "N2")
        accion = construir_accion_avanzar(arista)
        assert accion.tipo == TipoAccion.AVANZAR.value
        assert accion.nodo_destino == "N2"
        assert accion.tiempo_estimado == pytest.approx(5.0)
        assert accion.distancia == pytest.approx(500.0)

    def test_construir_esperar(self):
        accion = construir_accion_esperar("N1", "incidente en ruta")
        assert accion.tipo == TipoAccion.ESPERAR.value
        assert accion.tiempo_estimado > 0
        assert "incidente en ruta" in accion.descripcion

    def test_construir_recalcular(self):
        accion = construir_accion_recalcular("N2", "ciclo detectado")
        assert accion.tipo == TipoAccion.RECALCULAR.value

    def test_construir_finalizar(self):
        accion = construir_accion_finalizar("N3")
        assert accion.tipo == TipoAccion.FINALIZAR.value
        assert "N3" in accion.descripcion


# ─── Tests seleccionar_arista_criterio ───────────────────────────────────────

class TestSeleccionarArista:
    def test_menor_tiempo_selecciona_rapida(self, grafo_basico):
        aristas = grafo_basico.obtener_vecinos("N1")
        mejor = seleccionar_arista_criterio(aristas, "menor_tiempo", [])
        assert mejor is not None
        assert mejor.destino == "N2"  # 5 min < 20 min

    def test_menor_distancia_selecciona_corta(self, grafo_basico):
        aristas = grafo_basico.obtener_vecinos("N1")
        mejor = seleccionar_arista_criterio(aristas, "menor_distancia", [])
        assert mejor is not None
        assert mejor.destino == "N2"  # 500 m < 2000 m

    def test_evita_nodos_visitados(self, grafo_basico):
        aristas = grafo_basico.obtener_vecinos("N1")
        # Marcar N2 como visitado
        mejor = seleccionar_arista_criterio(aristas, "menor_tiempo", ["N2"])
        assert mejor is not None
        assert mejor.destino == "N3"  # única opción no visitada

    def test_retorna_none_si_no_hay_candidatas(self):
        resultado = seleccionar_arista_criterio([], "menor_tiempo", [])
        assert resultado is None

    def test_menor_conexiones_elige_la_mas_rapida(self):
        g = Grafo()
        for nid in ["A", "B", "C"]:
            g.agregar_nodo(_nodo(nid))
        g.agregar_arista(_arista("A", "B", tiempo=3.0, dist=800.0))
        g.agregar_arista(_arista("A", "C", tiempo=5.0, dist=600.0))

        aristas = g.obtener_vecinos("A")
        mejor = seleccionar_arista_criterio(aristas, "menor_conexiones", [])
        assert mejor is not None
        assert mejor.destino == "B"  # desempate por tiempo


# ─── Tests decidir_accion ─────────────────────────────────────────────────────

class TestDecidirAccion:
    def test_finaliza_si_en_destino(self, percepcion_basica, ambiente_basico):
        percepcion_basica.nodo_actual = "N3"  # ya en destino
        ctx = ContextoAccion(percepcion=percepcion_basica, ambiente=ambiente_basico)
        accion = decidir_accion(ctx)
        assert accion.tipo == TipoAccion.FINALIZAR.value

    def test_avanza_si_hay_conexiones(self, contexto_basico):
        accion = decidir_accion(contexto_basico)
        assert accion.tipo == TipoAccion.AVANZAR.value

    def test_espera_si_sin_conexiones(self, percepcion_basica):
        g = Grafo()
        g.agregar_nodo(_nodo("X"))
        g.agregar_nodo(_nodo("Y"))
        # Sin aristas
        percepcion_basica.nodo_actual = "X"
        percepcion_basica.nodo_destino = "Y"
        amb = Ambiente(grafo=g, fecha=datetime.now(), hora="08:00")
        ctx = ContextoAccion(percepcion=percepcion_basica, ambiente=amb, max_espera=2)
        accion = decidir_accion(ctx)
        assert accion.tipo == TipoAccion.ESPERAR.value

    def test_recalcula_tras_max_espera(self, percepcion_basica):
        g = Grafo()
        g.agregar_nodo(_nodo("X"))
        g.agregar_nodo(_nodo("Y"))
        percepcion_basica.nodo_actual = "X"
        percepcion_basica.nodo_destino = "Y"
        amb = Ambiente(grafo=g, fecha=datetime.now(), hora="08:00")
        ctx = ContextoAccion(percepcion=percepcion_basica, ambiente=amb, max_espera=1, pasos_espera=1)
        accion = decidir_accion(ctx)
        assert accion.tipo == TipoAccion.RECALCULAR.value


# ─── Tests MotorDecision ──────────────────────────────────────────────────────

class TestMotorDecision:
    def test_crear_motor_desde_parametros(self, grafo_basico):
        motor = MotorDecision.desde_parametros(grafo=grafo_basico, origen="N1", destino="N3")
        assert motor is not None
        assert motor.modelo.percepcion.nodo_actual == "N1"

    def test_ejecutar_paso_avanza(self, grafo_basico):
        motor = MotorDecision.desde_parametros(grafo=grafo_basico, origen="N1", destino="N3")
        resultado = motor.ejecutar_paso()
        assert resultado.paso == 1
        assert resultado.estado in [
            EstadoDecision.EN_CURSO,
            EstadoDecision.DESTINO_ALCANZADO,
        ]

    def test_ejecutar_completo_llega_a_destino(self, grafo_basico):
        motor = MotorDecision.desde_parametros(
            grafo=grafo_basico, origen="N1", destino="N3",
            criterio=CriterioOptimizacion.MENOR_TIEMPO,
        )
        resultados = motor.ejecutar_completo(max_pasos=10)
        estados_finales = [r.estado for r in resultados]
        assert EstadoDecision.DESTINO_ALCANZADO in estados_finales

    def test_resumen_contiene_campos_requeridos(self, grafo_basico):
        motor = MotorDecision.desde_parametros(grafo=grafo_basico, origen="N1", destino="N3")
        motor.ejecutar_paso()
        resumen = motor.obtener_resumen()
        for clave in ["paso_actual", "nodo_actual", "ruta_construida", "medida_desempeno"]:
            assert clave in resumen


# ─── Tests obtener_acciones_posibles ─────────────────────────────────────────

class TestObtenerAccionesPosibles:
    def test_retorna_lista_de_acciones(self, grafo_basico, ambiente_basico):
        acciones = obtener_acciones_posibles("N1", ambiente_basico, [])
        assert isinstance(acciones, list)
        assert len(acciones) >= 2  # N1→N2 y N1→N3

    def test_acciones_tienen_campos_requeridos(self, grafo_basico, ambiente_basico):
        acciones = obtener_acciones_posibles("N1", ambiente_basico, [])
        for a in acciones:
            for campo in ["tipo", "destino", "tiempo_estimado", "estado", "distancia"]:
                assert campo in a

    def test_nodo_visitado_marcado_como_tal(self, grafo_basico, ambiente_basico):
        acciones = obtener_acciones_posibles("N1", ambiente_basico, ["N2"])
        estados = {a["destino"]: a["estado"] for a in acciones}
        assert estados.get("N2") == "visitado"
