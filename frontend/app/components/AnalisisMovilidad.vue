<script setup lang="ts">
import { ref, computed } from 'vue'
import VistaEDA from './analisis/VistaEDA.vue'
import VistaRegresion from './analisis/VistaRegresion.vue'

type Modulo = 'eda' | 'regresion' | 'clasificacion' | 'agrupamiento'
const activo = ref<Modulo>('eda')
const modulos: { id: Modulo; numero: string; titulo: string; descripcion: string; disponible: boolean }[] = [
  { id: 'eda', numero: '01', titulo: 'Análisis exploratorio', descripcion: 'Datos y movilidad', disponible: true },
  { id: 'regresion', numero: '02', titulo: 'Regresión lineal', descripcion: 'Predicción de tiempos', disponible: true },
  { id: 'clasificacion', numero: '03', titulo: 'Clasificación', descripcion: 'Niveles de congestión', disponible: false },
  { id: 'agrupamiento', numero: '04', titulo: 'Agrupamiento', descripcion: 'Patrones de movilidad', disponible: false },
]
const actual = computed(() => modulos.find(m => m.id === activo.value)!)
</script>

<template>
  <section class="txml" aria-label="Centro de análisis de Taxi IA">
    <header class="txml-heading">
      <div>
        <p class="txml-eyebrow">TAXI IA · CHAPINERO / INTELIGENCIA ARTIFICIAL</p>
        <h2>Centro de análisis</h2>
        <p>Explora los datos y evalúa los modelos de aprendizaje automático sin salir del panel.</p>
      </div>
    </header>

    <div class="txml-layout">
      <nav class="txml-sidebar" aria-label="Secciones de análisis">
        <p class="txml-nav-heading">EXPLORAR MÓDULOS</p>
        <button v-for="modulo in modulos" :key="modulo.id" type="button"
          class="txml-nav-item" :class="{ 'txml-nav-item--active': activo === modulo.id }"
          :aria-current="activo === modulo.id ? 'page' : undefined" @click="activo = modulo.id">
          <span class="txml-nav-num">{{ modulo.numero }}</span>
          <span class="txml-nav-label"><strong>{{ modulo.titulo }}</strong><small>{{ modulo.descripcion }}</small></span>
          <span v-if="!modulo.disponible" class="txml-pending" aria-label="Pendiente de integrar">·</span>
        </button>
        <div class="txml-sidebar-footer">Los resultados de cada modelo se muestran por separado.</div>
      </nav>

      <main class="txml-content">
        <div class="txml-breadcrumb">CENTRO DE ANÁLISIS <span>/</span> {{ actual.titulo.toUpperCase() }}</div>
        <VistaEDA v-if="activo === 'eda'" />
        <VistaRegresion v-else-if="activo === 'regresion'" />
        <section v-else class="txml-placeholder" aria-live="polite">
          <div class="txml-placeholder-icon">{{ actual.numero }}</div>
          <p class="txml-eyebrow">MÓDULO RESERVADO</p>
          <h3>{{ actual.titulo }}</h3>
          <p>{{ activo === 'clasificacion' ? 'Este módulo mostrará la distribución de clases, matriz de confusión y métricas de evaluación cuando el modelo de clasificación esté listo.' : 'Este módulo mostrará los grupos encontrados, sus perfiles de movilidad y las métricas de agrupamiento cuando el modelo esté listo.' }}</p>
          <p class="txml-placeholder-note">Sin resultados cargados. No se muestran métricas de ejemplo.</p>
        </section>
      </main>
    </div>
  </section>
</template>

<style scoped>
.txml{color:var(--text-primary);background:var(--bg-base);font-family:var(--font-body);width:100%;min-width:0}.txml *{box-sizing:border-box}.txml-heading{display:flex;justify-content:space-between;gap:18px;align-items:center;margin-bottom:20px}.txml-eyebrow,.txml-nav-heading,.txml-breadcrumb{color:var(--accent-brand);font-family:var(--font-mono);font-size:10px;font-weight:700;letter-spacing:.10em}.txml-heading h2{font-size:clamp(23px,2.6vw,34px);font-family:var(--font-ui);line-height:1.1;margin:6px 0}.txml-heading p:last-child{color:var(--text-secondary);font-size:13px}.txml-layout{display:grid;grid-template-columns:minmax(208px,22%) minmax(0,1fr);gap:16px;align-items:start}.txml-sidebar{background:var(--bg-surface);border:1px solid var(--border-color);border-radius:var(--radius-md);padding:14px;display:flex;flex-direction:column;gap:7px;position:sticky;top:100px;min-width:0}.txml-nav-heading{color:var(--text-secondary);padding:6px 8px 11px;margin:0}.txml-nav-item{appearance:none;border:1px solid transparent;background:transparent;border-radius:10px;padding:11px 9px;display:flex;gap:10px;text-align:left;align-items:center;cursor:pointer;color:var(--text-primary);font-family:inherit;width:100%;transition:background .15s,border-color .15s}.txml-nav-item:hover{background:var(--bg-surface-hover)}.txml-nav-item--active{background:var(--bg-surface-active);border-color:var(--accent-brand)}.txml-nav-num{font-family:var(--font-mono);font-size:12px;color:var(--accent-brand);font-weight:700;align-self:flex-start}.txml-nav-label{display:flex;flex-direction:column;gap:4px;min-width:0;flex:1}.txml-nav-label strong{font-size:12px;font-weight:650;line-height:1.3}.txml-nav-label small{font-size:11px;color:var(--text-secondary);line-height:1.3}.txml-pending{font-size:22px;color:var(--text-tertiary)}.txml-sidebar-footer{border-top:1px solid var(--border-color);padding:13px 7px 4px;color:var(--text-tertiary);font-size:11px;line-height:1.6}.txml-content{min-width:0;background:var(--bg-surface);border:1px solid var(--border-color);border-radius:var(--radius-md);padding:clamp(14px,2vw,24px)}.txml-breadcrumb{color:var(--text-secondary);margin-bottom:15px}.txml-breadcrumb span{padding:0 7px;color:var(--accent-brand)}.txml-placeholder{min-height:360px;display:flex;flex-direction:column;align-items:flex-start;justify-content:center;gap:10px;padding:25px;background:var(--bg-base);border:1px dashed var(--border-color);border-radius:12px}.txml-placeholder h3{font-size:24px}.txml-placeholder>p:not(.txml-eyebrow){color:var(--text-secondary);max-width:550px;font-size:14px;line-height:1.6}.txml-placeholder-icon{border:1px solid var(--accent-brand);color:var(--accent-brand);padding:15px;border-radius:12px;font-family:var(--font-mono);font-size:23px}.txml-placeholder .txml-placeholder-note{font-size:12px;color:var(--text-tertiary)}
@media(max-width:860px){.txml-layout{grid-template-columns:1fr}.txml-sidebar{position:static;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.txml-nav-heading,.txml-sidebar-footer{grid-column:1/-1}.txml-nav-item{min-width:0}.txml-content{padding:14px}}@media(max-width:440px){.txml-nav-item{padding:9px 5px;gap:5px}.txml-nav-label strong{font-size:11px}.txml-nav-label small{font-size:10px}.txml-nav-num{font-size:10px}}
</style>
