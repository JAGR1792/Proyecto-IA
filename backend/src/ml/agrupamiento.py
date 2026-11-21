"""Agrupamiento no supervisado de patrones de movilidad (Persona 3, Corte 3).

Cada observación es una **arista dirigida** de la red OSM de Chapinero. Sus
features resumen cómo se mueve el tráfico por ella (perfil horario de velocidad
del dataset maestro operativo) y qué papel cumple en la red (centralidad de
intermediación, conectividad, capacidad y longitud). Con esas features se
entrena K-Means, se justifica el número de grupos ``k`` con varias métricas
internas y se analiza la distribución espacial de los grupos resultantes.

Fuentes compartidas por el equipo:

* ``datos/ml/red_osm_auditada/dataset_red_osm_operativo_auditado.csv.gz``:
  dataset maestro (1 741 aristas × 7 días × 24 horas) usado por la regresión.
* ``datos/dataset_osm.json``: grafo OSM (nodos con coordenadas y aristas).
* ``datos/ml/dataset_clasificacion_congestion.csv``: etiquetas de congestión de
  la clasificación (solo para interpretar los grupos, nunca como feature).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import networkx as nx
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import (
    adjusted_rand_score,
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_samples,
    silhouette_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

SEMILLA = 42
K_CANDIDATOS: tuple[int, ...] = tuple(range(2, 11))
K_MINIMO_INTERPRETABLE = 3
UMBRAL_ESTABILIDAD_ARI = 0.95
N_SEMILLAS_ESTABILIDAD = 10

#: Features que entran a K-Means (todas numéricas, se estandarizan).
FEATURES_AGRUPAMIENTO: tuple[str, ...] = (
    "velocidad_media_kmh",
    "caida_hora_pico",
    "log_intermediacion",
    "carriles",
    "log_distancia",
    "grado_medio",
)

DESCRIPCION_FEATURES: dict[str, str] = {
    "velocidad_media_kmh": "Velocidad promedio de la arista en las 168 horas de la semana.",
    "caida_hora_pico": "1 − (velocidad en la peor hora pico laboral / velocidad nocturna).",
    "log_intermediacion": "log(1 + 1000·betweenness) ponderado por tiempo: cuántas rutas "
    "más rápidas pasan por la arista.",
    "carriles": "Número de carriles OSM (imputado con la mediana del tipo de vía).",
    "log_distancia": "Logaritmo de la longitud de la arista en metros.",
    "grado_medio": "Grado promedio (entradas + salidas) de los dos nodos extremos.",
}

#: Franjas horarias de un día hábil para resumir el perfil de velocidad.
FRANJAS: dict[str, tuple[int, ...]] = {
    "pico_am": (6, 7, 8, 9),
    "valle": (10, 11, 12, 13, 14, 15),
    "pico_pm": (16, 17, 18, 19),
    "noche": (22, 23, 0, 1, 2, 3, 4),
}

DIR_BACKEND = Path(__file__).resolve().parents[2]
DIR_DATOS = DIR_BACKEND / "datos"
RUTA_DATASET_MAESTRO = (
    DIR_DATOS / "ml" / "red_osm_auditada" / "dataset_red_osm_operativo_auditado.csv.gz"
)
RUTA_GRAFO = DIR_DATOS / "dataset_osm.json"
RUTA_CLASIFICACION = DIR_DATOS / "ml" / "dataset_clasificacion_congestion.csv"
RUTA_PREDICCIONES_REGRESION = (
    DIR_DATOS
    / "ml"
    / "modelos_regresion_osm"
    / "evaluacion_detallada"
    / "predicciones_prueba_completas.csv.gz"
)

NOMBRE_DIRECTORIO = "agrupamiento"
NOMBRE_ARCHIVO_MODELO = "modelo_kmeans_movilidad.joblib"
NOMBRE_ARCHIVO_METRICAS = "metricas_agrupamiento.json"
NOMBRE_ARCHIVO_ASIGNACIONES = "asignaciones_clusters.csv"
NOMBRE_ARCHIVO_EVALUACION_K = "evaluacion_k.csv"


# ==================== Rutas de artefactos ====================


def directorio_agrupamiento(base_datos: Path | None = None) -> Path:
    """Ruta ``backend/datos/ml/agrupamiento`` (la crea si no existe)."""
    destino = (base_datos or DIR_DATOS) / "ml" / NOMBRE_DIRECTORIO
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def ruta_metricas(base_datos: Path | None = None) -> Path:
    """Ruta del JSON con métricas, perfiles y análisis espacial."""
    return directorio_agrupamiento(base_datos) / NOMBRE_ARCHIVO_METRICAS


def ruta_asignaciones(base_datos: Path | None = None) -> Path:
    """Ruta del CSV arista → cluster."""
    return directorio_agrupamiento(base_datos) / NOMBRE_ARCHIVO_ASIGNACIONES


def ruta_modelo(base_datos: Path | None = None) -> Path:
    """Ruta del pipeline (escalador + K-Means) persistido con joblib."""
    return directorio_agrupamiento(base_datos) / NOMBRE_ARCHIVO_MODELO


# ==================== Carga de datos ====================


def cargar_grafo_json(ruta: Path | str = RUTA_GRAFO) -> dict[str, Any]:
    """Lee el grafo OSM serializado (``dataset_osm.json``)."""
    return json.loads(Path(ruta).read_text(encoding="utf-8"))


def tablas_desde_grafo(grafo: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Convierte el JSON del grafo en tablas de nodos y aristas.

    Args:
        grafo: Diccionario con ``nodos`` (dict o lista) y ``aristas`` (lista).

    Returns:
        ``(nodos, aristas)``. Nodos con ``id, latitud, longitud``; aristas con
        ``arista_id, origen, destino, distancia_m, tiempo_base_min, tipo_via,
        nombre_via, carriles, sentido_unico, geometria``.
    """
    crudos = grafo["nodos"]
    lista_nodos = list(crudos.values()) if isinstance(crudos, dict) else list(crudos)
    nodos = pd.DataFrame(
        [
            {
                "id": str(n["id"]),
                "latitud": float(n["coordenadas"]["latitud"]),
                "longitud": float(n["coordenadas"]["longitud"]),
            }
            for n in lista_nodos
        ]
    )
    filas = []
    for a in grafo["aristas"]:
        atributos = a.get("atributos") or {}
        filas.append(
            {
                "arista_id": str(a["id"]),
                "origen": str(a["origen"]),
                "destino": str(a["destino"]),
                "distancia_m": float(a["distancia"]),
                "tiempo_base_min": float(a["tiempo_estimado"]),
                "tipo_via": str(atributos.get("tipo_via") or "otro"),
                "nombre_via": atributos.get("nombre_via") or "Sin nombre",
                "carriles": atributos.get("carriles"),
                "sentido_unico": bool(atributos.get("sentido_unico", False)),
                "geometria": atributos.get("geometria"),
            }
        )
    aristas = pd.DataFrame(filas)
    aristas["carriles"] = pd.to_numeric(aristas["carriles"], errors="coerce")
    return nodos, aristas


