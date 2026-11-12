"""API aislada para predicción y optimización de rutas por LinearRegression."""
from __future__ import annotations
from functools import lru_cache
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.api.rutas_grafo import obtener_grafo
from src.busqueda.ucs import BusquedaCostoUniforme
from src.ml.tiempos_ruta import DATASET, MODELO, cargar_indice, cargar_modelo, grafo_con_tiempos_ml
from src.ml.comparacion_ruta import cargar_referencias, comparar_ruta, comparar_con_grafo_base

router = APIRouter()

class SolicitudRutaML(BaseModel):
    origen: str = Field(min_length=1)
    destino: str = Field(min_length=1)
    dia_semana: int = Field(ge=0, le=6, description='0 lunes, 6 domingo')
    hora: int = Field(ge=0, le=23)

class SolicitudPrediccionML(BaseModel):
    distancia_m: float = Field(gt=0, le=100000)
    tipo_via: str = Field(min_length=1)
    dia_semana: int = Field(ge=0,le=6)
    hora: int = Field(ge=0,le=23)


def _recursos():
    try:
        return cargar_modelo(str(MODELO)), cargar_indice(str(DATASET))
    except FileNotFoundError as e:
        raise HTTPException(503, detail=str(e)) from e
    except (ValueError, OSError) as e:
        raise HTTPException(500, detail=str(e)) from e


@router.get('/estado')
def estado_ml():
    """Comprueba instalación del artefacto y archivo de datos."""
    return {'modelo_presente': MODELO.is_file(), 'dataset_presente':DATASET.is_file(),
            'algoritmo':'LinearRegression', 'endpoint_ruta':'/api/v1/ml/ruta'}


@router.post('/predecir')
def predecir(s: SolicitudPrediccionML):
    """Predice un tiempo individual; útil para validar el modelo por API."""
    from src.ml.tiempos_ruta import crear_entradas
    try:
        modelo = cargar_modelo(str(MODELO))
    except FileNotFoundError as e:
        raise HTTPException(503, detail=str(e)) from e
    fila = {'distancia_m':s.distancia_m, 'tipo_via':s.tipo_via}
    t = float(modelo.predict(crear_entradas([fila],s.dia_semana,s.hora))[0])
    if not __import__('math').isfinite(t):
        raise HTTPException(500,detail='Prediccion no finita')
    minimo, maximo = .06*s.distancia_m/80, .06*s.distancia_m/5
    return {'tiempo_estimado_min':max(minimo,min(maximo,t)),
            'algoritmo':'LinearRegression','unidad':'minutos'}


@router.post('/ruta')
def ruta_ml(s: SolicitudRutaML):
    """Calcula la ruta con UCS sobre tiempos predichos, sin alterar el grafo compartido."""
    # La prediccion depende de las características de cada arista, no del
    # identificador de la fila en el CSV de entrenamiento.
    try:
        modelo = cargar_modelo(str(MODELO))
    except FileNotFoundError as e:
        raise HTTPException(503, detail=str(e)) from e
    grafo = obtener_grafo()
    if s.origen not in grafo.nodos or s.destino not in grafo.nodos:
        raise HTTPException(404, detail='Origen o destino no pertenece al grafo activo')
    try:
        grafo_ml, auditoria = grafo_con_tiempos_ml(grafo, modelo, None, s.dia_semana, s.hora)
        resultado = BusquedaCostoUniforme().buscar(grafo_ml,s.origen,s.destino,'menor_tiempo')
    except ValueError as e:
        raise HTTPException(422, detail=str(e)) from e
    # La ruta se entrega aun si el CSV no tiene cobertura suficiente para
    # contrastarla. En ese caso la referencia y el loss NO se inventan.
    try:
        referencias = cargar_referencias(str(DATASET))
        comparacion = comparar_ruta(grafo_ml, resultado, referencias, s.dia_semana, s.hora)
    except (FileNotFoundError, ValueError, OSError, KeyError) as e:
        comparacion = {'disponible':False, 'motivo':f'Referencia no disponible: {e}',
                       'fuente':'Dataset operativo, tiempos derivados'}
    # Si faltan objetivos únicos del CSV, comparar con el tiempo BASE del
    # grafo original, claramente identificado como estimación simulada.
    # Nunca se presenta como observación real.
    if resultado.ruta_encontrada and not comparacion.get('disponible'):
        respaldo = comparar_con_grafo_base(grafo, grafo_ml, resultado)
        if respaldo.get('disponible'):
            comparacion = respaldo
    return {'resultado':resultado.model_dump(), 'modelo':'LinearRegression',
            'dia_semana':s.dia_semana,'hora':s.hora,'auditoria':auditoria,
            'comparacion_regresion':comparacion}
