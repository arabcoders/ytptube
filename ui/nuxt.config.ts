import path from "path";

export default defineNuxtConfig({
  ssr: false,
  devtools: { enabled: false },

  devServer: {
    port: 8082,
    host: "0.0.0.0",
  },
  css: [
    'vue-toastification/dist/index.css'
  ],
  runtimeConfig: {
    public: {
      domain: '/',
      wss: process.env.VUE_APP_BASE_URL ?? '',
      version: '2.0.0',
    }
  },
  build: {
    transpile: ['vue-toastification'],
  },
  app: {
    buildAssetsDir: "assets",
    head: {
      "meta": [
        { "charset": "utf-8" },
        { "name": "viewport", "content": "width=device-width, initial-scale=1.0, maximum-scale=1.0" },
        { "name": "theme-color", "content": "#000000" },
      ],
      link: [{ rel: 'icon', type: 'image/x-icon', href: '/favicon.ico' }]
    },
    pageTransition: { name: 'page', mode: 'out-in' }
  },
  router: {
    options: {
      linkActiveClass: "is-selected",
    }
  },

  modules: [
    '@pinia/nuxt',
    '@vueuse/nuxt',
    'floating-vue/nuxt',
  ],

  nitro: {
    output: {
      publicDir: path.join(__dirname, 'exported')
    }
  },

  telemetry: false,
  compatibilityDate: "2024-07-13",
})