def cargar_dataset_maestro(ruta: Path | str = RUTA_DATASET_MAESTRO) -> pd.DataFrame:
    """Lee el dataset maestro operativo (arista × día × hora)."""
    columnas = ["id_arista_osm", "dia_semana", "hora", "velocidad_kmh", "fuente_dato"]
    df = pd.read_csv(ruta, usecols=columnas)
    df["arista_id"] = df["id_arista_osm"].astype(str)
    return df.drop(columns=["id_arista_osm"])


# ==================== Ingeniería de features ====================


def perfil_movilidad(maestro: pd.DataFrame) -> pd.DataFrame:
    """Resume el perfil temporal de velocidad de cada arista.

    Args:
        maestro: Filas ``arista_id, dia_semana (0=lunes), hora, velocidad_kmh``.

    Returns:
        DataFrame indexado por ``arista_id`` con velocidad media, velocidad por
        franja de día hábil, fin de semana, caída en hora pico y variabilidad.
    """
    laboral = maestro[maestro["dia_semana"] <= 4]
    fin_semana = maestro[maestro["dia_semana"] >= 5]

    perfil = pd.DataFrame(
        {"velocidad_media_kmh": maestro.groupby("arista_id")["velocidad_kmh"].mean()}
    )
    for nombre, horas in FRANJAS.items():
        sub = laboral[laboral["hora"].isin(horas)]
        perfil[f"vel_{nombre}_kmh"] = sub.groupby("arista_id")["velocidad_kmh"].mean()
    perfil["vel_fin_semana_kmh"] = fin_semana.groupby("arista_id")["velocidad_kmh"].mean()

    por_hora = laboral.groupby(["arista_id", "hora"])["velocidad_kmh"].mean().unstack()
    peor_pico = np.minimum(perfil["vel_pico_am_kmh"], perfil["vel_pico_pm_kmh"])
    perfil["caida_hora_pico"] = 1.0 - peor_pico / perfil["vel_noche_kmh"]
    perfil["variabilidad_horaria"] = por_hora.std(axis=1) / por_hora.mean(axis=1)
    perfil["fuente_dato"] = maestro.groupby("arista_id")["fuente_dato"].agg(
        lambda s: s.mode().iat[0]
    )
    return perfil


