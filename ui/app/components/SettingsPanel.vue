<template>
  <div class="modal" :class="{ 'is-active': isOpen }">
    <div class="modal-background" @click="emitter('close')" />
    <div class="modal-card"
      :class="{ 'slide-from-right': direction === 'right', 'slide-from-left': direction === 'left' }">
      <header class="modal-card-head is-rounded-less">
        <p class="modal-card-title">WebUI Settings</p>
        <button class="delete" @click="emitter('close')" aria-label="close" />
      </header>
      <section class="modal-card-body">
        <div class="box">
          <div class="field">
            <label class="label">Page View</label>
            <div class="control">
              <input id="view_mode" type="checkbox" class="switch is-success" v-model="simpleMode">
              <label for="view_mode" class="is-unselectable">
                {{ simpleMode ? 'Simple View' : 'Regular View' }}
              </label>
            </div>
            <p class="help">
              <span class="icon"><i class="fa-solid fa-info-circle" /></span>
              The simple view is ideal for non-technical users and mobile devices.
            </p>
          </div>
        </div>

        <div class="box">
          <p class="title is-5 mb-4">
            <span class="icon-text">
              <span class="icon"><i class="fas fa-palette" /></span>
              <span>Theming</span>
            </span>
          </p>

          <div class="field">
            <label class="label">Color scheme</label>
            <div class="control">
              <label for="auto" class="radio">
                <input id="auto" type="radio" v-model="selectedTheme" value="auto">
                <span class="icon"><i class="fa-solid fa-circle-half-stroke" /></span>
                <span>Auto</span>
              </label>
              <label for="light" class="radio">
                <input id="light" type="radio" v-model="selectedTheme" value="light">
                <span class="icon has-text-warning"><i class="fa-solid fa-sun" /></span>
                <span>Light</span>
              </label>
              <label for="dark" class="radio">
                <input id="dark" type="radio" v-model="selectedTheme" value="dark">
                <span class="icon"><i class="fa-solid fa-moon" /></span>
                <span>Dark</span>
              </label>
            </div>
          </div>

          <div class="field">
            <label class="label">Show Background</label>
            <div class="control">
              <input id="random_bg" type="checkbox" class="switch is-success" v-model="bg_enable">
              <label for="random_bg" class="is-unselectable">
                {{ bg_enable ? 'Yes' : 'No' }}
              </label>
            </div>
          </div>

          <div class="field" v-if="bg_enable">
            <div class="control">
              <button @click="$emit('reload_bg')" class="button is-link is-light is-fullwidth" :disabled="isLoading">
                <span class="icon"><i class="fa"
                    :class="{ 'fa-spin fa-spinner': isLoading, 'fa-file-image': !isLoading }" /></span>
                <span>Reload Background</span>
              </button>
            </div>
          </div>

          <div class="field" v-if="bg_enable">
            <label class="label">Background visibility</label>
            <div class="field has-addons">
              <div class="control">
                <a class="button is-static">
                  <code>{{ parseFloat(String(1.0 - bg_opacity)).toFixed(2) }}</code>
                </a>
              </div>
              <div class="control is-expanded">
                <input class="input" type="range" v-model="bg_opacity" min="0.50" max="1.00" step="0.05">
              </div>
            </div>
          </div>
        </div>

        <div class="box">
          <p class="title is-5 mb-4">
            <span class="icon-text">
              <span class="icon"><i class="fas fa-home" /></span>
              <span>Dashboard</span>
            </span>
          </p>

          <div class="field" v-if="!simpleMode">
            <label class="label">URL Separator</label>
            <div class="control">
              <div class="select is-fullwidth">
                <select v-model="separator">
                  <option v-for="(sep, index) in separators" :key="`sep-${index}`" :value="sep.value">
                    {{ sep.name }} ({{ sep.value }})
                  </option>
                </select>
              </div>
            </div>
          </div>

          <div class="field">
            <label class="label">Show Thumbnails</label>
            <div class="control">
              <input id="show_thumbnail" type="checkbox" class="switch is-success" v-model="show_thumbnail">
              <label for="show_thumbnail" class="is-unselectable">
                {{ show_thumbnail ? 'Yes' : 'No' }}
              </label>
            </div>
            <p class="help">
              <span class="icon"><i class="fa-solid fa-info-circle" /></span>
              Show videos thumbnail if available
            </p>
          </div>

          <div class="field" v-if="show_thumbnail">
            <label class="label">Aspect Ratio</label>
            <div class="control">
              <label for="ratio_16by9" class="radio">
                <input id="ratio_16by9" type="radio" v-model="thumbnail_ratio" value="is-16by9">
                <span>&nbsp;16:9</span>
              </label>
              <label for="ratio_3by1" class="radio">
                <input id="ratio_3by1" type="radio" v-model="thumbnail_ratio" value="is-3by1">
                <span>&nbsp;3:1</span>
              </label>
            </div>
            <p class="help">
              <span class="icon"><i class="fa-solid fa-info-circle" /></span>
              Choose the aspect ratio for thumbnail display.
            </p>
          </div>
        </div>

        <div class="box">
          <p class="title is-5 mb-4">
            <span class="icon-text">
              <span class="icon"><i class="fas fa-bell" /></span>
              <span>Notifications</span>
            </span>
          </p>

          <div class="field">
            <label class="label">Show notifications</label>
            <div class="control">
              <input id="allow_toasts" type="checkbox" class="switch is-success" v-model="allow_toasts">
              <label for="allow_toasts" class="is-unselectable">
                {{ allow_toasts ? 'Yes' : 'No' }}
              </label>
            </div>
          </div>

          <div class="field" v-if="allow_toasts">
            <label class="label">Notification target</label>
            <div class="control">
              <div class="select is-fullwidth">
                <select v-model="toast_target" @change="onNotificationTargetChange">
                  <option value="toast">Toast</option>
                  <option value="browser" :disabled="!isSecureContext">Browser</option>
                </select>
              </div>
            </div>
            <p class="help">
              <span class="icon"><i class="fa-solid fa-info-circle" /></span>
              <template v-if="!isSecureContext">
                Browser notifications require HTTPS connection.
              </template>
              <template v-else>
                Choose where to display notifications. Browser requires permission.
              </template>
            </p>
          </div>

          <div class="field" v-if="allow_toasts && toast_target === 'toast'">
            <label class="label">Notifications position</label>
            <div class="control">
              <div class="select is-fullwidth">
                <select v-model="toast_position">
                  <option :value="POSITION.TOP_RIGHT">{{ POSITION.TOP_RIGHT }}</option>
                  <option :value="POSITION.TOP_CENTER">{{ POSITION.TOP_CENTER }}</option>
                  <option :value="POSITION.TOP_LEFT">{{ POSITION.TOP_LEFT }}</option>
                  <option :value="POSITION.BOTTOM_RIGHT">{{ POSITION.BOTTOM_RIGHT }}</option>
                  <option :value="POSITION.BOTTOM_CENTER">{{ POSITION.BOTTOM_CENTER }}</option>
                  <option :value="POSITION.BOTTOM_LEFT">{{ POSITION.BOTTOM_LEFT }}</option>
                </select>
              </div>
            </div>
          </div>

          <div class="field" v-if="allow_toasts && toast_target === 'toast'">
            <label class="label">Dismiss notification on click</label>
            <div class="control">
              <input id="dismiss_on_click" type="checkbox" class="switch is-success" v-model="toast_dismiss_on_click">
              <label for="dismiss_on_click" class="is-unselectable">
                {{ toast_dismiss_on_click ? 'Yes' : 'No' }}
              </label>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import 'assets/css/bulma-switch.css'
