"""Tests unitarios para src/busqueda/a_estrella.py."""

import pytest

from src.busqueda.a_estrella import BusquedaAEstrella
from src.busqueda.ucs import BusquedaCostoUniforme
from src.busqueda.voraz import BusquedaVoraz
from tests.conftest import construir_grafo, crear_arista


@pytest.fixture
def busqueda_astar() -> BusquedaAEstrella:
    return BusquedaAEstrella()


class TestBusquedaAEstrella:
    def test_encuentra_la_ruta_mas_rapida(self, busqueda_astar, grafo_diamante):
        resultado = busqueda_astar.buscar(grafo_diamante, "O", "D", "menor_tiempo")

        assert resultado.ruta_encontrada
        assert resultado.camino == ["O", "A", "D"]
        assert resultado.aristas_camino == ["rapida-1", "rapida-2"]
        assert resultado.costo_total == 4.0
        assert resultado.detalle["heuristica"] == "admisible_geografica"

    @pytest.mark.parametrize("criterio", ["menor_tiempo", "menor_distancia", "menor_conexiones"])
    def test_coincide_con_ucs_en_todos_los_criterios(
        self, busqueda_astar, grafo_diamante, criterio
    ):
        referencia = BusquedaCostoUniforme().buscar(grafo_diamante, "O", "D", criterio)
        resultado = busqueda_astar.buscar(grafo_diamante, "O", "D", criterio)

        assert resultado.camino == referencia.camino
        assert resultado.costo_total == referencia.costo_total

    def test_explora_menos_nodos_que_ucs(self, busqueda_astar, grafo_ramal_largo):
        referencia = BusquedaCostoUniforme().buscar(grafo_ramal_largo, "M0", "D")
        resultado = busqueda_astar.buscar(grafo_ramal_largo, "M0", "D")

        assert resultado.camino == referencia.camino
        assert resultado.costo_total == referencia.costo_total
        assert resultado.nodos_explorados < referencia.nodos_explorados

    def test_supera_al_voraz_en_optimalidad(self, busqueda_astar, grafo_diamante):
        voraz = BusquedaVoraz().buscar(grafo_diamante, "O", "D", "menor_tiempo")
        optimo = busqueda_astar.buscar(grafo_diamante, "O", "D", "menor_tiempo")

        assert voraz.camino == ["O", "D"]
        assert optimo.camino == ["O", "A", "D"]
        assert optimo.costo_total < voraz.costo_total

    def test_heuristica_nula_se_comporta_como_ucs(self, grafo_ramal_largo):
        referencia = BusquedaCostoUniforme().buscar(grafo_ramal_largo, "M0", "D")
        sin_heuristica = BusquedaAEstrella(heuristica=lambda grafo, nodo, contexto: 0.0).buscar(
            grafo_ramal_largo, "M0", "D"
        )

        assert sin_heuristica.camino == referencia.camino
        assert sin_heuristica.costo_total == referencia.costo_total
        assert sin_heuristica.nodos_explorados == referencia.nodos_explorados
        assert sin_heuristica.detalle["heuristica"] == "personalizada"

    def test_ignora_aristas_no_disponibles(self, busqueda_astar, grafo_con_bloqueo):
        resultado = busqueda_astar.buscar(grafo_con_bloqueo, "O", "D", "menor_tiempo")

        assert resultado.ruta_encontrada
        assert resultado.camino == ["O", "A", "D"]
        assert resultado.aristas_camino == ["desvio-1", "desvio-2"]

    def test_grafo_inconexo_no_encuentra_ruta(self, busqueda_astar, grafo_inconexo):
        resultado = busqueda_astar.buscar(grafo_inconexo, "O", "Y")

        assert not resultado.ruta_encontrada
        assert resultado.camino == []
        assert resultado.detalle["mensaje"]

    def test_origen_igual_destino(self, busqueda_astar, grafo_lineal):
        resultado = busqueda_astar.buscar(grafo_lineal, "N2", "N2")

        assert resultado.ruta_encontrada
        assert resultado.camino == ["N2"]
        assert resultado.costo_total == 0.0

    def test_criterio_invalido_lanza_error(self, busqueda_astar, grafo_lineal):
        with pytest.raises(ValueError):
            busqueda_astar.buscar(grafo_lineal, "N1", "N3", criterio="ruta_equilibrada")

    def test_aristas_paralelas_elige_la_mas_barata(self, busqueda_astar):
        grafo = construir_grafo(
            {"O": (4.60, -74.00), "D": (4.61, -74.00)},
            [
                crear_arista("O", "D", tiempo=1.0, dist=100.0, arista_id="rapida"),
                crear_arista("O", "D", tiempo=10.0, dist=1000.0, arista_id="lenta"),
            ],
        )

        resultado = busqueda_astar.buscar(grafo, "O", "D", "menor_tiempo")

        assert resultado.aristas_camino == ["rapida"]
        assert resultado.costo_total == 1.0

    def test_reporta_metricas_de_ejecucion(self, busqueda_astar, grafo_lineal):
        resultado = busqueda_astar.buscar(grafo_lineal, "N1", "N3")

        assert resultado.algoritmo == "a_estrella"
        assert resultado.tiempo_ejecucion_ms >= 0
        assert resultado.nodos_explorados >= 1