def metricas_red(aristas: pd.DataFrame) -> pd.DataFrame:
    """Centralidad de intermediación y conectividad de cada arista.

    La intermediación se calcula sobre el grafo dirigido ponderado por el tiempo
    base: aproxima cuántos viajes de menor tiempo pasan por la arista.

    Returns:
        DataFrame indexado por ``arista_id`` con ``intermediacion`` y ``grado_medio``.
    """
    g = nx.MultiDiGraph()
    for fila in aristas.itertuples(index=False):
        g.add_edge(fila.origen, fila.destino, key=fila.arista_id, peso=fila.tiempo_base_min)
    intermediacion = nx.edge_betweenness_centrality(g, weight="peso", normalized=True)
    por_arista = {clave[2]: valor for clave, valor in intermediacion.items()}
    grado = dict(g.degree())
    return pd.DataFrame(
        {
            "intermediacion": [por_arista.get(a, 0.0) for a in aristas["arista_id"]],
            "grado_medio": [
                (grado[o] + grado[d]) / 2.0
                for o, d in zip(aristas["origen"], aristas["destino"], strict=True)
            ],
        },
        index=aristas["arista_id"].to_numpy(),
    )


def construir_features_agrupamiento(
    maestro: pd.DataFrame,
    nodos: pd.DataFrame,
    aristas: pd.DataFrame,
) -> pd.DataFrame:
    """Tabla final de features (una fila por arista) lista para K-Means.

    Además de :data:`FEATURES_AGRUPAMIENTO` conserva columnas descriptivas
    (tipo de vía, nombre, coordenadas del punto medio) para interpretar y
    graficar los grupos.
    """
    perfil = perfil_movilidad(maestro)
    red = metricas_red(aristas)
    base = aristas.set_index("arista_id")
    df = base.join(perfil, how="inner").join(red, how="left")

    mediana_tipo = df.groupby("tipo_via")["carriles"].transform("median")
    df["carriles"] = df["carriles"].fillna(mediana_tipo).fillna(2.0)
    df["log_intermediacion"] = np.log1p(df["intermediacion"] * 1000.0)
    df["log_distancia"] = np.log(df["distancia_m"].clip(lower=1.0))

    coords = nodos.set_index("id")[["latitud", "longitud"]]
    o = coords.reindex(df["origen"]).to_numpy()
    d = coords.reindex(df["destino"]).to_numpy()
    df["lat_origen"], df["lon_origen"] = o[:, 0], o[:, 1]
    df["lat_destino"], df["lon_destino"] = d[:, 0], d[:, 1]
    df["latitud"] = (o[:, 0] + d[:, 0]) / 2.0
    df["longitud"] = (o[:, 1] + d[:, 1]) / 2.0

    df = df.dropna(subset=list(FEATURES_AGRUPAMIENTO))
    df.index.name = "arista_id"
    return df


# ==================== Selección de k y entrenamiento ====================


def crear_pipeline(k: int, semilla: int = SEMILLA, n_init: int = 20) -> Pipeline:
    """Estandarización + K-Means (k-means++)."""
    return Pipeline(
        steps=[
            ("escalador", StandardScaler()),
            ("kmeans", KMeans(n_clusters=k, n_init=n_init, random_state=semilla)),
        ]
    )


def estabilidad_ari(Z: np.ndarray, k: int, n_semillas: int = N_SEMILLAS_ESTABILIDAD) -> float:
    """ARI medio entre la partición de la semilla 0 y las de otras semillas.

    Cada corrida usa el mismo procedimiento que el modelo final (k-means++ con
    varias inicializaciones), así que mide si *ese procedimiento* es
    reproducible. 1.0 = mismos grupos con cualquier semilla; valores bajos
    indican grupos frágiles que dependen del azar.
    """
    etiquetas = [
        KMeans(n_clusters=k, n_init=10, random_state=s).fit_predict(Z) for s in range(n_semillas)
    ]
    return float(np.mean([adjusted_rand_score(etiquetas[0], e) for e in etiquetas[1:]]))