import { watch, onMounted, onBeforeUnmount, ref } from 'vue'
import { useStorage } from '@vueuse/core'
import { POSITION } from 'vue-toastification'
import { useConfigStore } from '~/stores/ConfigStore'
import { useNotification } from '~/composables/useNotification'
import type { notificationTarget } from '~/composables/useNotification'

const props = withDefaults(defineProps<{
  isOpen?: boolean
  direction?: 'left' | 'right'
  isLoading?: boolean
}>(), {
  isOpen: false,
  direction: 'right',
  isLoading: false
})

const emitter = defineEmits<{ (e: 'close' | 'reload_bg'): void }>()

const config = useConfigStore()
const notification = useNotification()

const bg_enable = useStorage<boolean>('random_bg', true)
const bg_opacity = useStorage<number>('random_bg_opacity', 0.95)
const selectedTheme = useStorage<'auto' | 'light' | 'dark'>('theme', 'auto')
const allow_toasts = useStorage<boolean>('allow_toasts', true)
const toast_position = useStorage<POSITION>('toast_position', POSITION.TOP_RIGHT)
const toast_dismiss_on_click = useStorage<boolean>('toast_dismiss_on_click', true)
const toast_target = useStorage<notificationTarget>('toast_target', 'toast')
const show_thumbnail = useStorage<boolean>('show_thumbnail', true)
const thumbnail_ratio = useStorage<'is-16by9' | 'is-3by1'>('thumbnail_ratio', 'is-3by1')
const separator = useStorage<string>('url_separator', separators[0]?.value ?? ',')
const simpleMode = useStorage<boolean>('simple_mode', config.app.simple_mode || false)
const isSecureContext = ref<boolean>(false)

