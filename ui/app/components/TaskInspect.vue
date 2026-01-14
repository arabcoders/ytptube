<style scoped>
code {
  color: var(--bulma-code) !important
}
</style>

<template>
  <div class="box">
    <h2 class="title is-5">Inspect Task Handler</h2>
    <form @submit.prevent="onSubmit">
      <div class="field">
        <label class="label" for="url">
          <span class="icon-text">
            <span class="icon"><i class="fas fa-link" /></span>
            <span>URL</span>
          </span>
        </label>
        <div class="control has-icons-left">
          <input id="url" v-model="url" type="url" class="input" :class="{ 'is-danger': urlError }"
            placeholder="https://..." required />
          <span class="icon is-small is-left"><i class="fa-solid fa-link" /></span>
        </div>
        <p v-if="urlError" class="help is-danger">{{ urlError }}</p>
        <p v-else class="help is-bold">
          Enter the URL of the resource you want to inspect.
        </p>
      </div>
      <div class="field">
        <label class="label" for="preset">
          <span class="icon-text">
            <span class="icon"> <i class="fa-solid fa-list" /> </span>
            <span>Preset</span>
          </span>
        </label>
        <div class="control has-icons-left">
          <div class="select is-fullwidth">
            <select id="preset" class="is-fullwidth" v-model="preset">
              <optgroup label="Custom presets" v-if="config?.presets.filter(p => !p?.default).length > 0">
                <option v-for="cPreset in filter_presets(false)" :key="cPreset.name" :value="cPreset.name">
                  {{ cPreset.name }}
                </option>
              </optgroup>
              <optgroup label="Default presets">
                <option v-for="dPreset in filter_presets(true)" :key="dPreset.name" :value="dPreset.name">
                  {{ dPreset.name }}
                </option>
              </optgroup>
            </select>
          </div>
          <span class="icon is-small is-left"><i class="fa-solid fa-list" /></span>
        </div>
        <p class="help is-bold">
          Select a preset to apply its settings during inspection. In real scenario, the preset will be based on what is
          selected when creating the task.
        </p>
      </div>
      <div class="field">
        <label class="label" for="handler">
          <span class="icon-text">
            <span class="icon"><i class="fa-solid fa-cogs" /></span>
            <span>Handler (For testing)</span>
          </span>
        </label>
        <div class="control has-icons-left">
          <input id="handler" v-model="handler" type="text" class="input" placeholder="Handler class name" />
          <span class="icon is-small is-left"><i class="fa-solid fa-cogs" /></span>
        </div>
        <p class="help is-bold">
          In real scenario, the system auto-detects the appropriate handler based on the URL. This field is for testing
          purposes only.
        </p>
      </div>
      <div class="field is-grouped is-grouped-right">
        <div class="control">
          <button class="button is-primary" type="submit" :disabled="loading">
            <span class="icon"> <i class="fas fa-search" /></span>
            <span>Inspect</span>
          </button>
        </div>
        <div class="control">
          <button class="button is-warning" type="button" @click="onReset" :disabled="loading">
            <span class="icon"> <i class="fas fa-undo" /> </span>
            <span>Reset</span>
          </button>
        </div>
      </div>
    </form>

    <Message v-if="loading" class="is-info">
      <p>
        <span class="icon-text">
          <span class="icon"><i class="fas fa-spinner fa-spin" /></span>
          <span>Inspecting.. please wait.</span>
        </span>
      </p>
    </Message>

    <div v-if="response" class="mt-4">
      <Message v-if="response.error" class="is-danger" title="Error"
        icon="fas fa-exclamation-triangle">
        <p>{{ response.error }}</p>
        <p v-if="response.message">{{ response.message }}</p>
      </Message>
      <div class="content" v-else>
        <h4>Result:</h4>
        <pre><code>{{ response }}</code></pre>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { request } from '~/utils'
import { useConfigStore } from '~/stores/ConfigStore'
import type { TaskInspectRequest, TaskInspectResponse } from '~/types/task_inspect'

const props = defineProps<{
  url?: string
  preset?: string
  handler?: string
}>()

const config = useConfigStore()
const url = ref<string>(props.url ?? '')
const preset = ref<string>(props.preset || config.app.default_preset || '')
const handler = ref<string>(props.handler ?? '')
const loading = ref<boolean>(false)
const response = ref<TaskInspectResponse | null>(null)
const urlError = ref<string>('')

// Watch for prop changes and update fields
watch(() => props.url, val => { if (val !== undefined) url.value = val })
watch(() => props.preset, val => { if (val !== undefined) preset.value = val })
watch(() => props.handler, val => { if (val !== undefined) handler.value = val })

const validateUrl = (val: string): boolean => {
  try {
    const u = new URL(val)
    return u.protocol === 'http:' || u.protocol === 'https:'
  } catch {
    return false
  }
}

async function onSubmit() {
  urlError.value = ''
  response.value = null

  if (!url.value || !validateUrl(url.value)) {
    urlError.value = 'Please enter a valid URL.'
    return
  }

  loading.value = true

  const payload: TaskInspectRequest = {
    url: url.value.trim(),
    preset: preset.value.trim() || undefined,
    handler: handler.value.trim() || undefined,
  }

  try {
    const res = await request('/api/tasks/inspect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    response.value = await res.json()
  } catch (err: any) {
    response.value = { error: err?.message || 'Unknown error' }
  } finally {
    loading.value = false
  }
}

const onReset = () => {
  url.value = props.url || ''
  preset.value = props.preset || config.app.default_preset || ''
  handler.value = props.handler || ''
  response.value = null
  urlError.value = ''
}
const filter_presets = (flag: boolean = true) => config.presets.filter(item => item.default === flag)
</script>
