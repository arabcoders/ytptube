<template>
  <main class="columns mt-2 is-multiline">
    <div class="column is-12">
      <form autocomplete="off" id="presetForm" @submit.prevent="checkInfo()">
        <div class="card">
          <div class="card-header">
            <div class="card-header-title is-text-overflow is-block">
              <span class="icon-text">
                <span class="icon"><i class="fa-solid" :class="reference ? 'fa-cog' : 'fa-plus'" /></span>
                <span>{{ reference ? 'Edit' : 'Add' }}</span>
              </span>
            </div>
            <div class="card-header-icon" v-if="reference">
              <button type="button" @click="showImport = !showImport">
                <span class="icon"><i class="fa-solid" :class="{
                  'fa-arrow-down': !showImport,
                  'fa-arrow-up': showImport,
                }" /></span>
                <span>{{ showImport ? 'Hide' : 'Show' }} import</span>
              </button>
            </div>
          </div>

          <div class="card-content">
            <div class="columns is-multiline is-mobile">
              <template v-if="showImport || !reference">
                <div class="column is-6-tablet is-12-mobile">
                  <div class="field">
                    <label class="label is-inline" for="import_string">
                      <span class="icon"><i class="fa-solid fa-file-import" /></span>
                      Import from pre-existing preset
                    </label>
                    <div class="control is-expanded">
                      <div class="select is-fullwidth">
                        <select class="is-fullwidth" v-model="selected_preset" @change="import_existing_preset">
                          <option value="" disabled>Select a preset</option>
                          <optgroup label="Custom presets" v-if="config?.presets.filter(p => !p?.default).length > 0">
                            <option v-for="item in filter_presets(false)" :key="item.name" :value="item.name">
                              {{ item.name }}
                            </option>
                          </optgroup>
                          <optgroup label="Default presets">
                            <option v-for="item in filter_presets(true)" :key="item.name" :value="item.name">
                              {{ item.name }}
                            </option>
                          </optgroup>
                        </select>
                      </div>
                    </div>
                    <span class="help is-bold">
                      <span class="icon"><i class="fa-solid fa-info" /></span>
                      <span>Select a preset to import its data. <span class="has-text-danger">Warning: This will
                          overwrite the current form data.</span></span>
                    </span>
                  </div>
                </div>

                <div class="column is-6-tablet is-12-mobile">
                  <div class="field">
                    <label class="label is-inline" for="import_string">
                      <span class="icon"><i class="fa-solid fa-file-import" /></span>
                      Import string
                    </label>
                    <div class="field-body">
                      <div class="field has-addons">
                        <div class="control is-expanded">
                          <input type="text" class="input" id="import_string" v-model="import_string"
                            autocomplete="off">
                        </div>
                        <div class="control">
                          <button class="button is-primary" :disabled="!import_string" type="button"
                            @click="importItem">
                            <span class="icon"><i class="fa-solid fa-add" /></span>
                            <span>Import</span>
                          </button>
                        </div>
                      </div>
                    </div>
                    <span class="help is-bold">
                      <span class="icon"><i class="fa-solid fa-info" /></span>
                      <span>Paste shared preset string here to import it. <span class="has-text-danger">Warning:
                          This will overwrite the current form data.</span></span>
                    </span>
                  </div>
                </div>

              </template>


              <div class="column is-12">
                <div class="field">
                  <label class="label is-inline" for="name">
                    <span class="icon"><i class="fa-solid fa-tag" /></span>
                    Name
                  </label>
                  <div class="control">
                    <input type="text" class="input" id="name" v-model="form.name" :disabled="addInProgress">
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>The name to refers to this preset of settings.</span>
                  </span>
                </div>
              </div>

              <div class="column is-6-tablet is-12-mobile">
                <div class="field">
                  <label class="label is-inline" for="folder">
                    <span class="icon"><i class="fa-solid fa-folder" /></span>
                    Default Download path
                  </label>
                  <div class="control">
                    <input type="text" class="input" id="folder" placeholder="Leave empty to use default download path"
                      v-model="form.folder" :disabled="addInProgress" list="folders">
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>Use this folder if non is given with URL. Leave empty to use default download path. Default
                      download path <code>{{ config.app.download_path }}</code>.</span>
                  </span>
                </div>
              </div>

              <div class="column is-6-tablet is-12-mobile">
                <div class="field">
                  <label class="label is-inline" for="output_template">
                    <span class="icon"><i class="fa-solid fa-file" /></span>
                    Default Output template
                  </label>
                  <div class="control">
                    <input type="text" class="input" id="output_template" :disabled="addInProgress"
                      placeholder="Leave empty to use default template." v-model="form.template">
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>Use this output template if non are given with URL. if not set, it will defaults to
                      <code>{{ config.app.output_template }}</code>.
                      For more information visit <NuxtLink href="https://github.com/yt-dlp/yt-dlp#output-template"
                        target="_blank">
                        this page</NuxtLink>.
                    </span>
                  </span>
                </div>
              </div>

              <div class="column is-6-tablet is-12-mobile">
                <div class="field">
                  <label class="label is-inline" for="cli_options">
                    <span class="icon"><i class="fa-solid fa-terminal" /></span>
                    Command options for yt-dlp
                  </label>
                  <div class="control">
                    <textarea class="textarea is-pre" v-model="form.cli" id="cli_options" :disabled="addInProgress"
                      placeholder="command options to use, e.g. --no-embed-metadata --no-embed-thumbnail" />
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>yt-dlp cli arguments. Check <NuxtLink target="_blank"
                        to="https://github.com/yt-dlp/yt-dlp?tab=readme-ov-file#general-options">this page</NuxtLink>.
                      For more info. <span class="has-text-danger">Not all options are supported some are ignored. Use
                        with caution those arguments can break yt-dlp or the frontend.</span>
                    </span>
                  </span>
                </div>
              </div>

              <div class="column is-6-tablet is-12-mobile">
                <div class="field">
                  <label class="label is-inline" for="cookies" v-tooltip="'Netscape HTTP Cookie format.'">
                    <span class="icon"><i class="fa-solid fa-cookie" /></span>
                    Cookies
                  </label>
                  <div class="control">
                    <textarea class="textarea is-pre" id="cookies" v-model="form.cookies" :disabled="addInProgress"
                      placeholder="Leave empty to use default cookies" />
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>Use this cookies if non are given with the URL. Use the <NuxtLink target="_blank"
                        to="https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp">
                        Recommended addon</NuxtLink> by yt-dlp to export cookies. The cookies MUST be in Netscape HTTP
                      Cookie format.
                    </span>
                  </span>
                </div>
              </div>

              <div class="column">
                <div class="field">
                  <label class="label is-inline" for="description">
                    <span class="icon"><i class="fa-solid fa-comment" /></span>
                    Description
                  </label>
                  <div class="control">
                    <textarea class="textarea" id="description" v-model="form.description" :disabled="addInProgress"
                      placeholder="Extras instructions for users to follow" />
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>Use this field to help users to understand how to use this preset.</span>
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div class="card-footer">
            <div class="card-footer-item">
              <button class="button is-fullwidth is-primary" :disabled="addInProgress" type="submit"
                :class="{ 'is-loading': addInProgress }" form="presetForm">
                <span class="icon"><i class="fa-solid fa-save" /></span>
                <span>Save</span>
              </button>
            </div>
            <div class="card-footer-item">
              <button class="button is-fullwidth is-danger" @click="emitter('cancel')" :disabled="addInProgress"
                type="button">
                <span class="icon"><i class="fa-solid fa-times" /></span>
                <span>Cancel</span>
              </button>
            </div>
          </div>
        </div>
      </form>
    </div>

    <datalist id="folders" v-if="config?.folders">
      <option v-for="dir in config.folders" :key="dir" :value="dir" />
    </datalist>
  </main>
