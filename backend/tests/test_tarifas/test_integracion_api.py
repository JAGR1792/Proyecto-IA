"""Tests de integración de la tarifa con los modelos de la API."""

import pytest
from pydantic import ValidationError

from src.api.rutas_busqueda import (
    OpcionesTarifa,
    SolicitudBusqueda,
    SolicitudComparacion,
    _aplicar_tarifa,
)
from src.busqueda.base import ResultadoBusqueda


def _resultado(distancia_m: float, encontrada: bool = True) -> ResultadoBusqueda:
    """Crea un resultado de búsqueda mínimo para probar la liquidación."""
    return ResultadoBusqueda(
        algoritmo="a_estrella",
        ruta_encontrada=encontrada,
        distancia_total_m=distancia_m,
        camino=["A", "B"] if encontrada else [],
    )


class TestOpcionesTarifa:
    """Validación del modelo de opciones."""

    def test_valores_por_defecto(self):
        opciones = OpcionesTarifa()

        assert opciones.espera_s == 0.0
        assert opciones.redondeo == "ceil"
        assert not opciones.nocturno
        assert not opciones.factor_excelencia

    def test_espera_negativa_lanza_error(self):
        with pytest.raises(ValidationError):
            OpcionesTarifa(espera_s=-1)

    def test_redondeo_invalido_lanza_error(self):
        with pytest.raises(ValidationError):
            OpcionesTarifa(redondeo="otro")

    def test_solicitud_busqueda_incluye_tarifa(self):
        solicitud = SolicitudBusqueda(origen="A", destino="B")

        assert solicitud.tarifa.redondeo == "ceil"

    def test_solicitud_comparacion_incluye_tarifa(self):
        solicitud = SolicitudComparacion(origen="A", destino="B")

        assert solicitud.tarifa.redondeo == "ceil"


class TestAplicarTarifa:
    """Liquidación y adjunción de la tarifa al resultado."""

    def test_ruta_encontrada_agrega_tarifa(self):
        original = _resultado(5_200)

        actualizado = _aplicar_tarifa(original, OpcionesTarifa())

        assert original.tarifa_taxi is None
        assert actualizado.tarifa_taxi is not None
        assert actualizado.tarifa_taxi.total == 12_800
        assert actualizado.tarifa_taxi.unidades == 80

    def test_sin_ruta_no_agrega_tarifa(self):
        original = _resultado(5_200, encontrada=False)

        actualizado = _aplicar_tarifa(original, OpcionesTarifa())

        assert actualizado is original
        assert actualizado.tarifa_taxi is None

    def test_tarifa_nocturna(self):
        actualizado = _aplicar_tarifa(_resultado(5_200), OpcionesTarifa(nocturno=True))

        assert actualizado.tarifa_taxi is not None
        assert actualizado.tarifa_taxi.total == 16_600

    def test_tarifa_con_redondeo_oficial(self):
        actualizado = _aplicar_tarifa(_resultado(5_200), OpcionesTarifa(redondeo="oficial"))

        assert actualizado.tarifa_taxi is not None
        assert actualizado.tarifa_taxi.total == 12_700

    def test_zona_amarilla_sin_excelencia_falla(self):
        with pytest.raises(ValueError, match="zona amarilla"):
            _aplicar_tarifa(_resultado(5_200), OpcionesTarifa(zona_amarilla=True))
