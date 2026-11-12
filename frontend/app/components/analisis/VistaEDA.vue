<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

type Estadisticas = { min:number|null; p25:number|null; mediana:number|null; media:number|null; p75:number|null; p95:number|null; max:number|null }
type Frecuencia = { desde:number; hasta:number; n:number }
type Hora = { hora:number; n:number; mediana:number|null }
type Dia = { dia:string; n:number; mediana:number|null }
type Via = { tipo:string; n:number; aristas:number; velocidad_mediana:number|null; tiempo_mediano:number|null }
type Seccion = { n:number; aristas:number; velocidad:Estadisticas; tiempo:Estadisticas; distancia:Estadisticas; hist_velocidad:Frecuencia[]; hist_tiempo:Frecuencia[]; horas:Hora[]; dias:Dia[]; calor:{dia:string; hora:number; n:number; mediana:number|null}[]; tipos:Via[]; velocidad_mayor_100:number }
type Resumen = {
  schema_version:3; tipo:'red_osm_integrada'; total:number; aristas_osm:number; horarios:number;
  procedencia:{transferencia_provisional:number; simulacion_calibrada:number; aristas_con_transferencia:number; aristas_transferencia_parcial:number; escenarios_respaldo_en_aristas_transferidas:number};
  calidad:{duplicados:number; aristas_incompletas:number; tiempos_inconsistentes:number; horas_por_arista_min:number; horas_por_arista_max:number; observaciones_reales_sobre_osm:number};
  segmentos:{todos:Seccion; transferencia:Seccion; simulacion:Seccion};
  aristas_tiempo_mayor:{id:string; nombre:string; tipo:string; distancia_m:number|null; tiempo_mediano:number|null; velocidad_mediana:number|null; transferencias:number}[];
  distancia_vs_tiempo:{distancia_m:number|null; tiempo_min:number|null; n_aristas:number}[];
  advertencias:string[];
}
const datos=ref<Resumen|null>(null)
const cargando=ref(true)
const error=ref('')
const dia=ref('Todos')
const metrica=ref<'velocidad'|'tiempo'>('velocidad')
const dias=['Todos','Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo']
const formato=(n:number)=>new Intl.NumberFormat('es-CO').format(n)
const num=(n:number|null|undefined,dec=1)=>n==null?'—':n.toLocaleString('es-CO',{minimumFractionDigits:dec,maximumFractionDigits:dec})
const actual=computed(()=>datos.value?.segmentos.todos??null)
const serie=computed<Hora[]>(()=> {
  if(!actual.value)return []
  if(dia.value==='Todos')return actual.value.horas
  return actual.value.calor.filter(x=>x.dia===dia.value)
})
const valores=computed(()=>serie.value.map(x=>x.mediana).filter((x):x is number=>x!==null))
const limites=computed(()=> {
  const v=valores.value
  return { minimo:Math.max(0,Math.floor((Math.min(...v,0)-3)/5)*5),maximo:Math.max(10,Math.ceil((Math.max(...v,35)+3)/5)*5)}
})
const xHora=(h:number)=>44+(h*28.2)
const yVel=(n:number)=>185-(n-limites.value.minimo)/Math.max(1,limites.value.maximo-limites.value.minimo)*157
const linea=computed(()=>serie.value.filter(x=>x.mediana!==null).map(x=>`${xHora(x.hora)},${yVel(x.mediana!)}`).join(' '))
const hist=computed(()=>metrica.value==='velocidad'?actual.value?.hist_velocidad??[]:actual.value?.hist_tiempo??[])
const histMax=computed(()=>Math.max(1,...hist.value.map(x=>x.n)))
const maxVia=computed(()=>Math.max(1,...(actual.value?.tipos??[]).map(x=>x.aristas)))
const celdas=computed(()=>new Map((actual.value?.calor??[]).map(c=>[`${c.dia}|${c.hora}`,c])))
const celda=(d:string,h:number)=>celdas.value.get(`${d}|${h}`)
const rangoCalor=computed(()=>{
  const vs=(actual.value?.calor??[]).map(c=>c.mediana).filter((x):x is number=>x!==null)
  return {min:Math.min(...vs,0), max:Math.max(...vs,1)}
})
function colorCalor(v:number|null|undefined){
  if(v==null)return '#4b5563'
  const p=Math.max(0,Math.min(1,(v-rangoCalor.value.min)/Math.max(1,rangoCalor.value.max-rangoCalor.value.min)))
  return `hsl(${10+165*p} 72% ${43+5*p}%)`
}
onMounted(async()=>{
  try{
    const r=await fetch('/datos/eda_red_osm.json')
    if(!r.ok)throw new Error(`Resumen no disponible (HTTP ${r.status}). Ejecuta generar_eda_red_osm.py.`)
    const j=await r.json() as Resumen
    if(j.schema_version!==3||j.tipo!=='red_osm_integrada')throw new Error('El JSON no corresponde al EDA de la red OSM integrada.')
    datos.value=j
  }catch(e){error.value=e instanceof Error?e.message:'Error cargando los datos'}
  finally{cargando.value=false}
})
</script>

