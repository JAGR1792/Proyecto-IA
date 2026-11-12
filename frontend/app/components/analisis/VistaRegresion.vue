<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

type Metricas = { Loss_MSE_min2?:number; MSE_min2?:number; MAE_min:number; RMSE_min:number; R2:number }
type Punto = { real:number; predicho:number; residuo:number }
type Fila = { etiqueta:string; n:number; mae:number; mse:number }
type Resumen = {schema_version:number;modelo:string;fecha_generacion:string;metricas:{regresion:Metricas;referencia:Metricas;entrenamiento?:Metricas};totales:{filas_prueba:number;predicciones_crudas_no_positivas:number;predicciones_ajustadas:number};muestra:Punto[];histograma_residuos:{desde:number;hasta:number;n:number}[];por_hora:Fila[];por_tipo_via:Fila[]}
const resumen=ref<Resumen|null>(null)
const cargando=ref(true)
const error=ref('')
type Pestana = 'metricas' | 'predicciones' | 'errores'
const vista=ref<Pestana>('metricas')
const pestanas: {id:Pestana;n:string}[]=[{id:'metricas',n:'Métricas'},{id:'predicciones',n:'Predicciones'},{id:'errores',n:'Análisis de errores'}]
const formato=(v:number|undefined,d=4)=>v==null?'—':v.toLocaleString('es-CO',{maximumFractionDigits:d,minimumFractionDigits:d})
const reg=computed(()=>resumen.value?.metricas.regresion)
const base=computed(()=>resumen.value?.metricas.referencia)
const mse=(v:Metricas|undefined)=>v?.Loss_MSE_min2??v?.MSE_min2??0
const mejora=computed(()=>reg.value&&base.value?(100*(1-reg.value.MAE_min/base.value.MAE_min)):null)
const maxResiduo=computed(()=>Math.max(1,...(resumen.value?.histograma_residuos??[]).map(x=>x.n)))
const maxMaeHora=computed(()=>Math.max(.001,...(resumen.value?.por_hora??[]).map(x=>x.mae)))
const maxMaeVia=computed(()=>Math.max(.001,...(resumen.value?.por_tipo_via??[]).map(x=>x.mae)))
const maxMse=computed(()=>Math.max(.000001,mse(reg.value),mse(base.value)))
const puntos=computed(()=>{
 const src=resumen.value?.muestra??[]
 const limite=Math.max(.01,...src.flatMap(p=>[p.real,p.predicho]))*1.06
 return src.filter(p=>[p.real,p.predicho].every(Number.isFinite)).map(p=>({...p,x:48+420*p.real/limite,y:255-217*p.predicho/limite}))
})
const limitePuntos=computed(()=>Math.max(.01,...(resumen.value?.muestra??[]).flatMap(p=>[p.real,p.predicho]))*1.06)
onMounted(async()=>{
 try{
  const response=await fetch('/datos/ml_regresion_resumen.json')
  if(!response.ok)throw new Error(`No se encontró el resumen de regresión (HTTP ${response.status}). Ejecuta exportar_metricas_front.py desde la raíz del proyecto.`)
  const data=await response.json() as Resumen
  if(data.schema_version!==1||!data.metricas?.regresion||!data.metricas?.referencia)throw new Error('El archivo de métricas no tiene el formato esperado.')
  resumen.value=data
 }catch(e){error.value=e instanceof Error?e.message:String(e)}finally{cargando.value=false}
})
</script>

