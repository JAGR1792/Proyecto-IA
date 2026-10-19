"""Tests unitarios para src/heuristicas/admisible.py."""

import pytest

from src.busqueda.base import costo_arista
from src.busqueda.ucs import BusquedaCostoUniforme
from src.grafo.modelos import Grafo
from src.heuristicas.admisible import (
    NOMBRE_HEURISTICA,
    ContextoHeuristico,
    estimar_costo_restante,
    preparar_contexto,
    velocidad_maxima_ms,
)

CRITERIOS = ["menor_tiempo", "menor_distancia", "menor_conexiones"]


class TestVelocidadMaxima:
    def test_grafo_vacio_devuelve_uno(self):
        assert velocidad_maxima_ms(Grafo()) == 1.0

    def test_usa_el_mayor_entre_velocidad_declarada_e_implicita(self, grafo_diamante):
        # O→A: 600 m en 2 min = 5 m/s; la velocidad declarada es 40 km/h ≈ 11.1 m/s.
        assert velocidad_maxima_ms(grafo_diamante) == pytest.approx(40 / 3.6)

    def test_ignora_aristas_no_disponibles(self, grafo_con_bloqueo):
        # La arista cortada declara 40 km/h, pero las demás son las únicas válidas.
        assert velocidad_maxima_ms(grafo_con_bloqueo) == pytest.approx(40 / 3.6)


class TestContexto:
    def test_prepara_el_contexto_de_tiempo(self, grafo_diamante):
        contexto = preparar_contexto(grafo_diamante, "D", "menor_tiempo")

        assert isinstance(contexto, ContextoHeuristico)
        assert contexto.destino == "D"
        assert contexto.criterio == "menor_tiempo"
        assert contexto.velocidad_maxima_ms == pytest.approx(40 / 3.6)
        assert contexto.nombre == NOMBRE_HEURISTICA

    def test_criterio_invalido_lanza_error(self, grafo_diamante):
        with pytest.raises(ValueError):
            preparar_contexto(grafo_diamante, "D", "ruta_equilibrada")


class TestEstimacion:
    def test_estimacion_cero_en_el_destino(self, grafo_diamante):
        contexto = preparar_contexto(grafo_diamante, "D", "menor_distancia")

        assert estimar_costo_restante(grafo_diamante, "D", contexto) == 0.0

    def test_conexiones_estima_al_menos_una_arista(self, grafo_diamante):
        contexto = preparar_contexto(grafo_diamante, "D", "menor_conexiones")

        assert estimar_costo_restante(grafo_diamante, "O", contexto) == 1.0
        assert estimar_costo_restante(grafo_diamante, "A", contexto) == 1.0

    def test_distancia_usa_la_linea_recta(self, grafo_diamante):
        contexto = preparar_contexto(grafo_diamante, "D", "menor_distancia")
        distancia_recta = grafo_diamante.nodos["O"].coordenadas.distancia_a(
            grafo_diamante.nodos["D"].coordenadas
        )

        assert estimar_costo_restante(grafo_diamante, "O", contexto) == pytest.approx(
            distancia_recta
        )

    @pytest.mark.parametrize("criterio", CRITERIOS)
    def test_es_admisible_en_cada_criterio(self, grafo_diamante, criterio):
        contexto = preparar_contexto(grafo_diamante, "D", criterio)
        busqueda = BusquedaCostoUniforme()

        for nodo_id in grafo_diamante.nodos:
            referencia = busqueda.buscar(grafo_diamante, nodo_id, "D", criterio)
            if not referencia.ruta_encontrada:
                continue
            estimacion = estimar_costo_restante(grafo_diamante, nodo_id, contexto)
            assert estimacion <= referencia.costo_total + 1e-9

    @pytest.mark.parametrize("criterio", CRITERIOS)
    def test_es_consistente_en_cada_criterio(self, grafo_diamante, criterio):
        contexto = preparar_contexto(grafo_diamante, "D", criterio)

        for arista in grafo_diamante.aristas:
            if not arista.disponible:
                continue
            h_origen = estimar_costo_restante(grafo_diamante, arista.origen, contexto)
            h_destino = estimar_costo_restante(grafo_diamante, arista.destino, contexto)
            assert h_origen <= costo_arista(arista, criterio) + h_destino + 1e-9

    def test_tiempo_usa_la_velocidad_maxima(self, grafo_ramal_largo):
        contexto = preparar_contexto(grafo_ramal_largo, "D", "menor_tiempo")
        distancia = grafo_ramal_largo.nodos["M0"].coordenadas.distancia_a(
            grafo_ramal_largo.nodos["D"].coordenadas
        )

        assert estimar_costo_restante(grafo_ramal_largo, "M0", contexto) == pytest.approx(
            distancia / contexto.velocidad_maxima_ms / 60.0
        )
