"""Tarifas oficiales de taxi para Bogotá D.C. (Decreto 042 de 2026).

El Decreto Distrital 042 de 2026, que modifica los artículos 315, 339 y 340
del Decreto 652 de 2025, fija la unidad de cobro del taxi en:

* ``$159`` por cada 100 metros recorridos o 24 segundos de espera, sin factor
  de excelencia.
* ``$172`` por unidad cuando la Secretaría Distrital de Movilidad autoriza el
  factor de excelencia (taxi azul/blanco).

La estructura de cobro es la siguiente:

* Banderazo: 28 unidades.
* Carrera mínima: 50 unidades.
* Recargo nocturno, dominical o festivo: 24 unidades (no se acumulan entre sí).
* Recargo aeropuerto o Puente Aéreo: 50 unidades.
* Recargo puerta a puerta: 9 unidades.
* Recargo zona amarilla (ZEO): 20 unidades, solo con factor de excelencia.

La tarjeta oficial de tarifas publica valores redondeados a la centena más
cercana. Este módulo permite reproducir esa tarjeta con ``redondeo="oficial"``
y también aplicar redondeo hacia arriba con ``redondeo="ceil"``, que es el
modo conservador solicitado para la simulación.
"""

from math import ceil
from typing import Literal

from pydantic import BaseModel, Field

ModoRedondeo = Literal["ceil", "oficial"]

UNIDAD = 159
UNIDAD_EXCELENCIA = 172

BANDERAZO_UNIDADES = 28
CARRERA_MINIMA_UNIDADES = 50

RECARGO_NOCTURNO = 3_800
RECARGO_NOCTURNO_EXCELENCIA = 4_100
RECARGO_AEROPUERTO = 8_000
RECARGO_AEROPUERTO_EXCELENCIA = 8_600
RECARGO_PUERTA_A_PUERTA = 1_400
RECARGO_PUERTA_A_PUERTA_EXCELENCIA = 1_500
RECARGO_ZONA_AMARILLA = 3_400


class TarifaTaxi(BaseModel):
    """Liquidación de una carrera de taxi en Bogotá D.C.

    Attributes:
        unidades: Unidades de 100 m / 24 s cobradas, incluido el banderazo y
            la carrera mínima.
        valor_metro: Valor de las unidades, redondeado según el modo elegido.
        recargos: Suma de los recargos oficiales aplicados.
        total: Valor final de la carrera en pesos colombianos.
        detalle: Desglose de unidades y recargos para auditoría.
    """

    unidades: int = Field(ge=0, description="Unidades cobradas de 100 m / 24 s")
    valor_metro: int = Field(ge=0, description="Valor de las unidades en COP")
    recargos: int = Field(ge=0, description="Recargos oficiales en COP")
    total: int = Field(ge=0, description="Total de la carrera en COP")
    detalle: dict[str, int] = Field(
        default_factory=dict,
        description="Desglose de unidades y recargos",
    )


def _redondear_centena(valor: int, modo: ModoRedondeo) -> int:
    """Redondea un valor en pesos a la centena, según el modo elegido.

    Args:
        valor: Valor en pesos colombianos.
        modo: ``"ceil"`` para redondear hacia arriba o ``"oficial"`` para
            redondear a la centena más cercana (tarjeta oficial).

    Returns:
        Valor redondeado a la centena más próxima en la dirección indicada.

    Raises:
        ValueError: Si el modo no es ``"ceil"`` ni ``"oficial"``.
    """
    if modo == "ceil":
        return ceil(valor / 100) * 100
    if modo == "oficial":
        return int(valor / 100 + 0.5) * 100
    raise ValueError(f"Modo de redondeo inválido: {modo!r}. Usa 'ceil' u 'oficial'.")