def evaluar_rango_k(
    X: pd.DataFrame,
    ks: tuple[int, ...] = K_CANDIDATOS,
    semilla: int = SEMILLA,
) -> pd.DataFrame:
    """Calcula inercia, silueta, Davies-Bouldin, Calinski-Harabasz y estabilidad.

    Args:
        X: Features sin escalar (columnas de :data:`FEATURES_AGRUPAMIENTO`).
        ks: Valores de ``k`` a evaluar.
        semilla: Semilla de K-Means.

    Returns:
        Una fila por ``k`` con todas las métricas y el tamaño del grupo mínimo.
    """
    Z = StandardScaler().fit_transform(X)
    filas = []
    for k in ks:
        modelo = KMeans(n_clusters=k, n_init=20, random_state=semilla).fit(Z)
        etiquetas = modelo.labels_
        conteos = np.bincount(etiquetas, minlength=k)
        filas.append(
            {
                "k": int(k),
                "inercia": float(modelo.inertia_),
                "silueta": float(silhouette_score(Z, etiquetas)),
                "davies_bouldin": float(davies_bouldin_score(Z, etiquetas)),
                "calinski_harabasz": float(calinski_harabasz_score(Z, etiquetas)),
                "estabilidad_ari": estabilidad_ari(Z, k),
                "grupo_minimo_pct": float(100.0 * conteos.min() / len(etiquetas)),
            }
        )
    tabla = pd.DataFrame(filas)
    tabla["codo_kneedle"] = _distancia_codo(tabla["k"].to_numpy(), tabla["inercia"].to_numpy())
    return tabla


def _distancia_codo(ks: np.ndarray, inercias: np.ndarray) -> np.ndarray:
    """Distancia normalizada de cada punto a la recta entre extremos (Kneedle)."""
    x = (ks - ks.min()) / max(ks.max() - ks.min(), 1)
    y = (inercias.max() - inercias) / max(inercias.max() - inercias.min(), 1e-12)
    return y - x


def seleccionar_k(tabla: pd.DataFrame) -> tuple[int, list[str]]:
    """Elige ``k`` con un criterio multi-métrica explícito y reproducible.

    Regla:

    1. Se descartan ``k < 3`` (dos grupos solo separan "rápidas" vs "resto").
    2. Se exige estabilidad ARI ≥ 0.95 entre semillas (grupos reproducibles).
    3. Entre los candidatos estables se puntúa cada ``k`` por su rango en
       silueta (↑), Davies-Bouldin (↓), Calinski-Harabasz (↑) y codo (↑);
       gana la menor suma de rangos y, en empate, el ``k`` más pequeño.

    Returns:
        ``(k_elegido, justificacion)`` con frases listas para el informe.
    """
    candidatos = tabla[tabla["k"] >= K_MINIMO_INTERPRETABLE].copy()
    estables = candidatos[candidatos["estabilidad_ari"] >= UMBRAL_ESTABILIDAD_ARI]
    if estables.empty:
        estables = candidatos.nlargest(1, "estabilidad_ari")
    estables = estables.copy()
    estables["rango_total"] = (
        estables["silueta"].rank(ascending=False)
        + estables["davies_bouldin"].rank(ascending=True)
        + estables["calinski_harabasz"].rank(ascending=False)
        + estables["codo_kneedle"].rank(ascending=False)
    )
    elegido = estables.sort_values(["rango_total", "k"]).iloc[0]
    k = int(elegido["k"])

    mejor_silueta = tabla.loc[tabla["silueta"].idxmax()]
    descartados = candidatos[candidatos["estabilidad_ari"] < UMBRAL_ESTABILIDAD_ARI]["k"]
    justificacion = [
        f"k = 2 tiene la silueta más alta ({mejor_silueta['silueta']:.3f}) pero solo separa "
        "las vías arteriales rápidas del resto; no describe patrones de movilidad útiles."
        if int(mejor_silueta["k"]) == 2
        else f"La silueta máxima se obtiene con k = {int(mejor_silueta['k'])}.",
        f"Se exige estabilidad ARI ≥ {UMBRAL_ESTABILIDAD_ARI:.2f} entre "
        f"{N_SEMILLAS_ESTABILIDAD} inicializaciones; quedan fuera k = "
        f"{', '.join(str(int(x)) for x in descartados) or 'ninguno'}.",
        f"Entre los k estables, k = {k} obtiene la mejor combinación de silueta "
        f"({elegido['silueta']:.3f}), Davies-Bouldin ({elegido['davies_bouldin']:.3f}), "
        f"Calinski-Harabasz ({elegido['calinski_harabasz']:.0f}) y codo de la inercia.",
        f"Con k = {k} el grupo más pequeño reúne el {elegido['grupo_minimo_pct']:.1f} % de "
        f"las aristas y la partición se repite con ARI {elegido['estabilidad_ari']:.3f}.",
    ]
    return k, justificacion


