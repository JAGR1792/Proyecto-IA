"""Tests unitarios para src/tarifas/taximetro.py."""

import pytest

from src.tarifas.taximetro import (
    BANDERAZO_UNIDADES,
    CARRERA_MINIMA_UNIDADES,
    RECARGO_AEROPUERTO,
    RECARGO_AEROPUERTO_EXCELENCIA,
    RECARGO_NOCTURNO,
    RECARGO_NOCTURNO_EXCELENCIA,
    RECARGO_PUERTA_A_PUERTA,
    RECARGO_PUERTA_A_PUERTA_EXCELENCIA,
    RECARGO_ZONA_AMARILLA,
    UNIDAD,
    UNIDAD_EXCELENCIA,
    calcular_tarifa_taximetro,
)


class TestUnidadesYMinimo:
    """Comportamiento del banderazo, la carrera mínima y las fracciones."""

    def test_carrera_cero_cobra_la_minima(self):
        tarifa = calcular_tarifa_taximetro(0)

        assert tarifa.unidades == CARRERA_MINIMA_UNIDADES
        assert tarifa.valor_metro == 8_000
        assert tarifa.recargos == 0
        assert tarifa.total == 8_000

    def test_cien_metros_suman_una_unidad_de_distancia(self):
        tarifa = calcular_tarifa_taximetro(100)

        assert tarifa.detalle["unidades_distancia"] == 1
        assert tarifa.detalle["unidades_brutas"] == BANDERAZO_UNIDADES + 1
        assert tarifa.unidades == CARRERA_MINIMA_UNIDADES

    def test_ciento_un_metros_redondean_hacia_arriba(self):
        tarifa = calcular_tarifa_taximetro(101)

        assert tarifa.detalle["unidades_distancia"] == 2
        assert tarifa.unidades == CARRERA_MINIMA_UNIDADES

    def test_veinticuatro_segundos_suman_una_unidad_de_espera(self):
        tarifa = calcular_tarifa_taximetro(5_200, espera_s=24)

        assert tarifa.detalle["unidades_espera"] == 1
        assert tarifa.detalle["unidades_brutas"] == 81
        assert tarifa.unidades == 81

    def test_veinticinco_segundos_redondean_hacia_arriba(self):
        tarifa = calcular_tarifa_taximetro(5_200, espera_s=25)

        assert tarifa.detalle["unidades_espera"] == 2
        assert tarifa.unidades == 82
        assert tarifa.total == 13_100

    def test_unidades_incluyen_banderazo(self):
        tarifa = calcular_tarifa_taximetro(5_200)

        assert tarifa.detalle["unidades_banderazo"] == BANDERAZO_UNIDADES
        assert tarifa.detalle["unidades_distancia"] == 52
        assert tarifa.detalle["unidades_brutas"] == 80
        assert tarifa.detalle["unidades_cobradas"] == 80
        assert tarifa.unidades == 80


class TestRedondeo:
    """Diferencia entre redondeo hacia arriba y tarjeta oficial."""

    def test_ceil_redondea_hacia_arriba(self):
        tarifa = calcular_tarifa_taximetro(5_200)

        assert tarifa.valor_metro == 12_800
        assert tarifa.total == 12_800

    def test_modo_oficial_usa_la_centena_mas_cercana(self):
        tarifa = calcular_tarifa_taximetro(5_200, redondeo="oficial")

        assert tarifa.valor_metro == 12_700
        assert tarifa.total == 12_700

    def test_ambos_modos_coinciden_cuando_el_valor_ya_es_centena(self):
        ceil = calcular_tarifa_taximetro(8_200)
        oficial = calcular_tarifa_taximetro(8_200, redondeo="oficial")

        assert ceil.total == oficial.total == 17_500

    @pytest.mark.parametrize(
        ("distancia_m", "unidades", "valor_oficial"),
        [
            (0, 50, 8_000),
            (5_200, 80, 12_700),
            (8_200, 110, 17_500),
            (11_200, 140, 22_300),
            (14_200, 170, 27_000),
            (17_200, 200, 31_800),
            (20_200, 230, 36_600),
        ],
    )
    def test_reproduce_la_tarjeta_oficial_basica(self, distancia_m, unidades, valor_oficial):
        tarifa = calcular_tarifa_taximetro(distancia_m, redondeo="oficial")

        assert tarifa.unidades == unidades
        assert tarifa.total == valor_oficial

    @pytest.mark.parametrize("modo", ["", "truncar", "arriba"])
    def test_modo_invalido_lanza_error(self, modo):
        with pytest.raises(ValueError, match="Modo de redondeo inválido"):
            calcular_tarifa_taximetro(0, redondeo=modo)  # type: ignore[arg-type]


