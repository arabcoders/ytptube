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
          <div class="field">
            <label class="label" for="random_bg">Color scheme</label>
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
              <span>Use random background image.</span>
            </p>
          </div>

          <div class="field">
            <label class="label" for="random_bg_opacity">
              Background Visibility: (<code>{{ bg_opacity }}</code>)
            </label>
            <div class="control">
              <input id="random_bg_opacity" style="width: 100%" type="range" v-model="bg_opacity" min="0.50" max="1.00"
                step="0.05">
            </div>
            <p class="help">
              <span class="icon"><i class="fa-solid fa-info" /></span>
              <span>How visible the background image should be.</span>
            </p>
          </div>

          <div class="field" v-if="bg_enable">
            <label class="label" for="random_bg_opacity">
              Reload the currently displayed background image.
            </label>
            <div class="control">
              <button class="button is-info" @click="$emit('reload_bg')" :class="{ 'is-loading': isLoading }"
                :disabled="isLoading">
                <span class="icon-text">
                  <span class="icon"><i class="fas fa-sync-alt" /></span>
                  <span>Reload</span>
                </span>
              </button>
            </div>
            <p class="help">
              <span class="icon"><i class="fa-solid fa-info" /></span>
              <span>Change the displayed picture.</span>
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>


<script setup>

import { useStorage } from '@vueuse/core'

defineProps({
  isLoading: {
    type: Boolean,
    required: true
  }
})

const bg_enable = useStorage('random_bg', true)
const bg_opacity = useStorage('random_bg_opacity', 0.85)
const selectedTheme = useStorage('theme', 'auto')

</script>
