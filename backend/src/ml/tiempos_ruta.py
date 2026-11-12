"""Aplicación conservadora de LinearRegression sobre el grafo OSM existente.

No altera el grafo global. El tiempo se estima para las aristas DEL GRAFO
que sirve el mapa; sus IDs no se usan como variables del modelo.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import math

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
MODELO = ROOT / 'backend/datos/ml/modelos_regresion_osm/modelo_regresion_osm.joblib'
DATASET = ROOT / 'backend/datos/ml/red_osm_auditada/dataset_red_osm_operativo_auditado.csv.gz'
COLUMNAS = ['id_arista_osm', 'origen', 'destino', 'distancia_m', 'tipo_via', 'dia_semana', 'hora']


@lru_cache(maxsize=2)
def cargar_modelo(ruta: str):
    """Carga solo el artefacto entrenado por este proyecto desde disco local."""
    p = Path(ruta)
    if not p.is_file():
        raise FileNotFoundError(f'Modelo no encontrado: {p}. Entrena primero la regresion.')
    return joblib.load(p)


@lru_cache(maxsize=2)
def cargar_indice(ruta: str) -> dict[str, list[dict]]:
    """Carga geometría/atributos únicos del dataset, sin materializar 168 horarios por arista."""
    p = Path(ruta)
    if not p.is_file():
        raise FileNotFoundError(f'Dataset auditado no encontrado: {p}')
    data = pd.read_csv(p, usecols=COLUMNAS, dtype={'id_arista_osm':str,'origen':str,'destino':str})
    if data[COLUMNAS].isna().any().any():
        raise ValueError('El dataset tiene campos esenciales incompletos')
    if data.duplicated(['id_arista_osm','origen','destino','dia_semana','hora']).any():
        # Las aristas con IDs repetidos se distinguen por el índice de arista;
        # este control detecta ambigüedades que requieren revisión manual.
        raise ValueError('Identidades ambiguas en dataset: falta una clave de arista unica')
    unique = data.drop_duplicates(['id_arista_osm','origen','destino'])
    index: dict[str, list[dict]] = {}
    for r in unique.itertuples(index=False):
        index.setdefault(str(r.id_arista_osm),[]).append({
            'id':str(r.id_arista_osm), 'origen':str(r.origen), 'destino':str(r.destino),
            'distancia_m':float(r.distancia_m), 'tipo_via':str(r.tipo_via)})
    return index


def identificar_arista(arista, indice: dict[str,list[dict]]) -> dict | None:
    """Exige identidad, dirección y distancia compatibles antes de predecir."""
    opciones = indice.get(str(arista.id), [])
    validas = [a for a in opciones if a['origen']==str(arista.origen)
               and a['destino']==str(arista.destino)
               and abs(a['distancia_m']-arista.distancia) <= max(.5,.01*arista.distancia)]
    return validas[0] if len(validas)==1 else None


def crear_entradas(aristas: list[dict], dia_semana: int, hora: int) -> pd.DataFrame:
    """Reproduce las transformaciones del script de entrenamiento."""
    if not 0 <= dia_semana <= 6 or not 0 <= hora <= 23:
        raise ValueError('Dia 0..6 y hora 0..23')
    return pd.DataFrame({
        'distancia_m':[a['distancia_m'] for a in aristas],
        'hora_sin':np.sin(2*np.pi*hora/24),
        'hora_cos':np.cos(2*np.pi*hora/24),
        'dia_semana':str(dia_semana),
        'tipo_via':[a['tipo_via'] for a in aristas],
    })


def _atributos_arista(arista, indice: dict[str, list[dict]] | None) -> tuple[dict, bool]:
    """Construye características desde el grafo activo, nunca enlaza otro grafo.

    Si una arista coincide plenamente con el CSV se permite recuperar su tipo
    OSM cuando el cargador del grafo lo haya degradado a ``otro``.
    """
    distancia = float(arista.distancia)
    if not math.isfinite(distancia) or distancia <= 0:
        raise ValueError(f'Arista {arista.id}: distancia no positiva o no finita')
    attrs = getattr(arista, 'atributos', None)
    tipo = getattr(attrs, 'tipo_via', 'otro')
    tipo = getattr(tipo, 'value', tipo)
    tipo = str(tipo or 'otro')
    coincidencia = identificar_arista(arista, indice) if indice else None
    if tipo == 'otro' and coincidencia is not None:
        tipo = coincidencia['tipo_via']
    return {'distancia_m': distancia, 'tipo_via': tipo}, coincidencia is not None


def grafo_con_tiempos_ml(grafo, modelo, indice: dict[str, list[dict]] | None,
                         dia_semana: int, hora: int):
    """Predice sobre el grafo que se dibuja en el mapa, conservando conectividad.

    IDs de CSV y grafo pueden diferir porque NO son entradas al modelo.
    Una coincidencia auditada se usa solo para enriquecer tipo_via faltante;
    nunca para sustituir origen, destino, distancia ni sentido del grafo.
    Limites de velocidad operativos: 5--80 km/h.
    """
    if not grafo.aristas:
        raise ValueError('El grafo activo no contiene aristas')
    caracteristicas = [_atributos_arista(a, indice) for a in grafo.aristas]
    entradas = crear_entradas([c for c, _ in caracteristicas], dia_semana, hora)
    raw = np.asarray(modelo.predict(entradas), dtype=float)
    if raw.shape != (len(grafo.aristas),) or not np.isfinite(raw).all():
        raise ValueError('El modelo produjo predicciones no finitas o tamaño incorrecto')
    aristas = []
    ajustadas = 0
    for arista, t in zip(grafo.aristas, raw):
        distancia = float(arista.distancia)
        minimo = .06 * distancia / 80
        maximo = .06 * distancia / 5
        corregido = float(np.clip(t, minimo, maximo))
        ajustadas += int(abs(t - corregido) > 1e-12)
        aristas.append(arista.model_copy(update={
            'tiempo_estimado': corregido,
            'velocidad_promedio': .06 * distancia / corregido,
        }))
    return grafo.model_copy(update={'aristas': aristas}), {
        'aristas': len(aristas),
        'tiempos_ajustados_a_limites': ajustadas,
        'coincidencias_auditadas': sum(coincide for _, coincide in caracteristicas),
        'modelo': 'LinearRegression',
    }
