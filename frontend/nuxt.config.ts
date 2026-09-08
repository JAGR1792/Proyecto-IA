// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },

  modules: [
    '@nuxtjs/tailwindcss',
  ],

  css: [
    '~/assets/css/main.css',
    'leaflet/dist/leaflet.css',
  ],

  app: {
    head: {
      title: 'TransMilenio IA - Planificación Inteligente de Rutas',
      meta: [
        { name: 'description', content: 'Sistema Inteligente para Planificación de Rutas y Análisis de Movilidad en TransMilenio' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
      ],
      link: [
        { rel: 'icon', type: 'image/x-icon', href: '/favicon.ico' },
      ],
    },
  },

  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || 'http://localhost:8000/api/v1',
    },
  },

  vite: {
    optimizeDeps: {
      include: ['cytoscape', 'cytoscape-cose-bilkent', 'cytoscape-dagre', 'leaflet'],
    },
  },

  typescript: {
    strict: true,
    typeCheck: false,
  },
})