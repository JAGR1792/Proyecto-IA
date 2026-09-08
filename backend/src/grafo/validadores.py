"""Validadores para atributos del grafo."""

from typing import Any, Dict, List, Tuple

from .modelos import Arista, Grafo, NivelCongestion, Nodo, TipoNodo, TipoVia


class ExcepcionValidacion(Exception):
    """Excepción para errores de validación."""

    pass


def validar_grafo_completo(grafo: Grafo) -> Tuple[bool, List[str]]:
    """Valida integridad completa del grafo.

    Returns:
        Tupla (es_valido, lista_errores)
    """
    errores = []

    # 1. Nodos referenciados existen
    ids_nodos = set(grafo.nodos.keys())
    for arista in grafo.aristas:
        if arista.origen not in ids_nodos:
            errores.append(f"Arista {arista.id}: nodo origen '{arista.origen}' no existe")
        if arista.destino not in ids_nodos:
            errores.append(f"Arista {arista.id}: nodo destino '{arista.destino}' no existe")

    # 2. Atributos numéricos razonables
    for arista in grafo.aristas:
        if arista.distancia <= 0:
            errores.append(f"Arista {arista.id}: distancia debe ser > 0")
        if arista.tiempo_estimado <= 0:
            errores.append(f"Arista {arista.id}: tiempo estimado debe ser > 0")
        if arista.velocidad_promedio <= 0 or arista.velocidad_promedio > 200:
            errores.append(f"Arista {arista.id}: velocidad fuera de rango (0-200 km/h)")

    # 3. Coherencia distancia/tiempo/velocidad
    for arista in grafo.aristas:
        if arista.velocidad_promedio > 0:
            tiempo_calculado = (arista.distancia / 1000) / arista.velocidad_promedio * 60  # min
            ratio = tiempo_calculado / arista.tiempo_estimado if arista.tiempo_estimado > 0 else 0
            if ratio > 3 or ratio < 0.3:
                errores.append(
                    f"Arista {arista.id}: incoherencia distancia/tiempo/velocidad "
                    f"(calculado={tiempo_calculado:.1f}min, declarado={arista.tiempo_estimado}min)"
                )

    # 4. Nodos aislados (opcional: warning)
    nodos_conectados = set()
    for arista in grafo.aristas:
        if arista.disponible:
            nodos_conectados.add(arista.origen)
            nodos_conectados.add(arista.destino)

    nodos_aislados = ids_nodos - nodos_conectados
    for nid in nodos_aislados:
        errores.append(f"Advertencia: Nodo '{nid}' ({grafo.nodos[nid].nombre}) está aislado")

    # 5. IDs duplicados
    ids_aristas = [a.id for a in grafo.aristas]
    duplicados = set([x for x in ids_aristas if ids_aristas.count(x) > 1])
    for dup in duplicados:
        errores.append(f"ID de arista duplicado: {dup}")

    return len([e for e in errores if not e.startswith("Advertencia")]) == 0, errores


def validar_nodo(nodo: Nodo) -> List[str]:
    """Valida un nodo individual."""
    errores = []

    if not nodo.id or not nodo.id.strip():
        errores.append("ID de nodo vacío")

    if not nodo.nombre or not nodo.nombre.strip():
        errores.append(f"Nodo {nodo.id}: nombre vacío")

    if nodo.coordenadas.latitud < -90 or nodo.coordenadas.latitud > 90:
        errores.append(f"Nodo {nodo.id}: latitud fuera de rango [-90, 90]")

    if nodo.coordenadas.longitud < -180 or nodo.coordenadas.longitud > 180:
        errores.append(f"Nodo {nodo.id}: longitud fuera de rango [-180, 180]")

    return errores


def validar_arista(arista: Arista, nodos: Dict[str, Nodo]) -> List[str]:
    """Valida una arista individual."""
    errores = []

    if not arista.id or not arista.id.strip():
        errores.append("ID de arista vacío")

    if arista.origen not in nodos:
        errores.append(f"Arista {arista.id}: nodo origen '{arista.origen}' no existe")

    if arista.destino not in nodos:
        errores.append(f"Arista {arista.id}: nodo destino '{arista.destino}' no existe")

    if arista.origen == arista.destino:
        errores.append(f"Arista {arista.id}: origen y destino son el mismo nodo")

    if arista.distancia <= 0:
        errores.append(f"Arista {arista.id}: distancia debe ser > 0")

    if arista.tiempo_estimado <= 0:
        errores.append(f"Arista {arista.id}: tiempo estimado debe ser > 0")

    return errores


def validar_conexion_bidireccional(grafo: Grafo) -> List[str]:
    """Verifica que conexiones bidireccionales tengan aristas en ambos sentidos."""
    advertencias = []
    pares_vistos = set()

    for arista in grafo.aristas:
        par = tuple(sorted([arista.origen, arista.destino]))
        if par in pares_vistos:
            continue
        pares_vistos.add(par)

        # Buscar arista inversa
        inversa = next((a for a in grafo.aristas if a.origen == arista.destino and a.destino == arista.origen), None)

        if inversa is None and not arista.atributos.sentido_unico:
            advertencias.append(
                f"Conexión {arista.origen}-{arista.destino} no tiene arista inversa "
                f"(posible vía de doble sentido sin modelar)"
            )

    return advertencias


def calcular_estadisticas(grafo: Grafo) -> Dict[str, Any]:
    """Calcula estadísticas descriptivas del grafo."""
    if not grafo.nodos:
        return {"nodos": 0, "aristas": 0}

    distancias = [a.distancia for a in grafo.aristas if a.disponible]
    tiempos = [a.tiempo_estimado for a in grafo.aristas if a.disponible]
    velocidades = [a.velocidad_promedio for a in grafo.aristas if a.disponible]
    congestiones = [a.congestion for a in grafo.aristas if a.disponible]

    from collections import Counter

    return {
        "nodos": len(grafo.nodos),
        "aristas_totales": len(grafo.aristas),
        "aristas_disponibles": len([a for a in grafo.aristas if a.disponible]),
        "aristas_bloqueadas": len([a for a in grafo.aristas if not a.disponible]),
        "distancia_total_m": sum(distancias) if distancias else 0,
        "distancia_promedio_m": sum(distancias) / len(distancias) if distancias else 0,
        "tiempo_promedio_min": sum(tiempos) / len(tiempos) if tiempos else 0,
        "velocidad_promedio_kmh": sum(velocidades) / len(velocidades) if velocidades else 0,
        "congestion_distribucion": dict(Counter(c.value for c in congestiones)),
        "tipos_nodo": dict(Counter(n.tipo.value for n in grafo.nodos.values())),
        "grados_nodo": {
            nid: len([a for a in grafo.aristas if a.origen == nid and a.disponible])
            for nid in grafo.nodos.keys()
        },
    }