def calcular_tarifa_taximetro(
    distancia_m: float,
    espera_s: float = 0.0,
    *,
    nocturno: bool = False,
    domingo_o_festivo: bool = False,
    aeropuerto: bool = False,
    puerta_a_puerta: bool = False,
    factor_excelencia: bool = False,
    zona_amarilla: bool = False,
    redondeo: ModoRedondeo = "ceil",
) -> TarifaTaxi:
    """Calcula la tarifa de una carrera de taxi en Bogotá D.C.

    Las unidades de distancia se cobran por cada 100 metros o fracción; las de
    espera, por cada 24 segundos o fracción. Al total de unidades se le suma el
    banderazo (28 unidades) y se aplica la carrera mínima (50 unidades).

    El recargo nocturno y el dominical/festivo son excluyentes: si ambos se
    activan, se cobra una sola vez. El recargo de zona amarilla solo es válido
    con factor de excelencia, tal como lo exige la norma.

    Args:
        distancia_m: Distancia recorrida en metros. Debe ser no negativa.
        espera_s: Tiempo detenido en segundos. Debe ser no negativo.
        nocturno: Aplica el recargo nocturno (20:00 a 5:00).
        domingo_o_festivo: Aplica el recargo dominical o festivo.
        aeropuerto: Aplica el recargo de aeropuerto o Puente Aéreo.
        puerta_a_puerta: Aplica el recargo de servicio puerta a puerta.
        factor_excelencia: Usa la unidad de $172 y los recargos de la modalidad
            de excelencia.
        zona_amarilla: Aplica el recargo de zona amarilla (ZEO). Requiere
            ``factor_excelencia=True``.
        redondeo: ``"ceil"`` (por defecto) redondea hacia arriba; ``"oficial"``
            reproduce la tarjeta de tarifas a la centena más cercana.

    Returns:
        Una instancia de :class:`TarifaTaxi` con unidades, valor del metro,
        recargos, total y detalle.

    Raises:
        ValueError: Si la distancia o la espera son negativas, si el modo de
            redondeo es inválido o si se pide zona amarilla sin factor de
            excelencia.

    Example:
        >>> calcular_tarifa_taximetro(5_200).total
        12800
        >>> calcular_tarifa_taximetro(5_200, redondeo="oficial").total
        12700
    """
    if distancia_m < 0:
        raise ValueError("La distancia no puede ser negativa.")
    if espera_s < 0:
        raise ValueError("La espera no puede ser negativa.")
    if redondeo not in ("ceil", "oficial"):
        raise ValueError(f"Modo de redondeo inválido: {redondeo!r}. Usa 'ceil' u 'oficial'.")
    if zona_amarilla and not factor_excelencia:
        raise ValueError("El recargo de zona amarilla (ZEO) solo aplica con factor de excelencia.")

    unidad = UNIDAD_EXCELENCIA if factor_excelencia else UNIDAD

    unidades_distancia = ceil(distancia_m / 100)
    unidades_espera = ceil(espera_s / 24)
    unidades_brutas = BANDERAZO_UNIDADES + unidades_distancia + unidades_espera
    unidades_cobradas = max(unidades_brutas, CARRERA_MINIMA_UNIDADES)
    valor_metro = _redondear_centena(unidades_cobradas * unidad, redondeo)

    recargo_nocturno = 0
    if nocturno or domingo_o_festivo:
        recargo_nocturno = RECARGO_NOCTURNO_EXCELENCIA if factor_excelencia else RECARGO_NOCTURNO

    recargo_aeropuerto = 0
    if aeropuerto:
        recargo_aeropuerto = (
            RECARGO_AEROPUERTO_EXCELENCIA if factor_excelencia else RECARGO_AEROPUERTO
        )

    recargo_puerta_a_puerta = 0
    if puerta_a_puerta:
        recargo_puerta_a_puerta = (
            RECARGO_PUERTA_A_PUERTA_EXCELENCIA if factor_excelencia else RECARGO_PUERTA_A_PUERTA
        )

    recargo_zona_amarilla = RECARGO_ZONA_AMARILLA if zona_amarilla else 0
    recargos = (
        recargo_nocturno + recargo_aeropuerto + recargo_puerta_a_puerta + recargo_zona_amarilla
    )

    detalle: dict[str, int] = {
        "unidades_banderazo": BANDERAZO_UNIDADES,
        "unidades_distancia": unidades_distancia,
        "unidades_espera": unidades_espera,
        "unidades_brutas": unidades_brutas,
        "unidades_cobradas": unidades_cobradas,
        "valor_unidad": unidad,
        "recargo_nocturno": recargo_nocturno,
        "recargo_aeropuerto": recargo_aeropuerto,
        "recargo_puerta_a_puerta": recargo_puerta_a_puerta,
        "recargo_zona_amarilla": recargo_zona_amarilla,
    }

    return TarifaTaxi(
        unidades=unidades_cobradas,
        valor_metro=valor_metro,
        recargos=recargos,
        total=valor_metro + recargos,
        detalle=detalle,
    )
