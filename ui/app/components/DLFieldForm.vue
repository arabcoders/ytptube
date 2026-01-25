<template>
  <main class="columns mt-2 is-multiline">
    <div class="column is-12">
      <form autocomplete="off" id="dlFieldForm" @submit.prevent="checkInfo">
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
            <div class="columns is-multiline">
              <div class="column is-12" v-if="showImport || !reference">
                <label class="label is-inline" for="import_string">
                  <span class="icon"><i class="fa-solid fa-file-import" /></span>
                  Import string
                </label>

                <div class="field has-addons">
                  <div class="control is-expanded">
                    <input type="text" class="input" id="import_string" v-model="import_string" autocomplete="off">
                  </div>

                  <div class="control">
                    <button class="button is-primary" :disabled="!import_string" type="button" @click="importItem">
                      <span class="icon"><i class="fa-solid fa-add" /></span>
                      <span>Import</span>
                    </button>
                  </div>
                </div>
                <span class="help">
                  <span class="icon"><i class="fa-solid fa-info" /></span>
                  <span>You can use this field to populate the data, using shared string.</span>
                </span>
              </div>

              <div class="column is-6 is-12-mobile">
                <div class="field">
                  <label class="label">
                    <span class="icon"><i class="fas fa-font" /></span>
                    <span>Field Name</span>
                  </label>
                  <input type="text" v-model="form.name" class="input" :disabled="addInProgress" />
                  <span class="help is-bold">
                    The name of the field, it will be shown in the UI.
                  </span>
                </div>
              </div>
              <div class="column is-6 is-12-mobile">
                <div class="field">
                  <label class="label">
                    <span class="icon"><i class="fas fa-info-circle" /></span>
                    <span>Field Description</span>
                  </label>
                  <input type="text" v-model="form.description" class="input" :disabled="addInProgress" />
                  <span class="help is-bold">
                    A short description of the field, it will be shown in the UI.
                  </span>
                </div>
              </div>

              <div class="column is-6 is-12-mobile">
                <div class="field">
                  <label class="label">
                    <span class="icon"><i class="fas fa-cog" /></span>
                    <span>Field Type</span>
                  </label>
                  <div class="select is-fullwidth" :class="{ 'is-loading': addInProgress }">
                    <select v-model="form.kind" :disabled="addInProgress" class="is-capitalized">
                      <option v-for="kind in fieldTypes" :key="`kind-${kind}`" :value="kind" v-text="kind" />
                    </select>
                  </div>
                  <span class="help is-bold">
                    Field Type. String is a single line input, Text is a multi-line input, Bool is a checkbox.
                  </span>
                </div>
              </div>

              <div class="column is-6 is-12-mobile">
                <div class="field">
                  <label class="label">
                    <span class="icon"><i class="fas fa-terminal" /></span>
                    <span>Associated yt-dlp option</span>
                  </label>
                  <InputAutocomplete v-model="form.field" :options="ytDlpOptions" :disabled="addInProgress"
                    placeholder="Type or select a yt-dlp option" :multiple="false" :openOnFocus="true" />
                  <span class="help is-bold">
                    The long form of yt-dlp option name, e.g. <code>--no-overwrites</code> not <code>-w</code>.
                  </span>
                </div>
              </div>


              <div class="column is-6 is-12-mobile">
                <div class="field">
                  <label class="label">
                    <span class="icon"><i class="fas fa-sort-numeric-up" /></span>
                    <span>Field Order</span>
                  </label>
                  <input type="number" v-model.number="form.order" class="input" :disabled="addInProgress" />
                  <span class="help is-bold">
                    The order of the field, used to sort the fields in the UI. Lower numbers will appear first.
                  </span>
                </div>
              </div>

              <div class="column is-6 is-12-mobile">
                <div class="field">
                  <label class="label">
                    <span class="icon"><i class="fas fa-image" /></span>
                    <span>Field Icon</span>
                  </label>
                  <input type="text" v-model="form.icon" class="input" :disabled="addInProgress" />
                  <span class="help is-bold">
                    The icon of the field, must be from <NuxtLink href="https://fontawesome.com/search?ic=free&o=r"
                      target="_blank">
                      font-awesome</NuxtLink> icon. e.g. <code>fa-solid fa-image</code>. Leave empty for no icon.
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div class="card-footer mt-auto">
            <div class="card-footer-item">
              <div class="card-footer-item">
                <button class="button is-fullwidth is-primary" :disabled="addInProgress" type="submit"
                  :class="{ 'is-loading': addInProgress }" form="dlFieldForm">
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
        </div>
      </form>
    </div>
  </main>
