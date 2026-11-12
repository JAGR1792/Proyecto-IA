"""Construye UN dataset maestro con observaciones Bitcarrier y escenarios OSM.

Usar desde raiz: python backend/scripts/ml/construir_dataset_maestro.py
Dependencia: construir_base_hibrida.py en la misma carpeta.

Precauciones:
* Filas HISTORICAS: unidad espacial TID, cada 15 minutos, SIN emparejamiento OSM confirmado.
* Filas SIMULADAS: unidad espacial arista OSM, cada hora de una SEMANA TIPO,
  calibrada SOLO con Bitcarrier del 1 al 21 de mayo 2022 para evitar fuga temporal.
* No son 426 mil observaciones reales ni una tabla de segmentos OSM medidos.
* Se conserva particion de validacion/prueba historica y procedencia por fila.
"""
from __future__ import annotations
import argparse
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
from construir_base_hibrida import cargar_historico, construir_perfiles, construir_aristas

RAIZ = Path(__file__).resolve().parents[3]
HISTORICO = RAIZ / 'backend/datos/ml/bitcarrier_mayo_2022_procesado/observaciones_limpias.csv.gz'
OSM = RAIZ / 'backend/datos/grafo_osm_aristas.csv'
SALIDA = RAIZ / 'backend/datos/ml/dataset_maestro_hibrido'
CAMPOS = ['id_registro','unidad_espacial','id_espacial','indice_arista_osm','id_arista_osm',
          'tid_bitcarrier','instante_fuente_utc','granularidad_min','dia_semana','hora',
          'distancia_m','velocidad_kmh','tiempo_min','tipo_via','nombre_via',
          'num_dispositivos','fuente_dato','particion','calidad_asociacion']


