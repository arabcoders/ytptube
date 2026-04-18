import { defineNuxtConfig } from 'nuxt/config';

let extraNitro = {};
try {
  const API_URL = process.env.NUXT_API_URL;
  if (API_URL) {
    extraNitro = {
      devProxy: {
        '/api/': {
          target: API_URL,
          changeOrigin: true,
        },
      },
    };
  }
} catch {}

const isProd = 'production' === process.env.NODE_ENV;
export default defineNuxtConfig({
  ssr: false,
  sourcemap: false === isProd,
  devtools: { enabled: true },
  devServer: {
    port: 8082,
    host: '0.0.0.0',
  },
  colorMode: {
    preference: 'dark',
    fallback: 'dark',
    classSuffix: '',
  },
  css: ['~/assets/css/tailwind.css'],
  runtimeConfig: {
    public: {
      APP_ENV: process.env.NODE_ENV,
      wss: process.env.NUXT_PUBLIC_WSS ?? '',
    },
  },
  app: {
    baseURL: 'production' == process.env.NODE_ENV ? '/_base_path/' : '/',
    buildAssetsDir: 'assets',
    head: {
      meta: [
        { charset: 'utf-8' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1.0, maximum-scale=1.0' },
        { name: 'theme-color', content: '#020817' },
        { name: 'mobile-web-app-capable', content: 'yes' },
        { name: 'apple-mobile-web-app-capable', content: 'yes' },
        { name: 'apple-mobile-web-app-status-bar-style', content: 'black-translucent' },
        { name: 'apple-mobile-web-app-title', content: 'YTPTube' },
      ],
      base: { href: '/' },
      link: [
        { rel: 'icon', type: 'image/x-icon', href: 'favicon.ico?v=100' },
        { rel: 'manifest', href: 'manifest.webmanifest?v=100' },
        { rel: 'apple-touch-icon', href: 'images/favicon.png' },
        { rel: 'apple-touch-startup-image', href: 'images/logo.png' },
      ],
    },
    pageTransition: { name: 'page' },
  },
  modules: ['@nuxt/ui', '@pinia/nuxt', '@vueuse/nuxt', '@nuxt/eslint'],
  icon: {
    provider: 'none',
    fallbackToApi: false,
    clientBundle: {
      scan: {
        globInclude: ['app/**/*.{vue,ts,js}', 'node_modules/@nuxt/ui/dist/shared/ui*.mjs'],
        globExclude: ['dist', 'build', 'coverage', 'test', 'tests', '.*'],
      },
    },
  },
  nitro: {
    sourceMap: false === isProd,
    output: {
      publicDir: isProd ? __dirname + '/exported' : __dirname + '/dist',
    },
    ...extraNitro,
  },
  vite: {
    optimizeDeps: {
      include: [
        'moment',
        '@microsoft/fetch-event-source',
        '@xterm/addon-fit',
        '@xterm/xterm',
        'cron-parser',
        'marked',
        'marked-base-url',
        'marked-alert',
        'marked-gfm-heading-id',
      ],
    },
    server: {
      allowedHosts: true,
    },
    build: {
      chunkSizeWarningLimit: 2000,
      rollupOptions: {
        onwarn(warning, warn) {
          if ('SOURCEMAP_BROKEN' === warning.code) {
            return;
          }

          warn(warning);
        },
      },
    },
  },
  telemetry: false,
  compatibilityDate: '2025-08-03',
  experimental: {
    checkOutdatedBuildInterval: 1000 * 60 * 60,
    payloadExtraction: 'client',
  },
  typescript: {
    typeCheck: true,
  },
});
