<template>
  <main class="m-6">

    <div>
      <template v-if="!simpleMode">
        <span class="title is-4">
          <span class="icon-text">
            <span class="icon"><i class="fas fa-cog" /></span>
            <p class="card-header-title">WebUI Settings</p>
          </span>
        </span>
        <span class="field is-horizontal" />
      </template>

      <div class="field is-horizontal">
        <div class="field-label is-normal">
          <label class="label">Page View</label>
        </div>
        <div class="field-body">
          <div class="field">
            <div class="control is-expanded has-icons-left">
              <input id="view_mode" type="checkbox" class="switch is-success" v-model="simpleMode">
              <label for="view_mode" class="is-unselectable">
                {{ simpleMode ? 'Simple View' : 'Regular View' }}
              </label>
            </div>
            <p class="help">
              <span class="icon"> <i class="fa-solid fa-info-circle" /></span>
              The simple view is ideal for non-technical users and mobile devices.
            </p>
          </div>
        </div>
      </div>


      <span class="field title is-4">
        <span class="icon-text">
          <span class="icon"><i class="fas fa-palette" /></span>
          <p class="card-header-title">Theming</p>
        </span>
      </span>
      <span class="field is-horizontal" />

      <div class="field is-horizontal">
        <div class="field-label">
          <label class="label">Color scheme</label>
        </div>
        <div class="field-body">
          <div class="field is-narrow">
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
        </div>
      </div>

      <div class="field is-horizontal">
        <div class="field-label is-normal">
          <label class="label">Show Background</label>
        </div>
        <div class="field-body">
          <div class="field">
            <div class="control">
              <input id="random_bg" type="checkbox" class="switch is-success" v-model="bg_enable">
              <label for="random_bg" class="is-unselectable">
                {{ bg_enable ? 'Yes' : 'No' }}
              </label>
            </div>
          </div>
        </div>
      </div>

      <div class="field is-horizontal">
        <div class="field-label is-normal">
          <label class="label"></label>
        </div>
        <div class="field-body">
          <div class="field">
            <div class="control">
              <template v-if="bg_enable">
                <button @click="$emit('reload_bg')" class="has-text-link" :disabled="isLoading">
                  <span class="icon-text">
                    <span class="icon"><i class="fa"
                        :class="{ 'fa-spin fa-spinner': isLoading, 'fa-file-image': !isLoading }" /></span>
                    <span>Reload Background</span>
                  </span>
                </button>
              </template>
            </div>
          </div>
        </div>
      </div>

      <div class="field is-horizontal">
        <div class="field-label is-normal">
          <label class="label">Background visibility</label>
        </div>
        <div class="field-body">
          <div class="field is-expanded">
            <a class="button is-static is-small">
              <code>{{ parseFloat(String(1.0 - bg_opacity)).toFixed(2) }}</code>
            </a>

            <div class="control">
              <input id="random_bg_opacity" style="width: 100%" type="range" v-model="bg_opacity" min="0.50" max="1.00"
                step="0.05">
            </div>
          </div>
        </div>
      </div>

      <span class="field title is-4">
        <span class="icon-text">
          <span class="icon"><i class="fas fa-home" /></span>
          <p class="card-header-title">Dashboard</p>
        </span>
      </span>
      <span class="field is-horizontal" />

      <div class="field is-horizontal" v-if="!simpleMode">
        <div class="field-label is-normal">
          <label class="label">URL Separator</label>
        </div>
        <div class="field-body">
          <div class="field is-narrow">
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
        </div>
      </div>

      <div class="field is-horizontal">
        <div class="field-label is-normal">
          <label class="label">Show Thumbnails</label>
        </div>

        <div class="field-body">
          <div class="control">
            <div class="field">
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
        </div>
      </div>

      <div class="field is-horizontal" v-if="show_thumbnail">
        <div class="field-label is-normal">
          <label class="label">Aspect Ratio</label>
        </div>

        <div class="field-body">
          <div class="control">
            <div class="field">
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
      </div>

      <span class="field title is-4">
        <span class="icon-text">
          <span class="icon"><i class="fas fa-bell" /></span>
          <p class="card-header-title">Notifications</p>
        </span>
      </span>
      <span class="field is-horizontal" />

      <div class="field is-horizontal">
        <div class="field-label is-normal">
          <label class="label">Show notifications</label>
        </div>

        <div class="field-body">
          <div class="control">
            <div class="field">
              <input id="allow_toasts" type="checkbox" class="switch is-success" v-model="allow_toasts">
              <label for="allow_toasts" class="is-unselectable">
                {{ allow_toasts ? 'Yes' : 'No' }}
              </label>
            </div>
          </div>
        </div>
      </div>

      <div class="field is-horizontal" v-if="allow_toasts">
        <div class="field-label is-normal">
          <label class="label">Notification target</label>
        </div>
        <div class="field-body">
          <div class="field is-narrow">
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
        </div>
      </div>

      <div class="field is-horizontal" v-if="allow_toasts && toast_target === 'toast'">
        <div class="field-label is-normal">
          <label class="label">Notifications position</label>
        </div>
        <div class="field-body">
          <div class="field is-narrow">
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
        </div>
      </div>

      <div class="field is-horizontal" v-if="allow_toasts && toast_target === 'toast'">
        <div class="field-label is-normal">
          <label class="label">Dismiss notification on click</label>
        </div>

        <div class="field-body">
          <div class="control">
            <div class="field">
              <input id="dismiss_on_click" type="checkbox" class="switch is-success" v-model="toast_dismiss_on_click">
              <label for="dismiss_on_click" class="is-unselectable">
                {{ toast_dismiss_on_click ? 'Yes' : 'No' }}
              </label>
            </div>
          </div>
        </div>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
import 'assets/css/bulma-switch.css'
import { useStorage } from '@vueuse/core'
import { ref, onMounted } from 'vue'
import { POSITION } from 'vue-toastification'
import { useConfigStore } from '~/stores/ConfigStore'
import { useNotification } from '~/composables/useNotification'
import type { notificationTarget } from '~/composables/useNotification'

defineProps<{ isLoading: boolean }>()
defineEmits<{ (e: 'reload_bg'): void }>()

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

onMounted(async () => {
  isSecureContext.value = window.isSecureContext
  await nextTick()
  if ('browser' === toast_target.value && !isSecureContext.value) {
    toast_target.value = 'toast'
  }
})

const onNotificationTargetChange = async (): Promise<void> => {
  if ('browser' === toast_target.value) {
    const permission = await notification.requestBrowserPermission()
    if ('granted' !== permission) {
      toast_target.value = 'toast'
      notification.warning('Browser notification permission denied. Reverting to toast notifications.')
    }
  }
}
</script>
