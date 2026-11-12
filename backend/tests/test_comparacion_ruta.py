import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as S
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.ml.comparacion_ruta import comparar_ruta

class TestComparacionRuta(unittest.TestCase):
    def setUp(self):
        self.grafo=S(aristas=[S(id='a',origen='1',destino='2',distancia=100,tiempo_estimado=.2),
                             S(id='b',origen='2',destino='3',distancia=200,tiempo_estimado=.4)])
        self.r=S(ruta_encontrada=True,camino=['1','2','3'],aristas_camino=['a','b'])
        self.idx={('1','2',1,8):[(100,.25)],('2','3',1,8):[(200,.5)]}
    def test_valores_y_loss(self):
        c=comparar_ruta(self.grafo,self.r,self.idx,1,8)
        self.assertTrue(c['disponible'])
        self.assertAlmostEqual(c['tiempo_predicho_min'],.6)
        self.assertAlmostEqual(c['tiempo_referencia_min'],.75)
        self.assertAlmostEqual(c['error_absoluto_min'],.15)
        self.assertAlmostEqual(c['loss_cuadratica_min2'],.0225)
    def test_un_tramo_sin_referencia_no_inventa_loss(self):
        c=comparar_ruta(self.grafo,self.r,{('1','2',1,8):[(100,.25)]},1,8)
        self.assertFalse(c['disponible'])
        self.assertNotIn('tiempo_referencia_min',c)
        self.assertNotIn('loss_cuadratica_min2',c)
    def test_ignora_ids_no_utiliza_como_clave(self):
        self.grafo.aristas[0].id='id-diferente';self.r.aristas_camino[0]='id-diferente'
        self.assertTrue(comparar_ruta(self.grafo,self.r,self.idx,1,8)['disponible'])
    def test_sentido_no_equivale(self):
        self.idx={('2','1',1,8):[(100,.25)],('2','3',1,8):[(200,.5)]}
        self.assertFalse(comparar_ruta(self.grafo,self.r,self.idx,1,8)['disponible'])
    def test_ambiguedad_no_equivale(self):
        self.idx[('1','2',1,8)].append((100,.33))
        self.assertFalse(comparar_ruta(self.grafo,self.r,self.idx,1,8)['disponible'])
    def test_ruta_fallida(self):
        self.r.ruta_encontrada=False
        self.assertFalse(comparar_ruta(self.grafo,self.r,self.idx,1,8)['disponible'])
if __name__=='__main__':unittest.main()

class TestComparacionBase(unittest.TestCase):
    def test_respaldo_etiquetado_simulado(self):
        from src.ml.comparacion_ruta import comparar_con_grafo_base
        b=S(aristas=[S(id='a',origen='1',destino='2',tiempo_estimado=.3)])
        m=S(aristas=[S(id='a',origen='1',destino='2',tiempo_estimado=.2)])
        r=S(ruta_encontrada=True,camino=['1','2'],aristas_camino=['a'])
        c=comparar_con_grafo_base(b,m,r)
        self.assertTrue(c['disponible'])
        self.assertIn('simulado',c['fuente'])
        self.assertAlmostEqual(c['loss_cuadratica_min2'],.01)
    def test_respaldo_no_confunde_sentidos(self):
        from src.ml.comparacion_ruta import comparar_con_grafo_base
        b=S(aristas=[S(id='a',origen='2',destino='1',tiempo_estimado=.3)])
        m=S(aristas=[S(id='a',origen='1',destino='2',tiempo_estimado=.2)])
        r=S(ruta_encontrada=True,camino=['1','2'],aristas_camino=['a'])
        self.assertFalse(comparar_con_grafo_base(b,m,r)['disponible'])
