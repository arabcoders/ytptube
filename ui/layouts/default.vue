<template>
  <div id="main_container" class="container">
    <nav class="navbar is-mobile is-dark">
      <div class="navbar-brand pl-5 is-hidden-mobile">
        <NuxtLink class="navbar-item  has-tooltip-bottom" to="/"
          v-tooltip="socket.isConnected ? 'Connected' : 'Connecting'">
          <span>
            <span class="icon"><i class="fas fa-home" /></span>
            <span class="has-text-bold" :class="`has-text-${socket.isConnected ? 'success' : 'danger'}`">
              YTPTube
            </span>
            <span v-if="config?.app?.instance_title">: {{ config.app.instance_title }}</span>
          </span>
        </NuxtLink>
      </div>

      <div class="navbar-end is-flex" style="flex-flow:wrap">

        <div class="navbar-item is-hidden-tablet">
          <NuxtLink class="button is-dark has-tooltip-bottom" to="/">
            <span :class="socket.isConnected ? 'has-text-success' : 'has-text-danger'" class="icon">
              <img src="/favicon.ico" /></span>
          </NuxtLink>
        </div>

        <div class="navbar-item" v-if="!config.app.basic_mode">
          <NuxtLink class="button is-dark has-tooltip-bottom" to="/presets">
            <span class="icon-text">
              <span class="icon"><i class="fa-solid fa-sliders" /></span>
              <span class="is-hidden-mobile">Presets</span>
            </span>
          </NuxtLink>
        </div>

        <div class="navbar-item" v-if="!config.app.basic_mode && config.app.console_enabled">
          <NuxtLink class="button is-dark has-tooltip-bottom" to="/console">
            <span class="icon-text">
              <span class="icon"><i class="fa-solid fa-terminal" /></span>
              <span class="is-hidden-mobile">Terminal</span>
            </span>
          </NuxtLink>
        </div>

        <div class="navbar-item" v-if="!config.app.basic_mode">
          <NuxtLink class="button is-dark has-tooltip-bottom" to="/tasks">
            <span class="icon-text">
              <span class="icon"><i class="fa-solid fa-tasks" /></span>
              <span class="is-hidden-mobile">Tasks</span>
            </span>
          </NuxtLink>
        </div>

        <div class="navbar-item" v-if="!config.app.basic_mode" v-tooltip.bottom="'Notifications'">
          <NuxtLink class="button is-dark has-tooltip-bottom" to="/notifications">
            <span class="icon-text">
              <span class="icon"><i class="fa-solid fa-paper-plane" /></span>
              <span class="is-hidden-mobile">Notifications</span>
            </span>
          </NuxtLink>
        </div>

        <div class="navbar-item">
          <button class="button is-dark has-tooltip-bottom" v-tooltip.bottom="'Switch to Light theme'"
            v-if="'auto' == selectedTheme" @click="selectTheme('light')">
            <span class="icon has-text-warning"><i class="fas fa-sun" /></span>
          </button>
          <button class="button is-dark has-tooltip-bottom" v-tooltip.bottom="'Switch to Dark theme'"
            v-if="'light' == selectedTheme" @click="selectTheme('dark')">
            <span class="icon"><i class="fas fa-moon" /></span>
          </button>
          <button class="button is-dark has-tooltip-bottom" v-tooltip.bottom="'Switch to auto theme'"
            v-if="'dark' == selectedTheme" @click="selectTheme('auto')">
            <span class="icon"><i class="fas fa-microchip" /></span>
          </button>
        </div>

        <div class="navbar-item is-hidden-mobile">
          <button class="button is-dark" @click="reloadPage">
            <span class="icon"><i class="fas fa-refresh"></i></span>
          </button>
        </div>

        <div class="navbar-item">
          <button class="button is-dark has-tooltip-bottom" v-tooltip.bottom="'WebUI Settings'"
            @click="show_settings = !show_settings">
            <span class="icon"><i class="fas fa-cog" /></span>
          </button>
        </div>

      </div>
    </nav>

    <div>
      <Settings v-if="show_settings" :isLoading="loadingImage" @reload_bg="() => loadImage(true)" />
      <NuxtPage />
    </div>

    <div class="columns mt-3 is-mobile">
      <div class="column is-8-mobile">
        <div class="has-text-left" v-if="config.app?.version">
          © {{ Year }} - <NuxtLink href="https://github.com/ArabCoders/ytptube" target="_blank">YTPTube</NuxtLink>
          <span class="is-hidden-mobile">&nbsp;({{ config?.app?.version || 'unknown' }})</span>
          - <NuxtLink target="_blank" href="https://github.com/yt-dlp/yt-dlp">yt-dlp</NuxtLink>
          <span class="is-hidden-mobile">&nbsp;({{ config?.app?.ytdlp_version || 'unknown' }})</span>
          - <NuxtLink :to="`/changeslog?version=${config?.app?.version || 'unknown'}`">CHANGELOG</NuxtLink>
        </div>
      </div>
      <div class="column is-4-mobile" v-if="config.app?.started">
        <div class="has-text-right">
          <span class="user-hint"
            v-tooltip="'App Started: ' + moment.unix(config.app?.started).format('YYYY-M-DD H:mm Z')">
            {{ moment.unix(config.app?.started).fromNow() }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import 'assets/css/bulma.css'
import 'assets/css/style.css'
import 'assets/css/all.css'
import { useStorage } from '@vueuse/core'
import moment from 'moment'
import * as Sentry from "@sentry/nuxt";

const Year = new Date().getFullYear()
const selectedTheme = useStorage('theme', 'auto')
const socket = useSocketStore()
const config = useConfigStore()
const loadedImage = ref()
const show_settings = ref(false)
const loadingImage = ref(false)
const bg_enable = useStorage('random_bg', true)
const bg_opacity = useStorage('random_bg_opacity', 0.85)

const applyPreferredColorScheme = scheme => {
  if (!scheme || 'auto' === scheme) {
    return
  }

  for (let s = 0; s < document.styleSheets.length; s++) {
    for (let i = 0; i < document.styleSheets[s].cssRules.length; i++) {
      try {
        const rule = document.styleSheets[s].cssRules[i]
        if (rule && rule.media && rule.media.mediaText.includes("prefers-color-scheme")) {
          switch (scheme) {
            case "light":
              rule.media.appendMedium("original-prefers-color-scheme")
              if (rule.media.mediaText.includes("light")) {
                rule.media.deleteMedium("(prefers-color-scheme: light)")
              }
              if (rule.media.mediaText.includes("dark")) {
                rule.media.deleteMedium("(prefers-color-scheme: dark)")
              }
              break
            case "dark":
              rule.media.appendMedium("(prefers-color-scheme: light)")
              rule.media.appendMedium("(prefers-color-scheme: dark)")
              if (rule.media.mediaText.includes("original")) {
                rule.media.deleteMedium("original-prefers-color-scheme")
              }
              break
            default:
              rule.media.appendMedium("(prefers-color-scheme: dark)")
              if (rule.media.mediaText.includes("light")) {
                rule.media.deleteMedium("(prefers-color-scheme: light)")
              }
              if (rule.media.mediaText.includes("original")) {
                rule.media.deleteMedium("original-prefers-color-scheme")
              }
              break
          }
        }
      } catch (e) {
        console.debug(e)
      }
    }
  }
}

watch(() => config.app.sentry_dsn, dsn => {
  if (!dsn) {
    return
  }
  console.warn('Loading sentry module.')
  Sentry.init({ dsn: dsn })
})

onMounted(async () => {
  try {
    await handleImage(bg_enable.value)
    applyPreferredColorScheme(selectedTheme.value)
  } catch (e) {
  }
})

watch(selectedTheme, value => {
  try {
    applyPreferredColorScheme(value)
  } catch (e) { }
})

const reloadPage = () => window.location.reload()

const selectTheme = theme => {
  selectedTheme.value = theme
  if ('auto' === theme) {
    return reloadPage()
  }
}

watch(bg_enable, async v => await handleImage(v))
watch(bg_opacity, v => {
  if (false === bg_enable.value) {
    return
  }
  document.querySelector('body').setAttribute("style", `opacity: ${v}`)
})

watch(loadedImage, v => {
  if (false === bg_enable.value) {
    return
  }

  const html = document.documentElement;
  const body = document.querySelector('body');

  const style = {
    "background-color": "unset",
    "display": 'block',
    "min-height": '100%',
    "min-width": '100%',
    "background-image": `url(${loadedImage.value})`,
  }

  html.setAttribute("style", Object.keys(style).map(k => `${k}: ${style[k]}`).join('; ').trim())
  html.classList.add('bg-fanart')
  body.setAttribute("style", `opacity: ${bg_opacity.value}`);
})

const handleImage = async enabled => {
  if (false === enabled) {
    if (!loadedImage.value) {
      return
    }

    const html = document.documentElement;
    const body = document.querySelector('body');

    if (html.getAttribute("style")) {
      html.removeAttribute("style");
    }
    if (body.getAttribute("style")) {
      body.removeAttribute("style");
    }
    loadedImage.value = ''
    return
  }

  if (loadedImage.value) {
    return
  }

  await loadImage()
}

const loadImage = async (force = false) => {
  if (loadingImage.value) {
    return
  }

  try {
    loadingImage.value = true

    let url = '/api/random/background'
    if (force) {
      url += '?force=true'
    }

    const imgRequest = await request(url)
    if (200 !== imgRequest.status) {
      return
    }

    loadedImage.value = URL.createObjectURL(await imgRequest.blob())
  } catch (e) {
    console.error(e)
  } finally {
    loadingImage.value = false
  }
}

</script>