<template>
  <section class="txreg" aria-label="Rendimiento de regresión lineal">
    <header class="txreg-head"><div><p class="txreg-kicker">MODELO 01 · APRENDIZAJE SUPERVISADO</p><h2>Regresión lineal múltiple</h2><p>Evaluación del tiempo estimado por arista de la red vial.</p></div></header>
    <p v-if="cargando" class="txreg-message">Cargando métricas…</p>
    <p v-else-if="error" role="alert" class="txreg-message">{{ error }}</p>
    <template v-else-if="resumen &amp;&amp; reg &amp;&amp; base">
      <div class="txreg-tabs" role="tablist" aria-label="Resultados de regresión">
        <button v-for="t in pestanas" :key="t.id" type="button" role="tab" :aria-selected="vista===t.id" :class="{'txreg-tab-on':vista===t.id}" @click="vista=t.id">{{ t.n }}</button>
      </div>
      <div class="txreg-kpis">
        <div><span>MSE · LOSS</span><strong>{{ formato(mse(reg),6) }}</strong><small>min² · menor es mejor</small></div>
        <div><span>MAE</span><strong>{{ formato(reg.MAE_min*60,2) }} s</strong><small>Error absoluto promedio por arista</small></div>
        <div><span>RMSE</span><strong>{{ formato(reg.RMSE_min*60,2) }} s</strong><small>Penaliza errores grandes</small></div>
        <div><span>R²</span><strong>{{ formato(reg.R2,4) }}</strong><small>Varianza explicada</small></div>
      </div>
      <template v-if="vista==='metricas'">
        <div class="txreg-grid">
          <article class="txreg-card"><header><span>GRÁFICA DE BARRAS</span><h3>Pérdida MSE · regresión frente a referencia</h3><p>Cuánto difieren los tiempos predichos de los tiempos objetivo, al cuadrado.</p></header>
            <div class="txreg-bars">
              <div v-for="x in [{nombre:'Regresión lineal',valor:mse(reg),color:'brand'},{nombre:'Referencia',valor:mse(base),color:'neutral'}]" :key="x.nombre" class="txreg-bar-row"><div><span>{{ x.nombre }}</span><strong>{{ formato(x.valor,6) }} min²</strong></div><div class="txreg-track"><i :class="`txreg-${x.color}`" :style="{width:`${100*x.valor/maxMse}%`}"></i></div></div>
            </div><p class="txreg-interpret">{{ mejora==null?'—':`La regresión reduce el MAE ${formato(mejora,1)} % frente a la referencia.` }}</p>
          </article>
          <article class="txreg-card"><header><span>TABLA COMPARATIVA</span><h3>Métricas en conjunto de prueba</h3><p>Las medidas se calculan sobre aristas reservadas para prueba.</p></header><div class="txreg-tablewrap"><table><thead><tr><th>Métrica</th><th>Regresión</th><th>Referencia</th></tr></thead><tbody><tr><td>MSE (min²)</td><td>{{ formato(mse(reg),6) }}</td><td>{{ formato(mse(base),6) }}</td></tr><tr><td>MAE (s)</td><td>{{ formato(reg.MAE_min*60,2) }}</td><td>{{ formato(base.MAE_min*60,2) }}</td></tr><tr><td>RMSE (s)</td><td>{{ formato(reg.RMSE_min*60,2) }}</td><td>{{ formato(base.RMSE_min*60,2) }}</td></tr><tr><td>R²</td><td>{{ formato(reg.R2,4) }}</td><td>{{ formato(base.R2,4) }}</td></tr></tbody></table></div></article>
        </div>
        <div class="txreg-foot">Registros de prueba: {{ resumen.totales.filas_prueba.toLocaleString('es-CO') }} · Predicciones ajustadas por límites físicos: {{ resumen.totales.predicciones_ajustadas.toLocaleString('es-CO') }}.</div>
      </template>
      <template v-else-if="vista==='predicciones'">
        <div class="txreg-grid"><article class="txreg-card txreg-wide"><header><span>DIAGRAMA DE DISPERSIÓN</span><h3>Tiempo objetivo frente a tiempo predicho</h3><p>Cada punto representa un registro muestreado; la diagonal indica predicción perfecta.</p></header>
          <svg viewBox="0 0 500 290" role="img" aria-label="Dispersión de predicciones y valores objetivo" class="txreg-plot"><line x1="48" y1="255" x2="470" y2="255" class="axis"/><line x1="48" y1="255" x2="48" y2="30" class="axis"/><line x1="48" y1="255" x2="457" y2="42" class="ref"/><circle v-for="(p,i) in puntos" :key="i" :cx="p.x" :cy="p.y" r="2.1" class="point"><title>Objetivo: {{ formato(p.real,3) }} min · Predicho: {{ formato(p.predicho,3) }} min</title></circle><text x="257" y="282" text-anchor="middle">Tiempo objetivo (min)</text><text transform="translate(15 155) rotate(-90)" text-anchor="middle">Tiempo predicho (min)</text><text x="48" y="268">0</text><text x="468" y="268" text-anchor="end">{{ formato(limitePuntos,2) }}</text></svg>
          <p class="txreg-interpret">Cuanto más cerca de la diagonal estén los puntos, menor es el error de predicción.</p>
        </article></div>
      </template>
      <template v-else>
        <div class="txreg-grid">
          <article class="txreg-card"><header><span>HISTOGRAMA</span><h3>Distribución de residuos</h3><p>Residuo = tiempo objetivo − tiempo predicho. Barras próximas a cero representan errores menores.</p></header><div class="txreg-hist"><div v-for="(b,i) in resumen.histograma_residuos" :key="i" class="txreg-col" :title="`${formato(b.desde,3)} a ${formato(b.hasta,3)} min · ${b.n} observaciones`"><i :style="{height:`${100*b.n/maxResiduo}%`}"></i><small v-if="i%Math.max(1,Math.ceil(resumen.histograma_residuos.length/5))===0">{{ formato(b.desde,2) }}</small></div></div><p class="txreg-axis-label">Eje X: residuo (min) · Eje Y: número de registros</p></article>
          <article class="txreg-card"><header><span>GRÁFICA DE BARRAS</span><h3>MAE según la hora del día</h3><p>Identifica en qué horas los errores de predicción son mayores.</p></header><div class="txreg-hour"><div v-for="fila in resumen.por_hora" :key="fila.etiqueta" class="txreg-hour-col" :title="`${fila.etiqueta}:00 · MAE ${formato(fila.mae*60,2)} s`"><i :style="{height:`${100*fila.mae/maxMaeHora}%`}"></i><small v-if="Number(fila.etiqueta)%4===0">{{ fila.etiqueta }}</small></div></div><p class="txreg-axis-label">Eje X: hora (0–23) · Eje Y: MAE (min)</p></article>
          <article class="txreg-card txreg-wide"><header><span>GRÁFICA DE BARRAS HORIZONTALES</span><h3>Error absoluto medio por tipo de vía</h3><p>Compara la precisión entre las distintas categorías viales.</p></header><div class="txreg-vias"><div v-for="r in resumen.por_tipo_via" :key="r.etiqueta"><div><span>{{ r.etiqueta }}</span><strong>{{ formato(r.mae*60,2) }} s</strong></div><div class="txreg-track"><i class="txreg-brand" :style="{width:`${100*r.mae/maxMaeVia}%`}"></i></div></div></div></article>
        </div>
        <div class="txreg-foot">Sin tiempos finales negativos. Predicciones crudas no positivas: {{ resumen.totales.predicciones_crudas_no_positivas.toLocaleString('es-CO') }}; ajustadas por límites: {{ resumen.totales.predicciones_ajustadas.toLocaleString('es-CO') }}.</div>
      </template>
    </template>
  </section>