def ejecutar(historico: Path, osm: Path, salida: Path):
    h, calidad = cargar_historico(historico)
    aristas, grafo = construir_aristas(osm)
    if len(aristas) != len(set(aristas['indice_arista_osm'])):
        raise ValueError('indices OSM duplicados')
    # Todos los parámetros de simulación se aprenden SOLO del entrenamiento.
    h['particion'] = np.select([h['fecha_fuente'].dt.day.le(21),
                                h['fecha_fuente'].dt.day.le(26)],
                               ['entrenamiento','validacion'], default='prueba')
    perfiles, metodo = construir_perfiles(h.loc[h['particion'].eq('entrenamiento')])
    salida.mkdir(parents=True, exist_ok=True)
    temporal = salida / 'dataset_maestro_hibrido.csv.gz.tmp'
    # Escribir primero a nombre temporal; no borrar dataset previo si falla.
    total_h = total_s = 0
    with gzip.open(temporal, 'wt', encoding='utf-8', newline='') as f:
        import csv
        writer = csv.DictWriter(f, fieldnames=CAMPOS)
        writer.writeheader()
        for row in h.itertuples(index=False):
            # Fecha es de CALENDARIO de fuente, no zona local contrastada.
            writer.writerow(dict(id_registro=f'BC:{row.objectid}', unidad_espacial='TID_BITCARRIER',
                id_espacial=f'BC:{row.tid}', indice_arista_osm='', id_arista_osm='',
                tid_bitcarrier=row.tid, instante_fuente_utc=row.fecha_fuente.isoformat(),
                granularidad_min=15, dia_semana=row.dia_semana, hora=row.hora,
                distancia_m=round(float(row.distancia_original),4),
                velocidad_kmh=round(float(row.velocidad_original),6),
                tiempo_min=round(float(row.tiempo_referencia_min),7), tipo_via='', nombre_via='',
                num_dispositivos=int(row.num_dispositivos), fuente_dato='HISTORICO_BITCARRIER_2022',
                particion=row.particion, calidad_asociacion='SIN_MATCH_OSM_VERIFICADO'))
            total_h += 1
        for p in perfiles.itertuples(index=False):
            for a in aristas.itertuples(index=False):
                vel = float(np.clip(a.velocidad_base_kmh * p.factor_simulacion, 5, 80))
                writer.writerow(dict(id_registro=f'SIM:{a.indice_arista_osm}:{p.dia_semana}:{p.hora}',
                    unidad_espacial='ARISTA_OSM',id_espacial=f'OSM:{a.indice_arista_osm}',
                    indice_arista_osm=a.indice_arista_osm,id_arista_osm=a.id_arista_osm,
                    tid_bitcarrier='',instante_fuente_utc='',granularidad_min=60,
                    dia_semana=p.dia_semana,hora=p.hora,
                    distancia_m=round(float(a.distancia_m),4),velocidad_kmh=round(vel,5),
                    tiempo_min=round(0.06*float(a.distancia_m)/vel,7),
                    tipo_via=getattr(a,'tipo_via','') if pd.notna(getattr(a,'tipo_via','')) else '',
                    nombre_via=getattr(a,'nombre_via','') if pd.notna(getattr(a,'nombre_via','')) else '',
                    num_dispositivos='',fuente_dato='SIMULADO_CALIBRADO_ENTRENAMIENTO',
                    particion='simulacion_no_evaluable',calidad_asociacion='NO_ES_MEDICION_OSM'))
                total_s += 1
    import os
    os.replace(temporal, salida / 'dataset_maestro_hibrido.csv.gz')
    # Índice de aristas y perfiles compactos para inferencia futura.
    aristas.to_csv(salida/'aristas_base.csv',index=False)
    perfiles.to_csv(salida/'perfiles_entrenamiento.csv',index=False)
    assert total_s == len(aristas)*168
    info = {
      'esquema_version':1,'generado_utc':datetime.now(timezone.utc).isoformat(),
      'filas_total':total_h+total_s,'filas_historicas':total_h,'filas_simuladas':total_s,
      'tid_distintos':calidad['tid_distintos'],'aristas_osm':len(aristas),
      'periodos_historico': {'entrenamiento':'1-21 mayo 2022', 'validacion':'22-26 mayo 2022', 'prueba':'27-31 mayo 2022'},
      'perfil_simulacion_calibrado_con':'Solo datos históricos de entrenamiento 1-21 mayo 2022',
      'unidades_no_confirmadas':{'DISTANCE':'metros (supuesto)', 'VEL_PROMEDIO':'km/h (supuesto)'},
      'tipos_registro':{'HISTORICO_BITCARRIER_2022':'TID/15 min',
        'SIMULADO_CALIBRADO_ENTRENAMIENTO':'OSM/semana tipo/60 min'},
      'advertencias':[
          'Un solo archivo con DOS unidades espaciales y temporales distintas. NO se deben confundir.',
          'Las 417 asociaciones con OSM son candidatas, ninguna verificada. No se atribuyen registros Bitcarrier a aristas OSM.',
          'Datos simulados calibrados solo con entrenamiento para reducir fuga temporal.',
          'Prohibido evaluar contra valores simulados como evidencia de precisión sobre tráfico real.',
          'Tiempos derivados de velocidad y distancia, NO tiempos de viaje medidos.',
          'No están confirmadas documentalmente las unidades ni la zona horaria de la fuente.',
          'Las 292488 filas simuladas son escenarios semanales, NO mediciones independientes.'
      ]
    }
    (salida/'metadatos_maestro.json').write_text(json.dumps(info,indent=2,ensure_ascii=False),encoding='utf-8')
    print(f'DATASET MAESTRO: {total_h+total_s:,} filas; historicas: {total_h:,}; simuladas: {total_s:,}')
    print(f'Aristas OSM: {len(aristas):,}; TID: {calidad["tid_distintos"]}')
    print('Calibracion: SOLO dias 1-21 mayo; validacion y prueba no calibran simulacion')
    print('Archivo:',salida/'dataset_maestro_hibrido.csv.gz')
    print('NOTA: unico dataset, con fuente_dato y unidad_espacial por fila; aun SIN matching verificado.')
    return info

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--historico',type=Path,default=HISTORICO)
    parser.add_argument('--osm',type=Path,default=OSM)
    parser.add_argument('--salida',type=Path,default=SALIDA)
    args=parser.parse_args()
    ejecutar(args.historico,args.osm,args.salida)
