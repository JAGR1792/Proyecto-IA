import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np
from sklearn.linear_model import LinearRegression

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/ml/evaluar_regresion_red_osm.py"
spec = importlib.util.spec_from_file_location("evaluar_regresion_red_osm", SCRIPT)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


class TestEvaluacionLineal(unittest.TestCase):
    def test_mse_es_media_cuadratica(self):
        a = m.calcular_metricas([1, 2, 3], [2, 2, 1])
        self.assertAlmostEqual(a["MSE_min2"], 5 / 3)
        self.assertAlmostEqual(a["RMSE_min"], np.sqrt(5 / 3))

    def test_residuo_con_signo(self):
        a = m.calcular_metricas([2, 4], [1, 3])
        self.assertEqual(a["error_medio_firmado_min"], -1)

    def test_predicciones_no_positivas(self):
        a = m.calcular_metricas([1, 2, 3], [-1, 0, 1])
        self.assertEqual(a["predicciones_no_positivas"], 2)

    def test_regresion_ordinaria(self):
        from entrenar_regresion_red_osm import crear_modelo

        self.assertIsInstance(crear_modelo().named_steps["regresion"], LinearRegression)


if __name__ == "__main__":
    unittest.main()
