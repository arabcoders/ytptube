import path from "path";

let extraNitro = {}
try {
  const API_URL = process.env.NUXT_API_URL;
  if (API_URL) {
    extraNitro = {
      devProxy: {
        '/api/': {
          target: API_URL,
          changeOrigin: true
        }
      }
    }
  }
}
catch (e) {
}

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
      APP_ENV: process.env.NODE_ENV,
      wss: process.env.NUXT_PUBLIC_WSS ?? '',
      sentry: process.env.NUXT_PUBLIC_SENTRY_DSN ?? '',
    }
  },
  build: {
    transpile: ['vue-toastification'],
  },
  app: {
    baseURL: 'production' == process.env.NODE_ENV ? '' : '/',
    buildAssetsDir: "assets",
    head: {
      "meta": [
        { "charset": "utf-8" },
        { "name": "viewport", "content": "width=device-width, initial-scale=1.0, maximum-scale=1.0" },
        { "name": "theme-color", "content": "#000000" },
      ],
      base: { "href": "/" },
      link: [{ rel: 'icon', type: 'image/x-icon', href: 'favicon.ico?v=100' }]
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
    '@sentry/nuxt/module',
  ],

  nitro: {
    output: {
      publicDir: path.join(__dirname, 'production' === process.env.NODE_ENV ? 'exported' : 'dist')
    },
    ...extraNitro,
  },

  telemetry: false,
  compatibilityDate: "2024-07-13",
})
