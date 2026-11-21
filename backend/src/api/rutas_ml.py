"""Endpoints de aprendizaje automático (regresión lineal y clasificación ML)."""

from __future__ import annotations

import math
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.api.rutas_grafo import obtener_grafo
from src.busqueda.ucs import BusquedaCostoUniforme
from src.ml.clasificacion import (
    cargar_metricas_desde_disco,
    cargar_modelo,
    modelo_disponible,
    predecir_congestion_aristas,
    reentrenar_y_persistir,
)
from src.ml.comparacion_ruta import cargar_referencias, comparar_con_grafo_base, comparar_ruta
from src.ml.tiempos_ruta import (
    DATASET,
    MODELO,
    cargar_indice,
    grafo_con_tiempos_ml,
)
from src.ml.tiempos_ruta import (
    cargar_modelo as cargar_modelo_regresion,
)

router = APIRouter()

_modelo_cache: Any | None = None


def _invalidar_cache_modelo() -> None:
    global _modelo_cache
    _modelo_cache = None


def _obtener_pipeline() -> Any:
    global _modelo_cache
    if _modelo_cache is None:
        try:
            _modelo_cache = cargar_modelo()
        except FileNotFoundError as e:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Modelo ML no entrenado. Ejecute POST /api/v1/ml/clasificacion/reentrenar "
                    "o el script generar_dataset_clasificacion.py."
                ),
            ) from e
    return _modelo_cache


# ==================== Regresión lineal (tiempos de viaje) ====================


class SolicitudRutaML(BaseModel):
    """Parámetros de solicitud para ruta óptima con regresión lineal."""

    origen: str = Field(min_length=1)
    destino: str = Field(min_length=1)
    dia_semana: int = Field(ge=0, le=6, description="0 lunes, 6 domingo")
    hora: int = Field(ge=0, le=23)


class SolicitudPrediccionML(BaseModel):
    """Parámetros para predicción individual de tiempo de viaje."""

    distancia_m: float = Field(gt=0, le=100000)
    tipo_via: str = Field(min_length=1)
    dia_semana: int = Field(ge=0, le=6)
    hora: int = Field(ge=0, le=23)


def _recursos():
    try:
        return cargar_modelo_regresion(str(MODELO)), cargar_indice(str(DATASET))
    except FileNotFoundError as e:
        raise HTTPException(503, detail=str(e)) from e
    except (ValueError, OSError) as e:
        raise HTTPException(500, detail=str(e)) from e


@router.get("/estado")
def estado_ml():
    """Comprueba instalación del artefacto y archivo de datos de regresión."""
    return {
        "modelo_presente": MODELO.is_file(),
        "dataset_presente": DATASET.is_file(),
        "algoritmo": "LinearRegression",
        "endpoint_ruta": "/api/v1/ml/ruta",
    }


@router.post("/predecir")
def predecir(s: SolicitudPrediccionML):
    """Predice un tiempo individual; útil para validar el modelo por API."""
    from src.ml.tiempos_ruta import crear_entradas

    try:
        modelo = cargar_modelo_regresion(str(MODELO))
    except FileNotFoundError as e:
        raise HTTPException(503, detail=str(e)) from e
    fila = {"distancia_m": s.distancia_m, "tipo_via": s.tipo_via}
    t = float(modelo.predict(crear_entradas([fila], s.dia_semana, s.hora))[0])
    if not math.isfinite(t):
        raise HTTPException(500, detail="Prediccion no finita")
    minimo, maximo = 0.06 * s.distancia_m / 80, 0.06 * s.distancia_m / 5
    return {
        "tiempo_estimado_min": max(minimo, min(maximo, t)),
        "algoritmo": "LinearRegression",
        "unidad": "minutos",
    }


