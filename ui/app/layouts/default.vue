<template>

  <template v-if="simpleMode">
    <Connection :status="socket.connectionStatus" @reconnect="() => socket.reconnect()" />
    <Simple @show_settings="() => show_settings = true" />
  </template>


  <template v-if="show_settings">
    <Modal @close="closeSettings()"
           :content-class="isMobile ? 'modal-content-max is-overflow-scroll ' : 'modal-content-max'">
      <div class="columns is-multiline">
        <div class="column is-12 mt-2">
          <div class="card">
            <header class="card-header">
              <p class="card-header-title">WebUI Settings</p>
              <span class="card-header-icon">
            <span class="icon"><i class="fas fa-cog" /></span>
          </span>
            </header>
            <div class="card-content">
              <div class="columns is-multiline">
                <div class="column is-6">
                    <settings v-if="show_settings" :isLoading="loadingImage" @reload_bg="() => loadImage(true)" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Modal>
  </template>

  <template v-if="!simpleMode">
    <Shutdown v-if="app_shutdown" />
    <div id="main_container" class="container" v-else>
      <NewVersion v-if="newVersionIsAvailable" />
      <Connection :status="socket.connectionStatus" @reconnect="() => socket.reconnect()" />
      <nav class="navbar is-mobile is-dark">

        <div class="navbar-brand pl-5">
          <NuxtLink class="navbar-item is-text-overflow" to="/" @click.prevent="(e: MouseEvent) => changeRoute(e)"
            v-tooltip="socket.isConnected ? 'Connected' : 'Connecting'">
            <span class="is-text-overflow">
              <span class="icon" v-if="'connecting' === socket.connectionStatus" >
                <i class="fas fa-arrows-rotate fa-spin" />
              </span>
              <span class="has-text-bold" :class="connectionStatusColor">
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
          <div class="navbar-start">

            <NuxtLink class="navbar-item" to="/" @click.prevent="(e: MouseEvent) => changeRoute(e)">
              <span class="icon"><i class="fa-solid fa-home" /></span>
              <span>Home</span>
            </NuxtLink>

            <NuxtLink class="navbar-item" to="/browser" @click.prevent="(e: MouseEvent) => changeRoute(e)">
              <span class="icon"><i class="fa-solid fa-folder-tree" /></span>
              <span>Files</span>
            </NuxtLink>

            <NuxtLink class="navbar-item" to="/presets" @click.prevent="(e: MouseEvent) => changeRoute(e)">
              <span class="icon"><i class="fa-solid fa-sliders" /></span>
              <span>Presets</span>
            </NuxtLink>

            <NuxtLink class="navbar-item" to="/tasks" @click.prevent="(e: MouseEvent) => changeRoute(e)">
              <span class="icon"><i class="fa-solid fa-tasks" /></span>
              <span>Tasks</span>
            </NuxtLink>

            <NuxtLink class="navbar-item" to="/task_definitions" @click.prevent="(e: MouseEvent) => changeRoute(e)">
              <span class="icon"><i class="fa-solid fa-diagram-project" /></span>
              <span>Website Scraper</span>
            </NuxtLink>

            <NuxtLink class="navbar-item" to="/notifications" @click.prevent="(e: MouseEvent) => changeRoute(e)">
              <span class="icon-text">
                <span class="icon"><i class="fa-solid fa-paper-plane" /></span>
                <span>Notifications</span>
              </span>
            </NuxtLink>

            <NuxtLink class="navbar-item" to="/conditions" @click.prevent="(e: MouseEvent) => changeRoute(e)">
              <span class="icon"><i class="fa-solid fa-filter" /></span>
              <span>Conditions</span>
            </NuxtLink>

          </div>
          <div class="navbar-end">
            <div class="navbar-item" v-if="true === config.app.is_native">
              <button class="button is-dark" @click="shutdownApp">
                <span class="icon"><i class="fas fa-power-off" /></span>
                <span v-if="isMobile">Shutdown</span>
              </button>
            </div>
            <NuxtLink class="navbar-item" to="/settings" @click.prevent="(e: MouseEvent) => changeRoute(e)">
              <span class="icon"><i class="fa-solid fa-cog" /></span>
              <span>Settings</span>
            </NuxtLink>
            <NotifyDropdown />
          </div>
        </div>
      </nav>
      <div>
        <NuxtLoadingIndicator />
        <NuxtPage v-if="config.is_loaded" />
        <Message v-if="!config.is_loaded" class="has-background-info-90 has-text-dark mt-5"
          title="Loading Configuration" icon="fas fa-spinner fa-spin">
          <p>Loading application configuration. This usually takes less than a second.</p>
          <p v-if="!socket.isConnected" class="mt-2">
            If this is taking too long, please check that the backend server is running and that the WebSocket
            connection is functional.
          </p>
        </Message>
        <Markdown @closeModel="() => doc.file = ''" :file="doc.file" v-if="doc.file" />
        <ClientOnly>
          <Dialog />
        </ClientOnly>
      </div>

      <div class="columns mt-3 is-mobile">
        <div class="column">
          <div class="has-text-left" v-if="config.app?.app_version">
            © {{ Year }} - <NuxtLink href="https://github.com/ArabCoders/ytptube" target="_blank">YTPTube</NuxtLink>
            <span class="has-tooltip"
              v-tooltip="`Build Date: ${config.app?.app_build_date}, Branch: ${config.app?.app_branch}, commit: ${config.app?.app_commit_sha}`">
              &nbsp;({{ config?.app?.app_version || 'unknown' }})</span>
            - <NuxtLink target="_blank" href="https://github.com/yt-dlp/yt-dlp">yt-dlp</NuxtLink>
            <span>&nbsp;({{ config?.app?.ytdlp_version || 'unknown' }})</span>
            - <NuxtLink to="/changelog">CHANGELOG</NuxtLink>
            - <NuxtLink @click="doc.file = '/api/docs/FAQ.md'">FAQ</NuxtLink>
            - <NuxtLink @click="doc.file = '/api/docs/README.md'">README</NuxtLink>
            - <NuxtLink @click="doc.file = '/api/docs/API.md'">API</NuxtLink>
          </div>
        </div>
        <div class="column is-narrow" v-if="config.app?.started">
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
</template>

