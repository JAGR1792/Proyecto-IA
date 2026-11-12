"""Pruebas básicas del dataset maestro construido (sin descargar fuentes)."""

import csv
import gzip
import json
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
BASE = RAIZ / "backend/datos/ml/dataset_maestro_hibrido"


class TestDatasetMaestroHibrido(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (BASE / "dataset_maestro_hibrido.csv.gz").exists():
            raise unittest.SkipTest("Ejecuta construir_dataset_maestro.py primero.")
        cls.info = json.loads((BASE / "metadatos_maestro.json").read_text(encoding="utf-8"))

    def test_conteos_y_tipos(self):
        info = self.info
        self.assertEqual(info["filas_total"], info["filas_historicas"] + info["filas_simuladas"])
        self.assertEqual(info["filas_simuladas"], info["aristas_osm"] * 168)

    def test_fuentes_particiones_y_tiempos(self):
        reales = simulados = 0
        with gzip.open(
            BASE / "dataset_maestro_hibrido.csv.gz", "rt", encoding="utf-8", newline=""
        ) as f:
            for r in csv.DictReader(f):
                self.assertGreater(float(r["velocidad_kmh"]), 0)
                self.assertGreater(float(r["tiempo_min"]), 0)
                self.assertGreater(float(r["distancia_m"]), 0)
                if r["fuente_dato"] == "HISTORICO_BITCARRIER_2022":
                    reales += 1
                    self.assertEqual(r["unidad_espacial"], "TID_BITCARRIER")
                    self.assertIn(r["particion"], {"entrenamiento", "validacion", "prueba"})
                    self.assertFalse(r["id_arista_osm"])
                elif r["fuente_dato"] == "SIMULADO_CALIBRADO_ENTRENAMIENTO":
                    simulados += 1
                    self.assertEqual(r["unidad_espacial"], "ARISTA_OSM")
                    self.assertEqual(r["particion"], "simulacion_no_evaluable")
                    self.assertFalse(r["tid_bitcarrier"])
                else:
                    self.fail("Fuente desconocida")
        self.assertEqual(reales, self.info["filas_historicas"])
        self.assertEqual(simulados, self.info["filas_simuladas"])


if __name__ == "__main__":
    unittest.main()
