"""Pruebas para datos sintéticos, independientes de servicios externos."""

import csv
import json
from datetime import date

from simular_congestion import generar_dataset


def fixture_red():
    nodos = {
        clave: {
            "id": clave,
            "nombre": f"Nodo {clave}",
            "coordenadas": {"latitud": 4.65, "longitud": -74.06},
        }
        for clave in ["A", "B", "C"]
    }
    aristas = [
        {"id": "e1", "origen": "A", "destino": "B", "distancia": 100,
         "tiempo_estimado": 0.12, "velocidad_promedio": 30,
         "costo": 0, "disponible": True,
         "atributos": {"tipo_via": "residencial"}},
        {"id": "e2", "origen": "B", "destino": "C", "distancia": 200,
         "tiempo_estimado": 0.24, "velocidad_promedio": 50,
         "costo": 0, "disponible": True,
         "atributos": {"tipo_via": "secundaria"}},
    ]
    return {"dirigido": True, "nodos": nodos, "aristas": aristas,
            "metadata": {"fuente": "OpenStreetMap"}}


def test_salidas_y_snapshot_sin_mutar_entrada(tmp_path):
    entrada = tmp_path / "red.json"
    grafo = fixture_red()
    entrada.write_text(json.dumps(grafo), encoding="utf-8")
    salida = tmp_path / "salida"
    info = generar_dataset(entrada, salida, date(2026, 10, 19), dias=2, semilla=42)

    assert info["registros"] == 2 * 6 * 2
    assert info["observaciones_reales_trafico"] == 0
    assert len(json.loads(entrada.read_text(encoding="utf-8"))["aristas"]) == 2
    with (salida / "historial_congestion_simulado.csv").open(encoding="utf-8", newline="") as f:
        filas = list(csv.DictReader(f))
    assert len(filas) == 24
    assert all(row["fuente_congestion"] == "simulada" for row in filas)
    assert all(float(row["tiempo_viaje_min"]) > 0 for row in filas if row["disponible"] == "1")

    for nombre in ["pico_manana", "valle", "pico_tarde"]:
        snap = json.loads((salida / f"escenario_{nombre}.json").read_text(encoding="utf-8"))
        assert snap["metadata"]["datos_trafico_reales"] is False
        assert snap["nodos"] == grafo["nodos"]
        assert len(snap["aristas"]) == 2
        assert all(e["congestion"] in {"baja", "media", "alta", "bloqueada"} for e in snap["aristas"])


def test_reproducibilidad(tmp_path):
    entrada = tmp_path / "red.json"
    entrada.write_text(json.dumps(fixture_red()), encoding="utf-8")
    p1, p2 = tmp_path / "uno", tmp_path / "dos"
    generar_dataset(entrada, p1, date(2026, 10, 19), dias=1, semilla=78)
    generar_dataset(entrada, p2, date(2026, 10, 19), dias=1, semilla=78)
    assert (p1 / "historial_congestion_simulado.csv").read_bytes() == (p2 / "historial_congestion_simulado.csv").read_bytes()


def test_pico_vs_valle(tmp_path):
    entrada = tmp_path / "red.json"
    grafo = fixture_red()
    # 1000 aristas artificiales para contrastar promedios y reducir ruido.
    grafo["aristas"] = [{**grafo["aristas"][1], "id": f"v{i}"} for i in range(1000)]
    entrada.write_text(json.dumps(grafo), encoding="utf-8")
    salida = tmp_path / "res"
    generar_dataset(entrada, salida, date(2026, 10, 19), dias=1, semilla=42)
    with (salida / "historial_congestion_simulado.csv").open(encoding="utf-8", newline="") as f:
        filas = list(csv.DictReader(f))
    promedio = lambda hora: sum(float(r["factor_congestion_sintetico"]) for r in filas if int(r["hora"]) == hora) / 1000
    assert promedio(8) > promedio(12)
    assert promedio(17) > promedio(12)


def test_dias_invalidos(tmp_path):
    entrada = tmp_path / "red.json"
    entrada.write_text(json.dumps(fixture_red()), encoding="utf-8")
    import pytest
    with pytest.raises(ValueError):
        generar_dataset(entrada, tmp_path / "salida", date(2026, 10, 19), dias=0)