<script setup lang="ts">
import { ref, onMounted, watch, readonly } from 'vue'
import 'assets/css/bulma.css'
import 'assets/css/style.css'
import 'assets/css/all.css'
import { useStorage } from '@vueuse/core'
import moment from 'moment'
import type { YTDLPOption } from '~/types/ytdlp'
import { useDialog } from '~/composables/useDialog'
import Dialog from '~/components/Dialog.vue'
import Simple from '~/components/Simple.vue'
import Shutdown from '~/components/shutdown.vue'
import Markdown from '~/components/Markdown.vue'
import Connection from '~/components/Connection.vue'
import Settings from "~/pages/settings.vue";

const Year = new Date().getFullYear()
const selectedTheme = useStorage('theme', 'auto')
const socket = useSocketStore()
const config = useConfigStore()
const loadedImage = ref()
const loadingImage = ref(false)
const bg_enable = useStorage('random_bg', true)
const bg_opacity = useStorage('random_bg_opacity', 0.95)
const showMenu = ref(false)
const isMobile = useMediaQuery({ maxWidth: 1024 })
const app_shutdown = ref<boolean>(false)
const simpleMode = useStorage<boolean>('simple_mode', config.app.simple_mode || false)
const show_settings = ref(false)

const doc = ref<{ file: string }>({ file: '' })

const applyPreferredColorScheme = (scheme: string) => {
  if (!scheme || scheme === 'auto') {
    return
  }

  for (let s = 0; s < document.styleSheets.length; s++) {
    const styleSheet = document.styleSheets[s]
    if (!styleSheet?.cssRules) {
      continue
    }

    let rules: CSSRuleList
    try {
      rules = styleSheet.cssRules
    } catch (e) {
      // Cross-origin stylesheet
      console.debug("Unable to access stylesheet rules:", e)
      continue
    }

    for (let i = 0; i < rules.length; i++) {
      const rule = rules[i]

      if (rule instanceof CSSMediaRule && rule.media.mediaText.includes("prefers-color-scheme")) {
        const media = rule.media

        const safeDelete = (medium: string) => {
          if (media.mediaText.includes(medium)) {
            try {
              media.deleteMedium(medium)
            } catch (e) {
              console.debug(`Failed to delete medium "${medium}"`, e)
            }
          }
        }

        try {
          switch (scheme) {
            case "light":
              if (!media.mediaText.includes("original-prefers-color-scheme")) {
                media.appendMedium("original-prefers-color-scheme")
              }
              safeDelete("(prefers-color-scheme: light)")
              safeDelete("(prefers-color-scheme: dark)")
              break

            case "dark":
              if (!media.mediaText.includes("(prefers-color-scheme: light)")) {
                media.appendMedium("(prefers-color-scheme: light)")
              }
              if (!media.mediaText.includes("(prefers-color-scheme: dark)")) {
                media.appendMedium("(prefers-color-scheme: dark)")
              }
              safeDelete("original-prefers-color-scheme")
              break

            default:
              if (!media.mediaText.includes("(prefers-color-scheme: dark)")) {
                media.appendMedium("(prefers-color-scheme: dark)")
              }
              safeDelete("(prefers-color-scheme: light)")
              safeDelete("original-prefers-color-scheme")
              break
          }
        } catch (e) {
          console.debug("Error modifying media rule:", e)
        }
      }
    }
  }
}

