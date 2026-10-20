"""Tests unitarios para src/busqueda/bfs.py."""

import pytest

from src.busqueda.bfs import BusquedaAmplitud
from src.busqueda.ucs import BusquedaCostoUniforme
from tests.conftest import construir_grafo, crear_arista


@pytest.fixture
def busqueda_bfs() -> BusquedaAmplitud:
    return BusquedaAmplitud()


class TestBusquedaAmplitud:
    def test_elige_la_ruta_con_menos_aristas(self, busqueda_bfs, grafo_diamante):
        # BFS ignora el tiempo: toma O→D directo aunque sea la más lenta.
        resultado = busqueda_bfs.buscar(grafo_diamante, "O", "D", "menor_tiempo")

        assert resultado.ruta_encontrada
        assert resultado.camino == ["O", "D"]
        assert resultado.aristas_camino == ["directa"]
        assert resultado.costo_total == 9.0
        assert resultado.detalle["num_aristas"] == 1

    def test_el_criterio_no_cambia_el_camino(self, busqueda_bfs, grafo_diamante):
        caminos = {
            criterio: busqueda_bfs.buscar(grafo_diamante, "O", "D", criterio).camino
            for criterio in ("menor_tiempo", "menor_distancia", "menor_conexiones")
        }

        assert set(map(tuple, caminos.values())) == {("O", "D")}

    def test_reporta_costo_en_la_unidad_del_criterio(self, busqueda_bfs, grafo_diamante):
        distancia = busqueda_bfs.buscar(grafo_diamante, "O", "D", "menor_distancia")
        conexiones = busqueda_bfs.buscar(grafo_diamante, "O", "D", "menor_conexiones")

        assert distancia.costo_total == 900.0
        assert conexiones.costo_total == 1.0

    def test_coincide_con_ucs_en_menor_conexiones(self, busqueda_bfs, grafo_ramal_largo):
        bfs = busqueda_bfs.buscar(grafo_ramal_largo, "M0", "D", "menor_conexiones")
        ucs = BusquedaCostoUniforme().buscar(grafo_ramal_largo, "M0", "D", "menor_conexiones")

        assert bfs.costo_total == ucs.costo_total == 11.0
        assert bfs.camino == ucs.camino

    def test_ruta_lineal(self, busqueda_bfs, grafo_lineal):
        resultado = busqueda_bfs.buscar(grafo_lineal, "N1", "N3", "menor_tiempo")

        assert resultado.camino == ["N1", "N2", "N3"]
        assert resultado.costo_total == 18.0
        assert resultado.distancia_total_m == 1800.0
        assert resultado.tiempo_total_min == 18.0

    def test_ignora_aristas_no_disponibles(self, busqueda_bfs, grafo_con_bloqueo):
        resultado = busqueda_bfs.buscar(grafo_con_bloqueo, "O", "D")

        assert resultado.ruta_encontrada
        assert resultado.aristas_camino == ["desvio-1", "desvio-2"]

    def test_grafo_inconexo_no_encuentra_ruta(self, busqueda_bfs, grafo_inconexo):
        resultado = busqueda_bfs.buscar(grafo_inconexo, "O", "Y")

        assert not resultado.ruta_encontrada
        assert resultado.camino == []
        assert resultado.aristas_camino == []
        assert resultado.costo_total == 0.0
        assert resultado.nodos_explorados == 2
        assert resultado.detalle["mensaje"]

    def test_origen_igual_destino(self, busqueda_bfs, grafo_lineal):
        resultado = busqueda_bfs.buscar(grafo_lineal, "N2", "N2")

        assert resultado.ruta_encontrada
        assert resultado.camino == ["N2"]
        assert resultado.nodos_explorados == 0
        assert resultado.detalle["mensaje"] == "Origen y destino son el mismo nodo"

    def test_criterio_invalido_lanza_error(self, busqueda_bfs, grafo_lineal):
        with pytest.raises(ValueError):
            busqueda_bfs.buscar(grafo_lineal, "N1", "N3", criterio="ruta_equilibrada")

    def test_nodo_inexistente_lanza_error(self, busqueda_bfs, grafo_lineal):
        with pytest.raises(ValueError):
            busqueda_bfs.buscar(grafo_lineal, "N1", "NO_EXISTE")

    def test_explora_por_niveles(self, busqueda_bfs):
        # O tiene 3 hijos (nivel 1); D está en el nivel 2 bajo el último hijo.
        # BFS debe expandir O y los 3 hijos antes de generar D.
        grafo = construir_grafo(
            {
                "O": (4.60, -74.00),
                "A": (4.61, -74.00),
                "B": (4.62, -74.00),
                "C": (4.63, -74.00),
                "A2": (4.61, -74.01),
                "D": (4.63, -74.01),
            },
            [
                crear_arista("O", "A", tiempo=1.0, dist=100.0),
                crear_arista("O", "B", tiempo=1.0, dist=100.0),
                crear_arista("O", "C", tiempo=1.0, dist=100.0),
                crear_arista("A", "A2", tiempo=1.0, dist=100.0),
                crear_arista("C", "D", tiempo=1.0, dist=100.0),
            ],
        )

        resultado = busqueda_bfs.buscar(grafo, "O", "D")

        assert resultado.camino == ["O", "C", "D"]
        assert resultado.nodos_explorados == 4
        assert resultado.detalle["max_frontera"] >= 3

    def test_no_se_atasca_en_ciclos(self, busqueda_bfs):
        grafo = construir_grafo(
            {"O": (4.60, -74.00), "A": (4.61, -74.00), "D": (4.62, -74.00)},
            [
                crear_arista("O", "A", tiempo=1.0, dist=100.0),
                crear_arista("A", "O", tiempo=1.0, dist=100.0),
                crear_arista("A", "D", tiempo=1.0, dist=100.0),
            ],
        )

        resultado = busqueda_bfs.buscar(grafo, "O", "D")

        assert resultado.camino == ["O", "A", "D"]

    def test_reporta_metricas_de_ejecucion(self, busqueda_bfs, grafo_lineal):
        resultado = busqueda_bfs.buscar(grafo_lineal, "N1", "N3")

        assert resultado.algoritmo == "bfs"
        assert resultado.tiempo_ejecucion_ms >= 0
        assert resultado.nodos_explorados >= 1
        assert resultado.detalle["nodos_alcanzados"] == 3
