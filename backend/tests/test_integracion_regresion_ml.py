"""Tests independientes de la API y de archivos grandes."""
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.ml.tiempos_ruta import crear_entradas, identificar_arista, grafo_con_tiempos_ml

class AristaFalsa:
    def __init__(self,id,origen,destino,distancia):
        self.id=id; self.origen=origen; self.destino=destino;self.distancia=distancia
        self.tiempo_estimado=9;self.velocidad_promedio=30
    def model_copy(self,update):
        other=AristaFalsa(self.id,self.origen,self.destino,self.distancia)
        other.__dict__.update(self.__dict__);other.__dict__.update(update)
        return other

class GrafoFalso:
    def __init__(self,aristas):self.aristas=aristas
    def model_copy(self,update):return GrafoFalso(update['aristas'])

class TestsIntegracion(unittest.TestCase):
    def setUp(self):
        self.a=AristaFalsa('A','1','2',100)
        self.index={'A':[{'id':'A','origen':'1','destino':'2','distancia_m':100,'tipo_via':'residencial'}]}
    def test_identidad_direccion(self):
        self.assertIsNotNone(identificar_arista(self.a,self.index))
        self.assertIsNone(identificar_arista(AristaFalsa('A','2','1',100),self.index))
    def test_entradas_iguales_entrenamiento(self):
        r=crear_entradas([self.index['A'][0]],0,8)
        self.assertEqual(list(r.columns),['distancia_m','hora_sin','hora_cos','dia_semana','tipo_via'])
        self.assertEqual(r.iloc[0].dia_semana,'0')
    def test_ruta_no_modifica_grafo(self):
        modelo=MagicMock();modelo.predict.return_value=[.2]
        original=GrafoFalso([self.a])
        nuevo,meta=grafo_con_tiempos_ml(original,modelo,self.index,0,8)
        self.assertAlmostEqual(nuevo.aristas[0].tiempo_estimado,.2)
        self.assertEqual(original.aristas[0].tiempo_estimado,9)
        self.assertEqual(meta['aristas'],1)
    def test_limites_fisicos(self):
        modelo=MagicMock();modelo.predict.return_value=[-5]
        nuevo,meta=grafo_con_tiempos_ml(GrafoFalso([self.a]),modelo,self.index,0,8)
        self.assertGreater(nuevo.aristas[0].tiempo_estimado,0)
        self.assertEqual(meta['tiempos_ajustados_a_limites'],1)
    def test_ids_distintos_no_impiden_prediccion(self):
        modelo = MagicMock()
        modelo.predict.return_value = [.2]
        grafo = GrafoFalso([AristaFalsa('B', '1', '2', 100)])
        nuevo, meta = grafo_con_tiempos_ml(grafo, modelo, self.index, 0, 8)
        self.assertAlmostEqual(nuevo.aristas[0].tiempo_estimado, .2)
        self.assertEqual(meta['coincidencias_auditadas'], 0)

    def test_sin_indice_permite_uso_del_grafo_activo(self):
        modelo = MagicMock()
        modelo.predict.return_value = [.2]
        nuevo, meta = grafo_con_tiempos_ml(GrafoFalso([self.a]), modelo, None, 0, 8)
        self.assertAlmostEqual(nuevo.aristas[0].tiempo_estimado, .2)
        self.assertEqual(meta['coincidencias_auditadas'], 0)

    def test_distancia_invalida_rechazada(self):
        modelo = MagicMock()
        with self.assertRaisesRegex(ValueError, 'distancia'):
            grafo_con_tiempos_ml(GrafoFalso([AristaFalsa('B', '1', '2', 0)]), modelo, None, 0, 8)
        modelo.predict.assert_not_called()

if __name__=='__main__':unittest.main()
