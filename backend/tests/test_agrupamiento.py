"""Tests del agrupamiento K-Means de patrones de movilidad (Persona 3)."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from src.ml import agrupamiento as ag


def _grafo_sintetico() -> dict:
    """Rejilla 4x4 con una avenida rápida (fila 0) y calles locales."""
    nodos = {}
    for i in range(4):
        for j in range(4):
            nid = f"n{i}{j}"
            nodos[nid] = {
                "id": nid,
                "coordenadas": {"latitud": 4.65 + i * 0.001, "longitud": -74.06 + j * 0.001},
            }
    aristas = []
    for i in range(4):
        for j in range(4):
            for di, dj in ((0, 1), (1, 0)):
                if i + di < 4 and j + dj < 4:
                    for o, d in (
                        (f"n{i}{j}", f"n{i + di}{j + dj}"),
                        (f"n{i + di}{j + dj}", f"n{i}{j}"),
                    ):
                        avenida = i == 0 and di == 0
                        aristas.append(
                            {
                                "id": f"{o}-{d}",
                                "origen": o,
                                "destino": d,
                                "distancia": 110.0,
                                "tiempo_estimado": 0.11 if avenida else 0.2,
                                "atributos": {
                                    "tipo_via": "primaria" if avenida else "residencial",
                                    "nombre_via": "Avenida 1" if avenida else f"Calle {i}",
                                    "carriles": 3 if avenida else 2,
                                    "sentido_unico": False,
                                },
                            }
                        )
    return {"nodos": nodos, "aristas": aristas}


def _maestro_sintetico(aristas: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for fila in aristas.itertuples(index=False):
        base = 55.0 if fila.tipo_via == "primaria" else 30.0
        for dia in range(7):
            for hora in range(24):
                factor = 0.6 if hora in (7, 8, 17, 18) and dia < 5 else 1.0
                filas.append(
                    {
                        "arista_id": fila.arista_id,
                        "dia_semana": dia,
                        "hora": hora,
                        "velocidad_kmh": base * factor,
                        "fuente_dato": "SIMULACION",
                    }
                )
    return pd.DataFrame(filas)


@pytest.fixture(scope="module")
def features_sinteticas() -> pd.DataFrame:
    nodos, aristas = ag.tablas_desde_grafo(_grafo_sintetico())
    return ag.construir_features_agrupamiento(_maestro_sintetico(aristas), nodos, aristas)


def test_tablas_desde_grafo_acepta_nodos_dict():
    nodos, aristas = ag.tablas_desde_grafo(_grafo_sintetico())
    assert len(nodos) == 16
    assert {"arista_id", "origen", "destino", "carriles", "tipo_via"} <= set(aristas.columns)


def test_perfil_movilidad_caida_en_pico(features_sinteticas):
    f = features_sinteticas
    # Franja pico = 4 horas, 2 de ellas al 60 %: velocidad media 0.8 → caída 0.2
    assert np.allclose(f["caida_hora_pico"], 0.2)
    avenida = f[f["tipo_via"] == "primaria"]["velocidad_media_kmh"]
    local = f[f["tipo_via"] == "residencial"]["velocidad_media_kmh"]
    assert avenida.min() > local.max()


def test_features_completas_sin_nulos(features_sinteticas):
    columnas = list(ag.FEATURES_AGRUPAMIENTO) + ["latitud", "longitud"]
    assert not features_sinteticas[columnas].isna().any().any()


def test_evaluar_rango_k_columnas(features_sinteticas):
    tabla = ag.evaluar_rango_k(features_sinteticas[list(ag.FEATURES_AGRUPAMIENTO)], ks=(2, 3, 4))
    assert list(tabla["k"]) == [2, 3, 4]
    for col in ("inercia", "silueta", "davies_bouldin", "calinski_harabasz", "estabilidad_ari"):
        assert col in tabla
    assert tabla["inercia"].is_monotonic_decreasing


def test_seleccionar_k_respeta_minimo_y_estabilidad():
    tabla = pd.DataFrame(
        {
            "k": [2, 3, 4, 5],
            "inercia": [100.0, 70.0, 50.0, 45.0],
            "silueta": [0.6, 0.3, 0.35, 0.36],
            "davies_bouldin": [0.8, 1.2, 1.0, 0.9],
            "calinski_harabasz": [300.0, 250.0, 320.0, 310.0],
            "estabilidad_ari": [1.0, 0.99, 0.98, 0.70],
            "grupo_minimo_pct": [40.0, 20.0, 10.0, 1.0],
        }
    )
    tabla["codo_kneedle"] = ag._distancia_codo(tabla["k"].to_numpy(), tabla["inercia"].to_numpy())
    k, justificacion = ag.seleccionar_k(tabla)
    assert k == 4  # k=2 excluido por regla, k=5 inestable
    assert len(justificacion) == 4


def test_entrenar_agrupamiento_etiquetas_ordenadas(features_sinteticas):
    res = ag.entrenar_agrupamiento(features_sinteticas, k=2, ks=(2, 3))
    assert res.k == 2
    assert set(res.datos["cluster"]) == {0, 1}
    # cluster 0 = mayor velocidad media (renumeración estable)
    vel = res.datos.groupby("cluster")["velocidad_media_kmh"].mean()
    assert vel.loc[0] >= vel.loc[1]
    assert len(res.nombres) == 2
    assert -1.0 <= res.metricas["silueta"] <= 1.0


def test_nombrar_grupos_cubre_todos():
    perfiles = pd.DataFrame(
        {
            "caida_hora_pico": [0.4, 0.5, 0.4, 0.4, 0.4, 0.4, 0.4],
            "velocidad_media_kmh": [50, 26, 31, 31, 31, 31, 30],
            "grado_medio": [3.7, 3.8, 6.3, 4.1, 3.8, 3.9, 3.9],
            "log_intermediacion": [2.5, 3.3, 1.3, 3.1, 1.8, 0.9, 1.5],
            "log_distancia": [4.4, 4.6, 4.4, 4.4, 2.7, 4.6, 4.5],
        }
    )
    nombres = ag.nombrar_grupos(perfiles)
    assert nombres[1]["nombre"] == "Corredores críticos en hora pico"
    assert nombres[0]["nombre"] == "Corredores rápidos"
    assert nombres[2]["nombre"] == "Malla local densa"
    assert nombres[3]["nombre"] == "Vías colectoras de paso"
    assert nombres[4]["nombre"] == "Tramos cortos de intersección"
    assert nombres[5]["nombre"] == "Vías residenciales internas"
    assert nombres[6]["nombre"] == "Vías locales mixtas"


def test_homofilia_espacial_detecta_agrupacion(features_sinteticas):
    res = ag.entrenar_agrupamiento(features_sinteticas, k=2, ks=(2, 3))
    h = ag.homofilia_espacial(res.datos, n_permutaciones=50)
    assert h["pares"] > 0
    assert 0.0 <= h["observada"] <= 1.0
    assert h["razon"] > 1.0  # avenida contigua: vecinos comparten grupo más que al azar


def test_resultado_a_json_serializable(features_sinteticas):
    res = ag.entrenar_agrupamiento(features_sinteticas, k=2, ks=(2, 3))
    payload = ag.resultado_a_json(res)
    texto = json.dumps(payload)
    assert payload["k"] == 2
    assert len(payload["grupos"]) == 2
    assert len(payload["aristas"]) == len(features_sinteticas)
    assert "justificacion_k" in payload and texto


def test_pipeline_completo_datos_reales(tmp_path):
    """Integración sobre el dataset maestro real del repositorio."""
    if not ag.RUTA_DATASET_MAESTRO.is_file() or not ag.RUTA_GRAFO.is_file():
        pytest.skip("Datos reales no disponibles")
    base = tmp_path / "datos"
    (base / "ml" / "red_osm_auditada").mkdir(parents=True)
    (base / "dataset_osm.json").write_bytes(ag.RUTA_GRAFO.read_bytes())
    (base / "ml" / "red_osm_auditada" / ag.RUTA_DATASET_MAESTRO.name).write_bytes(
        ag.RUTA_DATASET_MAESTRO.read_bytes()
    )
    res, payload = ag.ejecutar_pipeline_completo(base_datos=base)
    assert 3 <= res.k <= 10
    assert payload["resumen_dataset"]["aristas"] == 1741
    assert res.metricas["estabilidad_ari"] >= ag.UMBRAL_ESTABILIDAD_ARI
    assert ag.cargar_metricas_desde_disco(base)["k"] == res.k
    asign = ag.cargar_asignaciones(base)
    assert len(asign) == 1741 and asign["arista_id"].is_unique
