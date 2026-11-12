"""Pruebas de posprocesamiento de la regresión lineal ordinaria."""
import importlib.util
from pathlib import Path
import sys
import unittest
import numpy as np
from sklearn.linear_model import LinearRegression

archivo=Path(__file__).resolve().parents[1] / 'scripts/ml/entrenar_regresion_red_osm.py'
spec=importlib.util.spec_from_file_location('entrenar_limites', archivo)
mod=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=mod
spec.loader.exec_module(mod)

class TestsLimites(unittest.TestCase):
    def test_limite_inferior_evitar_negativos(self):
        p=mod.limitar_tiempos(np.array([-1., 0.]),np.array([100.,200.]))
        np.testing.assert_allclose(p,[.075,.15])
        self.assertTrue(np.all(p>0))

    def test_limite_superior(self):
        p=mod.limitar_tiempos([100],[100])
        np.testing.assert_allclose(p,[1.2])

    def test_centro_no_alterado(self):
        p=mod.limitar_tiempos([.3],[100])
        np.testing.assert_allclose(p,[.3])

    def test_rechazo_entradas_invalidas(self):
        with self.assertRaises(ValueError):mod.limitar_tiempos([np.nan],[100])
        with self.assertRaises(ValueError):mod.limitar_tiempos([1],[0])

    def test_lineal_sin_ridge(self):
        self.assertIsInstance(mod.crear_modelo().named_steps['regresion'],LinearRegression)

if __name__=='__main__': unittest.main()