</template>

<script setup lang="ts">
import { useStorage } from '@vueuse/core'
import InputAutocomplete from '~/components/InputAutocomplete.vue'
import type { AutoCompleteOptions } from '~/types/autocomplete'
import type { DLField } from '~/types/dl_fields'
import type { ImportedItem } from '~/types'
import { decode } from '~/utils'
import { useConfirm } from '~/composables/useConfirm'

const emitter = defineEmits<{
  (e: 'cancel'): void
  (e: 'submit', payload: { reference: number | null | undefined, item: DLField }): void
}>()

const props = defineProps<{
  reference?: number | null
  item: DLField
  addInProgress?: boolean
}>()

const toast = useNotification()
const box = useConfirm()
const config = useConfigStore()

const fieldTypes = ['string', 'text', 'bool'] as const

const form = reactive<DLField>(JSON.parse(JSON.stringify(props.item)))
const ytDlpOptions = ref<AutoCompleteOptions>([])
const showImport = useStorage('showDlFieldsImport', false)
const import_string = ref('')

if (!form.extras) {
  form.extras = {}
}

if (!form.kind) {
  form.kind = 'string'
}

if (!form.description) {
  form.description = ''
}

if (!form.value) {
  form.value = ''
}

if (!form.icon) {
  form.icon = ''
}

if (!form.order) {
  form.order = 1
}

watch(() => config.ytdlp_options, newOptions => ytDlpOptions.value = newOptions
  .filter(opt => !opt.ignored)
  .flatMap(opt => opt.flags.filter(flag => flag.startsWith('--'))
    .map(flag => ({ value: flag, description: opt.description || '' }))),
  { immediate: true }
)

const importItem = async (): Promise<void> => {
  const val = import_string.value.trim()
  if (!val) {
    toast.error('The import string is required.')
    return
  }

  try {
    const item = decode(val) as DLField & ImportedItem

    if (!item._type || item._type !== 'dl_field') {
      toast.error(`Invalid import string. Expected type 'dl_field', got '${item._type ?? 'unknown'}'.`)
      return
    }

    if ((form.name || form.field || form.description) && !(await box.confirm('Overwrite the current form fields?'))) {
      return
    }

    if (item.name) {
      form.name = item.name
    }

    if (item.field) {
      form.field = item.field
    }

    if (item.description !== undefined) {
      form.description = item.description
    }

    if (item.kind) {
      form.kind = item.kind
    }

    if (item.icon !== undefined) {
      form.icon = item.icon
    }

    if (item.order !== undefined) {
      form.order = item.order
    }

    if (item.value !== undefined) {
      form.value = item.value
    }

    if (item.extras) {
      form.extras = { ...item.extras }
    }

    import_string.value = ''
    showImport.value = false
  } catch (e: any) {
    console.error(e)
    toast.error(`Failed to parse import string. ${e.message}`)
  }
}

const checkInfo = (): void => {
  const required: (keyof DLField)[] = ['name', 'field', 'kind', 'description']

  for (const key of required) {
    if (!form[key]) {
      toast.error(`The ${key} field is required.`)
      return
    }
  }

  if (!form.order || form.order < 1) {
    toast.error('Order must be a positive number.')
    return
  }

  if (!fieldTypes.includes(form.kind)) {
    toast.error(`Invalid field type: ${form.kind}`)
    return
  }

  if (!/^--[a-zA-Z0-9-]+$/.test(form.field)) {
    toast.error('Invalid field format, it must start with "--" and contain no spaces.')
    return
  }

  const copy: DLField = JSON.parse(JSON.stringify(form))

  const entries = copy as unknown as Record<string, unknown>
  for (const key in entries) {
    if ('string' !== typeof entries[key]) {
      continue
    }
    entries[key] = entries[key].trim()
  }

  emitter('submit', { reference: toRaw(props.reference), item: toRaw(copy) })
}
</script>
