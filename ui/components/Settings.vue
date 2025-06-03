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
                <label class="label">Color scheme</label>
                <div class="control">
                  <label for="auto" class="radio">
                    <input id="auto" type="radio" v-model="selectedTheme" value="auto">
                    System Default
                  </label>
                  <label for="light" class="radio">
                    <input id="light" type="radio" v-model="selectedTheme" value="light">
                    Light
                  </label>
                  <label for="dark" class="radio">
                    <input id="dark" type="radio" v-model="selectedTheme" value="dark">
                    Dark
                  </label>
                </div>
                <p class="help">
                  <span class="icon"><i class="fa-solid fa-info" /></span>
                  <span>Select the color scheme for the WebUI.</span>
                </p>
              </div>

              <div class="field">
                <label class="label" for="random_bg">Backgrounds</label>
                <div class="control">
                  <input id="random_bg" type="checkbox" class="switch is-success" v-model="bg_enable">
                  <label for="random_bg" class="is-unselectable">&nbsp;Enable</label>
                </div>
                <p class="help">
                  <span class="icon"><i class="fa-solid fa-info" /></span>
                  <span>
                    Use random background image.
                    <NuxtLink @click="$emit('reload_bg')" class="is-bold" v-if="bg_enable">
                      Reload
                    </NuxtLink>
                    <span class="icon" v-if="isLoading"><i class="fa fa-spin fa-spinner" /></span>
                  </span>
                </p>
              </div>

              <div class="field">
                <label class="label" for="random_bg_opacity">
                  Background Visibility: (<code>{{ bg_opacity }}</code>)
                </label>
                <div class="control">
                  <input id="random_bg_opacity" style="width: 100%" type="range" v-model="bg_opacity" min="0.50"
                    max="1.00" step="0.05">
                </div>
                <p class="help">
                  <span class="icon"><i class="fa-solid fa-info" /></span>
                  <span>How visible the background image should be.</span>
                </p>
              </div>
            </div>
            <div class="column is-6">
              <div class="field">
                <label class="label" for="reduce_confirm">Reduce confirm box usage</label>
                <div class="control">
                  <input id="reduce_confirm" type="checkbox" class="switch is-success" v-model="reduce_confirm">
                  <label for="reduce_confirm" class="is-unselectable">
                    &nbsp;{{ reduce_confirm ? 'Enabled' : 'Disabled' }}
                  </label>
                </div>
                <p class="help">
                  <span class="icon"><i class="fa-solid fa-info" /></span>
                  <span>Reduce the usage of confirm boxes in the WebUI.</span>
                </p>
              </div>

              <div class="field">
                <label class="label" for="allow_toasts">Show toasts</label>
                <div class="control">
                  <input id="allow_toasts" type="checkbox" class="switch is-success" v-model="allow_toasts">
                  <label for="allow_toasts" class="is-unselectable">
                    &nbsp;{{ allow_toasts ? 'Enabled' : 'Disabled' }}
                  </label>
                </div>
                <p class="help">
                  <span class="icon"><i class="fa-solid fa-info" /></span>
                  <span class="has-text-danger is-bold">
                    Show notification toasts. If disabled, you will not see errors reported or anything else.
                  </span>
                </p>
              </div>

              <div class="field">
                <label class="label">Toasts position</label>
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

              <div class="field">
                <label class="label" for="dismiss_on_click">Dismiss toasts on click</label>
                <div class="control">
                  <input id="dismiss_on_click" type="checkbox" class="switch is-success"
                    v-model="toast_dismiss_on_click">
                  <label for="dismiss_on_click" class="is-unselectable">
                    &nbsp;{{ toast_dismiss_on_click ? 'Enabled' : 'Disabled' }}
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

<script setup>
import { useStorage } from '@vueuse/core'
import { POSITION } from 'vue-toastification'

defineProps({
  isLoading: {
    type: Boolean,
    required: true
  }
})

const bg_enable = useStorage('random_bg', true)
const bg_opacity = useStorage('random_bg_opacity', 0.85)
const selectedTheme = useStorage('theme', 'auto')
const allow_toasts = useStorage('allow_toasts', true)
const reduce_confirm = useStorage('reduce_confirm', false)
const toast_position = useStorage('toast_position', POSITION.TOP_RIGHT)
const toast_dismiss_on_click = useStorage('toast_dismiss_on_click', true)
</script>
