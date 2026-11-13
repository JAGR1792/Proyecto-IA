import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/ml/entrenar_regresion_red_osm.py"
spec = importlib.util.spec_from_file_location("entrenar_regresion_red_osm", SCRIPT)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


def ejemplo(n=20):
    filas = []
    for i in range(n):
        for dia in range(7):
            for h in range(24):
                dist = 100 + i * 10
                vel = 18 + 2 * (h % 6)
                filas.append(
                    (
                        i,
                        str(i),
                        dia,
                        h,
                        "residencial",
                        dist,
                        vel,
                        0.06 * dist / vel,
                        "SIMULACION_CALIBRADA_OSM",
                    )
                )
    return pd.DataFrame(filas, columns=m.COLUMNS)


class TestRegresion(unittest.TestCase):
    def test_modelo_es_regresion_lineal_ordinaria(self):
        from sklearn.linear_model import LinearRegression

        modelo = m.crear_modelo()
        self.assertIsInstance(modelo.named_steps["regresion"], LinearRegression)

    def test_preparacion_division(self):
        df = m.validar_y_preparar(ejemplo())
        grupos = m.dividir_por_aristas(df)
        self.assertEqual(sum(map(len, grupos.values())), len(df))
        self.assertEqual(sum(int(v.indice_arista_osm.nunique()) for v in grupos.values()), 20)

    def test_rechaza_incoherencias(self):
        df = ejemplo()
        df.loc[0, "tiempo_min"] = 100
        with self.assertRaises(ValueError):
            m.validar_y_preparar(df)

    def test_rechaza_duplicados(self):
        df = ejemplo()
        df = pd.concat([df, df.iloc[:1]], ignore_index=True)
        with self.assertRaises(ValueError):
            m.validar_y_preparar(df)

    def test_rechaza_arista_incompleta(self):
        df = ejemplo().iloc[1:]
        with self.assertRaises(ValueError):
            m.validar_y_preparar(df)


if __name__ == "__main__":
    unittest.main()
