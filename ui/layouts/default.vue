<template>
  <div id="main_container" class="container">
    <nav class="navbar is-mobile is-dark">
      <div class="navbar-brand pl-5">
        <NuxtLink class="navbar-item  has-tooltip-bottom" to="/"
          v-tooltip="socket.isConnected ? 'Connected' : 'Connecting'">
          <span class="icon-text">
            <span class="icon"><i class="fas fa-home"></i></span>
            <span :class="socket.isConnected ? 'has-text-success' : 'has-text-danger'"><b>YTPTube</b></span>
          </span>
        </NuxtLink>
      </div>
      <div class="navbar-end is-flex">
        <div class="navbar-item">
          <NuxtLink class="button is-dark has-tooltip-bottom" to="/console">
            <span class="icon-text">
              <span class="icon"><i class="fa-solid fa-terminal" /></span>
              <span>Terminal</span>
            </span>
          </NuxtLink>
        </div>

        <div class="navbar-item">
          <button v-tooltip.bottom="'Toggle Add Form'" class="button is-dark has-tooltip-bottom"
            @click="config.showForm = !config.showForm">
            <span class="icon-text">
              <span class="icon"><i class="fa-solid fa-plus" /></span>
              <span>Add</span>
            </span>
          </button>
        </div>

        <div class="navbar-item" v-if="config.tasks.length > 0">
          <NuxtLink class="button is-dark has-tooltip-bottom" to="/tasks">
            <span class="icon"><i class="fa-solid fa-tasks" /></span>
            <span class="is-hidden-mobile">Tasks</span>
          </NuxtLink>
        </div>

        <div class="navbar-item">
          <button class="button is-dark" @click="selectedTheme = 'light'" v-if="'dark' === selectedTheme"
            v-tooltip="'Switch to light theme'">
            <span class="icon has-text-warning"><i class="fas fa-sun"></i></span>
          </button>
          <button class="button is-dark" @click="selectedTheme = 'dark'" v-if="'light' === selectedTheme"
            v-tooltip="'Switch to dark theme'">
            <span class="icon"><i class="fas fa-moon"></i></span>
          </button>
        </div>

        <div class="navbar-item">
          <button class="button is-dark" @click="reloadPage">
            <span class="icon"><i class="fas fa-refresh"></i></span>
          </button>
        </div>
      </div>
    </nav>

    <NewDownload v-if="config.showForm" />
    <NuxtPage />

    <div class="columns mt-3 is-mobile">
      <div class="column is-8-mobile">
        <div class="has-text-left" v-if="config.app?.version">
          © {{ Year }} - <NuxtLink href="https://github.com/ArabCoders/ytptube" target="_blank">YTPTube</NuxtLink>
          <span class="is-hidden-mobile">&nbsp;({{ config.app?.version || 'unknown' }})</span>
          - <NuxtLink target="_blank" href="https://github.com/yt-dlp/yt-dlp">yt-dlp</NuxtLink>
          <span class="is-hidden-mobile">&nbsp;({{ config?.app.ytdlp_version || 'unknown' }})</span>
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
import moment from "moment";

const Year = new Date().getFullYear()
const selectedTheme = useStorage('theme', (() => window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')())
const socket = useSocketStore()
const config = useConfigStore()

const applyPreferredColorScheme = scheme => {
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
    if (config.app.ui_update_title) {
      const s = useStateStore()
      useHead({ title: `YTPTube: ( ${Object.keys(s.queue).length || 0} | ${Object.keys(s.history).length || 0} )` })
      watch([s.queue, s.history], () => {
        const title = `YTPTube: ( ${Object.keys(s.queue).length || 0} | ${Object.keys(s.history).length || 0} )`
        useHead({ title })
      }, { deep: true })
    }
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
</script>
