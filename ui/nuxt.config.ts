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
catch { }

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
      wss: process.env.NUXT_PUBLIC_WSS ?? ''
    }
  },
  build: {
    transpile: ['vue-toastification'],
  },
  app: {
    baseURL: 'production' == process.env.NODE_ENV ? '/_base_path/' : '/',
    buildAssetsDir: "assets",
    head: {
      "meta": [
        { "charset": "utf-8" },
        { "name": "viewport", "content": "width=device-width, initial-scale=1.0, maximum-scale=1.0" },
        { "name": "theme-color", "content": "#000000" },
        { "name": "mobile-web-app-capable", "content": "yes" },
        { "name": "apple-mobile-web-app-capable", "content": "yes" },
        { "name": "apple-mobile-web-app-status-bar-style", "content": "black-translucent" },
        { "name": "apple-mobile-web-app-title", "content": "YTPTube" },
      ],
      base: { "href": "/" },
      link: [
        { rel: 'icon', type: 'image/x-icon', href: 'favicon.ico?v=100' },
        { rel: 'manifest', href: 'manifest.webmanifest?v=100' },
        { rel: 'apple-touch-icon', href: 'images/favicon.png' },
        { rel: 'apple-touch-startup-image', href: 'images/logo.png' }
      ]
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
    'development' === process.env.NODE_ENV ? '@nuxt/eslint' : '',
  ].filter(Boolean),

  nitro: {
    output: {
      publicDir: path.join(__dirname, 'production' === process.env.NODE_ENV ? 'exported' : 'dist')
    },
    ...extraNitro,
  },
  vite: {
    server: {
      allowedHosts: true,
    },
    build: {
      chunkSizeWarningLimit: 2000,
    }
  },
  telemetry: false,
  compatibilityDate: "2025-08-03",
  experimental: {
    checkOutdatedBuildInterval: 1000 * 60 * 10,
  }
})