<template>
  <section class="txeda" aria-label="Análisis exploratorio de movilidad">
    <div class="txeda-top">
      <div>
        <p class="txeda-eyebrow">TAXI IA / CHAPINERO / APRENDIZAJE AUTOMÁTICO</p>
        <h2>Análisis exploratorio de movilidad</h2>
        <p class="txeda-sub">Distribuciones, patrones temporales, comportamiento por vía y calidad de los escenarios.</p>
      </div>
      <span class="txeda-status"><span class="txeda-dot"></span> Movilidad de Chapinero</span>
    </div>
    <div v-if="cargando" class="txeda-info" role="status">Cargando estadísticas de la red…</div>
    <div v-else-if="error" class="txeda-info txeda-error" role="alert">{{ error }}</div>
    <template v-else-if="datos && actual">
      <div class="txeda-kpis">
        <div class="txeda-kpi"><span>Registros analizados</span><strong>{{ formato(datos.total) }}</strong><small>Arista × día × hora</small></div>
        <div class="txeda-kpi"><span>Tramos de la red</span><strong>{{ formato(datos.aristas_osm) }}</strong><small>Calles y conexiones</small></div>
        <div class="txeda-kpi"><span>Velocidad mediana</span><strong>{{ num(actual.velocidad.mediana,1) }}</strong><small>km/h</small></div>
        <div class="txeda-kpi"><span>Tiempo mediano por tramo</span><strong>{{ num(actual.tiempo.mediana,3) }}</strong><small>minutos</small></div>
      </div>

      <div class="txeda-section-head"><div><h3>01 · Patrones de movilidad</h3><p>Comparación horaria y comportamiento por día de la semana.</p></div></div>
      <div class="txeda-grid">
        <article class="txeda-panel txeda-wide">
          <div class="txeda-cardhead"><div><h4>Gráfica de líneas · velocidad mediana por hora</h4><p>Mediana de velocidades por hora</p></div><label>Día <select v-model="dia"><option v-for="d in dias" :key="d">{{ d }}</option></select></label></div>
          <svg viewBox="0 0 740 226" class="txeda-line" role="img" :aria-label="`Perfil horario de ${dia}`">
            <g v-for="i in 4" :key="i"><line x1="44" x2="710" :y1="185-(i-1)*157/3" :y2="185-(i-1)*157/3" stroke="var(--text-tertiary)" stroke-opacity=".35"/><text x="36" :y="189-(i-1)*157/3" text-anchor="end" fill="var(--text-secondary)" font-size="11">{{ num(limites.minimo+(i-1)*(limites.maximo-limites.minimo)/3,0) }}</text></g>
            <polyline :points="linea" fill="none" stroke="var(--accent-brand)" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>
            <g v-for="p in serie" :key="p.hora"><circle v-if="p.mediana!==null" :cx="xHora(p.hora)" :cy="yVel(p.mediana)" r="4" fill="var(--accent-brand)"><title>{{ p.hora }}:00 · {{ num(p.mediana,2) }} · {{ formato(p.n) }} registros</title></circle><text v-if="p.hora%3===0" :x="xHora(p.hora)" y="210" text-anchor="middle" font-size="11" fill="var(--text-secondary)">{{ String(p.hora).padStart(2,'0') }}</text></g>
          </svg>
          <p class="txeda-note">Eje X: hora del día · Eje Y: velocidad (km/h).</p>
        </article>
        <article class="txeda-panel"><div class="txeda-cardhead"><div><h4>Histograma de {{ metrica === 'velocidad' ? 'velocidades' : 'tiempos por tramo' }}</h4><p>Barras contiguas: frecuencia de registros por intervalo</p></div><label>Variable <select v-model="metrica"><option value="velocidad">Velocidad</option><option value="tiempo">Tiempo</option></select></label></div>
          <div class="txeda-hist"><div v-for="b in hist" :key="b.desde" class="txeda-hcol" :title="`${b.desde}–${b.hasta}: ${formato(b.n)} registros`"><div class="txeda-hbar" :style="{height:`${100*b.n/histMax}%`}"></div><small>{{ b.desde }}</small></div></div>
          <p class="txeda-note">{{ metrica==='velocidad'?'Velocidad (km/h)':'Tiempo por tramo (minutos)' }} · {{ formato(actual.n) }} registros analizados.</p>
        </article>
        <article class="txeda-panel"><div class="txeda-cardhead"><div><h4>Gráfica de barras · velocidad por día</h4><p>Mediana de la semana tipo</p></div></div>
          <div class="txeda-days"><div v-for="d in actual.dias" :key="d.dia" class="txeda-day"><span>{{ d.dia.slice(0,3) }}</span><div class="txeda-track"><i :style="{width:`${Math.min(100,100*(d.mediana??0)/Math.max(1,limites.maximo))}%`}"></i></div><strong>{{ num(d.mediana,1) }}</strong></div></div>
          <p class="txeda-note">Comparación de los perfiles de movilidad según el día de la semana.</p>
        </article>
        <article class="txeda-panel txeda-wide"><div class="txeda-cardhead"><div><h4>Mapa de calor · velocidad por día y hora</h4><p>Valores menores: cálidos · valores mayores: verde azulado</p></div></div>
          <div class="txeda-heat-scroll"><div class="txeda-heat"><div class="txeda-heat-row"><b></b><small v-for="h in 24" :key="h">{{ String(h-1).padStart(2,'0') }}</small></div><div v-for="d in dias.slice(1)" :key="d" class="txeda-heat-row"><b>{{ d.slice(0,3) }}</b><span v-for="h in 24" :key="h" :style="{backgroundColor:colorCalor(celda(d,h-1)?.mediana)}" :title="`${d} ${h-1}:00 · ${num(celda(d,h-1)?.mediana,2)} · n=${celda(d,h-1)?.n??0}`"></span></div></div></div>
          <p class="txeda-note">Amarillo = velocidades menores; verde = velocidades mayores. Pasa el cursor para consultar km/h y registros.</p>
        </article>
      </div>

      <div class="txeda-section-head"><div><h3>02 · Vías y tiempos de desplazamiento</h3><p>Análisis de características disponibles para la regresión.</p></div></div>
      <div class="txeda-grid">
        <article class="txeda-panel"><h4>Comparación por tipo de vía · velocidad mediana</h4><p>La cifra indica km/h; la barra representa cantidad de aristas</p><div class="txeda-types"><div v-for="t in actual.tipos" :key="t.tipo" class="txeda-type"><div class="txeda-type-top"><span :title="t.tipo">{{ t.tipo }}</span><strong>{{ num(t.velocidad_mediana,1) }}</strong></div><div class="txeda-track"><i :style="{width:`${100*t.aristas/maxVia}%`}"></i></div><small>{{ t.aristas }} aristas · {{ formato(t.n) }} registros</small></div></div><p class="txeda-note">Comparación de las velocidades según la clasificación de las vías.</p></article>
        <article class="txeda-panel"><h4>Diagrama de dispersión · distancia y tiempo</h4><p>Medianas agregadas por intervalos de longitud</p><svg viewBox="0 0 520 300" role="img" class="txeda-scatter" aria-label="Relación entre longitud y tiempo mediano por arista"><line x1="46" y1="258" x2="490" y2="258" stroke="var(--text-tertiary)"/><line x1="46" y1="28" x2="46" y2="258" stroke="var(--text-tertiary)"/><g v-for="(p,i) in datos.distancia_vs_tiempo" :key="i"><circle v-if="p.distancia_m!==null&&p.tiempo_min!==null" :cx="46+(p.distancia_m/(Math.max(1,...datos.distancia_vs_tiempo.map(q=>q.distancia_m??0))))*425" :cy="258-(p.tiempo_min/(Math.max(0.01,...datos.distancia_vs_tiempo.map(q=>q.tiempo_min??0))))*215" r="5" fill="var(--accent-route)"><title>{{ num(p.distancia_m,1) }} m · {{ num(p.tiempo_min,3) }} min · {{ p.n_aristas }} aristas</title></circle></g><text x="268" y="289" text-anchor="middle" fill="var(--text-secondary)" font-size="12">Longitud mediana (m)</text><text x="21" y="142" transform="rotate(-90 21 142)" text-anchor="middle" fill="var(--text-secondary)" font-size="12">Tiempo mediano (min)</text></svg><p class="txeda-note">Cada punto resume un rango de distancias; no es un ajuste de regresión.</p></article>
        <article class="txeda-panel txeda-wide"><h4>Tramos con mayor tiempo mediano</h4><p>Tabla de 12 ejemplos para inspeccionar la relación entre distancia, velocidad y tiempo</p><div class="txeda-table-wrap"><table><thead><tr><th>Arista</th><th>Vía</th><th>Tipo</th><th>Distancia (m)</th><th>Velocidad (km/h)</th><th>Tiempo (min)</th></tr></thead><tbody><tr v-for="r in datos.aristas_tiempo_mayor" :key="r.id"><td>{{ r.id }}</td><td>{{ r.nombre }}</td><td>{{ r.tipo }}</td><td>{{ num(r.distancia_m,1) }}</td><td>{{ num(r.velocidad_mediana,1) }}</td><td>{{ num(r.tiempo_mediano,3) }}</td></tr></tbody></table></div></article>
      </div>
      <div class="txeda-section-head"><div><h3>03 · Calidad de los datos</h3><p>Indicadores de consistencia de los registros analizados.</p></div></div>
      <div class="txeda-quality"><div><strong>{{ datos.calidad.duplicados }}</strong><small>Duplicados</small></div><div><strong>{{ datos.calidad.aristas_incompletas }}</strong><small>Aristas incompletas</small></div><div><strong>{{ datos.calidad.tiempos_inconsistentes }}</strong><small>Tiempos inconsistentes</small></div><div><strong>{{ datos.calidad.horas_por_arista_min }}–{{ datos.calidad.horas_por_arista_max }}</strong><small>Horarios por arista</small></div></div>
    </template>
  </section>
