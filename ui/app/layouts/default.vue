<template>

  <template v-if="simpleMode">
    <Connection :status="socket.connectionStatus" @reconnect="() => socket.reconnect()" />
    <Simple @show_settings="() => show_settings = true" :class="{ 'settings-open': show_settings }" />
  </template>

  <SettingsPanel :isOpen="show_settings" :isLoading="loadingImage" @close="closeSettings()"
    @reload_bg="() => loadImage(true)" direction="right" />

  <template v-if="!simpleMode">
    <Shutdown v-if="app_shutdown" />
    <div id="main_container" class="container" :class="{ 'settings-open': show_settings }" v-else>
      <NewVersion v-if="newVersionIsAvailable" />
      <nav class="navbar is-mobile is-dark">
        <div class="navbar-brand pl-5">
          <NuxtLink class="navbar-item is-text-overflow" to="/" @click.prevent="(e: MouseEvent) => changeRoute(e)"
            v-tooltip="socket.isConnected ? 'Connected' : 'Connecting'" id="top">
            <span class="is-text-overflow">
              <span class="icon">
                <i v-if="'connecting' === socket.connectionStatus" class="fas fa-arrows-rotate fa-spin" />
                <i v-else class="fas fa-home" />
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
            <NuxtLink class="navbar-item" to="/browser" @click.prevent="(e: MouseEvent) => changeRoute(e)">
              <span class="icon"><i class="fa-solid fa-folder-tree" /></span>
              <span>Files</span>
            </NuxtLink>

            <NuxtLink class="navbar-item" to="/presets" @click.prevent="(e: MouseEvent) => changeRoute(e)">
              <span class="icon"><i class="fa-solid fa-sliders" /></span>
              <span>Presets</span>
            </NuxtLink>

            <div class="navbar-item has-dropdown">
              <a class="navbar-link" @click="(e: MouseEvent) => openMenu(e)">
                <span class="icon"><i class="fas fa-tasks" /></span>
                <span>Tasks</span>
              </a>
              <div class="navbar-dropdown">
                <NuxtLink class="navbar-item" to="/tasks" @click.prevent="(e: MouseEvent) => changeRoute(e)">
                  <span class="icon"><i class="fa-solid fa-tasks" /></span>
                  <span>List</span>
                </NuxtLink>

                <NuxtLink class="navbar-item" to="/task_definitions" @click.prevent="(e: MouseEvent) => changeRoute(e)">
                  <span class="icon"><i class="fa-solid fa-diagram-project" /></span>
                  <span>Definitions</span>
                </NuxtLink>
              </div>
            </div>

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
            <div class="navbar-item has-dropdown">
              <a class="navbar-link" @click="(e: MouseEvent) => openMenu(e)">
                <span class="icon"><i class="fas fa-tools" /></span>
                <span>Other</span>
              </a>

              <div class="navbar-dropdown">
                <NuxtLink class="navbar-item" to="/logs" @click.prevent="(e: MouseEvent) => changeRoute(e)"
                  v-if="config.app?.file_logging">
                  <span class="icon"><i class="fa-solid fa-file-lines" /></span>
                  <span>Logs</span>
                </NuxtLink>

                <NuxtLink class="navbar-item" to="/console" @click.prevent="(e: MouseEvent) => changeRoute(e)"
                  v-if="config.app.console_enabled">
                  <span class="icon"><i class="fa-solid fa-terminal" /></span>
                  <span>Console</span>
                </NuxtLink>

                <NuxtLink class="navbar-item" to="/dl_fields" @click.prevent="(e: MouseEvent) => changeRoute(e)">
                  <span class="icon"><i class="fa-solid fa-file-lines" /></span>
                  <span>Custom fields</span>
                </NuxtLink>
              </div>
            </div>

            <div class="navbar-item" v-if="true === config.app.is_native">
              <button class="button is-dark" @click="shutdownApp">
                <span class="icon"><i class="fas fa-power-off" /></span>
                <span v-if="isMobile">Shutdown</span>
              </button>
            </div>

            <NotifyDropdown />

            <div class="navbar-item">
              <button class="button is-dark" @click="reloadPage">
                <span class="icon"><i class="fas fa-refresh" /></span>
                <span v-if="isMobile">Reload</span>
              </button>
            </div>

            <div class="navbar-item">
              <button class="button is-dark " :class="{ 'has-tooltip-bottom mr-4': !isMobile }"
                @click="show_settings = !show_settings">
                <span class="icon"><i class="fas fa-cog" /></span>
                <span v-if="isMobile">WebUI Settings</span>
              </button>
            </div>

          </div>
        </div>
      </nav>
      <div>
        <NuxtLoadingIndicator />
        <NuxtPage v-if="config.is_loaded" :isLoading="loadingImage" @reload_bg="() => loadImage(true)" />
        <Message v-if="!config.is_loaded" class="mt-5"
          :class="{ 'is-info': config.is_loading, 'is-danger': !config.is_loading }"
          :title="config.is_loading ? 'Loading configuration...' : 'Failed to load configuration'"
          :icon="config.is_loading ? 'fas fa-spinner fa-spin' : 'fas fa-triangle-exclamation'">
          <p v-if="config.is_loading">
            This usually takes less than a few seconds. If this is taking too long,
            <NuxtLink class="button is-text p-0" @click="reloadPage">click here</NuxtLink> to reload the
            page.
          </p>
          <p v-if="!config.is_loading">
            Failed to load the application configuration. This likely indicates a problem with the backend. Try to
            <NuxtLink class="button is-text p-0" @click="() => config.loadConfig(true)">reload
              configuration</NuxtLink> or <NuxtLink class="button is-text p-0" @click="reloadPage">reload the page
            </NuxtLink>.
          </p>
          <template v-if="socket.error">
            <hr>
            <p class="has-text-danger">
              <span class="icon-text">
                <span class="icon"><i class="fas fa-triangle-exclamation" /></span>
                <span class="tag is-danger">{{ socket.error_count }}</span>
                {{ socket.error }}. Check the developer console for more information.
              </span>
            </p>
          </template>
        </Message>
        <Markdown @closeModel="() => doc.file = ''" :file="doc.file" v-if="doc.file" />
        <ClientOnly>
          <Dialog />
        </ClientOnly>
      </div>

      <div class="mt-6">
        <div class="columns is-multiline">
          <div class="column is-12">
            <Connection :status="socket.connectionStatus" @reconnect="() => socket.reconnect()" />
          </div>
        </div>
      </div>

      <footer class="footer py-5 is-unselectable" v-if="config.is_loaded">
        <div class="columns is-multiline is-variable is-8">
          <div class="column is-12-mobile is-6-tablet">
            <div class="mb-3">
              <NuxtLink href="https://github.com/ArabCoders/ytptube" target="_blank"
                class="has-text-weight-semibold is-size-6">
                <span class="icon-text">
                  <span class="icon"><i class="fab fa-github" /></span>
                  <span>YTPTube</span>
                </span>
              </NuxtLink>
              <span class="is-size-7 ml-2 has-tooltip" style="opacity: 0.7"
                v-tooltip="`Build: ${config.app?.app_build_date}, Branch: ${config.app?.app_branch}, SHA: ${config.app?.app_commit_sha}`">
                {{ config?.app?.app_version || 'unknown' }}
              </span>
            </div>

            <p v-if="config.app?.new_version" class="is-size-7 mb-2" style="opacity: 0.8">
              <span class="icon-text">
                <span class="icon has-text-warning"><i class="fas fa-circle-info" /></span>
                <span>Update available:</span>
                <NuxtLink :href="`https://github.com/ArabCoders/ytptube/releases/tag/${config.app.new_version}`"
                  target="_blank" class="has-text-weight-semibold ml-1">
                  {{ config.app.new_version }}
                </NuxtLink>
              </span>
            </p>

            <p v-else class="is-size-7 mb-2" style="opacity: 0.6">
              <button @click="checkForUpdates" :disabled="checkingUpdates" class="is-text is-small p-0 is-size-7"
                :class="{ 'is-loading': checkingUpdates }"
                style="opacity: 0.8; height: auto; vertical-align: baseline; border: none; text-decoration: none; background: none;">
                <span class="icon-text">
                  <span class="icon">
                    <i class="fas" :class="checkingUpdates ? 'fa-spinner fa-spin' : 'fa-circle-check'" />
                  </span>
                  <span>{{ updateCheckMessage }}</span>
                </span>
              </button>
            </p>

            <p v-if="config.app?.started" class="is-size-7 mb-0" style="opacity: 0.6">
              <span class="icon-text">
                <span class="icon"><i class="fas fa-clock" /></span>
                <span class="has-tooltip"
                  v-tooltip="'Started: ' + moment.unix(config.app?.started).format('YYYY-MM-DD HH:mm Z')">
                  {{ moment.unix(config.app?.started).fromNow() }}
                </span>
              </span>
            </p>
          </div>

          <div class="column is-12-mobile is-3-tablet">
            <div class="footer-divider"
              style="border-left: 1px solid rgba(128,128,128,0.2); border-right: 1px solid rgba(128,128,128,0.2); padding: 0 2rem;">
              <p class="is-size-7 mb-2" style="opacity: 0.7">Powered by</p>
              <NuxtLink href="https://github.com/yt-dlp/yt-dlp" target="_blank" class="has-text-weight-semibold">
                <span class="icon-text">
                  <span class="icon"><i class="fab fa-github" /></span>
                  <span>yt-dlp</span>
                </span>
              </NuxtLink>
              <span class="is-size-7 ml-1" style="opacity: 0.6">{{ config?.app?.ytdlp_version || 'unknown' }}</span>

              <p v-if="config.app?.yt_new_version" class="is-size-7 mb-0 mt-2" style="opacity: 0.8">
                <span class="icon-text">
                  <span class="has-tooltip" v-tooltip="`Restart container to update yt-dlp`">
                    <span class="icon has-text-warning"><i class="fas fa-circle-info" /></span>
                    <span>Update available:</span>
                  </span>
                  <NuxtLink :href="`https://github.com/yt-dlp/yt-dlp/releases/tag/${config.app.yt_new_version}`"
                    target="_blank" class="has-text-weight-semibold ml-1">
                    {{ config.app.yt_new_version }}
                  </NuxtLink>
                </span>
              </p>
            </div>
          </div>

          <div class="column is-12-mobile is-3-tablet">
            <p class="is-size-7 mb-2" style="opacity: 0.7">Quick Links</p>
            <div
              class="is-flex is-flex-direction-row is-flex-wrap-wrap is-justify-content-flex-start is-justify-content-flex-end-tablet"
              style="gap: 0.75rem;">
              <NuxtLink to="/changelog" class="is-size-7">
                <span class="icon-text">
                  <span class="icon"><i class="fas fa-list" /></span>
                  <span>Changelog</span>
                </span>
              </NuxtLink>
              <NuxtLink @click="doc.file = '/api/docs/FAQ.md'" class="is-size-7">
                <span class="icon-text">
                  <span class="icon"><i class="fas fa-question-circle" /></span>
                  <span>FAQ</span>
                </span>
              </NuxtLink>
              <NuxtLink @click="doc.file = '/api/docs/README.md'" class="is-size-7">
                <span class="icon-text">
                  <span class="icon"><i class="fas fa-book" /></span>
                  <span>Docs</span>
                </span>
              </NuxtLink>
              <NuxtLink @click="doc.file = '/api/docs/API.md'" class="is-size-7">
                <span class="icon-text">
                  <span class="icon"><i class="fas fa-code" /></span>
                  <span>API</span>
                </span>
              </NuxtLink>
              <button @click="scrollToTop" class="is-size-7 button is-text is-small p-0">
                <span class="icon-text">
                  <span class="icon"><i class="fas fa-arrow-up" /></span>
                  <span>Top</span>
                </span>
              </button>
            </div>
          </div>
        </div>
      </footer>
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
import type { version_check } from '~/types'

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
const checkingUpdates = ref(false)
const updateCheckMessage = ref('Up to date - Click to check')

