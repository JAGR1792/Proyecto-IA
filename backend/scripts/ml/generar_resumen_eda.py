"""EDA reproducible Bitcarrier (mayo 2022); exporta resumen estático para Nuxt.

Ejecutar desde cualquier carpeta:
    python backend/scripts/ml/generar_resumen_eda.py
    python backend/scripts/ml/generar_resumen_eda.py --input ruta.csv.gz --output ruta.json

Solo analiza observaciones históricas (sin datos simulados). No entrena modelos.
No interpreta el epoch en UTC como prueba de la zona horaria local original.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[3]
ENTRADA = RAIZ / 'backend/datos/ml/bitcarrier_mayo_2022_procesado/observaciones_limpias.csv.gz'
SALIDA = RAIZ / 'frontend/public/datos/eda_bitcarrier.json'
DIAS = ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado', 'Domingo']
COLUMNAS = ['objectid', 'tid', 'inicio_original', 'dia_semana_original', 'hora', 'distancia_original', 'velocidad_original', 'num_dispositivos', 'nombre_origen', 'nombre_destino']


def _num(x, dec=3):
    return round(float(x), dec) if pd.notna(x) and np.isfinite(x) else None


def _serie_resumen(s):
    return {'min': _num(s.min()), 'p25': _num(s.quantile(.25)), 'mediana': _num(s.median()),
            'media': _num(s.mean()), 'p75': _num(s.quantile(.75)), 'p95': _num(s.quantile(.95)),
            'max': _num(s.max())}


def calcular_resumen(df):
    df = df.copy()
    for k in ['hora', 'inicio_original', 'distancia_original', 'velocidad_original', 'num_dispositivos']:
        df[k] = pd.to_numeric(df[k], errors='coerce')
    df['tid'] = df['tid'].astype('string')
    df['dia_semana_original'] = df['dia_semana_original'].astype('string').str.strip().str.capitalize().replace({'Miércoles':'Miercoles','Sábado':'Sabado'})
    fechas = pd.to_datetime(df['inicio_original'], unit='ms', utc=True, errors='coerce')
    validas = df['velocidad_original'].gt(0) & df['distancia_original'].gt(0)
    vel = df['velocidad_original'].loc[validas]
    dist = df['distancia_original'].loc[validas]
    # Solo estimación derivada bajo el supuesto de unidades; NO es tiempo medido.
    tiempo = 0.06 * dist / vel
    objetivo = pd.Series(np.nan, index=df.index)
    objetivo.loc[validas] = tiempo
    df['tiempo_derivado_min'] = objetivo
    df['fecha_utc'] = fechas
    df['fecha_dia'] = fechas.dt.strftime('%Y-%m-%d')

    q1, q3 = vel.quantile([.25, .75])
    iqr = q3 - q1
    limite_superior = q3 + 1.5 * iqr
    outlier_iqr = int((vel > limite_superior).sum())
    # Los extremos se cuentan, NO se eliminan silenciosamente.
    missing = {k: int(df[k].isna().sum()) for k in COLUMNAS}
    n_unicos = int(df['objectid'].nunique(dropna=True))
    datos = {
      'schema_version': 1,
      'fuente': 'Velocidades Bitcarrier Mayo 2022 (Secretaría Distrital de Movilidad / servicio ArcGIS)',
      'tipo': 'historico_observado',
      'periodo': {'inicio_epoch_utc': fechas.min().isoformat(), 'fin_epoch_utc': fechas.max().isoformat(),
                  'dias_distintos_utc': int(fechas.dt.date.nunique()), 'intervalos_distintos': int(fechas.nunique())},
      'resumen': {'observaciones': int(len(df)), 'tids': int(df['tid'].nunique()),
                  'horas': int(df['hora'].nunique()), 'objectids_unicos': n_unicos,
                  'duplicados_objectid': int(len(df) - n_unicos),
                  'hora_coincide_epoch_utc': int((fechas.dt.hour == df['hora']).sum()),
                  'validos_vel_dist': int(validas.sum())},
      'faltantes': missing,
      'estadisticas': {'velocidad_original': _serie_resumen(vel), 'distancia_original': _serie_resumen(dist),
                       'dispositivos': _serie_resumen(df['num_dispositivos']),
                       'tiempo_derivado_min': _serie_resumen(tiempo)},
      'atipicos': {'velocidad_mayor_100': int((vel > 100).sum()),
                  'velocidad_mayor_120': int((vel > 120).sum()),
                  'limite_superior_iqr': _num(limite_superior), 'atipicos_superiores_iqr': outlier_iqr,
                  'dispositivos_igual_1': int((df['num_dispositivos'] == 1).sum())},
      'advertencias': [
        'Serie histórica de mayo de 2022; no representa tránsito actual.',
        'Las 46 geometrías TID NO están validadas como aristas del grafo OSM.',
        'INICIO coincide con HORA si se interpreta como UTC; zona horaria original sin confirmación documental.',
        'El tiempo derivado se calcula suponiendo metros y km/h; validar unidades con la fuente.',
        'El tiempo derivado no es una medición directa del recorrido de taxi.',
        'Los perfiles presentados son DESCRIPTIVOS de todo el mes: no utilizarlos directamente como features en evaluación temporal.',
        'Los datos simulados para OSM NO forman parte de este resumen.'
      ],
    }
    # Histograma con bordes fijos para que la interfaz interprete cifras sin ambigüedad.
    limites = [0,5,10,15,20,25,30,40,50,60,80,100,120,180]
    conteos, bordes = np.histogram(vel, bins=limites)
    datos['histograma_velocidad'] = [{'desde':float(bordes[i]),'hasta':float(bordes[i+1]),'cantidad':int(c)} for i,c in enumerate(conteos)]
    por_hora = df.groupby('hora', observed=True)['velocidad_original'].agg(['count','median','mean'])
    datos['por_hora'] = [{'hora':int(h), 'n':int(z['count']), 'mediana':_num(z['median']),'media':_num(z['mean'])} for h,z in por_hora.iterrows()]
    por_dia = df.groupby('dia_semana_original', observed=True)['velocidad_original'].agg(['count','median','mean'])
    datos['por_dia'] = [{'dia':d,'n':int(por_dia.loc[d,'count']) if d in por_dia.index else 0,
                        'mediana':_num(por_dia.loc[d,'median']) if d in por_dia.index else None} for d in DIAS]
    g = df.groupby(['dia_semana_original','hora'], observed=True)['velocidad_original'].agg(['count','median'])
    datos['mapa_calor'] = [{'dia':d,'hora':h,'n':int(g.loc[(d,h),'count']) if (d,h) in g.index else 0,
                           'mediana':_num(g.loc[(d,h),'median']) if (d,h) in g.index else None}
                          for d in DIAS for h in range(24)]
    rutas = df.groupby('tid', observed=True).agg(n=('objectid','size'),
                mediana_velocidad=('velocidad_original','median'),
                q1_velocidad=('velocidad_original',lambda s:s.quantile(.25)),
                q3_velocidad=('velocidad_original',lambda s:s.quantile(.75)),
                distancia_mediana=('distancia_original','median'),
                dispositivos_mediana=('num_dispositivos','median'),
                nombre_origen=('nombre_origen','first'), nombre_destino=('nombre_destino','first'),
                intervalos=('inicio_original','nunique'))
    datos['por_tramo'] = [{'tid':str(tid),'n':int(z.n),'nombre':str(z.nombre_origen)+' → '+str(z.nombre_destino),
             'mediana_velocidad':_num(z.mediana_velocidad),'q1_velocidad':_num(z.q1_velocidad),
             'q3_velocidad':_num(z.q3_velocidad), 'distancia_mediana':_num(z.distancia_mediana),
             'dispositivos_mediana':_num(z.dispositivos_mediana),'intervalos':int(z.intervalos)}
            for tid,z in rutas.sort_values('n',ascending=False).iterrows()]
    cobertura = df.groupby('fecha_dia',observed=True).agg(n=('objectid','size'), tids=('tid','nunique'))
    datos['por_fecha'] = [{'fecha':str(fecha),'n':int(z.n),'tids':int(z.tids)} for fecha,z in cobertura.iterrows()]
    datos['correlacion_pearson'] = {
      'distancia_vs_velocidad':_num(df['distancia_original'].corr(df['velocidad_original'])),
      'dispositivos_vs_velocidad':_num(df['num_dispositivos'].corr(df['velocidad_original'])),
      'distancia_vs_tiempo_derivado':_num(df['distancia_original'].corr(df['tiempo_derivado_min']))
    }
    return datos


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ENTRADA)
    parser.add_argument('--output', type=Path, default=SALIDA)
    args = parser.parse_args()
    if not args.input.is_file():
        parser.error(f'No existe {args.input}. Ejecuta primero preparar_bitcarrier.py.')
    df = pd.read_csv(args.input, usecols=COLUMNAS, low_memory=False)
    datos = calcular_resumen(df)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w',encoding='utf-8') as f:
        json.dump(datos, f, ensure_ascii=False, indent=2, allow_nan=False)
    print('EDA histórico:', datos['resumen']['observaciones'], 'filas;', datos['resumen']['tids'],'TID')
    print('Horas coinciden con UTC:', datos['resumen']['hora_coincide_epoch_utc'])
    print('Atípicos >100:', datos['atipicos']['velocidad_mayor_100'])
    print('JSON dashboard:',args.output)

if __name__=='__main__':
    main()
