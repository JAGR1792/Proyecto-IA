"""EDA del UNICO dataset maestro híbrido; exporta JSON estático para Nuxt.

Ejecutar desde la raíz:
    python backend/scripts/ml/generar_resumen_eda_hibrido.py

NO combina fuentes para evaluar modelos. La opción 'Todos' es descriptiva y
NO es una estimación representativa del tráfico real: mezcla unidades distintas.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[3]
ENTRADA = RAIZ / 'backend/datos/ml/dataset_maestro_hibrido/dataset_maestro_hibrido.csv.gz'
SALIDA = RAIZ / 'frontend/public/datos/eda_hibrido.json'
DIAS = ['Lunes','Martes','Miercoles','Jueves','Viernes','Sabado','Domingo']
FUENTE_REAL = 'HISTORICO_BITCARRIER_2022'
FUENTE_SIM = 'SIMULADO_CALIBRADO_ENTRENAMIENTO'
BINS = [0,5,10,15,20,25,30,40,50,60,80,100,120,180,300]

def numero(x, dec=3):
    return round(float(x),dec) if pd.notna(x) and np.isfinite(x) else None

def metricas(s):
    return {k:numero(v) for k,v in {'min':s.min(),'p25':s.quantile(.25),
        'mediana':s.median(),'media':s.mean(),'p75':s.quantile(.75),
        'p95':s.quantile(.95),'max':s.max()}.items()}

def descripcion(df:pd.DataFrame,clave:str):
    v=df.loc[df['fuente_dato'].eq(clave)] if clave!='todos' else df
    hist,bordes=np.histogram(v['velocidad_kmh'].dropna(),bins=BINS)
    por_hora=v.groupby('hora',observed=True)['velocidad_kmh'].agg(['size','median','mean'])
    por_dia=v.groupby('dia_semana',observed=True)['velocidad_kmh'].agg(['size','median'])
    calor=v.groupby(['dia_semana','hora'],observed=True)['velocidad_kmh'].agg(['size','median'])
    # Etiquetas espaciales: TID y OSM permanecen distintos. Top 12 por n
    tramos=v.groupby(['unidad_espacial','id_espacial'],observed=True).agg(
       n=('id_registro','size'),mediana=('velocidad_kmh','median'),
       p25=('velocidad_kmh',lambda x:x.quantile(.25)),
       p75=('velocidad_kmh',lambda x:x.quantile(.75)),
       nombre=('nombre_via','first')).sort_values('n',ascending=False).head(12)
    tipos=v.copy()
    tipos['tipo_via']=tipos['tipo_via'].fillna('').replace('', 'No disponible')
    tipos_res=tipos.groupby('tipo_via',observed=True)['velocidad_kmh'].agg(['size','median']).sort_values('size',ascending=False).head(12)
    return {
      'filas':int(len(v)),
      'aristas_osm':int(v.loc[v.unidad_espacial.eq('ARISTA_OSM'),'indice_arista_osm'].nunique()),
      'tids_bitcarrier':int(v.loc[v.unidad_espacial.eq('TID_BITCARRIER'),'tid_bitcarrier'].nunique()),
      'velocidad':metricas(v['velocidad_kmh']),
      'distancia':metricas(v['distancia_m']),
      'tiempo':metricas(v['tiempo_min']),
      'atipicos_velocidad_mayor_100':int(v['velocidad_kmh'].gt(100).sum()),
      'histograma_velocidad':[{'desde':float(bordes[i]),'hasta':float(bordes[i+1]),'cantidad':int(c)} for i,c in enumerate(hist)],
      'por_hora':[{'hora':h,'n':int(por_hora.loc[h,'size']) if h in por_hora.index else 0,
            'mediana':numero(por_hora.loc[h,'median']) if h in por_hora.index else None} for h in range(24)],
      'por_dia':[{'dia':DIAS[d],'n':int(por_dia.loc[d,'size']) if d in por_dia.index else 0,
             'mediana':numero(por_dia.loc[d,'median']) if d in por_dia.index else None} for d in range(7)],
      'mapa_calor':[{'dia':DIAS[d],'hora':h,'n':int(calor.loc[(d,h),'size']) if (d,h) in calor.index else 0,
             'mediana':numero(calor.loc[(d,h),'median']) if (d,h) in calor.index else None} for d in range(7) for h in range(24)],
      'por_tramo':[{'id':str(id),'unidad':str(unidad),'n':int(x.n),
                    'nombre':str(x.nombre or ''),'mediana':numero(x.mediana),
                    'p25':numero(x.p25),'p75':numero(x.p75)}
                   for (unidad,id),x in tramos.iterrows()],
      'por_tipo_via':[{'tipo':str(k),'n':int(x['size']),'mediana':numero(x['median'])}
                     for k,x in tipos_res.iterrows()]
    }

def ejecutar(entrada:Path,salida:Path):
    columnas=['id_registro','unidad_espacial','id_espacial','indice_arista_osm',
             'tid_bitcarrier','granularidad_min','dia_semana','hora','distancia_m',
             'velocidad_kmh','tiempo_min','tipo_via','nombre_via','fuente_dato','particion']
    df=pd.read_csv(entrada,usecols=columnas,dtype={'id_registro':str,'id_espacial':str,'tid_bitcarrier':str,'tipo_via':str,'nombre_via':str},low_memory=False)
    assert len(df)>0
    if df['id_registro'].duplicated().any(): raise ValueError('IDs duplicados en maestro')
    if set(df['fuente_dato'].unique())!={FUENTE_REAL,FUENTE_SIM}:
        raise ValueError(f'Fuentes no reconocidas: {df.fuente_dato.unique().tolist()}')
    for c in ['dia_semana','hora','distancia_m','velocidad_kmh','tiempo_min']:
        df[c]=pd.to_numeric(df[c],errors='coerce')
    if df[['distancia_m','velocidad_kmh','tiempo_min']].isna().any().any(): raise ValueError('Valores numéricos nulos')
    if (df[['distancia_m','velocidad_kmh','tiempo_min']]<=0).any().any():raise ValueError('Tiempo o velocidad no positivos')
    if not df.hora.between(0,23).all():raise ValueError('Hora fuera de 0..23')
    if not df.dia_semana.between(0,6).all():raise ValueError('Dia fuera de 0..6')
    pre=descripcion(df,'todos')
    rec={
       'schema_version':2,'tipo':'dataset_maestro_hibrido',
       'titulo':'Análisis exploratorio del dataset maestro híbrido',
       'filas_total':int(len(df)),
       'fuentes':{'real':int(df.fuente_dato.eq(FUENTE_REAL).sum()),
                  'simulado':int(df.fuente_dato.eq(FUENTE_SIM).sum())},
       'aristas_osm':int(df.loc[df.unidad_espacial.eq('ARISTA_OSM'),'indice_arista_osm'].nunique()),
       'tid_bitcarrier':int(df.loc[df.unidad_espacial.eq('TID_BITCARRIER'),'tid_bitcarrier'].nunique()),
       'conjuntos':{'todos':pre,'historico':descripcion(df,FUENTE_REAL),
                    'simulado':descripcion(df,FUENTE_SIM)},
       'particiones_historico':{str(k):int(v) for k,v in
                df.loc[df.fuente_dato.eq(FUENTE_REAL),'particion'].value_counts().items()},
       'advertencias':[
          'Todos = mezcla descriptiva de tramos TID/15 min y aristas OSM/60 min: NO interpretar una mediana conjunta como velocidad real de la ciudad.',
          'El dataset maestro es uno solo, pero mantiene fuente_dato y unidad_espacial para análisis y modelado responsables.',
          'Las filas simuladas son 168 escenarios semanales por arista, no mediciones independientes.',
          'Las simulaciones se calibraron usando únicamente el periodo de entrenamiento histórico.',
          'Ninguna asociación Bitcarrier–OSM se ha validado. Los históricos no se atribuyen a aristas OSM.',
          'El tiempo objetivo es derivado de distancia y velocidad, no un tiempo de recorrido medido.',
          'Las unidades DISTANCE=m y VEL_PROMEDIO=km/h son supuestos pendientes de verificación.',
          'La evaluación predictiva debe reservar el historial de validación y prueba; nunca evaluar exclusivamente contra simulaciones.'
       ]
    }
    salida.parent.mkdir(parents=True,exist_ok=True)
    salida.write_text(json.dumps(rec,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print('EDA híbrido:',rec['filas_total'],'filas; observadas:',rec['fuentes']['real'],
          '; simuladas:',rec['fuentes']['simulado'])
    print('JSON:',salida)
    return rec

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,default=ENTRADA)
    p.add_argument('--output',type=Path,default=SALIDA)
    a=p.parse_args()
    ejecutar(a.input,a.output)
