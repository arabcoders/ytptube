<template>
  <div id="main_container" class="container" :class="{ 'is-max-fullwidth': expandContainer }">
    <nav class="navbar is-dark mb-5">
      <div class="navbar-brand pl-5">
        <NuxtLink class="navbar-item" to="/">
          <span class="icon-text">
            <span class="icon"><i class="fas fa-home"></i></span>
            <span>Home</span>
          </span>
        </NuxtLink>

        <a class="navbar-item is-hidden-tablet" id="top" href="#bottom">
          <span class="icon"><i class="fas fa-arrow-down"></i></span>
        </a>

        <button class="navbar-burger burger" @click="showMenu = !showMenu">
          <span aria-hidden="true"></span>
          <span aria-hidden="true"></span>
          <span aria-hidden="true"></span>
        </button>
      </div>

      <div class="navbar-menu is-unselectable" :class="{ 'is-active': showMenu }">
        <div class="navbar-end pr-3">

          <div class="navbar-item">
            <button v-tooltip.bottom="'Toggle Console'" class="button is-dark has-tooltip-bottom"
              @click="config.showConsole = !config.showConsole">
              <span class="icon">
                <i class="fa-solid fa-terminal" />
              </span>
              <span class="is-hidden-mobile">Console</span>
            </button>
          </div>

          <div class="navbar-item">
            <button v-tooltip.bottom="'Toggle Add Form'" class="button is-dark has-tooltip-bottom"
            @click="config.showForm = !config.showForm">
              <span class="icon"><i class="fa-solid fa-plus" /></span>
              <span class="is-hidden-mobile">Add</span>
            </button>
          </div>

          <div class="navbar-item" v-if="config.tasks.length > 0">
            <button v-tooltip.bottom="'Toggle Tasks'" class="button is-dark has-tooltip-bottom"
              @click="config.showTasks = !config.showTasks">
              <span class="icon">
                <i class="fa-solid fa-tasks" />
              </span>
              <span class="is-hidden-mobile">Tasks</span>
            </button>
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
      </div>
    </nav>

    <NuxtPage />

    <div class="columns is-multiline is-mobile mt-3">
      <div class="column is-12 is-hidden-tablet has-text-centered">
        <a href="#top" id="bottom" class="button">
          <span class="icon"><i class="fas fa-arrow-up"></i>&nbsp;</span>
          <span>Go to Top</span>
        </a>
      </div>
      <div class="column is-6 is-9-mobile has-text-left"></div>
      <div class="column is-6 is-4-mobile has-text-right">
        v{{ VERSION }}
      </div>
    </div>

    <NuxtNotifications position="top right" :speed="800" :ignoreDuplicates="true" :width="340" :pauseOnHover="true" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import 'assets/css/bulma.css'
import 'assets/css/style.css'
import 'assets/css/all.css'
import { useStorage } from '@vueuse/core'
import { useConfigStore } from '~/store/ConfigStore'

const runtimeConfig = useRuntimeConfig()
const config = useConfigStore()
const selectedTheme = useStorage('theme', (() => window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')())
const showMenu = ref(false)
const VERSION = ref(runtimeConfig.public.version)
const expandContainer = ref(false)
const bus = useEventBus('show_form')

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
const toggleForm = () => {
  console.log('emitting show_form');
  bus.emit('show_form', { foo: 'bar' })
  dEvent('show_form', { foo: 'bar' })
}
</script>
