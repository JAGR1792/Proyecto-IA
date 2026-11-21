"""Categorías de congestión para clasificación supervisada (Persona 2).

Alineadas con el simulador de Corte 2 (`congestion/horarios.py`) y con el
alcance del PDF: baja / media / alta. Las vías `bloqueada` se excluyen del
entrenamiento porque no son un estado predicible por atributos de tráfico,
sino un cierre explícito.
"""

from __future__ import annotations

from src.grafo.modelos import NivelCongestion

# Orden canónico para métricas, matrices de confusión y reportes.
CATEGORIAS_CONGESTION: tuple[str, ...] = (
    NivelCongestion.BAJA.value,
    NivelCongestion.MEDIA.value,
    NivelCongestion.ALTA.value,
)

# Umbrales del factor de ralentización sintético (ADR-026).
UMBRAL_BAJA_MEDIA = 1.40
UMBRAL_MEDIA_ALTA = 2.00


def umbral_factor_a_categoria(factor: float) -> str:
    """Mapea el factor de ralentización a una categoría de congestión.

    Args:
        factor: Multiplicador de tiempo (≥ 1.0 en el simulador).

    Returns:
        Etiqueta ``baja``, ``media`` o ``alta``.
    """
    if factor < UMBRAL_BAJA_MEDIA:
        return NivelCongestion.BAJA.value
    if factor < UMBRAL_MEDIA_ALTA:
        return NivelCongestion.MEDIA.value
    return NivelCongestion.ALTA.value


def descripcion_categorias() -> dict[str, str]:
    """Descripciones legibles de cada clase para documentación y notebook."""
    return {
        NivelCongestion.BAJA.value: (
            f"Tráfico fluido: factor de ralentización < {UMBRAL_BAJA_MEDIA:.2f}"
        ),
        NivelCongestion.MEDIA.value: (
            f"Tráfico moderado: factor en [{UMBRAL_BAJA_MEDIA:.2f}, {UMBRAL_MEDIA_ALTA:.2f})"
        ),
        NivelCongestion.ALTA.value: (f"Tráfico congestionado: factor ≥ {UMBRAL_MEDIA_ALTA:.2f}"),
    }
