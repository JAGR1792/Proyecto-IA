"""Ejecutar: python -m unittest discover -s backend/tests -p test_auditoria_red_osm.py -v"""

import importlib.util
import tempfile
import unittest
from pathlib import Path

import pandas as pd

FILE = Path(__file__).resolve().parents[1] / "scripts/ml/auditar_y_cerrar_red_osm.py"
spec = importlib.util.spec_from_file_location("auditoria_red", FILE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class TestAuditoria(unittest.TestCase):
    def test_unidades_y_geometria(self):
        h = pd.DataFrame(
            {
                "tid": [1, 1, 2],
                "distancia_original": [100, 100, 200],
                "velocidad_original": [20, 30, 40],
            }
        )
        r = pd.DataFrame(
            {
                "tid_bitcarrier": [1, 2],
                "longitud_bitcarrier_geom_m": [99.8, 201],
                "geometrias_distintas": [1, 1],
                "frecuencia_geometria_representativa": [1, 1],
            }
        )
        tabla, rep = mod.auditar_unidades(h, r)
        self.assertEqual(rep["tramos_distancia_compatible_25pct"], 2)
        self.assertEqual(len(tabla), 2)

    def test_rechaza_duplicados(self):
        d = pd.DataFrame(
            {
                "indice_arista_osm": [1, 1],
                "dia_semana": [0, 0],
                "hora": [0, 0],
                "distancia_m": [100, 100],
                "velocidad_kmh": [20, 20],
                "tiempo_min": [0.3, 0.3],
                "fuente_dato": ["X", "X"],
                "estado_match": ["X", "X"],
            }
        )
        with self.assertRaisesRegex(ValueError, "duplicadas"):
            mod.verificar_red(d, pd.DataFrame({"indice_arista_osm": [1]}))

    def test_rechaza_tiempos_incoherentes(self):
        filas = []
        for dia in range(7):
            for hora in range(24):
                filas.append(
                    {
                        "indice_arista_osm": 1,
                        "dia_semana": dia,
                        "hora": hora,
                        "distancia_m": 100,
                        "velocidad_kmh": 20,
                        "tiempo_min": 2,
                        "fuente_dato": "X",
                        "estado_match": "X",
                    }
                )
        with self.assertRaisesRegex(ValueError, "incoherente"):
            mod.verificar_red(pd.DataFrame(filas), pd.DataFrame({"indice_arista_osm": [1]}))

    def test_no_aprueba_sin_evidencia(self):
        c = pd.DataFrame(
            {
                "indice_osm": [1],
                "id_arista_osm": ["a"],
                "tid_bitcarrier": ["t"],
                "propuesta_estricta_vigente": [True],
            }
        )
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "revision.csv"
            pd.DataFrame(
                [
                    {
                        "indice_osm": 1,
                        "id_arista_osm": "a",
                        "tid_bitcarrier": "t",
                        "decision": "APROBADO",
                        "geometria_confirmada": "SI",
                        "sentido_legal_confirmado": "NO",
                        "evidencia": "foto sin fecha",
                        "revisor": "equipo",
                    }
                ]
            ).to_csv(p, index=False)
            with self.assertRaisesRegex(ValueError, "sentido_legal_confirmado"):
                mod.cargar_aprobaciones(p, c)

    def test_aprobacion_documentada(self):
        c = pd.DataFrame(
            {
                "indice_osm": [1],
                "id_arista_osm": ["a"],
                "tid_bitcarrier": ["t"],
                "propuesta_estricta_vigente": [True],
            }
        )
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "revision.csv"
            pd.DataFrame(
                [
                    {
                        "indice_osm": 1,
                        "id_arista_osm": "a",
                        "tid_bitcarrier": "t",
                        "decision": "APROBADO",
                        "geometria_confirmada": "SI",
                        "sentido_legal_confirmado": "SI",
                        "evidencia": "Verificado en mapa OSM y evidencia de sentido",
                        "revisor": "Estudiante",
                    }
                ]
            ).to_csv(p, index=False)
            self.assertEqual(len(mod.cargar_aprobaciones(p, c)), 1)


if __name__ == "__main__":
    unittest.main()
