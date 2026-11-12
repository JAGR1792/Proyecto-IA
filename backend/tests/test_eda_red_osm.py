"""Pruebas de agregación e integridad de red OSM para EDA."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

import pandas as pd

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/ml/generar_eda_red_osm.py'
spec = importlib.util.spec_from_file_location('generar_eda_red_osm', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class TestEDA(unittest.TestCase):
    def setUp(self):
        self.dir=tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.input=Path(self.dir.name)/'red.csv.gz'
        self.output=Path(self.dir.name)/'salida.json'
        registros=[]
        for i in (101,102):
            for d in range(7):
                for h in range(24):
                    distancia=100.0+i%10
                    velocidad=20. if i==101 else 40.
                    registros.append({'indice_arista_osm':i,'id_arista_osm':f'arista-{i}',
                      'dia_semana':d,'hora':h,'distancia_m':distancia,'velocidad_kmh':velocidad,
                      'tiempo_min':round(.06*distancia/velocidad,6),
                      'fuente_dato':mod.FUENTES[0] if i==101 and h<12 else mod.FUENTES[1],
                      'tipo_via':'residencial', 'nombre_via':'Calle Test',
                      'estado_match':'NO_VERIFICADO', 'observaciones_calibracion':3})
        pd.DataFrame(registros).to_csv(self.input,index=False,compression='gzip')

    def test_conteo_y_fuentes(self):
        res=mod.generar(self.input,self.output,Path(self.dir.name)/'sin_meta.json')
        self.assertEqual(res['total'],336)
        self.assertEqual(res['aristas_osm'],2)
        self.assertEqual(res['procedencia']['transferencia_provisional'],84)
        self.assertEqual(res['procedencia']['aristas_transferencia_parcial'],1)
        self.assertEqual(res['procedencia']['escenarios_respaldo_en_aristas_transferidas'],84)
        self.assertEqual(res['calidad']['duplicados'],0)
        self.assertEqual(len(res['segmentos']['todos']['calor']),168)
        self.assertTrue(self.output.exists())

    def test_duplicado_rechazado(self):
        d=pd.read_csv(self.input)
        pd.concat([d,d.iloc[:1]],ignore_index=True).to_csv(self.input,index=False,compression='gzip')
        with self.assertRaisesRegex(ValueError,'duplicad'):
            mod.generar(self.input,self.output)

    def test_tiempo_incoherente_rechazado(self):
        d=pd.read_csv(self.input)
        d.loc[0,'tiempo_min']=100
        d.to_csv(self.input,index=False,compression='gzip')
        with self.assertRaisesRegex(ValueError,'incoherentes'):
            mod.generar(self.input,self.output)

if __name__=='__main__': unittest.main()