</template>
<style scoped>
.txreg{min-width:0;color:var(--text-primary)}.txreg *{box-sizing:border-box}.txreg-kicker{font:700 10px var(--font-mono);color:var(--accent-brand);letter-spacing:.11em}.txreg-head h2{font:700 clamp(21px,2.3vw,29px) var(--font-ui);margin:5px 0 7px}.txreg-head p:last-child,.txreg-card header p{font-size:12px;color:var(--text-secondary);line-height:1.6}.txreg-tabs{margin:20px 0;display:flex;gap:5px;border-bottom:1px solid var(--border-color);overflow:auto}.txreg-tabs button{border:0;border-bottom:2px solid transparent;background:transparent;color:var(--text-secondary);font-family:var(--font-ui);font-size:12px;font-weight:600;padding:12px 14px;white-space:nowrap;cursor:pointer}.txreg-tabs button:hover{color:var(--text-primary)}.txreg-tabs .txreg-tab-on{border-bottom-color:var(--accent-brand);color:var(--accent-brand)}.txreg-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:16px}.txreg-kpis>div,.txreg-card{background:var(--bg-base);border:1px solid var(--border-color);border-radius:12px;padding:16px;min-width:0}.txreg-kpis>div{display:flex;flex-direction:column;gap:7px}.txreg-kpis span{color:var(--text-secondary);font:700 10px var(--font-mono)}.txreg-kpis strong{font:700 clamp(17px,2vw,25px) var(--font-ui);color:var(--accent-brand);font-variant-numeric:tabular-nums}.txreg-kpis small{font-size:11px;color:var(--text-secondary);line-height:1.5}.txreg-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:13px;align-items:start}.txreg-wide{grid-column:1/-1}.txreg-card header span{color:var(--accent-brand);font:700 10px var(--font-mono);letter-spacing:.08em}.txreg-card h3{font:650 15px var(--font-ui);margin:6px 0}.txreg-bars{display:flex;flex-direction:column;gap:25px;margin:30px 0}.txreg-bar-row>div:first-child,.txreg-vias>div>div:first-child{display:flex;justify-content:space-between;gap:8px;margin-bottom:7px;font-size:12px}.txreg-bar-row strong,.txreg-vias strong{font-family:var(--font-mono);white-space:nowrap}.txreg-track{height:14px;background:var(--bg-surface-active);border-radius:6px;overflow:hidden}.txreg-track i{height:100%;display:block;border-radius:6px}.txreg-brand{background:var(--accent-brand)}.txreg-neutral{background:var(--text-tertiary)}.txreg-interpret{font-size:12px;color:var(--text-secondary);border-top:1px solid var(--border-color);padding-top:12px;line-height:1.6}.txreg-tablewrap{overflow:auto}.txreg table{border-collapse:collapse;width:100%;margin-top:24px;font-size:12px;min-width:300px}.txreg th,.txreg td{text-align:left;border-bottom:1px solid var(--border-color);padding:12px 7px}.txreg th{color:var(--text-secondary)}.txreg td:not(:first-child){font-family:var(--font-mono)}.txreg td:nth-child(2){color:var(--accent-brand)}.txreg-foot{margin-top:15px;font-size:11px;color:var(--text-secondary);line-height:1.6}.txreg-plot{display:block;width:100%;max-height:450px;margin-top:12px}.txreg-plot text{fill:var(--text-secondary);font-size:12px}.txreg-plot .axis{stroke:var(--text-tertiary)}.txreg-plot .ref{stroke:var(--accent-route);stroke-dasharray:6 5;stroke-width:2}.txreg-plot .point{fill:var(--accent-brand);opacity:.57}.txreg-hist,.txreg-hour{height:205px;display:flex;align-items:flex-end;gap:3px;margin:22px 0 8px;overflow:hidden}.txreg-col,.txreg-hour-col{height:100%;flex:1;min-width:0;display:flex;flex-direction:column;justify-content:flex-end;align-items:center}.txreg-col i,.txreg-hour-col i{display:block;width:100%;max-width:23px;background:var(--accent-brand);border-radius:3px 3px 0 0;min-height:1px}.txreg-col small,.txreg-hour-col small{font-size:9px;color:var(--text-secondary);min-height:15px;margin-top:5px}.txreg-axis-label{color:var(--text-secondary);font-size:11px;margin-top:10px}.txreg-vias{display:flex;flex-direction:column;gap:16px;margin-top:21px}.txreg-vias>div{min-width:0}.txreg-message{border:1px solid var(--border-color);border-radius:10px;padding:20px;color:var(--text-secondary);font-size:13px;line-height:1.7}
@media(max-width:1090px){.txreg-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.txreg-grid{grid-template-columns:1fr}.txreg-wide{grid-column:auto}}@media(max-width:480px){.txreg-kpis>div,.txreg-card{padding:12px}.txreg-kpis strong{font-size:18px}}
</style>
