"""Tests unitarios para src/busqueda/ucs.py."""

import pytest

from src.busqueda.ucs import BusquedaCostoUniforme
from tests.conftest import construir_grafo, crear_arista


@pytest.fixture
def busqueda_ucs() -> BusquedaCostoUniforme:
    return BusquedaCostoUniforme()


class TestBusquedaCostoUniforme:
    def test_encuentra_la_ruta_mas_rapida(self, busqueda_ucs, grafo_diamante):
        resultado = busqueda_ucs.buscar(grafo_diamante, "O", "D", "menor_tiempo")

        assert resultado.ruta_encontrada
        assert resultado.camino == ["O", "A", "D"]
        assert resultado.aristas_camino == ["rapida-1", "rapida-2"]
        assert resultado.costo_total == 4.0
        assert resultado.tiempo_total_min == 4.0
        assert resultado.distancia_total_m == 1200.0
        assert resultado.detalle["num_aristas"] == 2

    def test_criterio_distancia_elige_la_ruta_mas_corta(self, busqueda_ucs, grafo_diamante):
        resultado = busqueda_ucs.buscar(grafo_diamante, "O", "D", "menor_distancia")

        assert resultado.ruta_encontrada
        assert resultado.camino == ["O", "D"]
        assert resultado.costo_total == 900.0
        assert resultado.distancia_total_m == 900.0
        assert resultado.tiempo_total_min == 9.0

    def test_criterio_conexiones_prefiere_menos_aristas(self, busqueda_ucs, grafo_diamante):
        resultado = busqueda_ucs.buscar(grafo_diamante, "O", "D", "menor_conexiones")

        assert resultado.ruta_encontrada
        assert resultado.camino == ["O", "D"]
        assert resultado.costo_total == 1.0
        assert resultado.detalle["num_aristas"] == 1

    def test_ruta_lineal(self, busqueda_ucs, grafo_lineal):
        resultado = busqueda_ucs.buscar(grafo_lineal, "N1", "N3", "menor_tiempo")

        assert resultado.camino == ["N1", "N2", "N3"]
        assert resultado.costo_total == 18.0
        assert resultado.distancia_total_m == 1800.0

    def test_ignora_aristas_no_disponibles(self, busqueda_ucs, grafo_con_bloqueo):
        resultado = busqueda_ucs.buscar(grafo_con_bloqueo, "O", "D", "menor_tiempo")

        assert resultado.ruta_encontrada
        assert resultado.camino == ["O", "A", "D"]
        assert resultado.aristas_camino == ["desvio-1", "desvio-2"]
        assert resultado.costo_total == 10.0

    def test_grafo_inconexo_no_encuentra_ruta(self, busqueda_ucs, grafo_inconexo):
        resultado = busqueda_ucs.buscar(grafo_inconexo, "O", "Y")

        assert not resultado.ruta_encontrada
        assert resultado.camino == []
        assert resultado.aristas_camino == []
        assert resultado.costo_total == 0.0
        assert resultado.detalle["mensaje"]

    def test_origen_igual_destino(self, busqueda_ucs, grafo_lineal):
        resultado = busqueda_ucs.buscar(grafo_lineal, "N2", "N2")

        assert resultado.ruta_encontrada
        assert resultado.camino == ["N2"]
        assert resultado.costo_total == 0.0
        assert resultado.detalle["mensaje"] == "Origen y destino son el mismo nodo"

    def test_criterio_invalido_lanza_error(self, busqueda_ucs, grafo_lineal):
        with pytest.raises(ValueError):
            busqueda_ucs.buscar(grafo_lineal, "N1", "N3", criterio="ruta_equilibrada")

    def test_nodo_inexistente_lanza_error(self, busqueda_ucs, grafo_lineal):
        with pytest.raises(ValueError):
            busqueda_ucs.buscar(grafo_lineal, "N1", "NO_EXISTE")

    def test_aristas_paralelas_elige_la_mas_barata(self, busqueda_ucs):
        grafo = construir_grafo(
            {"O": (4.60, -74.00), "D": (4.61, -74.00)},
            [
                crear_arista("O", "D", tiempo=1.0, dist=100.0, arista_id="rapida"),
                crear_arista("O", "D", tiempo=10.0, dist=1000.0, arista_id="lenta"),
            ],
        )

        resultado = busqueda_ucs.buscar(grafo, "O", "D", "menor_tiempo")

        assert resultado.aristas_camino == ["rapida"]
        assert resultado.costo_total == 1.0

    def test_usa_solo_aristas_disponibles_entre_paralelas(self, busqueda_ucs):
        grafo = construir_grafo(
            {"O": (4.60, -74.00), "D": (4.61, -74.00)},
            [
                crear_arista(
                    "O", "D", tiempo=1.0, dist=100.0, arista_id="cortada", disponible=False
                ),
                crear_arista("O", "D", tiempo=10.0, dist=1000.0, arista_id="abierta"),
            ],
        )

        resultado = busqueda_ucs.buscar(grafo, "O", "D", "menor_tiempo")

        assert resultado.aristas_camino == ["abierta"]
        assert resultado.costo_total == 10.0

    def test_explora_todos_los_nodos_del_ramal(self, busqueda_ucs, grafo_ramal_largo):
        resultado = busqueda_ucs.buscar(grafo_ramal_largo, "M0", "D", "menor_tiempo")

        assert resultado.ruta_encontrada
        assert resultado.costo_total == 11.0
        # El ramal Z1..Z5 tiene costo acumulado menor que la ruta óptima,
        # por lo que UCS lo expande antes de cerrar el destino.
        assert resultado.nodos_explorados >= 15

    def test_reporta_metricas_de_ejecucion(self, busqueda_ucs, grafo_lineal):
        resultado = busqueda_ucs.buscar(grafo_lineal, "N1", "N3")

        assert resultado.algoritmo == "ucs"
        assert resultado.tiempo_ejecucion_ms >= 0
        assert resultado.nodos_explorados >= 1