# ==================== Interpretación de grupos ====================


def nombrar_grupos(perfiles: pd.DataFrame) -> dict[int, dict[str, str]]:
    """Asigna nombres legibles a cada cluster a partir de sus centroides.

    Los nombres no dependen del número interno que asigne K-Means; se reparten
    en este orden, cada vez entre los grupos que aún no tienen nombre:

    1. mayor caída en hora pico → corredores críticos en hora pico;
    2. mayor velocidad media → corredores rápidos;
    3. mayor grado de los nodos → malla local densa;
    4. mayor intermediación → vías colectoras de paso;
    5. menor longitud → tramos cortos de intersección;
    6. menor intermediación → vías residenciales internas;
    7. el resto → vías locales mixtas.
    """
    restantes = list(perfiles.index)
    nombres: dict[int, dict[str, str]] = {}

    def asignar(columna: str, mayor: bool, nombre: str, descripcion: str) -> None:
        if not restantes:
            return
        valores = perfiles.loc[restantes, columna]
        cid = int(valores.idxmax() if mayor else valores.idxmin())
        restantes.remove(cid)
        nombres[cid] = {"nombre": nombre, "descripcion": descripcion}

    reglas = [
        (
            "caida_hora_pico",
            True,
            "Corredores críticos en hora pico",
            "Arterias con muchas rutas de paso que pierden más velocidad en las horas pico.",
        ),
        (
            "velocidad_media_kmh",
            True,
            "Corredores rápidos",
            "Avenidas y troncales con las velocidades más altas durante todo el día.",
        ),
        (
            "grado_medio",
            True,
            "Malla local densa",
            "Vías locales entre intersecciones muy conectadas, con poco tráfico de paso.",
        ),
        (
            "log_intermediacion",
            True,
            "Vías colectoras de paso",
            "Calles locales que muchas rutas usan para llegar a los corredores.",
        ),
        (
            "log_distancia",
            False,
            "Tramos cortos de intersección",
            "Segmentos muy cortos que conectan cruces, glorietas y accesos.",
        ),
        (
            "log_intermediacion",
            False,
            "Vías residenciales internas",
            "Calles de barrio que casi ninguna ruta usa como paso.",
        ),
    ]
    for regla in reglas:
        asignar(*regla)
    for i, cid in enumerate(sorted(restantes), start=1):
        sufijo = "" if len(restantes) == 1 else f" {i}"
        nombres[int(cid)] = {
            "nombre": f"Vías locales mixtas{sufijo}",
            "descripcion": "Vías locales sin un rasgo dominante frente a los demás grupos.",
        }
    return nombres


def perfiles_grupos(df: pd.DataFrame) -> pd.DataFrame:
    """Promedio de features y velocidades por franja de cada cluster."""
    columnas = list(FEATURES_AGRUPAMIENTO) + [
        "intermediacion",
        "distancia_m",
        "vel_pico_am_kmh",
        "vel_valle_kmh",
        "vel_pico_pm_kmh",
        "vel_noche_kmh",
        "vel_fin_semana_kmh",
        "variabilidad_horaria",
    ]
    return df.groupby("cluster")[columnas].mean()


def homofilia_espacial(
    df: pd.DataFrame, n_permutaciones: int = 300, semilla: int = SEMILLA
) -> dict[str, float]:
    """Mide si aristas vecinas (que comparten nodo) caen en el mismo grupo.

    Compara la proporción observada de pares vecinos del mismo cluster con la
    que se obtendría permutando las etiquetas al azar (test de permutación).

    Returns:
        ``observada``, ``esperada_azar``, ``razon`` y ``p_valor``.
    """
    por_nodo: dict[str, list[int]] = {}
    for i, (o, d) in enumerate(zip(df["origen"], df["destino"], strict=True)):
        por_nodo.setdefault(o, []).append(i)
        por_nodo.setdefault(d, []).append(i)
    pares = {(a, b) for ids in por_nodo.values() for a in ids for b in ids if a < b}
    if not pares:
        return {"observada": 0.0, "esperada_azar": 0.0, "razon": 0.0, "p_valor": 1.0, "pares": 0}
    pa, pb = (np.array(x) for x in zip(*sorted(pares), strict=True))
    etiquetas = df["cluster"].to_numpy()
    observada = float(np.mean(etiquetas[pa] == etiquetas[pb]))

    rng = np.random.default_rng(semilla)
    azar = np.empty(n_permutaciones)
    for i in range(n_permutaciones):
        perm = rng.permutation(etiquetas)
        azar[i] = np.mean(perm[pa] == perm[pb])
    esperada = float(azar.mean())
    return {
        "observada": observada,
        "esperada_azar": esperada,
        "razon": observada / esperada if esperada else 0.0,
        "p_valor": float((np.sum(azar >= observada) + 1) / (n_permutaciones + 1)),
        "pares": len(pares),
    }


