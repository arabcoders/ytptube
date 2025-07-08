<template>
  <div id="main_container" class="container">
    <nav class="navbar is-mobile is-dark">

      <div class="navbar-brand pl-5">
        <NuxtLink class="navbar-item is-text-overflow" to="/" @click.native="e => changeRoute(e)"
          v-tooltip="socket.isConnected ? 'Connected' : 'Connecting'">
          <span class="is-text-overflow">
            <span class="icon"><i class="fas fa-home" /></span>
            <span class="has-text-bold" :class="`has-text-${socket.isConnected ? 'success' : 'danger'}`">
              YTPTube
            </span>
            <span class="has-text-bold" v-if="config?.app?.instance_title">: {{ config.app.instance_title }}</span>
          </span>
        </NuxtLink>

        <button class="navbar-burger burger" @click="showMenu = !showMenu">
          <span aria-hidden="true"></span>
          <span aria-hidden="true"></span>
          <span aria-hidden="true"></span>
        </button>
      </div>

      <div class="navbar-menu is-unselectable" :class="{ 'is-active': showMenu }">
        <div class="navbar-start" v-if="!config.app.basic_mode">
          <NuxtLink class="navbar-item" to="/browser" @click.native="e => changeRoute(e)"
            v-if="config.app.browser_enabled">
            <span class="icon"><i class="fa-solid fa-folder-tree" /></span>
            <span>Files</span>
          </NuxtLink>

          <NuxtLink class="navbar-item" to="/presets" @click.native="e => changeRoute(e)">
            <span class="icon"><i class="fa-solid fa-sliders" /></span>
            <span>Presets</span>
          </NuxtLink>

          <NuxtLink class="navbar-item" to="/tasks" @click.native="e => changeRoute(e)">
            <span class="icon"><i class="fa-solid fa-tasks" /></span>
            <span>Tasks</span>
          </NuxtLink>

          <NuxtLink class="navbar-item" to="/notifications" @click.native="e => changeRoute(e)">
            <span class="icon-text">
              <span class="icon"><i class="fa-solid fa-paper-plane" /></span>
              <span>Notifications</span>
            </span>
          </NuxtLink>

          <NuxtLink class="navbar-item" to="/conditions" @click.native="e => changeRoute(e)">
            <span class="icon"><i class="fa-solid fa-filter" /></span>
            <span>Conditions</span>
          </NuxtLink>

        </div>
        <div class="navbar-end">
          <div class="navbar-item has-dropdown" v-if="!config.app.basic_mode">
            <a class="navbar-link" @click="e => openMenu(e)">
              <span class="icon"><i class="fas fa-tools" /></span>
              <span>Other</span>
            </a>

            <div class="navbar-dropdown">
              <NuxtLink class="navbar-item" to="/logs" @click.native="e => changeRoute(e)"
                v-if="config.app.file_logging">
                <span class="icon"><i class="fa-solid fa-file-lines" /></span>
                <span>Logs</span>
              </NuxtLink>

              <NuxtLink class="navbar-item" to="/console" @click.native="e => changeRoute(e)"
                v-if="config.app.console_enabled">
                <span class="icon"><i class="fa-solid fa-terminal" /></span>
                <span>Console</span>
              </NuxtLink>
            </div>
          </div>

          <div class="navbar-item is-hidden-mobile" v-if="false === config.app.is_native">
            <button class="button is-dark" @click="reloadPage">
              <span class="icon"><i class="fas fa-refresh" /></span>
            </button>
          </div>
          <div class="navbar-item is-hidden-tablet">
            <button class="button is-dark" @click="reloadPage">
              <span class="icon"><i class="fas fa-refresh" /></span>
              <span>Reload</span>
            </button>
          </div>

          <NotifyDropdown />

          <div class="navbar-item is-hidden-mobile">
            <button class="button is-dark has-tooltip-bottom mr-4" v-tooltip.bottom="'WebUI Settings'"
              @click="show_settings = !show_settings">
              <span class="icon"><i class="fas fa-cog" /></span>
            </button>
          </div>
          <div class="navbar-item is-hidden-tablet">
            <button class="button is-dark" @click="show_settings = !show_settings">
              <span class="icon"><i class="fas fa-cog" /></span>
              <span>WebUI Settings</span>
            </button>
          </div>

        </div>
      </div>
    </nav>

    <div>
      <Settings v-if="show_settings" :isLoading="loadingImage" @reload_bg="() => loadImage(true)" />
      <NuxtLoadingIndicator />
      <NuxtPage />
    </div>

    <div class="columns mt-3 is-mobile">
      <div class="column is-8-mobile">
        <div class="has-text-left" v-if="config.app?.app_version">
          © {{ Year }} - <NuxtLink href="https://github.com/ArabCoders/ytptube" target="_blank">YTPTube</NuxtLink>
          <span class="is-hidden-mobile has-tooltip"
            v-tooltip="`Build Date: ${config.app?.app_build_date}, Branch: ${config.app?.app_branch}, commit: ${config.app?.app_commit_sha}`">
            &nbsp;({{ config?.app?.app_version || 'unknown' }})</span>
          - <NuxtLink target="_blank" href="https://github.com/yt-dlp/yt-dlp">yt-dlp</NuxtLink>
          <span class="is-hidden-mobile">&nbsp;({{ config?.app?.ytdlp_version || 'unknown' }})</span>
          - <NuxtLink to="/changelog">CHANGELOG</NuxtLink>
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
import * as Sentry from '@sentry/nuxt'

const Year = new Date().getFullYear()
const selectedTheme = useStorage('theme', 'auto')
const socket = useSocketStore()
const config = useConfigStore()
const loadedImage = ref()
const show_settings = ref(false)
const loadingImage = ref(false)
const bg_enable = useStorage('random_bg', true)
const bg_opacity = useStorage('random_bg_opacity', 0.95)
const showMenu = ref(false)

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
  } catch (e) {
  }

  try {
    applyPreferredColorScheme(selectedTheme.value)
  } catch (e) {
  }
})

watch(selectedTheme, value => {
  try {
    if ('auto' === value) {
      applyPreferredColorScheme(window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
      return
    }
    applyPreferredColorScheme(value)
  } catch (e) { }
})

const reloadPage = () => window.location.reload()

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

  const html = document.documentElement
  const body = document.querySelector('body')

  const style = {
    "background-color": "unset",
    "display": 'block',
    "min-height": '100%',
    "min-width": '100%',
    "background-image": `url(${loadedImage.value})`,
  }

  html.setAttribute("style", Object.keys(style).map(k => `${k}: ${style[k]}`).join('; ').trim())
  html.classList.add('bg-fanart')
  body.setAttribute("style", `opacity: ${bg_opacity.value}`)
})

const handleImage = async enabled => {
  if (false === enabled) {
    if (!loadedImage.value) {
      return
    }

    const html = document.documentElement
    const body = document.querySelector('body')

    if (html.getAttribute("style")) {
      html.removeAttribute("style")
    }
    if (body.getAttribute("style")) {
      body.removeAttribute("style")
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

const changeRoute = async (_, callback) => {
  showMenu.value = false
  document.querySelectorAll('div.has-dropdown').forEach(el => el.classList.remove('is-active'))
  if (callback) {
    callback()
  }
}

const openMenu = e => {
  const elm = e.target.closest('div.has-dropdown')

  document.querySelectorAll('div.has-dropdown').forEach(el => {
    if (el !== elm) {
      el.classList.remove('is-active')
    }
  })

  e.target.closest('div.has-dropdown').classList.toggle('is-active')
}
</script>