const handleKeydown = (e: KeyboardEvent) => {
  if ('Escape' === e.key && props.isOpen) {
    e.preventDefault()
    e.stopPropagation()
    emitter('close')
  }
}

onMounted(async () => {
  isSecureContext.value = window.isSecureContext
  await nextTick()

  if ('browser' === toast_target.value && !isSecureContext.value) {
    toast_target.value = 'toast'
  }

  document.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => document.removeEventListener('keydown', handleKeydown))

const onNotificationTargetChange = async (): Promise<void> => {
  if ('browser' === toast_target.value) {
    const permission = await notification.requestBrowserPermission()
    if ('granted' !== permission) {
      toast_target.value = 'toast'
      notification.warning('Browser notification permission denied. Reverting to toast notifications.')
    }
  }
}

watch(() => props.isOpen, isOpen => {
  if (isOpen) {
    document.body.classList.add('settings-panel-open')
  } else {
    document.body.classList.remove('settings-panel-open')
  }
})
</script>

<style scoped>
.modal-card.slide-from-right {
  position: fixed;
  right: 0;
  top: 0;
  height: 100vh;
  max-height: 100vh;
  margin: 0;
  width: 600px;
  max-width: 90vw;
  transition: transform 0.3s ease;
  transform: translateX(100%);
}

.modal.is-active .modal-card.slide-from-right {
  transform: translateX(0);
}

.modal-card.slide-from-left {
  position: fixed;
  left: 0;
  top: 0;
  height: 100vh;
  max-height: 100vh;
  margin: 0;
  width: 600px;
  max-width: 90vw;
  transition: transform 0.3s ease;
  transform: translateX(-100%);
}

.modal.is-active .modal-card.slide-from-left {
  transform: translateX(0);
}

.modal-card-body {
  overflow-y: auto;
}

@media screen and (max-width: 768px) {

  .modal-card.slide-from-right,
  .modal-card.slide-from-left {
    width: 100vw;
    max-width: 100vw;
  }
}

:global(body.settings-panel-open) {
  overflow: hidden;
}

#main_container {
  transition: transform 0.3s ease;
}

@media screen and (min-width: 769px) {
  :global(.settings-open #main_container) {
    transform: translateX(-300px);
  }
}
</style>