</template>

<style scoped>
.txeda{--tx-accent:var(--accent-brand);--tx-surface:var(--bg-surface);--tx-border:var(--border-color);--tx-fg:var(--text-primary);--tx-muted:var(--text-secondary);color:var(--tx-fg);background:transparent;border:1px solid var(--tx-border);border-radius:18px;padding:clamp(16px,2.8vw,30px);min-width:0;width:100%;box-sizing:border-box;font-family:inherit}
.txeda *{box-sizing:border-box}.txeda-top,.txeda-section-head,.txeda-cardhead,.txeda-controls,.txeda-composition-label{display:flex;justify-content:space-between;align-items:start;gap:16px;flex-wrap:wrap}
.txeda-eyebrow{font-size:11px!important;letter-spacing:.16em;color:var(--tx-accent)!important;font-weight:700;margin:0 0 8px!important}.txeda-top h2{font-size:clamp(22px,3vw,32px);font-weight:750;letter-spacing:-.025em;margin:0 0 6px;color:var(--text-primary)}.txeda-sub,.txeda-top p,.txeda-panel p,.txeda-section-head p,.txeda-controls p{font-size:12px;color:var(--tx-muted);margin:2px 0 0;line-height:1.6}
.txeda-status{white-space:nowrap;display:flex;align-items:center;gap:8px;color:var(--accent-brand);border-radius:25px;padding:8px 11px;border:1px solid var(--border-focus);background:var(--bg-surface-hover);font-size:11px}.txeda-dot{width:7px;height:7px;background:var(--accent-brand);border-radius:100%}.txeda-kpis,.txeda-quality{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-top:22px}.txeda-kpi,.txeda-quality>div{border:1px solid var(--tx-border);background:var(--tx-surface);border-radius:12px;padding:17px;min-width:0}.txeda-kpi>span,.txeda-quality small{display:block;color:var(--tx-muted);font-size:11px}.txeda-kpi strong{display:block;font-size:clamp(19px,2.4vw,29px);margin:7px 0 5px;color:var(--text-primary);font-variant-numeric:tabular-nums}.txeda-kpi small{color:var(--text-secondary);font-size:11px}.txeda-section-head{margin:30px 0 12px}.txeda-section-head h3{font-size:16px;color:var(--text-primary);margin:0 0 3px;font-weight:680}.txeda-panel{border:1px solid var(--tx-border);border-radius:13px;padding:18px;background:var(--tx-surface);min-width:0}.txeda-panel h4{font-size:15px;font-weight:680;margin:0 0 4px;color:var(--text-primary)}.txeda-panel p{margin:0}.txeda-note{font-size:11px!important;color:var(--text-secondary)!important;line-height:1.6;margin:10px 0 0!important}.txeda-controls{margin-top:20px;background:var(--bg-surface);border:1px solid var(--tx-border);padding:16px;border-radius:12px;align-items:center}.txeda-controls strong{font-size:13px}.txeda label{display:flex;align-items:center;gap:8px;font-size:11px;color:var(--text-secondary)}.txeda select{background:var(--bg-base);color:var(--text-primary);border:1px solid var(--border-focus);padding:8px 10px;border-radius:8px;font-size:12px;max-width:260px}.txeda-kpis-secondary{margin-top:12px}.txeda-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.txeda-wide{grid-column:1/-1}.txeda-cardhead{align-items:center}.txeda-line{width:100%;display:block;height:auto;max-height:275px;margin-top:12px}.txeda-hist{display:flex;align-items:flex-end;height:174px;gap:3px;margin-top:22px}.txeda-hcol{height:100%;flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;min-width:0}.txeda-hbar{background:linear-gradient(#fcd34d,var(--accent-brand-hover));border-radius:4px 4px 0 0;width:100%;max-width:28px;min-height:2px}.txeda-hcol small{font-size:9px;color:var(--text-secondary);margin-top:7px}.txeda-days,.txeda-types{margin-top:19px;display:flex;flex-direction:column;gap:12px}.txeda-day{display:grid;grid-template-columns:42px 1fr 45px;align-items:center;gap:9px;font-size:12px;color:var(--text-secondary)}.txeda-track{height:9px;background:var(--bg-surface-active);border-radius:15px;overflow:hidden}.txeda-track i{display:block;height:100%;background:var(--accent-brand);border-radius:15px}.txeda-day strong{text-align:right}.txeda-heat-scroll,.txeda-table-wrap{overflow-x:auto;margin-top:15px}.txeda-heat{min-width:690px}.txeda-heat-row{display:grid;grid-template-columns:48px repeat(24,minmax(18px,1fr));gap:4px;align-items:center;margin-bottom:5px}.txeda-heat-row b,.txeda-heat-row small{font-size:10px;color:var(--text-secondary);text-align:center}.txeda-heat-row span{height:27px;border-radius:4px;cursor:help}.txeda-type-top{display:flex;justify-content:space-between;gap:10px;margin-bottom:6px;font-size:12px;color:var(--text-secondary)}.txeda-type-top span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.txeda-type>small{font-size:10px;color:var(--tx-muted)}.txeda-scatter{display:block;width:100%;height:auto;max-height:295px;margin-top:14px}.txeda table{width:100%;border-collapse:collapse;min-width:760px;font-size:11px}.txeda th{text-align:left;color:var(--text-secondary);border-bottom:1px solid var(--border-color);padding:10px 8px;white-space:nowrap}.txeda td{color:var(--text-secondary);border-bottom:1px solid var(--border-color);padding:10px 8px}.txeda tr:hover td{background:var(--bg-surface-hover)}.txeda-quality{margin-top:0}.txeda-quality strong{display:block;font-size:20px;margin-bottom:8px;color:var(--text-primary)}.txeda-info{padding:25px;color:var(--text-secondary)}.txeda-error{color:#fecaca}
@media(max-width:880px){.txeda-kpis,.txeda-quality{grid-template-columns:repeat(2,minmax(0,1fr))}.txeda-grid{grid-template-columns:1fr}.txeda-wide{grid-column:auto}}@media(max-width:500px){.txeda{padding:13px}.txeda-kpis{gap:8px}.txeda-kpi{padding:12px}.txeda-panel{padding:13px}.txeda-cardhead label,.txeda-controls label{width:100%;justify-content:space-between}}

.txeda{border:none;padding:0;border-radius:0;box-shadow:none}.txeda-top{margin-bottom:18px}.txeda-status{color:var(--accent-brand);background:var(--bg-surface);border-color:var(--border-color)}.txeda-dot{background:var(--accent-brand)}.txeda h2,.txeda h3,.txeda h4{font-family:var(--font-ui)}.txeda-kpi strong{color:var(--accent-brand)}.txeda select{background-color:var(--bg-base);border:1px solid var(--border-color);color:var(--text-primary)}.txeda-line text,.txeda-scatter text{fill:var(--text-secondary)}.txeda-track i{background:var(--accent-brand)}.txeda-hbar{background:linear-gradient(#fcd34d,var(--accent-brand-hover))}.txeda-panel{overflow:hidden}.txeda-heat-row span:focus{outline:2px solid var(--accent-brand)}.txeda-grid{align-items:start}.txeda-cardhead{margin-bottom:10px}
</style>
