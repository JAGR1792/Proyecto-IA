"""Construcción del dataset supervisado para clasificar congestión.

Combina la geometría OSM compartida con el perfil horario sintético del
Corte 2. Cada fila es una observación (arista × hora): atributos observables
de la vía + contexto temporal → etiqueta de congestión.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from src.congestion.horarios import grafo_en_hora, intensidad_en_hora, peso_tipo_via
from src.grafo.modelos import Grafo, NivelCongestion
from src.grafo.repositorio import RepositorioGrafo
from src.ml.categorias import CATEGORIAS_CONGESTION

# Features que el clasificador puede "observar" (sin el factor ni la etiqueta).
FEATURES_NUMERICAS: tuple[str, ...] = (
    "hora_decimal",
    "intensidad_hora",
    "distancia_m",
    "tiempo_base_min",
    "velocidad_base_kmh",
    "carriles",
    "sentido_unico",
    "incidentes",
    "peso_tipo_via",
)

FEATURE_CATEGORICA = "tipo_via"
TARGET = "congestion"

# Horas de muestreo: cubren valle, picos y noche (día hábil típico).
HORAS_MUESTREO_DEFAULT: tuple[str, ...] = (
    "00:00",
    "05:00",
    "06:30",
    "07:30",
    "08:00",
    "09:00",
    "10:30",
    "12:00",
    "14:00",
    "16:00",
    "17:00",
    "17:45",
    "19:00",
    "20:30",
    "22:00",
    "23:30",
)


def _hora_a_decimal(hora_salida: str) -> float:
    horas, minutos = map(int, hora_salida.split(":"))
    return horas + minutos / 60.0


def construir_dataset_clasificacion(
    grafo: Grafo,
    horas: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Genera filas etiquetadas (arista × hora) para ML supervisado.

    Excluye aristas no disponibles o ya marcadas como ``bloqueada`` en el
    grafo base: no aportan señal de congestión predicible.

    Args:
        grafo: Grafo OSM (tiempos/velocidades base).
        horas: Lista HH:MM a simular. Si es None, usa el muestreo por defecto.

    Returns:
        DataFrame con features, ``tipo_via`` y columna objetivo ``congestion``.
    """
    horas_lista = tuple(horas) if horas is not None else HORAS_MUESTREO_DEFAULT
    filas: list[dict] = []

    for hora in horas_lista:
        intensidad = intensidad_en_hora(hora)
        simulado = grafo_en_hora(grafo, hora)
        hora_decimal = _hora_a_decimal(hora)

        for base, actual in zip(grafo.aristas, simulado.aristas):
            if (
                not base.disponible
                or base.congestion == NivelCongestion.BLOQUEADA
                or actual.congestion == NivelCongestion.BLOQUEADA
            ):
                continue

            tipo = base.atributos.tipo_via.value
            carriles = base.atributos.carriles if base.atributos.carriles is not None else 1
            filas.append(
                {
                    "arista_id": base.id,
                    "hora_salida": hora,
                    "hora_decimal": hora_decimal,
                    "intensidad_hora": intensidad,
                    "distancia_m": base.distancia,
                    "tiempo_base_min": base.tiempo_estimado,
                    "velocidad_base_kmh": base.velocidad_promedio,
                    "carriles": float(carriles),
                    "sentido_unico": int(base.atributos.sentido_unico),
                    "incidentes": float(base.incidentes),
                    "peso_tipo_via": float(peso_tipo_via(tipo)),
                    FEATURE_CATEGORICA: tipo,
                    TARGET: actual.congestion.value,
                    "tiempo_simulado_min": actual.tiempo_estimado,
                    "velocidad_simulada_kmh": actual.velocidad_promedio,
                }
            )

    df = pd.DataFrame(filas)
    if df.empty:
        return df

    # Solo las tres clases del alcance académico.
    df = df[df[TARGET].isin(CATEGORIAS_CONGESTION)].reset_index(drop=True)
    return df


def cargar_grafo_osm(ruta: Path | str | None = None) -> Grafo:
    """Carga el grafo compartido OSM desde ``backend/datos``."""
    if ruta is None:
        datos = Path(__file__).resolve().parents[2] / "datos"
        return RepositorioGrafo(datos).cargar_json("grafo_osm.json")
    ruta_p = Path(ruta)
    return RepositorioGrafo(ruta_p.parent).cargar_json(ruta_p.name)


def guardar_dataset(df: pd.DataFrame, ruta: Path | str) -> Path:
    """Persiste el CSV compartido para notebooks y otros compañeros."""
    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(destino, index=False)
    return destino


def resumen_dataset(df: pd.DataFrame) -> dict:
    """Conteo de clases y dimensiones para reportes."""
    if df.empty:
        return {"filas": 0, "columnas": 0, "clases": {}}
    return {
        "filas": int(len(df)),
        "columnas": int(df.shape[1]),
        "clases": {k: int(v) for k, v in df[TARGET].value_counts().to_dict().items()},
        "horas_unicas": int(df["hora_salida"].nunique()) if "hora_salida" in df else 0,
        "aristas_unicas": int(df["arista_id"].nunique()) if "arista_id" in df else 0,
    }