</template>

<script setup lang="ts">
import { useStorage } from '@vueuse/core'
import type { Preset, PresetImport } from '~/types/presets'

const emitter = defineEmits<{
  (event: 'cancel'): void
  (event: 'submit', payload: { reference: string | null, preset: Preset }): void
}>()

const props = defineProps<{
  reference?: string | null
  preset: Partial<Preset>
  addInProgress?: boolean
  presets?: Preset[]
}>()

const config = useConfigStore()
const toast = useNotification()
const form = reactive<Preset>(JSON.parse(JSON.stringify(props.preset)))
const import_string = ref<string>('')
const showImport = useStorage<boolean>('showImport', false)
const selected_preset = ref<string>('')

const checkInfo = async (): Promise<void> => {
  for (const key of ['name']) {
    if (!form[key as keyof Preset]) {
      toast.error(`The ${key} field is required.`)
      return
    }
  }

  if (form.cli && '' !== form.cli) {
    const options = await convertOptions(form.cli)
    if (null === options) {
      return
    }
    form.cli = form.cli.trim()
  }

  const copy: Preset = JSON.parse(JSON.stringify(form))
  let usedName = false
  const name = String(form.name).trim().toLowerCase()

  props.presets?.forEach(p => {
    if (p.id === props.reference) {
      return
    }
    if (String(p.name).toLowerCase() === name) {
      usedName = true
    }
  })

  if (usedName) {
    toast.error('The preset name is already in use.')
    return
  }

  for (const key in copy) {
    const val = copy[key as keyof Preset]
    if ('string' === typeof val) {
      (copy as any)[key] = val.trim()
    }
  }

  emitter('submit', { reference: toRaw(props.reference ?? null), preset: toRaw(copy) })
}

const convertOptions = async (args: string): Promise<Record<string, any> | null> => {
  try {
    const response = await convertCliOptions(args)

    if (response.output_template) {
      form.template = response.output_template
    }

    if (response.download_path) {
      form.folder = response.download_path
    }

    return response.opts as Record<string, any>
  } catch (e: any) {
    toast.error(e.message)
    return null
  }
}

const importItem = async (): Promise<void> => {
  const val = import_string.value.trim()
  if (!val) {
    toast.error('The import string is required.')
    return
  }

  try {
    const item = decode(val) as PresetImport

    if (!item?._type || 'preset' !== item._type) {
      toast.error(`Invalid import string. Expected type 'preset', got '${item._type ?? 'unknown'}'.`)
      return
    }

    if (item.name) {
      form.name = item.name
    }

    if (item.cli) {
      form.cli = item.cli
    }

    if (item.template) {
      form.template = item.template
    }

    if (item.folder) {
      form.folder = item.folder
    }

    if (item.description) {
      form.description = item.description
    }

    import_string.value = ''
    showImport.value = false
  } catch (e: any) {
    console.error(e)
    toast.error(`Failed to parse. ${e.message}`)
  }
}

const filter_presets = (flag = true): Preset[] => config.presets.filter(item => item.default === flag)

const import_existing_preset = async (): Promise<void> => {
  if (!selected_preset.value) {
    return
  }

  const preset = config.presets.find(p => p.name === selected_preset.value)
  if (!preset) {
    toast.error('Preset not found.')
    return
  }

  form.cli = preset.cli || ''
  form.folder = preset.folder || ''
  form.template = preset.template || ''
  form.cookies = preset.cookies || ''
  form.description = preset.description || ''

  await nextTick()
  selected_preset.value = ''
}
</script>