def _distancia_m(lat1: np.ndarray, lon1: np.ndarray, lat2: float, lon2: float) -> np.ndarray:
    """Distancia aproximada en metros (equirectangular; suficiente a escala barrio)."""
    r = 6_371_000.0
    x = np.radians(lon1 - lon2) * np.cos(np.radians((lat1 + lat2) / 2))
    y = np.radians(lat1 - lat2)
    return r * np.sqrt(x * x + y * y)


def distribucion_espacial(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Centroide geográfico, dispersión y vías más representativas por grupo."""
    lat0, lon0 = df["latitud"].mean(), df["longitud"].mean()
    filas = []
    for cid, sub in df.groupby("cluster"):
        lat_c, lon_c = sub["latitud"].mean(), sub["longitud"].mean()
        dispersion = _distancia_m(
            sub["latitud"].to_numpy(), sub["longitud"].to_numpy(), lat_c, lon_c
        )
        vias = (
            sub[sub["nombre_via"] != "Sin nombre"]
            .groupby("nombre_via")["distancia_m"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
        )
        filas.append(
            {
                "cluster": int(cid),
                "centroide": {"latitud": float(lat_c), "longitud": float(lon_c)},
                "distancia_al_centro_zona_m": float(
                    _distancia_m(np.array([lat_c]), np.array([lon_c]), lat0, lon0)[0]
                ),
                "dispersion_media_m": float(dispersion.mean()),
                "longitud_total_km": float(sub["distancia_m"].sum() / 1000.0),
                "vias_principales": [
                    {"nombre": str(n), "metros": round(float(m), 1)} for n, m in vias.items()
                ],
            }
        )
    return filas


def cruce_clasificacion(
    df: pd.DataFrame, ruta: Path | str = RUTA_CLASIFICACION
) -> dict[int, dict[str, float]] | None:
    """Distribución de congestión (Persona 2) dentro de cada cluster.

    Las etiquetas de congestión **no** se usan para entrenar; solo sirven para
    comprobar que los grupos tienen sentido frente a la clasificación.
    """
    ruta = Path(ruta)
    if not ruta.is_file():
        return None
    clas = pd.read_csv(ruta, usecols=["arista_id", "congestion"])
    clas["arista_id"] = clas["arista_id"].astype(str)
    unido = clas.merge(df[["cluster"]], left_on="arista_id", right_index=True, how="inner")
    tabla = pd.crosstab(unido["cluster"], unido["congestion"], normalize="index")
    return {int(c): {str(k): float(v) for k, v in fila.items()} for c, fila in tabla.iterrows()}


def cruce_regresion(
    df: pd.DataFrame, ruta: Path | str = RUTA_PREDICCIONES_REGRESION
) -> dict[int, dict[str, float]] | None:
    """Error de la regresión lineal (Persona 1) en cada cluster.

    Permite ver en qué tipo de vía la predicción de tiempos es menos precisa.
    """
    ruta = Path(ruta)
    if not ruta.is_file():
        return None
    pred = pd.read_csv(ruta, usecols=["indice_arista_osm", "error_absoluto_min", "tiempo_min"])
    indice = df.reset_index()[["indice_osm", "cluster"]] if "indice_osm" in df else None
    if indice is None:
        return None
    unido = pred.merge(indice, left_on="indice_arista_osm", right_on="indice_osm", how="inner")
    salida = {}
    for c, sub in unido.groupby("cluster"):
        salida[int(c)] = {
            "mae_s": float(sub["error_absoluto_min"].mean() * 60.0),
            "mae_relativo_pct": float(
                100.0 * sub["error_absoluto_min"].sum() / sub["tiempo_min"].sum()
            ),
            "registros": int(len(sub)),
        }
    return salida


# ==================== Resultado completo ====================


@dataclass
class ResultadoAgrupamiento:
    """Artefactos del agrupamiento final."""

    k: int
    justificacion: list[str]
    evaluacion_k: pd.DataFrame
    datos: pd.DataFrame
    pipeline: Pipeline = field(repr=False)
    metricas: dict[str, float]
    nombres: dict[int, dict[str, str]]
    perfiles: pd.DataFrame


def entrenar_agrupamiento(
    features: pd.DataFrame,
    k: int | None = None,
    ks: tuple[int, ...] = K_CANDIDATOS,
    semilla: int = SEMILLA,
) -> ResultadoAgrupamiento:
    """Evalúa ``k``, entrena K-Means final y etiqueta cada arista.

    Args:
        features: Salida de :func:`construir_features_agrupamiento`.
        k: Fuerza un número de grupos; si es None se usa :func:`seleccionar_k`.
        ks: Rango evaluado para justificar ``k``.
        semilla: Semilla de reproducibilidad.
    """
    X = features[list(FEATURES_AGRUPAMIENTO)]
    tabla = evaluar_rango_k(X, ks, semilla)
    if k is None:
        k, justificacion = seleccionar_k(tabla)
    else:
        justificacion = [f"k = {k} fijado manualmente."]

    pipeline = crear_pipeline(k, semilla).fit(X)
    Z = pipeline.named_steps["escalador"].transform(X)
    etiquetas_crudas = pipeline.named_steps["kmeans"].labels_

    # Renumerar 0..k-1 por velocidad media descendente para que los IDs sean estables.
    vel = pd.Series(X["velocidad_media_kmh"].to_numpy()).groupby(etiquetas_crudas).mean()
    orden = {int(c): i for i, c in enumerate(vel.sort_values(ascending=False).index)}
    etiquetas = np.array([orden[int(e)] for e in etiquetas_crudas])

    datos = features.copy()
    datos["cluster"] = etiquetas
    datos["silueta"] = silhouette_samples(Z, etiquetas)
    pca = PCA(n_components=2, random_state=semilla).fit(Z)
    comp = pca.transform(Z)
    datos["pca_1"], datos["pca_2"] = comp[:, 0], comp[:, 1]

    fila_k = tabla.set_index("k").loc[k]
    metricas = {
        "silueta": float(silhouette_score(Z, etiquetas)),
        "davies_bouldin": float(davies_bouldin_score(Z, etiquetas)),
        "calinski_harabasz": float(calinski_harabasz_score(Z, etiquetas)),
        "inercia": float(pipeline.named_steps["kmeans"].inertia_),
        "estabilidad_ari": float(fila_k["estabilidad_ari"]),
        "varianza_pca_2d": float(pca.explained_variance_ratio_.sum()),
    }
    perfiles = perfiles_grupos(datos)
    nombres = nombrar_grupos(perfiles)
    return ResultadoAgrupamiento(
        k=k,
        justificacion=justificacion,
        evaluacion_k=tabla,
        datos=datos,
        pipeline=pipeline,
        metricas=metricas,
        nombres=nombres,
        perfiles=perfiles,
    )


def resultado_a_json(
    res: ResultadoAgrupamiento,
    incluir_geometria: bool = True,
) -> dict[str, Any]:
    """Serializa el agrupamiento para la API y el dashboard (sin pipeline)."""
    datos = res.datos
    conteos = datos["cluster"].value_counts().sort_index()
    tipos = pd.crosstab(datos["cluster"], datos["tipo_via"])
    sil_grupo = datos.groupby("cluster")["silueta"].mean()
    clasif = cruce_clasificacion(datos)
    regres = cruce_regresion(datos)
    espacial = {e["cluster"]: e for e in distribucion_espacial(datos)}

    grupos = []
    for cid in conteos.index:
        p = res.perfiles.loc[cid]
        grupos.append(
            {
                "cluster": int(cid),
                **res.nombres[int(cid)],
                "aristas": int(conteos[cid]),
                "porcentaje": float(100.0 * conteos[cid] / len(datos)),
                "silueta_media": float(sil_grupo[cid]),
                "perfil": {k: round(float(v), 5) for k, v in p.items()},
                "tipos_via": {str(t): int(n) for t, n in tipos.loc[cid].items() if n > 0},
                "congestion": clasif.get(int(cid)) if clasif else None,
                "regresion": regres.get(int(cid)) if regres else None,
                "espacial": espacial[int(cid)],
            }
        )

    payload: dict[str, Any] = {
        "schema_version": 1,
        "algoritmo": "K-Means (k-means++, n_init=20) sobre features estandarizadas",
        "fecha_generacion": datetime.now().isoformat(timespec="seconds"),
        "k": res.k,
        "justificacion_k": res.justificacion,
        "features": [
            {"nombre": f, "descripcion": DESCRIPCION_FEATURES[f]} for f in FEATURES_AGRUPAMIENTO
        ],
        "metricas": res.metricas,
        "evaluacion_k": res.evaluacion_k.round(5).to_dict(orient="records"),
        "grupos": grupos,
        "homofilia_espacial": homofilia_espacial(datos),
        "resumen_dataset": {
            "aristas": int(len(datos)),
            "observaciones_maestro": int(len(datos)) * 168,
            "fuente": "dataset_red_osm_operativo_auditado.csv.gz + dataset_osm.json",
        },
    }
    if incluir_geometria:
        payload["aristas"] = aristas_para_mapa(datos)
    return payload


def _simplificar(puntos: list[list[float]], maximo: int = 6) -> list[list[float]]:
    if len(puntos) <= maximo:
        return puntos
    idx = np.linspace(0, len(puntos) - 1, maximo).round().astype(int)
    return [puntos[i] for i in idx]


def aristas_para_mapa(datos: pd.DataFrame) -> list[dict[str, Any]]:
    """Lista compacta arista → cluster con su trazo ``[[lon, lat], ...]``."""
    salida = []
    for aid, fila in datos.iterrows():
        geom = fila.get("geometria")
        if isinstance(geom, list) and len(geom) >= 2:
            trazo = _simplificar([[float(x), float(y)] for x, y in geom])
        else:
            trazo = [
                [fila["lon_origen"], fila["lat_origen"]],
                [fila["lon_destino"], fila["lat_destino"]],
            ]
        salida.append(
            {
                "id": str(aid),
                "c": int(fila["cluster"]),
                "v": str(fila["nombre_via"]),
                "t": [[round(x, 5), round(y, 5)] for x, y in trazo],
            }
        )
    return salida


def tabla_asignaciones(res: ResultadoAgrupamiento) -> pd.DataFrame:
    """Tabla plana arista → cluster con features (para CSV y endpoint)."""
    columnas = [
        "cluster",
        "silueta",
        "nombre_via",
        "tipo_via",
        "origen",
        "destino",
        "latitud",
        "longitud",
        *FEATURES_AGRUPAMIENTO,
        "intermediacion",
    ]
    tabla = res.datos[columnas].copy()
    tabla.insert(1, "nombre_cluster", tabla["cluster"].map(lambda c: res.nombres[int(c)]["nombre"]))
    return tabla.reset_index()


# ==================== Persistencia ====================


def ejecutar_pipeline_completo(
    base_datos: Path | None = None,
    k: int | None = None,
) -> tuple[ResultadoAgrupamiento, dict[str, Any]]:
    """Carga datos, entrena y guarda JSON, CSV y joblib.

    Returns:
        ``(resultado, payload_json)``.
    """
    base = base_datos or DIR_DATOS
    grafo = cargar_grafo_json(base / "dataset_osm.json")
    nodos, aristas = tablas_desde_grafo(grafo)
    aristas["indice_osm"] = np.arange(len(aristas))
    maestro = cargar_dataset_maestro(
        base / "ml" / "red_osm_auditada" / "dataset_red_osm_operativo_auditado.csv.gz"
    )
    features = construir_features_agrupamiento(maestro, nodos, aristas)
    res = entrenar_agrupamiento(features, k=k)
    payload = resultado_a_json(res)

    destino = directorio_agrupamiento(base)
    joblib.dump(res.pipeline, destino / NOMBRE_ARCHIVO_MODELO)
    tabla_asignaciones(res).to_csv(destino / NOMBRE_ARCHIVO_ASIGNACIONES, index=False)
    res.evaluacion_k.to_csv(destino / NOMBRE_ARCHIVO_EVALUACION_K, index=False)
    sin_geometria = {k_: v for k_, v in payload.items() if k_ != "aristas"}
    (destino / NOMBRE_ARCHIVO_METRICAS).write_text(
        json.dumps(sin_geometria, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return res, payload


def cargar_metricas_desde_disco(base_datos: Path | None = None) -> dict[str, Any]:
    """Lee ``metricas_agrupamiento.json``.

    Raises:
        FileNotFoundError: Si aún no se ha entrenado el agrupamiento.
    """
    ruta = ruta_metricas(base_datos)
    if not ruta.is_file():
        raise FileNotFoundError(f"No hay métricas de agrupamiento en {ruta}")
    return json.loads(ruta.read_text(encoding="utf-8"))


def cargar_asignaciones(base_datos: Path | None = None) -> pd.DataFrame:
    """Lee el CSV arista → cluster.

    Raises:
        FileNotFoundError: Si aún no se ha entrenado el agrupamiento.
    """
    ruta = ruta_asignaciones(base_datos)
    if not ruta.is_file():
        raise FileNotFoundError(f"No hay asignaciones de agrupamiento en {ruta}")
    return pd.read_csv(ruta, dtype={"arista_id": str, "origen": str, "destino": str})
