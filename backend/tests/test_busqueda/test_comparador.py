"""Tests unitarios para src/busqueda/comparador.py."""

import pytest

from src.busqueda.comparador import comparar_algoritmos
from src.busqueda.registro import crear_algoritmos
from src.busqueda.ucs import BusquedaCostoUniforme


@pytest.fixture
def algoritmos():
    return crear_algoritmos()


class TestComparadorAlgoritmos:
    def test_compara_todos_los_registrados(self, grafo_diamante, algoritmos):
        comparacion = comparar_algoritmos(grafo_diamante, "O", "D", "menor_tiempo", algoritmos)

        assert [r.algoritmo for r in comparacion.resultados] == list(algoritmos)
        assert comparacion.origen == "O"
        assert comparacion.destino == "D"
        assert comparacion.criterio == "menor_tiempo"
        assert comparacion.mejor_costo == 4.0
        assert comparacion.mejor_algoritmo in comparacion.optimos
        assert {"ucs", "a_estrella"} <= set(comparacion.optimos)
        assert {"ucs", "a_estrella"} <= set(comparacion.optimos)
        assert "voraz" not in comparacion.optimos

    def test_voraz_puede_quedar_por_debajo_del_optimo(self, grafo_diamante, algoritmos):
        comparacion = comparar_algoritmos(grafo_diamante, "O", "D", "menor_tiempo", algoritmos)
        voraz = next(r for r in comparacion.resultados if r.algoritmo == "voraz")

        assert voraz.costo_total == 9.0
        assert voraz.costo_total > comparacion.mejor_costo

    @pytest.mark.parametrize("criterio", ["menor_tiempo", "menor_distancia", "menor_conexiones"])
    def test_ucs_y_astar_empatan_en_el_optimo(self, grafo_diamante, algoritmos, criterio):
        comparacion = comparar_algoritmos(grafo_diamante, "O", "D", criterio, algoritmos)

        assert {"ucs", "a_estrella"} <= set(comparacion.optimos)

    def test_sin_ruta_no_hay_mejor(self, grafo_inconexo, algoritmos):
        comparacion = comparar_algoritmos(grafo_inconexo, "O", "Y", "menor_tiempo", algoritmos)

        assert comparacion.resultados
        assert all(not resultado.ruta_encontrada for resultado in comparacion.resultados)
        assert comparacion.mejor_algoritmo is None
        assert comparacion.mejor_costo is None
        assert comparacion.optimos == []

    def test_metricas_presentes(self, grafo_diamante, algoritmos):
        comparacion = comparar_algoritmos(grafo_diamante, "O", "D", "menor_tiempo", algoritmos)

        for resultado in comparacion.resultados:
            assert resultado.tiempo_ejecucion_ms >= 0
            assert resultado.detalle["num_aristas"] > 0
            assert resultado.distancia_total_m > 0

    def test_criterio_invalido_lanza_error(self, grafo_diamante, algoritmos):
        with pytest.raises(ValueError):
            comparar_algoritmos(grafo_diamante, "O", "D", "ruta_equilibrada", algoritmos)

    def test_nodo_inexistente_lanza_error(self, grafo_diamante, algoritmos):
        with pytest.raises(ValueError):
            comparar_algoritmos(grafo_diamante, "O", "NO_EXISTE", "menor_tiempo", algoritmos)

    def test_registro_vacio_lanza_error(self, grafo_diamante):
        with pytest.raises(ValueError):
            comparar_algoritmos(grafo_diamante, "O", "D", "menor_tiempo", {})

    def test_registro_con_un_solo_algoritmo(self, grafo_diamante):
        comparacion = comparar_algoritmos(
            grafo_diamante,
            "O",
            "D",
            "menor_tiempo",
            {"ucs": BusquedaCostoUniforme()},
        )

        assert len(comparacion.resultados) == 1
        assert comparacion.mejor_algoritmo == "ucs"
        assert comparacion.optimos == ["ucs"]

    def test_crear_algoritmos_devuelve_instancias_nuevas(self):
        assert crear_algoritmos() is not crear_algoritmos()
        assert set(crear_algoritmos()) == {"voraz", "ucs", "a_estrella", "dfs"}
