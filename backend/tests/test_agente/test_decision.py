"""Tests unitarios para src/agente/acciones.py y decision.py"""

import pytest
from datetime import datetime
from src.agente.peas import CriterioOptimizacion, Ambiente, Percepcion, crear_peas_inicial
from src.agente.acciones import (
    TipoAccion, ContextoAccion,
    construir_accion_avanzar, construir_accion_transbordo,
    construir_accion_esperar, construir_accion_recalcular,
    construir_accion_finalizar, seleccionar_arista_criterio,
    decidir_accion, obtener_acciones_posibles,
)
from src.agente.decision import MotorDecision, EstadoDecision
from src.grafo.modelos import (
    Grafo, Nodo, Arista, Coordenadas, TipoNodo,
    NivelCongestion, AtributosArista,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _nodo(nid: str, lat: float = 4.6) -> Nodo:
    return Nodo(
        id=nid, nombre=f"Est. {nid}",
        coordenadas=Coordenadas(latitud=lat, longitud=-74.0),
    )


def _arista(oid: str, did: str, tiempo: float = 5.0, congestion=NivelCongestion.BAJA, linea: str = "L1") -> Arista:
    atrib = AtributosArista(nombre_via=linea)
    return Arista(
        id=f"{oid}-{did}", origen=oid, destino=did,
        distancia=1000.0, tiempo_estimado=tiempo,
        congestion=congestion, atributos=atrib,
    )


@pytest.fixture
def grafo_basico():
    """N1 → N2 → N3, N1 → N3 (directa lenta)."""
    g = Grafo()
    for nid in ["N1", "N2", "N3"]:
        g.agregar_nodo(_nodo(nid))
    g.agregar_arista(_arista("N1", "N2", tiempo=5.0))
    g.agregar_arista(_arista("N2", "N3", tiempo=5.0))
    g.agregar_arista(_arista("N1", "N3", tiempo=20.0))
    return g


@pytest.fixture
def ambiente_basico(grafo_basico):
    return Ambiente(grafo=grafo_basico, fecha=datetime.now(), hora="08:00", franja_horaria="08:00-08:15")


@pytest.fixture
def percepcion_basica(ambiente_basico):
    return Percepcion(
        estacion_origen="N1",
        estacion_destino="N3",
        fecha=datetime.now(),
        hora="08:00",
        criterio=CriterioOptimizacion.MENOR_TIEMPO,
        estacion_actual="N1",
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
        assert accion.estacion_destino == "N2"
        assert accion.es_transbordo is False
        assert accion.tiempo_estimado == pytest.approx(5.0)

    def test_construir_transbordo(self):
        accion = construir_accion_transbordo("N2", "L2", "L1")
        assert accion.tipo == TipoAccion.TRANSBORDAR.value
        assert accion.es_transbordo is True
        assert accion.servicio == "L2"
        assert "L1" in accion.descripcion
        assert "L2" in accion.descripcion

    def test_construir_transbordo_sin_servicio_actual(self):
        accion = construir_accion_transbordo("N2", "L2", None)
        assert accion.tipo == TipoAccion.TRANSBORDAR.value
        assert "L2" in accion.descripcion

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

    def test_evita_nodos_visitados(self, grafo_basico):
        aristas = grafo_basico.obtener_vecinos("N1")
        # Marcar N2 como visitado
        mejor = seleccionar_arista_criterio(aristas, "menor_tiempo", ["N2"])
        assert mejor is not None
        assert mejor.destino == "N3"  # única opción no visitada

    def test_retorna_none_si_no_hay_candidatas(self):
        resultado = seleccionar_arista_criterio([], "menor_tiempo", [])
        assert resultado is None

    def test_menor_demanda_evita_alta_congestion(self):
        g = Grafo()
        for nid in ["A", "B", "C"]:
            g.agregar_nodo(_nodo(nid))
        g.agregar_arista(_arista("A", "B", tiempo=3.0, congestion=NivelCongestion.ALTA))
        g.agregar_arista(_arista("A", "C", tiempo=5.0, congestion=NivelCongestion.BAJA))

        aristas = g.obtener_vecinos("A")
        mejor = seleccionar_arista_criterio(aristas, "menor_demanda", [])
        assert mejor is not None
        assert mejor.destino == "C"  # baja congestión preferida


# ─── Tests decidir_accion ─────────────────────────────────────────────────────

class TestDecidirAccion:
    def test_finaliza_si_en_destino(self, percepcion_basica, ambiente_basico):
        percepcion_basica.estacion_actual = "N3"  # ya en destino
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
        percepcion_basica.estacion_actual = "X"
        percepcion_basica.estacion_destino = "Y"
        amb = Ambiente(grafo=g, fecha=datetime.now(), hora="08:00", franja_horaria="08:00-08:15")
        ctx = ContextoAccion(percepcion=percepcion_basica, ambiente=amb, max_espera=2)
        accion = decidir_accion(ctx)
        assert accion.tipo == TipoAccion.ESPERAR.value

    def test_recalcula_tras_max_espera(self, percepcion_basica):
        g = Grafo()
        g.agregar_nodo(_nodo("X"))
        g.agregar_nodo(_nodo("Y"))
        percepcion_basica.estacion_actual = "X"
        percepcion_basica.estacion_destino = "Y"
        amb = Ambiente(grafo=g, fecha=datetime.now(), hora="08:00", franja_horaria="08:00-08:15")
        ctx = ContextoAccion(percepcion=percepcion_basica, ambiente=amb, max_espera=1, pasos_espera=1)
        accion = decidir_accion(ctx)
        assert accion.tipo == TipoAccion.RECALCULAR.value


# ─── Tests MotorDecision ──────────────────────────────────────────────────────

class TestMotorDecision:
    def test_crear_motor_desde_parametros(self, grafo_basico):
        motor = MotorDecision.desde_parametros(grafo=grafo_basico, origen="N1", destino="N3")
        assert motor is not None
        assert motor.modelo.percepcion.estacion_actual == "N1"

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
        for clave in ["paso_actual", "estacion_actual", "ruta_construida", "medida_desempeno"]:
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
            for campo in ["tipo", "destino", "tiempo_estimado", "estado"]:
                assert campo in a

    def test_nodo_visitado_marcado_como_tal(self, grafo_basico, ambiente_basico):
        acciones = obtener_acciones_posibles("N1", ambiente_basico, ["N2"])
        estados = {a["destino"]: a["estado"] for a in acciones}
        assert estados.get("N2") == "visitado"