onMounted(async () => {
  try {
    await handleImage(bg_enable.value)
  } catch { }

  try {
    const opts = await request('/api/yt-dlp/options')
    if (!opts.ok) {
      return
    }
    const data: Array<YTDLPOption> = await opts.json()
    config.ytdlp_options = data
  } catch { }

  try {
    applyPreferredColorScheme(selectedTheme.value)
  } catch { }
})

watch(selectedTheme, value => {
  try {
    if ('auto' === value) {
      applyPreferredColorScheme(window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
      return
    }
    applyPreferredColorScheme(value)
  } catch { }
})

watch(bg_enable, async v => await handleImage(v))
watch(bg_opacity, v => {
  if (false === bg_enable.value) {
    return
  }
  document.querySelector('body')?.setAttribute("style", `opacity: ${v}`)
})

watch(loadedImage, _ => {
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
  } as any

  html.setAttribute("style", Object.keys(style).map(k => `${k}: ${style[k]}`).join('; ').trim())
  html.classList.add('bg-fanart')
  body?.setAttribute("style", `opacity: ${bg_opacity.value}`)
})

const handleImage = async (enabled: boolean) => {
  if (false === enabled) {
    if (!loadedImage.value) {
      return
    }

    const html = document.documentElement
    const body = document.querySelector('body')

    if (html.getAttribute("style")) {
      html.removeAttribute("style")
    }

    if (body?.getAttribute("style")) {
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

const changeRoute = async (_: MouseEvent, callback: (() => void) | null = null) => {
  showMenu.value = false
  document.querySelectorAll('div.has-dropdown').forEach(el => el.classList.remove('is-active'))
  if (callback) {
    callback()
  }
}

const useVersionUpdate = () => {
  const newVersionIsAvailable = ref(false)
  const nuxtApp = useNuxtApp()
  nuxtApp.hooks.addHooks({
    'app:manifest:update': () => {
      newVersionIsAvailable.value = true
    }
  });

  return {
    newVersionIsAvailable: readonly(newVersionIsAvailable),
  }
}

const { newVersionIsAvailable } = useVersionUpdate()

const closeSettings = () => {
  show_settings.value = false
  navigateTo('/')
}

const shutdownApp = async () => {
  const { alertDialog, confirmDialog: confirm_message } = useDialog()

  if (false === config.app.is_native) {
    await alertDialog({
      title: 'Shutdown Unavailable',
      message: 'The shutdown feature is only available when running as native application.',
    })
    return
  }

  const { status } = await confirm_message({
    title: 'Shutdown Application',
    message: 'Are you sure you want to shutdown the application?',
  })

  if (false === status) {
    return
  }

  try {
    const resp = await fetch('/api/system/shutdown', { method: 'POST' })
    if (!resp.ok) {
      const body = await resp.json()
      await alertDialog({
        title: 'Shutdown Failed',
        message: `Failed to shutdown the application: ${body.error || resp.statusText || resp.status}`,
      })
      return
    }
    app_shutdown.value = true
    await nextTick()
  } catch (e: any) {
    await alertDialog({
      title: 'Shutdown Failed',
      message: `Failed to shutdown the application: ${e.message || e}`,
    })
  }
}

const connectionStatusColor = computed(() => {
  switch (socket.connectionStatus) {
    case 'connected':
      return 'has-text-success'
    case 'connecting':
      return 'has-text-warning'
    case 'disconnected':
    default:
      return 'has-text-danger'
  }
})

</script>
