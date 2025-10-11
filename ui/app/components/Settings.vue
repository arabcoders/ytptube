<template>
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

              <div class="field">
                <label class="label is-unselectable">
                  <span class="icon"><i class="fa-solid fa-computer" /></span>
                  Page View
                </label>
                <div class="control">
                  <div class="control">
                    <input id="view_mode" type="checkbox" class="switch is-success" v-model="simpleMode">
                    <label for="view_mode" class="is-unselectable">
                      &nbsp;{{ simpleMode ? 'Simple View' : 'Regular View' }}
                    </label>
                  </div>
                </div>
                <p class="help is-bold">
                  <span class="icon"> <i class="fa-solid fa-info-circle" /></span>
                  The simple view is ideal for non-technical users and mobile devices.
                </p>
              </div>

              <div class="field">
                <label class="label is-unselectable">Color scheme</label>
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
                <label class="label is-unselectable">
                  Show Background
                  <template v-if="bg_enable">
                    <NuxtLink @click="$emit('reload_bg')" class="is-bold">Reload</NuxtLink>
                    <span class="icon" v-if="isLoading"><i class="fa fa-spin fa-spinner" /></span>
                  </template>
                </label>
                <div class="control">
                  <input id="random_bg" type="checkbox" class="switch is-success" v-model="bg_enable">
                  <label for="random_bg" class="is-unselectable">
                    &nbsp;{{ bg_enable ? 'Yes' : 'No' }}
                  </label>
                </div>
              </div>

              <div class="field">
                <label class="label is-unselectable" for="random_bg_opacity">
                  Background visibility <code>{{ parseFloat(String(1.0 - bg_opacity)).toFixed(2) }}</code>
                </label>
                <div class="control">
                  <input id="random_bg_opacity" style="width: 100%" type="range" v-model="bg_opacity" min="0.50"
                    max="1.00" step="0.05">
                </div>
              </div>

              <div class="field" v-if="!simpleMode">
                <label class="label is-unselectable" for="show_thumbnail">URLs Separator</label>
                <div class="control">
                  <div class="select is-fullwidth">
                    <select class="is-fullwidth" v-model="separator">
                      <option v-for="(sep, index) in separators" :key="`sep-${index}`" :value="sep.value">
                        {{ sep.name }} ({{ sep.value }})
                      </option>
                    </select>
                  </div>
                </div>
              </div>

            </div>
            <div class="column is-6">
              <div class="field">
                <label class="label is-unselectable" for="show_thumbnail">Show Thumbnails</label>
                <div class="control">
                  <input id="show_thumbnail" type="checkbox" class="switch is-success" v-model="show_thumbnail">
                  <label for="show_thumbnail" class="is-unselectable">
                    &nbsp;{{ show_thumbnail ? 'Yes' : 'No' }}
                  </label>
                </div>
                <p class="help is-bold"> Show videos thumbnail if available.</p>
              </div>

              <div class="field">
                <label class="label" for="allow_toasts">Show notifications</label>
                <div class="control">
                  <input id="allow_toasts" type="checkbox" class="switch is-success" v-model="allow_toasts">
                  <label for="allow_toasts" class="is-unselectable">
                    &nbsp;{{ allow_toasts ? 'Yes' : 'No' }}
                  </label>
                </div>
              </div>

              <div class="field" v-if="allow_toasts">
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

              <div class="field" v-if="allow_toasts">
                <label class="label" for="dismiss_on_click">Dismiss notification on click</label>
                <div class="control">
                  <input id="dismiss_on_click" type="checkbox" class="switch is-success"
                    v-model="toast_dismiss_on_click">
                  <label for="dismiss_on_click" class="is-unselectable">
                    &nbsp;{{ toast_dismiss_on_click ? 'Yes' : 'No' }}
                  </label>
                </div>
              </div>

            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
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
</script>