@router.post("/ruta")
def ruta_ml(s: SolicitudRutaML):
    """Calcula la ruta con UCS sobre tiempos predichos, sin alterar el grafo compartido."""
    try:
        modelo = cargar_modelo_regresion(str(MODELO))
    except FileNotFoundError as e:
        raise HTTPException(503, detail=str(e)) from e
    grafo = obtener_grafo()
    if s.origen not in grafo.nodos or s.destino not in grafo.nodos:
        raise HTTPException(404, detail="Origen o destino no pertenece al grafo activo")
    try:
        grafo_ml, auditoria = grafo_con_tiempos_ml(grafo, modelo, None, s.dia_semana, s.hora)
        resultado = BusquedaCostoUniforme().buscar(grafo_ml, s.origen, s.destino, "menor_tiempo")
    except ValueError as e:
        raise HTTPException(422, detail=str(e)) from e

    try:
        referencias = cargar_referencias(str(DATASET))
        comparacion = comparar_ruta(grafo_ml, resultado, referencias, s.dia_semana, s.hora)
    except (FileNotFoundError, ValueError, OSError, KeyError) as e:
        comparacion = {
            "disponible": False,
            "motivo": f"Referencia no disponible: {e}",
            "fuente": "Dataset operativo, tiempos derivados",
        }

    if resultado.ruta_encontrada and not comparacion.get("disponible"):
        respaldo = comparar_con_grafo_base(grafo, grafo_ml, resultado)
        if respaldo.get("disponible"):
            comparacion = respaldo

    return {
        "resultado": resultado.model_dump(),
        "modelo": "LinearRegression",
        "dia_semana": s.dia_semana,
        "hora": s.hora,
        "auditoria": auditoria,
        "comparacion_regresion": comparacion,
    }


# ==================== Clasificación supervisada de congestión ====================


class PredecirCongestionEntrada(BaseModel):
    """Cuerpo para predicción por hora de salida."""

    hora_salida: str = Field(
        ...,
        pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$",
        description="Hora de salida HH:MM (día hábil sintético).",
    )
    arista_ids: list[str] | None = Field(
        default=None,
        description="IDs de aristas a predecir; si se omite, todas las predicibles.",
    )


@router.get("/clasificacion")
async def obtener_metricas_clasificacion() -> dict[str, Any]:
    """Métricas, mejor modelo y matrices de confusión desde JSON en disco."""
    try:
        payload = cargar_metricas_desde_disco()
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail="No hay metricas_clasificacion.json. Entrene con POST .../reentrenar.",
        ) from e
    payload["modelo_disponible"] = modelo_disponible()
    return payload


@router.post("/clasificacion/predecir")
async def predecir_clasificacion(entrada: PredecirCongestionEntrada) -> dict[str, Any]:
    """Predice congestión (baja/media/alta) por arista según hora de salida."""
    pipeline = _obtener_pipeline()
    grafo = obtener_grafo()

    if entrada.arista_ids:
        ids_grafo = {a.id for a in grafo.aristas}
        desconocidas = [aid for aid in entrada.arista_ids if aid not in ids_grafo]
        if desconocidas:
            raise HTTPException(
                status_code=422,
                detail=f"Aristas no encontradas en el grafo: {desconocidas[:20]}",
            )

    predicciones = predecir_congestion_aristas(
        pipeline,
        grafo,
        entrada.hora_salida,
        entrada.arista_ids,
    )
    return {
        "hora_salida": entrada.hora_salida,
        "total": len(predicciones),
        "predicciones": predicciones,
    }


@router.post("/clasificacion/reentrenar")
async def reentrenar_clasificacion() -> dict[str, Any]:
    """Regenera CSV, métricas JSON y joblib del mejor clasificador."""
    try:
        grafo = obtener_grafo()
        resultado = reentrenar_y_persistir(grafo)
        _invalidar_cache_modelo()
        return {
            "mensaje": "Clasificación reentrenada",
            "mejor_modelo": resultado["mejor_modelo"],
            "resumen_dataset": resultado["resumen_dataset"],
            "modelo_guardado": resultado["modelo_guardado"],
            "metricas_guardadas": resultado["metricas_guardadas"],
        }
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reentrenando: {e}") from e


def reentrenar_tras_grafo_nuevo() -> dict[str, Any]:
    """Hook interno tras recarga OSM: reentrena y limpia caché del pipeline."""
    grafo = obtener_grafo()
    resultado = reentrenar_y_persistir(grafo)
    _invalidar_cache_modelo()
    return resultado
