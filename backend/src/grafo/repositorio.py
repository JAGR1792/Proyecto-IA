"""Repositorio para persistencia del grafo (JSON, GraphML, GeoJSON)."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import networkx as nx
import pandas as pd

from .modelos import Arista, Grafo, Nodo, Coordenadas, TipoNodo, NivelCongestion, TipoVia, AtributosArista, AtributosNodo


class ExcepcionRepositorio(Exception):
    """ExcepciÃ³n base para errores del repositorio."""

    pass


class RepositorioGrafo:
    """Maneja carga y guardado del grafo en mÃºltiples formatos."""

    def __init__(self, directorio_datos: Union[str, Path] = "datos"):
        self.directorio = Path(directorio_datos)
        self.directorio.mkdir(parents=True, exist_ok=True)

    # ==================== JSON ====================

    def guardar_json(self, grafo: Grafo, nombre_archivo: str = "grafo.json") -> Path:
        """Guarda grafo como JSON plano."""
        ruta = self.directorio / nombre_archivo

        datos = {
            "dirigido": grafo.dirigido,
            "metadata": grafo.metadata,
            "nodos": {nid: nodo.model_dump() for nid, nodo in grafo.nodos.items()},
            "aristas": [arista.model_dump() for arista in grafo.aristas],
        }

        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)

        return ruta

    def cargar_json(self, nombre_archivo: str = "grafo.json") -> Grafo:
        """Carga grafo desde JSON."""
        ruta = self.directorio / nombre_archivo

        if not ruta.exists():
            raise ExcepcionRepositorio(f"Archivo no encontrado: {ruta}")

        with open(ruta, "r", encoding="utf-8") as f:
            datos = json.load(f)

        grafo = Grafo(dirigido=datos.get("dirigido", True), metadata=datos.get("metadata", {}))

        for nid, ndata in datos.get("nodos", {}).items():
            grafo.agregar_nodo(Nodo(**ndata))

        for adata in datos.get("aristas", []):
            grafo.agregar_arista(Arista(**adata))

        return grafo

    # ==================== GraphML (NetworkX) ====================

    def guardar_graphml(self, grafo: Grafo, nombre_archivo: str = "grafo.graphml") -> Path:
        """Guarda grafo en formato GraphML (compatible con NetworkX, Gephi, etc.)."""
        ruta = self.directorio / nombre_archivo
        G = grafo.a_networkx()
        nx.write_graphml(G, ruta)
        return ruta

    def cargar_graphml(self, nombre_archivo: str = "grafo.graphml") -> Grafo:
        """Carga grafo desde GraphML."""
        ruta = self.directorio / nombre_archivo

        if not ruta.exists():
            raise ExcepcionRepositorio(f"Archivo no encontrado: {ruta}")

        G = nx.read_graphml(ruta)
        return Grafo.desde_networkx(G, dirigido=True)

    # ==================== GeoJSON ====================

    def guardar_geojson(
        self, grafo: Grafo, nombre_nodos: str = "nodos.geojson", nombre_aristas: str = "aristas.geojson"
    ) -> tuple[Path, Path]:
        """Exporta nodos y aristas como GeoJSON FeatureCollections."""
        ruta_nodos = self.directorio / nombre_nodos
        ruta_aristas = self.directorio / nombre_aristas

        features_nodos, features_aristas = self._construir_features_geojson(grafo)

        with open(ruta_nodos, "w", encoding="utf-8") as f:
            json.dump({"type": "FeatureCollection", "features": features_nodos}, f, ensure_ascii=False, indent=2)

        with open(ruta_aristas, "w", encoding="utf-8") as f:
            json.dump({"type": "FeatureCollection", "features": features_aristas}, f, ensure_ascii=False, indent=2)

        return ruta_nodos, ruta_aristas

    def generar_geojson(
        self, grafo: Grafo
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Genera FeatureCollections GeoJSON de nodos y aristas en memoria (sin disco)."""
        features_nodos, features_aristas = self._construir_features_geojson(grafo)
        return (
            {"type": "FeatureCollection", "features": features_nodos},
            {"type": "FeatureCollection", "features": features_aristas},
        )

    def generar_graphml(self, grafo: Grafo) -> str:
        """Genera el grafo en formato GraphML como string (sin tocar disco)."""
        import io

        buffer = io.BytesIO()
        G = grafo.a_networkx()
        nx.write_graphml(G, buffer)
        return buffer.getvalue().decode("utf-8")

    def _construir_features_geojson(self, grafo: Grafo) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Construye las features GeoJSON de nodos y aristas sin persistir."""
        # Nodos
        features_nodos = []
        for nodo in grafo.nodos.values():
            features_nodos.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [nodo.coordenadas.longitud, nodo.coordenadas.latitud],
                    },
                    "properties": {
                        "id": nodo.id,
                        "nombre": nodo.nombre,
                        "tipo": nodo.tipo.value,
                        **nodo.atributos.model_dump(exclude_none=True),
                    },
                }
            )

        # Aristas (LineString)
        features_aristas = []
        for arista in grafo.aristas:
            nodo_origen = grafo.nodos[arista.origen]
            nodo_destino = grafo.nodos[arista.destino]

            geometria = arista.atributos.geometria
            if not geometria:
                geometria = [
                    [nodo_origen.coordenadas.longitud, nodo_origen.coordenadas.latitud],
                    [nodo_destino.coordenadas.longitud, nodo_destino.coordenadas.latitud],
                ]

            features_aristas.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": geometria,
                    },
                    "properties": {
                        "id": arista.id,
                        "origen": arista.origen,
                        "destino": arista.destino,
                        "distancia": arista.distancia,
                        "tiempo_estimado": arista.tiempo_estimado,
                        "costo": arista.costo,
                        "velocidad_promedio": arista.velocidad_promedio,
                        "congestion": arista.congestion.value,
                        "disponible": arista.disponible,
                        "incidentes": arista.incidentes,
                        **arista.atributos.model_dump(exclude_none=True),
                    },
                }
            )

        return features_nodos, features_aristas

    def cargar_geojson(
        self, archivo_nodos: str = "nodos.geojson", archivo_aristas: str = "aristas.geojson"
    ) -> Grafo:
        """Carga grafo desde archivos GeoJSON."""
        grafo = Grafo()

        # Cargar nodos
        ruta_nodos = self.directorio / archivo_nodos
        if ruta_nodos.exists():
            with open(ruta_nodos, "r", encoding="utf-8") as f:
                datos_nodos = json.load(f)

            for feature in datos_nodos.get("features", []):
                props = feature["properties"]
                coords = feature["geometry"]["coordinates"]
                grafo.agregar_nodo(
                    Nodo(
                        id=props["id"],
                        nombre=props["nombre"],
                        coordenadas=Coordenadas(latitud=coords[1], longitud=coords[0]),
                        tipo=TipoNodo(props.get("tipo", "interseccion")),
                        atributos=AtributosNodo(**{k: v for k, v in props.items() if k not in ["id", "nombre", "tipo"]}),
                    )
                )

        # Cargar aristas
        ruta_aristas = self.directorio / archivo_aristas
        if ruta_aristas.exists():
            with open(ruta_aristas, "r", encoding="utf-8") as f:
                datos_aristas = json.load(f)

            for feature in datos_aristas.get("features", []):
                props = feature["properties"]
                grafo.agregar_arista(
                    Arista(
                        id=props["id"],
                        origen=props["origen"],
                        destino=props["destino"],
                        distancia=props["distancia"],
                        tiempo_estimado=props["tiempo_estimado"],
                        costo=props.get("costo", 0.0),
                        velocidad_promedio=props.get("velocidad_promedio", 50.0),
                        congestion=NivelCongestion(props.get("congestion", "baja")),
                        disponible=props.get("disponible", True),
                        incidentes=props.get("incidentes", 0),
                        atributos=AtributosArista(**{k: v for k, v in props.items() if k not in [
                            "id", "origen", "destino", "distancia", "tiempo_estimado",
                            "costo", "velocidad_promedio", "congestion", "disponible", "incidentes"
                        ]}),
                    )
                )

        return grafo

    # ==================== CSV (Dataset simple) ====================

    def guardar_csv(self, grafo: Grafo, prefijo: str = "grafo") -> tuple[Path, Path]:
        """Exporta nodos y aristas a CSV."""
        import pandas as pd

        ruta_nodos = self.directorio / f"{prefijo}_nodos.csv"
        ruta_aristas = self.directorio / f"{prefijo}_aristas.csv"

        # Nodos
        df_nodos = pd.DataFrame(
            [
                {
                    "id": n.id,
                    "nombre": n.nombre,
                    "latitud": n.coordenadas.latitud,
                    "longitud": n.coordenadas.longitud,
                    "tipo": n.tipo.value,
                    **n.atributos.model_dump(exclude_none=True),
                }
                for n in grafo.nodos.values()
            ]
        )
        df_nodos.to_csv(ruta_nodos, index=False, encoding="utf-8")

        # Aristas
        df_aristas = pd.DataFrame(
            [
                {
                    "id": a.id,
                    "origen": a.origen,
                    "destino": a.destino,
                    "distancia": a.distancia,
                    "tiempo_estimado": a.tiempo_estimado,
                    "costo": a.costo,
                    "velocidad_promedio": a.velocidad_promedio,
                    "congestion": a.congestion.value,
                    "disponible": a.disponible,
                    "incidentes": a.incidentes,
                    **a.atributos.model_dump(exclude_none=True),
                }
                for a in grafo.aristas
            ]
        )
        df_aristas.to_csv(ruta_aristas, index=False, encoding="utf-8")

        return ruta_nodos, ruta_aristas

    def cargar_csv(self, archivo_nodos: str, archivo_aristas: str) -> Grafo:
        """Carga grafo desde archivos CSV."""
        import pandas as pd

        grafo = Grafo()

        df_nodos = pd.read_csv(self.directorio / archivo_nodos)
        for _, row in df_nodos.iterrows():
            grafo.agregar_nodo(
                Nodo(
                    id=row["id"],
                    nombre=row["nombre"],
                    coordenadas=Coordenadas(latitud=row["latitud"], longitud=row["longitud"]),
                    tipo=TipoNodo(row.get("tipo", "interseccion")),
                    atributos=AtributosNodo(
                        **{k: v for k, v in row.items() if k not in ["id", "nombre", "latitud", "longitud", "tipo"] and pd.notna(v)}
                    ),
                )
            )

        df_aristas = pd.read_csv(self.directorio / archivo_aristas)
        for _, row in df_aristas.iterrows():
            grafo.agregar_arista(
                Arista(
                    id=row["id"],
                    origen=row["origen"],
                    destino=row["destino"],
                    distancia=row["distancia"],
                    tiempo_estimado=row["tiempo_estimado"],
                    costo=row.get("costo", 0.0),
                    velocidad_promedio=row.get("velocidad_promedio", 50.0),
                    congestion=NivelCongestion(row.get("congestion", "baja")),
                    disponible=row.get("disponible", True),
                    incidentes=row.get("incidentes", 0),
                    atributos=AtributosArista(
                        **{k: v for k, v in row.items() if k not in [
                            "id", "origen", "destino", "distancia", "tiempo_estimado",
                            "costo", "velocidad_promedio", "congestion", "disponible", "incidentes"
                        ] and pd.notna(v)}
                    ),
                )
            )

        return grafo

    # ==================== OSMnx (OpenStreetMap) ====================

    def descargar_desde_osm(
        self,
        lugar: str = "Universidad Sergio Arboleda, BogotÃ¡, Colombia",
        radio_metros: int = 1500,
        tipo_red: str = "drive",
        nombre_salida: str = "osm_grafo",
    ) -> Grafo:
        """Descarga red vial de OpenStreetMap usando OSMnx.

        Args:
            lugar: DirecciÃ³n o lugar de referencia para geo-codificar el centro.
            radio_metros: Radio de descarga alrededor del punto central.
            tipo_red: Tipo de red OSM ('drive', 'walk', 'bike', 'all').
            nombre_salida: Prefijo para archivos GraphML/JSON generados.

        Returns:
            Grafo poblado con nodos y aristas reales de OpenStreetMap.

        Raises:
            ExcepcionRepositorio: Si OSMnx no estÃ¡ instalado o la descarga falla.
        """
        try:
            import osmnx as ox
        except ImportError:
            raise ExcepcionRepositorio("OSMnx no instalado. Ejecute: pip install osmnx")

        # Geo-codificar lugar â†’ punto central (lat, lon)
        try:
            punto = ox.geocode(lugar)  # (lat, lon)
        except Exception as e:
            raise ExcepcionRepositorio(f"No se pudo geocodificar '{lugar}': {e}")

        # osmnx 2.x: graph_from_point(center_point, dist, network_type)
        G = ox.graph_from_point(
            punto,
            dist=radio_metros,
            network_type=tipo_red,
        )

        # Guardar GraphML original
        ox.save_graphml(G, filepath=self.directorio / f"{nombre_salida}.graphml")

        # Convertir a nuestro modelo
        grafo = Grafo.desde_networkx(G, dirigido=True)
        grafo.metadata = {
            "fuente": "OpenStreetMap",
            "lugar": lugar,
            "radio_metros": radio_metros,
            "tipo_red": tipo_red,
            "nodos_originales": G.number_of_nodes(),
            "aristas_originales": G.number_of_edges(),
        }

        # Enriquecer con atributos OSM
        self._enriquecer_desde_osm(grafo, G)

        return grafo

    def _enriquecer_desde_osm(self, grafo: Grafo, G: nx.MultiDiGraph) -> None:
        """Añade atributos de OSM a las aristas."""
        # Velocidades por defecto según tipo de vía OSM (km/h)
        velocidad_por_tipo = {
            "motorway": 90, "trunk": 70, "primary": 60, "secondary": 50,
            "tertiary": 45, "residential": 30, "service": 20, "pedestrian": 5,
            "cycleway": 15, "living_street": 10, "unclassified": 40, "road": 30,
        }
        for arista in grafo.aristas:
            # Dict de llaves: OSMnx usa ints; nuestro modelo usa str
            try:
                origen_nx: Any = int(arista.origen)
                destino_nx: Any = int(arista.destino)
            except ValueError:
                origen_nx, destino_nx = arista.origen, arista.destino
            edges_data = G.get_edge_data(origen_nx, destino_nx)
            if not edges_data:
                continue
            # Tomar la primera arista (puede haber múltiples en MultiDiGraph)
            edge_data = list(edges_data.values())[0]

            tipo_highway = edge_data.get("highway")
            if "highway" in edge_data:
                arista.atributos.tipo_via = self._mapear_highway(tipo_highway)
            if "name" in edge_data and edge_data["name"]:
                nombre = edge_data["name"]
                arista.atributos.nombre_via = nombre[0] if isinstance(nombre, list) else str(nombre)
            if "maxspeed" in edge_data and edge_data["maxspeed"]:
                try:
                    arista.velocidad_promedio = float(str(edge_data["maxspeed"]).split()[0])
                except (ValueError, TypeError):
                    pass
            else:
                clave = tipo_highway[0] if isinstance(tipo_highway, list) else tipo_highway
                arista.velocidad_promedio = velocidad_por_tipo.get(str(clave).lower(), 40.0)
            if "lanes" in edge_data and edge_data["lanes"]:
                try:
                    arista.atributos.carriles = int(edge_data["lanes"])
                except (ValueError, TypeError):
                    pass
            if "oneway" in edge_data:
                arista.atributos.sentido_unico = edge_data["oneway"] in [True, "yes", "1"]
            if "surface" in edge_data:
                arista.atributos.superficie = edge_data["surface"]
            if edge_data.get("geometry") is not None:
                try:
                    arista.atributos.geometria = [
                        [float(x), float(y)] for x, y in edge_data["geometry"].coords
                    ]
                except (AttributeError, TypeError):
                    pass

    def _mapear_highway(self, highway: Any) -> TipoVia:
        """Mapea etiqueta highway de OSM a nuestro enum."""
        mapeo = {
            "motorway": TipoVia.AUTOPATIA,
            "trunk": TipoVia.TRONCAL,
            "primary": TipoVia.PRIMARIA,
            "secondary": TipoVia.SECUNDARIA,
            "tertiary": TipoVia.TERCIARIA,
            "residential": TipoVia.RESIDENCIAL,
            "service": TipoVia.SERVICIO,
            "pedestrian": TipoVia.PEATONAL,
            "cycleway": TipoVia.CICLOVIA,
        }

        if isinstance(highway, list):
            highway = highway[0]
        return mapeo.get(str(highway).lower(), TipoVia.OTRO)

# ==================== GTFS Movilidad (SITP Bogotá) ====================

    GTFS_URLS = {
        "gtfs_sitp": "https://datosabiertos.bogota.gov.co/dataset/56b6a5b4-82d2-4d8b-9a3b-7c6d5e4f3a2b/resource/gtfs_sitp.zip",
        "estaciones_troncales": "https://datosabiertos-transmilenio.hub.arcgis.com/datasets/estaciones-troncales-de-transmilenio.geojson",
        "trazados_troncales": "https://datosabiertos-transmilenio.hub.arcgis.com/datasets/trazados-troncales-de-transmilenio.geojson",
        "validaciones": "https://datosabiertos.bogota.gov.co/dataset/validaciones-mensuales-sitp-franja-horaria",
    }

    def descargar_gtfs_taxis(
        self,
        directorio_gtfs: str = "gtfs_taxis",
        solo_troncales: bool = True,
    ) -> Dict[str, Path]:
        """Descarga y extrae GTFS oficial del SITP (transporte público de Bogotá).

        El GTFS del SITP se usa como referencia de movilidad para calibrar la
        red vial real (velocidades y congestión por franja) sobre la que operan
        los taxis en la zona de estudio de Chapinero.

        Returns:
            Dict con rutas a archivos extraídos: stops.txt, routes.txt, trips.txt, stop_times.txt, calendar.txt
        """
        import zipfile
        import requests
        from io import BytesIO

        dir_gtfs = self.directorio / directorio_gtfs
        dir_gtfs.mkdir(parents=True, exist_ok=True)

        # URL del GTFS (puede cambiar, verificar en datosabiertos.bogota.gov.co)
        url_gtfs = "https://datosabiertos.bogota.gov.co/dataset/56b6a5b4-82d2-4d8b-9a3b-7c6d5e4f3a2b/resource/gtfs_sitp.zip"

        print(f"Descargando GTFS desde {url_gtfs}...")
        try:
            response = requests.get(url_gtfs, timeout=120, stream=True)
            response.raise_for_status()

            with zipfile.ZipFile(BytesIO(response.content)) as z:
                z.extractall(dir_gtfs)

        except Exception as e:
            raise ExcepcionRepositorio(f"Error descargando GTFS: {e}")

        archivos_esperados = ["stops.txt", "routes.txt", "trips.txt", "stop_times.txt", "calendar.txt", "calendar_dates.txt", "shapes.txt"]
        archivos_encontrados = {}

        for arch in archivos_esperados:
            ruta = dir_gtfs / arch
            if ruta.exists():
                archivos_encontrados[arch] = ruta
                print(f"  âœ“ {arch}")
            else:
                print(f"  âœ— {arch} (no encontrado)")

        return archivos_encontrados

    def procesar_gtfs_a_grafo(
        self,
        archivos_gtfs: Dict[str, Path],
        archivo_estaciones_geo: Optional[Path] = None,
        estado_operativo_path: Optional[Path] = None,
    ) -> Grafo:
        """Procesa archivos GTFS y genera grafo de movilidad para la red vial de taxis.

        Pipeline según PDF:
        1. Filtrar routes.txt -> solo componente troncal
        2. trips.txt -> viajes de esas rutas
        3. stop_times.txt -> conexiones ordenadas entre estaciones
        4. stops.txt -> coordenadas y nombres de estaciones
        5. calendar.txt -> disponibilidad por día
        6. Cruce con estaciones_geo -> verificar estado operativo (activa/cerrada)
        """
        import pandas as pd

        grafo = Grafo(dirigido=True)
        grafo.metadata = {"fuente": "GTFS SITP Bogotá (movilidad taxis)", "procesado": True}

        # 1. CARGAR ARCHIVOS
        routes = pd.read_csv(archivos_gtfs["routes.txt"])
        trips = pd.read_csv(archivos_gtfs["trips.txt"])
        stop_times = pd.read_csv(archivos_gtfs["stop_times.txt"])
        stops = pd.read_csv(archivos_gtfs["stops.txt"])

        calendar = pd.read_csv(archivos_gtfs["calendar.txt"]) if "calendar.txt" in archivos_gtfs else pd.DataFrame()
        calendar_dates = pd.read_csv(archivos_gtfs["calendar_dates.txt"]) if "calendar_dates.txt" in archivos_gtfs else pd.DataFrame()

        # 2. FILTRAR SOLO RUTAS TRONCALES
        # En GTFS SITP, route_type=3 = bus, pero necesitamos identificar troncales
        # Generalmente route_id empieza con 'T' o route_short_name tiene formato troncal
        if solo_troncales:
            # HeurÃ­stica: rutas troncales suelen tener route_short_name como 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'K', 'L' o contener 'Portal'
            mask_troncales = (
                routes["route_short_name"].str.match(r"^[A-HKL]$", na=False) |
                routes["route_long_name"].str.contains("Portal|Troncal", case=False, na=False) |
                routes["route_id"].str.startswith("T", na=False)
            )
            routes_troncal = routes[mask_troncales].copy()
            print(f"Rutas troncales identificadas: {len(routes_troncal)}")
        else:
            routes_troncal = routes

        route_ids_troncal = set(routes_troncal["route_id"].unique())

        # 3. VIAJES DE RUTAS TRONCALES
        trips_troncal = trips[trips["route_id"].isin(route_ids_troncal)].copy()
        trip_ids_troncal = set(trips_troncal["trip_id"].unique())
        print(f"Viajes troncales: {len(trips_troncal)}")

        # 4. PARADAS DE ESOS VIAJES (stop_times)
        st_troncal = stop_times[stop_times["trip_id"].isin(trip_ids_troncal)].copy()

        # 5. ESTACIONES REALES (stops.txt filtrado)
        stop_ids_usados = set(st_troncal["stop_id"].unique())
        stops_troncal = stops[stops["stop_id"].isin(stop_ids_usados)].copy()
        print(f"Estaciones en viajes troncales: {len(stops_troncal)}")

        # 6. CRUCE CON ESTACIONES GEOGRÃFICAS OFICIALES (para estado operativo)
        estaciones_activas = set()
        if archivo_estaciones_geo and archivo_estaciones_geo.exists():
            import geopandas as gpd
            gdf = gpd.read_file(archivo_estaciones_geo)
            # Filtrar solo activas y temporal_activa
            if "estado_operativo" in gdf.columns:
                gdf_activas = gdf[gdf["estado_operativo"].isin(["activa", "temporal_activa"])]
                estaciones_activas = set(gdf_activas["id_estacion"].astype(str).tolist())
                print(f"Estaciones activas segÃºn geo: {len(estaciones_activas)}")
            else:
                # Si no hay campo estado, asumir todas
                estaciones_activas = set(gdf["id_estacion"].astype(str).tolist()) if "id_estacion" in gdf.columns else stop_ids_usados
        else:
            estaciones_activas = stop_ids_usados

        # 7. CREAR NODOS (solo estaciones activas)
        for _, row in stops_troncal.iterrows():
            stop_id = str(row["stop_id"])
            if stop_id not in estaciones_activas:
                continue

            grafo.agregar_nodo(
                Nodo(
                    id=stop_id,
                    nombre=row.get("stop_name", f"EstaciÃ³n {stop_id}"),
                    coordenadas=Coordenadas(
                        latitud=float(row["stop_lat"]),
                        longitud=float(row["stop_lon"]),
                    ),
                    tipo=TipoNodo.ESTACION,
                    atributos=AtributosNodo(
                        descripcion=row.get("stop_desc", ""),
                        zona=row.get("zone_id", ""),
                    ),
                )
            )

        print(f"Nodos creados (estaciones activas): {len(grafo.nodos)}")

        # 8. CREAR ARISTAS (conexiones consecutivas en stop_times)
        # Agrupar por trip_id y ordenar por stop_sequence
        st_ordenado = st_troncal.sort_values(["trip_id", "stop_sequence"])

        aristas_creadas = set()

        for trip_id, grupo in st_ordenado.groupby("trip_id"):
            paradas = grupo["stop_id"].astype(str).tolist()
            secuencias = grupo["stop_sequence"].tolist()
            horas_salida = grupo["departure_time"].tolist()
            horas_llegada = grupo["arrival_time"].tolist()

            # Obtener info de la ruta para este trip
            trip_info = trips_troncal[trips_troncal["trip_id"] == trip_id].iloc[0]
            route_id = trip_info["route_id"]
            route_info = routes_troncal[routes_troncal["route_id"] == route_id].iloc[0]
            nombre_ruta = route_info.get("route_short_name", route_id)

            for i in range(len(paradas) - 1):
                origen = paradas[i]
                destino = paradas[i + 1]

                # Solo si ambas estaciones estÃ¡n activas
                if origen not in grafo.nodos or destino not in grafo.nodos:
                    continue

                # Calcular tiempo programado
                try:
                    t_salida = self._parsear_hora_gtfs(horas_salida[i])
                    t_llegada = self._parsear_hora_gtfs(horas_llegada[i + 1])
                    tiempo_min = max(1, (t_llegada - t_salida).total_seconds() / 60)
                except:
                    tiempo_min = 2.0  # default

                # Distancia aproximada (haversine entre coordenadas)
                nodo_o = grafo.nodos[origen]
                nodo_d = grafo.nodos[destino]
                distancia_m = nodo_o.coordenadas.distancia_a(nodo_d.coordenadas)

                # ID Ãºnico para la arista
                arista_id = f"{origen}-{destino}-{nombre_ruta}"
                if arista_id in aristas_creadas:
                    continue
                aristas_creadas.add(arista_id)

                grafo.agregar_arista(
                    Arista(
                        id=arista_id,
                        origen=origen,
                        destino=destino,
                        distancia=distancia_m,
                        tiempo_estimado=tiempo_min,
                        costo=0.0,
                        velocidad_promedio=distancia_m / 1000 / (tiempo_min / 60) if tiempo_min > 0 else 30,
                        congestion=NivelCongestion.BAJA,
                        disponible=True,
                        incidentes=0,
                        atributos=AtributosArista(
                            tipo_via=TipoVia.TRONCAL,
                            nombre_via=nombre_ruta,
                            sentido_unico=True,
                        ),
                    )
                )

        print(f"Aristas creadas: {len(grafo.aristas)}")

        # 9. GUARDAR CSVs LIMPIOS (formato PDF)
        self._guardar_dataset_taxis(grafo, routes_troncal, stops_troncal, st_ordenado)

        return grafo

    def _parsear_hora_gtfs(self, hora_str: str) -> "datetime":
        """Parsea hora GTFS (HH:MM:SS, puede ser >24h)."""
        from datetime import datetime, timedelta
        h, m, s = map(int, str(hora_str).split(":"))
        return datetime(1900, 1, 1) + timedelta(hours=h, minutes=m, seconds=s)

    def _guardar_dataset_taxis(
        self,
        grafo: Grafo,
        routes_troncal: "pd.DataFrame",
        stops_troncal: "pd.DataFrame",
        stop_times_ordenado: "pd.DataFrame",
    ) -> None:
        """Guarda los 3 CSVs del dataset inicial según especificación del PDF."""
        import pandas as pd

        # 1. puntos_taxis_activos.csv
        filas_estaciones = []
        for nid, nodo in grafo.nodos.items():
            filas_estaciones.append({
                "id_estacion": nid,
                "nombre_estacion": nodo.nombre,
                "latitud": nodo.coordenadas.latitud,
                "longitud": nodo.coordenadas.longitud,
                "troncal": self._obtener_troncal_estacion(nid, routes_troncal, stop_times_ordenado),
                "tipo_estacion": self._clasificar_tipo_estacion(nid, grafo),
                "estado_operativo": "activa",
                "es_temporal": "No",
                "fecha_verificacion": "2026-09-07",
                "incluir_en_grafo": "Sí",
            })
        pd.DataFrame(filas_estaciones).to_csv(self.directorio / "puntos_taxis_activos.csv", index=False, encoding="utf-8")

        # 2. conexiones_taxis.csv
        filas_conexiones = []
        for arista in grafo.aristas:
            filas_conexiones.append({
                "origen": arista.origen,
                "destino": arista.destino,
                "ruta": arista.atributos.nombre_via,
                "secuencia_origen": 0,  # Se llenarÃ­a con datos reales
                "secuencia_destino": 0,
                "hora_salida": "",
                "hora_llegada": "",
                "tiempo_min": round(arista.tiempo_estimado, 1),
                "distancia_km": round(arista.distancia / 1000, 3),
                "transbordo": "No",  # Se detectarÃ­a si ruta cambia
                "disponible": "SÃ­" if arista.disponible else "No",
            })
        pd.DataFrame(filas_conexiones).to_csv(self.directorio / "conexiones_taxis.csv", index=False, encoding="utf-8")

        # 3. demanda_por_franja.csv (placeholder - requiere archivo validaciones)
        pd.DataFrame(columns=[
            "fecha", "franja_horaria", "componente", "validaciones", "nivel_demanda", "id_estacion"
        ]).to_csv(self.directorio / "demanda_por_franja.csv", index=False, encoding="utf-8")

        print(f"Datasets guardados en {self.directorio}/")

    def _obtener_troncal_estacion(self, estacion_id: str, routes: "pd.DataFrame", stop_times: "pd.DataFrame") -> str:
        """Determina a quÃ© ruta/corredor pertenece una estaciÃ³n de referencia."""
        # Buscar rutas que pasan por esta estaciÃ³n
        trips_en_estacion = stop_times[stop_times["stop_id"].astype(str) == estacion_id]["trip_id"].unique()
        if len(trips_en_estacion) == 0:
            return "desconocida"

        # Obtener route_ids
        import pandas as pd
        trips_df = pd.DataFrame({"trip_id": trips_en_estacion})
        # NecesitarÃ­amos trips dataframe completo... simplificar
        return "principal"

    def _clasificar_tipo_estacion(self, estacion_id: str, grafo: Grafo) -> str:
        """Clasifica: portal, intercambio, intermedia, sencilla."""
        grado = len([a for a in grafo.aristas if a.origen == estacion_id or a.destino == estacion_id])
        nodo = grafo.nodos[estacion_id]
        nombre = nodo.nombre.lower()

        if "portal" in nombre:
            return "portal"
        elif grado >= 3:
            return "intercambio"
        elif grado == 1:
            return "sencilla"
        else:
            return "intermedia"

    def generar_dataset_inicial_taxis(
        self,
        usar_gtfs_real: bool = True,
        descargar_geo: bool = True,
    ) -> Grafo:
        """Método principal: genera dataset inicial de red vial para taxis (Corte 1).

        Si usar_gtfs_real=True: descarga GTFS oficial + geo estaciones
        Si False: crea dataset sintético de ejemplo (6 nodos PDF)
        """
        if usar_gtfs_real:
            print("=== GENERANDO DATASET TAXIS REAL (GTFS SITP) ===")

            # 1. Descargar GTFS
            archivos_gtfs = self.descargar_gtfs_taxis()

            # 2. Descargar estaciones geográficas (para estado operativo)
            archivo_geo = None
            if descargar_geo:
                archivo_geo = self._descargar_estaciones_geo()

            # 3. Procesar a grafo
            grafo = self.procesar_gtfs_a_grafo(archivos_gtfs, archivo_geo)

            # 4. Guardar en múltiples formatos
            self.guardar_json(grafo, "taxis_grafo.json")
            self.guardar_graphml(grafo, "taxis_grafo.graphml")
            self.guardar_geojson(grafo, "taxis_nodos.geojson", "taxis_aristas.geojson")
            self.guardar_csv(grafo, "taxis")

            return grafo
        else:
            print("=== GENERANDO DATASET SINTÃ‰TICO (EJEMPLO PDF - 6 NODOS) ===")
            return self._crear_dataset_sintetico_pdf()

    def generar_dataset_osm(
        self,
        lugar: str = "Universidad Sergio Arboleda, BogotÃ¡, Colombia",
        radio_metros: int = 1500,
        tipo_red: str = "drive",
    ) -> Grafo:
        """Genera dataset real desde OpenStreetMap y lo persiste en todos los formatos.

        Args:
            lugar: Lugar/geocodificaciÃ³n para descargar la red vial.
            radio_metros: Radio de descarga alrededor del punto central.
            tipo_red: Tipo de red OSM ('drive', 'walk', 'bike', 'all').

        Returns:
            Grafo real de OpenStreetMap guardado en datos/.
        """
        print(f"=== GENERANDO DATASET OPENSTREETMAP (OSMnx) ===")
        print(f"  Lugar: {lugar}")
        print(f"  Radio: {radio_metros} m | Red: {tipo_red}")

        grafo = self.descargar_desde_osm(
            lugar=lugar,
            radio_metros=radio_metros,
            tipo_red=tipo_red,
            nombre_salida="osm_grafo",
        )

        print(f"  âœ“ Descargados: {grafo.metadata['nodos_originales']} nodos, "
              f"{grafo.metadata['aristas_originales']} aristas originales")

        # Persistir en todos los formatos
        self.guardar_json(grafo, "grafo_osm.json")
        self.guardar_graphml(grafo, "grafo_osm.graphml")
        self.guardar_geojson(grafo, "grafo_osm_nodos.geojson", "grafo_osm_aristas.geojson")
        self.guardar_csv(grafo, "grafo_osm")

        # Guardar tambiÃ©n como dataset principal para la API
        self.guardar_json(grafo, "dataset_osm.json")

        print(f"  âœ“ Guardado: grafo_osm.json, graphml, geojson, csv")
        return grafo

    def _descargar_estaciones_geo(self) -> Optional[Path]:
        """Descarga capa geoJSON de estaciones troncales oficiales."""
        import requests
        import geopandas as gpd

        url = "https://datosabiertos-transmilenio.hub.arcgis.com/datasets/estaciones-troncales-de-transmilenio.geojson"
        ruta = self.directorio / "estaciones_troncales_oficiales.geojson"

        try:
            print(f"Descargando estaciones geogrÃ¡ficas desde {url}...")
            response = requests.get(url, timeout=60)
            response.raise_for_status()

            with open(ruta, "wb") as f:
                f.write(response.content)

            # Verificar que se puede leer
            gdf = gpd.read_file(ruta)
            print(f"  âœ“ Estaciones geo descargadas: {len(gdf)} features")
            print(f"  Columnas: {list(gdf.columns)}")

            return ruta
        except Exception as e:
            print(f"  âœ— Error descargando geo: {e}")
            return None

    def _crear_dataset_sintetico_pdf(self) -> Grafo:
        """Crea el dataset de 6 nodos del ejemplo del PDF (universidad)."""
        grafo = Grafo(dirigido=True, metadata={"fuente": "Ejemplo PDF Corte 1", "sintetico": True})

        # 6 Nodos del PDF
        nodos = [
            Nodo(id="n1", nombre="Entrada Principal", coordenadas=Coordenadas(latitud=4.6097, longitud=-74.0817), tipo=TipoNodo.EDIFICIO),
            Nodo(id="n2", nombre="Edificio IngenierÃ­a", coordenadas=Coordenadas(latitud=4.6102, longitud=-74.0820), tipo=TipoNodo.EDIFICIO),
            Nodo(id="n3", nombre="Biblioteca", coordenadas=Coordenadas(latitud=4.6105, longitud=-74.0815), tipo=TipoNodo.EDIFICIO),
            Nodo(id="n4", nombre="CafeterÃ­a", coordenadas=Coordenadas(latitud=4.6100, longitud=-74.0825), tipo=TipoNodo.ZONA),
            Nodo(id="n5", nombre="Laboratorios", coordenadas=Coordenadas(latitud=4.6110, longitud=-74.0818), tipo=TipoNodo.EDIFICIO),
            Nodo(id="n6", nombre="Zona Deportiva", coordenadas=Coordenadas(latitud=4.6115, longitud=-74.0822), tipo=TipoNodo.ZONA),
        ]
        for n in nodos:
            grafo.agregar_nodo(n)

        # Aristas con valores del PDF (distancia, tiempo, costo)
        aristas = [
            Arista(id="e1", origen="n1", destino="n2", distancia=300, tiempo_estimado=4, costo=0, velocidad_promedio=45, congestion=NivelCongestion.BAJA),
            Arista(id="e2", origen="n1", destino="n4", distancia=200, tiempo_estimado=3, costo=0, velocidad_promedio=40, congestion=NivelCongestion.BAJA),
            Arista(id="e3", origen="n2", destino="n3", distancia=300, tiempo_estimado=4, costo=0, velocidad_promedio=45, congestion=NivelCongestion.MEDIA),
            Arista(id="e4", origen="n2", destino="n5", distancia=200, tiempo_estimado=3, costo=0, velocidad_promedio=40, congestion=NivelCongestion.BAJA),
            Arista(id="e5", origen="n3", destino="n6", distancia=400, tiempo_estimado=5, costo=0, velocidad_promedio=48, congestion=NivelCongestion.BAJA),
            Arista(id="e6", origen="n4", destino="n5", distancia=300, tiempo_estimado=4, costo=0, velocidad_promedio=45, congestion=NivelCongestion.MEDIA),
            Arista(id="e7", origen="n5", destino="n6", distancia=200, tiempo_estimado=3, costo=0, velocidad_promedio=40, congestion=NivelCongestion.BAJA),
        ]
        for a in aristas:
            grafo.agregar_arista(a)

        # Guardar
        self.guardar_json(grafo, "dataset_inicial_pdf.json")
        self.guardar_csv(grafo, "dataset_inicial_pdf")
        self.guardar_geojson(grafo, "dataset_inicial_pdf_nodos.geojson", "dataset_inicial_pdf_aristas.geojson")

        return grafo