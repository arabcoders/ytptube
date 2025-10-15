<template>
  <main  class="m-6">

    <div>
      <span class="title is-4">
        <span class="icon-text">
          <span class="icon"><i class="fas fa-cog" /></span>
          <p class="card-header-title">Settings</p>
        </span>
      </span>

      <!-- Link buttons -->
      <div class="field is-horizontal">
        <div class="field-label is-normal">
          <label class="label"></label>
        </div>
        <div class="field-body">
          <div class="field is-narrow">
            <div class="control">

              <NuxtLink class="button is-primary" to="/logs" @click.prevent="(e: MouseEvent) => changeRoute(e)"
                        v-if="config.app.file_logging">
                <span class="icon"><i class="fa-solid fa-file-lines" /></span>
                <span>Open Logs</span>
              </NuxtLink>

              <NuxtLink class="button is-primary" to="/console" @click.prevent="(e: MouseEvent) => changeRoute(e)"
                        v-if="config.app.console_enabled">
                <span class="icon"><i class="fa-solid fa-terminal" /></span>
                <span>Open Console</span>
              </NuxtLink>
            </div>
          </div>
        </div>
      </div>


      <!-- Page View -->
      <div class="field is-horizontal">
        <div class="field-label is-normal">
          <label class="label"><i class="icon fa-solid fa-computer" /> Page View</label>
        </div>
        <div class="field-body">
          <div class="field">
            <div class="control is-expanded has-icons-left">
              <input id="view_mode" type="checkbox" class="switch is-success" v-model="simpleMode">
              <label for="view_mode" class="is-unselectable">
                &nbsp;{{ simpleMode ? 'Simple View' : 'Regular View' }}
              </label>
            </div>
            <p class="help">
              <span class="icon"> <i class="fa-solid fa-info-circle" /></span>
              The simple view is ideal for non-technical users and mobile devices.
            </p>
          </div>
        </div>
      </div>

      <!-- Color Scheme -->
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

      <!-- Show Background -->
      <div class="field is-horizontal">
        <div class="field-label is-normal">
          <label class="label">Show Background</label>
        </div>
        <div class="field-body">
          <div class="field">
            <div class="control">
              <input id="random_bg" type="checkbox" class="switch is-success" v-model="bg_enable">
              <label for="random_bg" class="is-unselectable">
                &nbsp;{{ bg_enable ? 'Yes' : 'No' }}
              </label>
            </div>
          </div>

          <div class="field">
            <template v-if="bg_enable">
              <NuxtLink @click="$emit('reload_bg')" class="is-bold">Reload</NuxtLink>
              <span class="icon" v-if="isLoading"><i class="fa fa-spin fa-spinner" /></span>
            </template>
          </div>
        </div>
      </div>


      <!-- Background visibility -->
      <div class="field is-horizontal">
        <div class="field-label is-normal">
          <label class="label">Background visibility</label>
        </div>
        <div class="field-body">
          <div class="field is-expanded">

            <a class="button is-static">
              <code>{{ parseFloat(String(1.0 - bg_opacity)).toFixed(2) }}</code>
            </a>


            <div class="control">
              <input id="random_bg_opacity" style="width: 100%" type="range" v-model="bg_opacity" min="0.50"
                     max="1.00" step="0.05">
            </div>
          </div>
        </div>
      </div>

      <!-- URL Separator -->
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



      <!-- Show Thumbnails -->
      <div class="field is-horizontal">
        <div class="field-label is-normal">
          <label class="label">Show Thumbnails</label>
        </div>

        <div class="field-body">
          <div class="control">
            <div class="field">
              <input id="show_thumbnail" type="checkbox" class="switch is-success" v-model="show_thumbnail">
              <label for="show_thumbnail" class="is-unselectable">
                &nbsp;{{ show_thumbnail ? 'Yes' : 'No' }}
              </label>
            </div>
            <p class="help">
              <span class="icon"><i class="fa-solid fa-info-circle"/></span>
              Show videos thumbnail if available
            </p>
          </div>
        </div>
      </div>


      <!-- Show notifications -->
      <div class="field is-horizontal">
        <div class="field-label is-normal">
          <label class="label">Show notifications</label>
        </div>

        <div class="field-body">
          <div class="control">
            <div class="field">
              <input id="allow_toasts" type="checkbox" class="switch is-success" v-model="allow_toasts">
              <label for="allow_toasts" class="is-unselectable">
                &nbsp;{{ allow_toasts ? 'Yes' : 'No' }}
              </label>
            </div>
          </div>
        </div>
      </div>


      <!-- Notification Position -->
      <div class="field is-horizontal" v-if="allow_toasts">
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



      <!-- Dismiss notification on click -->
      <div class="field is-horizontal" v-if="allow_toasts">
        <div class="field-label is-normal">
          <label class="label">Dismiss notification on click</label>
        </div>

        <div class="field-body">
          <div class="control">
            <div class="field">
              <input id="dismiss_on_click" type="checkbox" class="switch is-success" v-model="toast_dismiss_on_click">
              <label for="dismiss_on_click" class="is-unselectable">
                &nbsp;{{ toast_dismiss_on_click ? 'Yes' : 'No' }}
              </label>
            </div>
          </div>
        </div>
      </div>

      <!--end-->
    </div>
  </main>
</template>

<script setup lang="ts">
import { useStorage } from '@vueuse/core'
import { POSITION } from 'vue-toastification'
import { useConfigStore } from '~/stores/ConfigStore'

defineProps<{ isLoading: boolean }>()
defineEmits<{ (e: 'reload_bg'): void }>()

const bg_enable = useStorage<boolean>('random_bg', true)
const bg_opacity = useStorage<number>('random_bg_opacity', 0.95)
const selectedTheme = useStorage<'auto' | 'light' | 'dark'>('theme', 'auto')
const allow_toasts = useStorage<boolean>('allow_toasts', true)
const toast_position = useStorage<POSITION>('toast_position', POSITION.TOP_RIGHT)
const toast_dismiss_on_click = useStorage<boolean>('toast_dismiss_on_click', true)
const show_thumbnail = useStorage<boolean>('show_thumbnail', true)
const separator = useStorage<string>('url_separator', separators[0]?.value ?? ',')
const simpleMode = useStorage<boolean>('simple_mode', useConfigStore().app.simple_mode || false)



const config = useConfigStore()

const changeRoute = async (_: MouseEvent, callback: (() => void) | null = null) => {
  document.querySelectorAll('div.has-dropdown').forEach(el => el.classList.remove('is-active'))
  if (callback) {
    callback()
  }
}

</script>