class TestRecargos:
    """Recargos oficiales y sus reglas de acumulación."""

    def test_recargo_nocturno(self):
        tarifa = calcular_tarifa_taximetro(5_200, nocturno=True)

        assert tarifa.detalle["recargo_nocturno"] == RECARGO_NOCTURNO
        assert tarifa.recargos == RECARGO_NOCTURNO
        assert tarifa.total == 16_600

    def test_recargo_dominical(self):
        tarifa = calcular_tarifa_taximetro(5_200, domingo_o_festivo=True)

        assert tarifa.detalle["recargo_nocturno"] == RECARGO_NOCTURNO
        assert tarifa.total == 16_600

    def test_nocturno_y_dominical_no_se_acumulan(self):
        solo_nocturno = calcular_tarifa_taximetro(5_200, nocturno=True)
        ambos = calcular_tarifa_taximetro(5_200, nocturno=True, domingo_o_festivo=True)

        assert ambos.recargos == solo_nocturno.recargos
        assert ambos.total == solo_nocturno.total

    def test_recargo_aeropuerto(self):
        tarifa = calcular_tarifa_taximetro(5_200, aeropuerto=True)

        assert tarifa.detalle["recargo_aeropuerto"] == RECARGO_AEROPUERTO
        assert tarifa.total == 20_800

    def test_recargo_puerta_a_puerta(self):
        tarifa = calcular_tarifa_taximetro(5_200, puerta_a_puerta=True)

        assert tarifa.detalle["recargo_puerta_a_puerta"] == RECARGO_PUERTA_A_PUERTA
        assert tarifa.total == 14_200

    def test_todos_los_recargos_basicos(self):
        tarifa = calcular_tarifa_taximetro(
            5_200,
            nocturno=True,
            aeropuerto=True,
            puerta_a_puerta=True,
        )

        assert tarifa.recargos == 3_800 + 8_000 + 1_400
        assert tarifa.total == 26_000

    def test_carrera_minima_con_recargo_nocturno(self):
        tarifa = calcular_tarifa_taximetro(100, nocturno=True)

        assert tarifa.unidades == CARRERA_MINIMA_UNIDADES
        assert tarifa.total == 8_000 + RECARGO_NOCTURNO

    def test_total_es_suma_de_componentes(self):
        tarifa = calcular_tarifa_taximetro(5_200, nocturno=True, aeropuerto=True)

        assert tarifa.total == tarifa.valor_metro + tarifa.recargos


class TestFactorExcelencia:
    """Unidad de $172 y recargos de la modalidad de excelencia."""

    def test_unidad_de_excelencia(self):
        tarifa = calcular_tarifa_taximetro(5_200, factor_excelencia=True)

        assert tarifa.detalle["valor_unidad"] == UNIDAD_EXCELENCIA
        assert tarifa.detalle["valor_unidad"] != UNIDAD
        assert tarifa.valor_metro == 13_800
        assert tarifa.total == 13_800

    def test_minima_de_excelencia(self):
        tarifa = calcular_tarifa_taximetro(0, factor_excelencia=True)

        assert tarifa.total == 8_600

    def test_recargo_nocturno_de_excelencia(self):
        tarifa = calcular_tarifa_taximetro(5_200, factor_excelencia=True, nocturno=True)

        assert tarifa.detalle["recargo_nocturno"] == RECARGO_NOCTURNO_EXCELENCIA
        assert tarifa.total == 13_800 + RECARGO_NOCTURNO_EXCELENCIA

    def test_recargo_aeropuerto_de_excelencia(self):
        tarifa = calcular_tarifa_taximetro(5_200, factor_excelencia=True, aeropuerto=True)

        assert tarifa.detalle["recargo_aeropuerto"] == RECARGO_AEROPUERTO_EXCELENCIA
        assert tarifa.total == 13_800 + RECARGO_AEROPUERTO_EXCELENCIA

    def test_recargo_puerta_a_puerta_de_excelencia(self):
        tarifa = calcular_tarifa_taximetro(5_200, factor_excelencia=True, puerta_a_puerta=True)

        assert tarifa.detalle["recargo_puerta_a_puerta"] == RECARGO_PUERTA_A_PUERTA_EXCELENCIA
        assert tarifa.total == 13_800 + RECARGO_PUERTA_A_PUERTA_EXCELENCIA

    def test_zona_amarilla_con_excelencia(self):
        tarifa = calcular_tarifa_taximetro(5_200, factor_excelencia=True, zona_amarilla=True)

        assert tarifa.detalle["recargo_zona_amarilla"] == RECARGO_ZONA_AMARILLA
        assert tarifa.total == 13_800 + RECARGO_ZONA_AMARILLA

    def test_zona_amarilla_sin_excelencia_lanza_error(self):
        with pytest.raises(ValueError, match="zona amarilla"):
            calcular_tarifa_taximetro(5_200, zona_amarilla=True)


class TestValidaciones:
    """Entradas inválidas."""

    def test_distancia_negativa(self):
        with pytest.raises(ValueError, match="distancia"):
            calcular_tarifa_taximetro(-1)

    def test_espera_negativa(self):
        with pytest.raises(ValueError, match="espera"):
            calcular_tarifa_taximetro(0, espera_s=-1)

    def test_detalle_tiene_todas_las_claves(self):
        tarifa = calcular_tarifa_taximetro(5_200)

        assert set(tarifa.detalle) == {
            "unidades_banderazo",
            "unidades_distancia",
            "unidades_espera",
            "unidades_brutas",
            "unidades_cobradas",
            "valor_unidad",
            "recargo_nocturno",
            "recargo_aeropuerto",
            "recargo_puerta_a_puerta",
            "recargo_zona_amarilla",
        }
