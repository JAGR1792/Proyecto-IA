"""Escenario SINTÉTICO de congestión para cualquier hora HH:MM de un día hábil.

La geometría proviene de OSM, NO la congestión. Los perfiles se basan en el
simulador sintético anterior: 06, 08, 12, 17, 19 y 22 h; se interpolan los
minutos de manera lineal, incluyendo la transición entre 22 y 06 h.

No es tráfico observado, pronóstico real ni considera la fecha o festivos.
Cada arista conserva un factor espacial fijo para que cambiar 1 minuto no
regenere el azar ni produzca saltos artificiales.
"""

import hashlib
import re

from src.grafo.modelos import Grafo, NivelCongestion

_HORA_VALIDADA = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")

# Perfil relativo hipotético: (hora, intensidad). La última marca es 06+24.
_PERFIL = (
    (6.0, 0.32),
    (8.0, 1.05),
    (12.0, 0.36),
    (17.0, 1.20),
    (19.0, 0.79),
    (22.0, 0.10),
    (30.0, 0.32),
)

_PESO_VIA = {
    "autopista": 1.35,
    "troncal": 1.25,
    "primaria": 1.24,
    "secundaria": 1.12,
    "terciaria": 1.00,
    "residencial": 0.78,
    "servicio": 0.60,
    "otro": 0.85,
}


def validar_hora(hora_salida: str) -> int:
    """Convierte HH:MM a minutos desde medianoche; rechaza formatos inválidos."""
    if not _HORA_VALIDADA.fullmatch(hora_salida):
        raise ValueError("Hora de salida inválida: usa HH:MM entre 00:00 y 23:59")
    horas, minutos = map(int, hora_salida.split(":"))
    return 60 * horas + minutos


def intensidad_en_hora(hora_salida: str) -> float:
    """Interpola el perfil original para cualquier minuto, incluido medianoche."""
    horas = validar_hora(hora_salida) / 60
    if horas < 6:
        horas += 24

    for (h0, i0), (h1, i1) in zip(_PERFIL, _PERFIL[1:]):
        if h0 <= horas <= h1:
            fraccion = (horas - h0) / (h1 - h0)
            return i0 + fraccion * (i1 - i0)
    raise AssertionError("La hora normalizada debe pertenecer al perfil")


def _factor_calle(arista_id: str) -> float:
    """Variación espacial determinista de +/-15 %, independiente del horario."""
    valor = int.from_bytes(hashlib.sha256(arista_id.encode()).digest()[:4], "big")
    return 0.85 + (valor / (2**32 - 1)) * 0.30


def grafo_en_hora(grafo: Grafo, hora_salida: str | None) -> Grafo:
    """Devuelve un nuevo grafo con tiempos/congestión simulados para HH:MM.

    Sin hora devuelve el grafo recibido, preservando el contrato anterior.
    No altera el grafo OSM cacheado: permite consultas simultáneas independientes.
    Mantiene aristas bloqueadas y sentidos viales tal como estaban en el origen.
    """
    if hora_salida is None:
        return grafo

    intensidad = intensidad_en_hora(hora_salida)
    aristas_simuladas = []
    for arista in grafo.aristas:
        tipo = arista.atributos.tipo_via.value
        peso = _PESO_VIA.get(tipo, _PESO_VIA["otro"])
        factor = 1.0 + intensidad * peso * _factor_calle(arista.id)
        tiempo = round(arista.tiempo_estimado * factor, 6)
        velocidad = round(arista.velocidad_promedio / factor, 6)

        if not arista.disponible or arista.congestion == NivelCongestion.BLOQUEADA:
            congestion = NivelCongestion.BLOQUEADA
        elif factor < 1.40:
            congestion = NivelCongestion.BAJA
        elif factor < 2.00:
            congestion = NivelCongestion.MEDIA
        else:
            congestion = NivelCongestion.ALTA

        aristas_simuladas.append(
            arista.model_copy(
                update={
                    "tiempo_estimado": tiempo,
                    "velocidad_promedio": velocidad,
                    "congestion": congestion,
                }
            )
        )

    return grafo.model_copy(update={"aristas": aristas_simuladas})
