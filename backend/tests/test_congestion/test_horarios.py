"""Comportamiento del perfil de congestión sintético de 24 horas."""

import asyncio

import pytest
from pydantic import ValidationError

from src.api import rutas_busqueda, rutas_grafo
from src.congestion.horarios import grafo_en_hora, intensidad_en_hora, validar_hora
from src.grafo.modelos import NivelCongestion


@pytest.mark.parametrize("hora", ["00:00", "00:01", "05:59", "07:23", "12:07", "18:47", "23:59"])
def test_acepta_cualquier_minuto(hora):
    assert 0 <= validar_hora(hora) < 1440
    assert intensidad_en_hora(hora) >= 0


@pytest.mark.parametrize("hora", ["24:00", "7:23", "12:60", "-1:00", "08:5", ""])
def test_rechaza_horas_invalidas(hora):
    with pytest.raises(ValueError):
        validar_hora(hora)
    with pytest.raises(ValidationError):
        rutas_busqueda.SolicitudBusqueda(origen="A", destino="B", hora_salida=hora)


def test_hora_pico_empeora_tiempos_y_no_modifica_original(grafo_lineal):
    tiempo_original = grafo_lineal.aristas[0].tiempo_estimado
    pico = grafo_en_hora(grafo_lineal, "17:00")
    valle = grafo_en_hora(grafo_lineal, "22:00")
    assert pico.aristas[0].tiempo_estimado > valle.aristas[0].tiempo_estimado
    assert grafo_lineal.aristas[0].tiempo_estimado == tiempo_original
    assert pico is not grafo_lineal
    assert pico.nodos == grafo_lineal.nodos


def test_resultado_reproducible_y_minutos_interpolados(grafo_lineal):
    a = grafo_en_hora(grafo_lineal, "08:12")
    b = grafo_en_hora(grafo_lineal, "08:12")
    c = grafo_en_hora(grafo_lineal, "08:13")
    assert a.aristas[0].tiempo_estimado == b.aristas[0].tiempo_estimado
    assert a.aristas[0].tiempo_estimado != c.aristas[0].tiempo_estimado


def test_interpolacion_continua_en_medianoche():
    assert abs(intensidad_en_hora("23:59") - intensidad_en_hora("00:00")) < 0.005


def test_respeta_cierres_existentes(grafo_con_bloqueo):
    esc = grafo_en_hora(grafo_con_bloqueo, "17:45")
    assert esc.aristas[0].disponible is False
    assert esc.aristas[0].congestion == NivelCongestion.BLOQUEADA
    assert esc.aristas[1].disponible is True


def test_sin_hora_preserva_comportamiento_anterior(grafo_lineal):
    assert grafo_en_hora(grafo_lineal, None) is grafo_lineal


def test_busqueda_y_comparacion_comparten_hora(monkeypatch, grafo_lineal):
    monkeypatch.setattr(rutas_busqueda, "obtener_grafo", lambda: grafo_lineal)
    baja = asyncio.run(
        rutas_busqueda.buscar_ruta(
            rutas_busqueda.SolicitudBusqueda(
                origen="N1", destino="N3", algoritmo="dfs", hora_salida="22:00"
            )
        )
    )
    alta = asyncio.run(
        rutas_busqueda.buscar_ruta(
            rutas_busqueda.SolicitudBusqueda(
                origen="N1", destino="N3", algoritmo="dfs", hora_salida="17:00"
            )
        )
    )
    comparacion = asyncio.run(
        rutas_busqueda.comparar_ruta(
            rutas_busqueda.SolicitudComparacion(origen="N1", destino="N3", hora_salida="17:00")
        )
    )
    assert alta.tiempo_total_min > baja.tiempo_total_min
    assert alta.detalle["hora_salida"] == "17:00"
    assert comparacion.resultados
    assert all(r.detalle["hora_salida"] == "17:00" for r in comparacion.resultados)


def test_mapa_coincide_con_grafo_de_busqueda(monkeypatch, grafo_lineal):
    monkeypatch.setattr(rutas_grafo, "obtener_grafo", lambda: grafo_lineal)
    response = asyncio.run(rutas_grafo.obtener_grafo_completo(hora_salida="17:00"))
    escenario = grafo_en_hora(grafo_lineal, "17:00")
    assert response["aristas"][0]["tiempo_estimado"] == escenario.aristas[0].tiempo_estimado
    assert response["aristas"][0]["congestion"] == escenario.aristas[0].congestion.value
