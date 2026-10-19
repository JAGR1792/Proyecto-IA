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
      title: 'Taxi IA Chapinero - Planificación Inteligente de Rutas',
      meta: [
        { name: 'description', content: 'Sistema Inteligente para Planificación de Rutas de Taxis en la zona de estudio de Chapinero (Bogotá)' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
      ],
      link: [
        { rel: 'icon', type: 'image/x-icon', href: '/favicon.ico' },
      ],
    },
  },

  runtimeConfig: {
    public: {
      // URL relativa: en desarrollo Nitro la redirige al backend local (devProxy)
      // y en producción Vercel la reescribe al servicio backend (ver vercel.json).
      apiBase: process.env.NUXT_PUBLIC_API_BASE || '/api/v1',
    },
  },

  // Proxy solo para `nuxt dev`: evita CORS y que /api/v1 caiga en el router SPA.
  nitro: {
    devProxy: {
      '/api/v1': {
        target: 'http://localhost:8000/api/v1',
        changeOrigin: true,
      },
    },
  },

  vite: {
    server: {
      watch: {
        // Evita que los guardados atómicos de algunos editores (archivos
        // temporales .tmpdir/.tmp) reinicien o tumben el dev server en Windows.
        ignored: ['**/*.tmpdir/**', '**/*.tmp'],
      },
    },
    optimizeDeps: {
      include: ['cytoscape', 'cytoscape-cose-bilkent', 'cytoscape-dagre', 'leaflet'],
    },
  },

  typescript: {
    strict: true,
    typeCheck: false,
  },
})