const checkForUpdates = async () => {
  if (checkingUpdates.value) {
    return
  }

  const msg = 'Up to date - Click to check'

  try {
    checkingUpdates.value = true
    updateCheckMessage.value = 'Checking...'

    const response = await fetch('/api/system/check-updates', { method: 'POST' })

    if (!response.ok) {
      await response.json()
      updateCheckMessage.value = 'Check failed'
      setTimeout(() => updateCheckMessage.value = msg, 3000)
      return
    }

    const data = await parse_api_response<version_check>(await response.json())

    if ('update_available' === data.app.status) {
      config.app.new_version = data.app.new_version
    }
    if (data.ytdlp && 'update_available' === data.ytdlp.status) {
      config.app.yt_new_version = data.ytdlp.new_version
    }

    // Only show "Update found!" if app has update (button is in app section)
    if ('update_available' === data.app.status) {
      updateCheckMessage.value = 'Update found!'
    } else if ('up_to_date' === data.app.status && 'up_to_date' === data.ytdlp?.status) {
      updateCheckMessage.value = 'Up to date ✓'
      setTimeout(() => updateCheckMessage.value = msg, 3000)
    } else if ('up_to_date' === data.app.status && 'update_available' === data.ytdlp?.status) {
      // App is up to date, but yt-dlp has update (shows in yt-dlp section)
      updateCheckMessage.value = 'Up to date ✓'
      setTimeout(() => updateCheckMessage.value = msg, 3000)
    } else {
      updateCheckMessage.value = 'Check failed'
      setTimeout(() => updateCheckMessage.value = msg, 3000)
    }

  } catch (e) {
    console.error('Update check failed:', e)
    updateCheckMessage.value = 'Check failed'
    setTimeout(() => updateCheckMessage.value = msg, 3000)
  } finally {
    checkingUpdates.value = false
  }
}

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
    applyPreferredColorScheme(selectedTheme.value)
  } catch { }

  try {
    await config.loadConfig()
  } catch { }

  try {
    const opts = await request('/api/yt-dlp/options')
    if (opts.ok) {
      config.ytdlp_options = await opts.json() as Array<YTDLPOption>
    }
  } catch { }

  try {
    socket.connect()
  } catch { }

  try {
    await handleImage(bg_enable.value)
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

const closeSettings = () => show_settings.value = false

const shutdownApp = async () => {
  const { alertDialog, confirmDialog: cDialog } = useDialog()

  if (false === config.app.is_native) {
    await alertDialog({
      title: 'Shutdown Unavailable',
      message: 'The shutdown feature is only available when running as native application.',
    })
    return
  }

  const { status } = await cDialog({
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

const openMenu = (e: MouseEvent) => {
  const elm = (e.target as HTMLElement)?.closest('div.has-dropdown') as HTMLElement | null

  document.querySelectorAll<HTMLElement>('div.has-dropdown').forEach(el => {
    if (el !== elm) {
      el.classList.remove('is-active')
    }
  })

  elm?.classList.toggle('is-active')
}

const reloadPage = () => window.location.reload()

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

const scrollToTop = () => document.getElementById('top')?.scrollIntoView({ behavior: 'smooth' });
</script>

<style>
#main_container,
.basic-wrapper {
  transition: transform 0.3s ease, margin-right 0.3s ease;
}

#main_container.settings-open,
.basic-wrapper.settings-open {
  transform: translateX(-300px);
}

@media screen and (max-width: 768px) {

  #main_container.settings-open,
  .basic-wrapper.settings-open {
    transform: translateX(0);
  }

  .footer .footer-divider {
    border-left: none !important;
    border-right: none !important;
    padding: 0 !important;
    border-top: 1px solid rgba(128, 128, 128, 0.2);
    padding-top: 1.5rem !important;
    margin-top: 1.5rem !important;
  }
}
</style>
