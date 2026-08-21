import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { defineNuxtConfig } from 'nuxt/config';

const faviconHash = createHash('sha256')
  .update(readFileSync(new URL('./public/favicon.ico', import.meta.url)))
  .digest('hex')
  .slice(0, 12);

const appleIconHash = createHash('sha256')
  .update(readFileSync(new URL('./public/images/favicon.png', import.meta.url)))
  .digest('hex')
  .slice(0, 12);

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
const baseURL = isProd ? '/_base_path/' : '/';
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
    baseURL,
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
        { rel: 'icon', type: 'image/x-icon', href: `favicon.ico?v=${faviconHash}` },
        { rel: 'manifest', href: 'manifest.webmanifest?v=100' },
        { rel: 'apple-touch-icon', sizes: '1024x1024', href: `apple-touch-icon.${appleIconHash}.png` },
        { rel: 'apple-touch-startup-image', href: 'images/logo.png' },
      ],
    },
    pageTransition: { name: 'page', mode: 'out-in' },
  },
  modules: ['./modules/icon-catalog', '@nuxt/ui', '@vueuse/nuxt', '@nuxt/eslint', '@nuxtjs/i18n'],

  i18n: {
    compilation: {
      strictMessage: false,
    },
    strategy: 'no_prefix',
    defaultLocale: 'en',
    langDir: 'locales',

    locales: [
      {
        code: 'en',
        name: 'English',
        language: 'en',
        file: 'en.json',
        dir: 'ltr',
      },
      {
        code: 'ar',
        name: 'العربية',
        language: 'ar',
        file: 'ar.json',
        dir: 'rtl',
      },
      {
        code: 'fr',
        name: 'Français',
        language: 'fr',
        file: 'fr.json',
        dir: 'ltr',
      },
      {
        code: 'zh',
        name: '中文',
        language: 'zh',
        file: 'zh.json',
        dir: 'ltr',
      },
      {
        code: 'ja',
        name: '日本語',
        language: 'ja',
        file: 'ja.json',
        dir: 'ltr',
      },
    ],

    detectBrowserLanguage: {
      useCookie: true,
      cookieKey: 'ytptube_locale',
      redirectOn: 'root',
      fallbackLocale: 'en',
    },
  },
  icon: {
    provider: 'none',
    fallbackToApi: false,
    clientBundle: {
      scan: {
        globInclude: ['app/**/*.{vue,ts,js}', 'node_modules/@nuxt/ui/dist/shared/ui*.mjs'],
        globExclude: [
          'dist',
          'build',
          'coverage',
          'test',
          'tests',
          '.*',
          'app/utils/generatedIconCatalog.ts',
        ],
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
        '@microsoft/fetch-event-source',
        '@xterm/addon-fit',
        '@xterm/xterm',
        'cron-parser',
        'marked',
        'marked-base-url',
        'marked-alert',
        'marked-gfm-heading-id',
        'hls.js',
        'assjs',
        '@vue/devtools-core',
        '@vue/devtools-kit',
      ],
    },
    server: {
      allowedHosts: true,
    },
    build: {
      chunkSizeWarningLimit: 550,
      rollupOptions: {
        onwarn(warning, warn) {
          if ('SOURCEMAP_BROKEN' === warning.code || 'PLUGIN_TIMINGS' === warning.code) {
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
    defaults: {
      nuxtLink: {
        prefetchOn: {
          interaction: true,
          visibility: false,
        },
      },
    },
  },
  typescript: {
    typeCheck: true,
  },
});
