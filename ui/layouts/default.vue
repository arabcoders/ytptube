<template>
  <div id="main_container" class="container">
    <nav class="navbar is-mobile is-dark">
      <div class="navbar-brand pl-5 is-hidden-mobile">
        <NuxtLink class="navbar-item  has-tooltip-bottom" to="/"
          v-tooltip="socket.isConnected ? 'Connected' : 'Connecting'">
          <span>
            <span class="icon"> <i class="fas fa-home" /></span>
            <span :class="socket.isConnected ? 'has-text-success' : 'has-text-danger'">
              <b>YTPTube</b>
            </span>
            <span v-if="config?.app?.instance_title">: {{ config.app.instance_title }}</span>
          </span>
        </NuxtLink>
      </div>

      <div class="navbar-end is-flex" style="flex-flow:wrap">

        <div class="navbar-item is-hidden-tablet">
          <NuxtLink class="button is-dark has-tooltip-bottom" to="/" v-tooltip.bottom="'Downloads'">
            <span :class="socket.isConnected ? 'has-text-success' : 'has-text-danger'" class="icon"><i
                class="fa-solid fa-home" /></span>
          </NuxtLink>
        </div>

        <div class="navbar-item" v-if="!config.app.basic_mode">
          <NuxtLink class="button is-dark has-tooltip-bottom" to="/console" v-tooltip.bottom="'Terminal'">
            <span class="icon"><i class="fa-solid fa-terminal" /></span>
          </NuxtLink>
        </div>

        <div class="navbar-item" v-if="!config.app.basic_mode" v-tooltip.bottom="'Tasks'">
          <NuxtLink class="button is-dark has-tooltip-bottom" to="/tasks">
            <span class="icon"><i class="fa-solid fa-tasks" /></span>
          </NuxtLink>
        </div>

        <div class="navbar-item" v-if="!config.app.basic_mode" v-tooltip.bottom="'Notifications'">
          <NuxtLink class="button is-dark has-tooltip-bottom" to="/notifications">
            <span class="icon"><i class="fa-solid fa-paper-plane" /></span>
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

        <div class="navbar-item">
          <button class="button is-dark" @click="reloadPage">
            <span class="icon"><i class="fas fa-refresh"></i></span>
          </button>
        </div>
      </div>
    </nav>

    <NuxtPage />

    <div class="columns mt-3 is-mobile">
      <div class="column is-8-mobile">
        <div class="has-text-left" v-if="config.app?.version">
          © {{ Year }} - <NuxtLink href="https://github.com/ArabCoders/ytptube" target="_blank">YTPTube</NuxtLink>
          <span class="is-hidden-mobile">&nbsp;({{ config?.app?.version || 'unknown' }})</span>
          - <NuxtLink target="_blank" href="https://github.com/yt-dlp/yt-dlp">yt-dlp</NuxtLink>
          <span class="is-hidden-mobile">&nbsp;({{ config?.app?.ytdlp_version || 'unknown' }})</span>
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

const Year = new Date().getFullYear()
const selectedTheme = useStorage('theme', 'auto')
const socket = useSocketStore()
const config = useConfigStore()

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

onMounted(async () => {
  try {
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
</script>
