"""Tests de los endpoints de búsqueda con tarifa de taxi."""

import asyncio

import pytest
from fastapi import HTTPException

from src.api import rutas_busqueda
from src.grafo.modelos import Arista, Coordenadas, Grafo, Nodo, TipoNodo


@pytest.fixture
def grafo_tarifa() -> Grafo:
    """Grafo mínimo A -> B de 5.2 km para liquidar la tarifa."""
    grafo = Grafo()
    for nodo_id, lat in (("A", 4.600), ("B", 4.601)):
        grafo.agregar_nodo(
            Nodo(
                id=nodo_id,
                nombre=nodo_id,
                coordenadas=Coordenadas(latitud=lat, longitud=-74.000),
                tipo=TipoNodo.INTERSECCION,
            )
        )
    grafo.agregar_arista(
        Arista(
            id="AB",
            origen="A",
            destino="B",
            distancia=5_200.0,
            tiempo_estimado=10.0,
            velocidad_promedio=30.0,
            disponible=True,
        )
    )
    return grafo


@pytest.fixture(autouse=True)
def parchear_grafo(monkeypatch, grafo_tarifa):
    """Sustituye el grafo global por el grafo mínimo del test."""
    monkeypatch.setattr(rutas_busqueda, "obtener_grafo", lambda: grafo_tarifa)


def test_buscar_incluye_tarifa_nocturna():
    resultado = asyncio.run(
        rutas_busqueda.buscar_ruta(
            rutas_busqueda.SolicitudBusqueda(
                origen="A",
                destino="B",
                algoritmo="a_estrella",
                tarifa=rutas_busqueda.OpcionesTarifa(nocturno=True),
            )
        )
    )

    assert resultado.tarifa_taxi is not None
    assert resultado.tarifa_taxi.total == 16_600
    assert resultado.tarifa_taxi.recargos == 3_800


def test_comparar_incluye_tarifa_en_cada_algoritmo():
    comparacion = asyncio.run(
        rutas_busqueda.comparar_ruta(
            rutas_busqueda.SolicitudComparacion(
                origen="A",
                destino="B",
                criterio="menor_tiempo",
            )
        )
    )

    assert comparacion.resultados
    for resultado in comparacion.resultados:
        assert resultado.tarifa_taxi is not None
        assert resultado.tarifa_taxi.total == 12_800


def test_zona_amarilla_sin_excelencia_devuelve_422():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            rutas_busqueda.buscar_ruta(
                rutas_busqueda.SolicitudBusqueda(
                    origen="A",
                    destino="B",
                    algoritmo="a_estrella",
                    tarifa=rutas_busqueda.OpcionesTarifa(zona_amarilla=True),
                )
            )
        )

    assert exc.value.status_code == 422
    assert "zona amarilla" in exc.value.detail
