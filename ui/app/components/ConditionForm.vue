<template>
  <main class="columns mt-2 is-multiline">
    <div class="column is-12">
      <form autocomplete="off" id="addForm" @submit.prevent="checkInfo()">
        <div class="card is-flex is-full-height is-flex-direction-column">
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

          <div class="card-content is-flex-grow-1">

            <div class="columns is-multiline is-mobile">

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

              <div class="column is-12">
                <div class="field">
                  <label class="label is-inline" for="name">
                    <span class="icon"><i class="fa-solid fa-tag" /></span>
                    Name
                  </label>
                  <div class="control">
                    <input type="text" class="input" id="name" v-model="form.name" :disabled="addInProgress"
                      placeholder="For the problematic channel or video name.">
                  </div>
                  <span class="help is-bold">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>The name that refers to this condition.</span>
                  </span>
                </div>
              </div>

              <div class="column is-12">
                <div class="field">
                  <label class="label is-inline" for="filter">
                    <span class="icon"><i class="fa-solid fa-filter" /></span>
                    Condition Filter
                    <template v-if="!addInProgress || form.filter">
                      - <NuxtLink @click="test_data.show = true" class="is-bold">
                        Test filter logic
                      </NuxtLink>
                    </template>
                  </label>
                  <div class="control">
                    <input type="text" class="input" id="filter" v-model="form.filter" :disabled="addInProgress"
                      placeholder="availability = 'needs_auth' & channel_id = 'channel_id'">
                  </div>
                  <span class="help is-bold">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>yt-dlp <code>--match-filters</code> logic with <code>OR</code>, <code>||</code>
                      support.</span>
                  </span>
                </div>
              </div>

              <div class="column is-12">
                <div class="field">
                  <label class="label is-unselectable" for="cli_options">
                    <span class="icon"><i class="fa-solid fa-terminal" /></span>
                    <span>Command options for yt-dlp</span>
                  </label>
                  <TextareaAutocomplete id="cli_options" v-model="form.cli" :options="ytDlpOpt"
                    :disabled="addInProgress" />
                  <span class="help is-bold">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>
                      <NuxtLink @click="showOptions = true">View all options</NuxtLink>. Not all options are
                      supported <NuxtLink target="_blank"
                        to="https://github.com/arabcoders/ytptube/blob/master/app/library/Utils.py#L26">some
                        are ignored</NuxtLink>. Use with caution.
                    </span>
                  </span>
                </div>
              </div>

              <div class="column is-12">
                <div class="field">
                  <label class="label is-inline">
                    <span class="icon"><i class="fa-solid fa-plus-square" /></span>
                    Extra Options
                  </label>
                  <div class="content">
                    <div v-if="form.extras && Object.keys(form.extras).length > 0" class="mb-3">
                      <div v-for="(value, key) in form.extras" :key="key" class="field is-grouped mb-2">
                        <div class="control">
                          <input type="text" class="input" :value="key" @input="updateExtraKey($event, key)"
                            :disabled="addInProgress" placeholder="key_name">
                        </div>
                        <div class="control is-expanded">
                          <input type="text" class="input" :value="value" @input="updateExtraValue(key, $event)"
                            :disabled="addInProgress" placeholder="value">
                        </div>
                        <div class="control">
                          <button type="button" class="button is-danger" @click="removeExtra(key)"
                            :disabled="addInProgress">
                            <span class="icon"><i class="fa-solid fa-times" /></span>
                          </button>
                        </div>
                      </div>
                    </div>

                    <div class="field is-grouped">
                      <div class="control">
                        <input type="text" class="input" v-model="newExtraKey" :disabled="addInProgress"
                          placeholder="new_key" @keyup.enter="addExtra">
                      </div>
                      <div class="control is-expanded">
                        <input type="text" class="input" v-model="newExtraValue" :disabled="addInProgress"
                          placeholder="new_value" @keyup.enter="addExtra">
                      </div>
                      <div class="control">
                        <button type="button" class="button is-primary" @click="addExtra"
                          :disabled="addInProgress || !newExtraKey || !newExtraValue">
                          <span class="icon"><i class="fa-solid fa-plus" /></span>
                          <span>Add</span>
                        </button>
                      </div>
                    </div>
                  </div>
                  <span class="help is-bold">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>
                      For advanced users only. This feature is meant to be expanded later. the only supported key right
                      now. <code>ignore_download</code> with value of <code>true</code>. Keys must be lowercase with
                      underscores (e.g., custom_field).</span>
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div class="card-footer mt-auto">
            <div class="card-footer-item">
              <div class="card-footer-item">
                <button class="button is-fullwidth is-primary" :disabled="addInProgress" type="submit"
                  :class="{ 'is-loading': addInProgress }" form="addForm">
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

    <div v-if="test_data.show" class="column is-12">
      <Modal @close="test_data.show = false" title="Test condition">
        <form autocomplete="off" id="testCondition" @submit.prevent="run_test()">
          <div class="card">
            <div class="card-content">
              <div class="field">
                <label class="label is-inline" for="url">
                  <span class="icon"><i class="fa-solid fa-link" /></span>
                  URL
                </label>
                <div class="field-body">
                  <div class="field is-grouped">
                    <div class="control is-expanded">
                      <input type="url" class="input " id="url" v-model="test_data.url"
                        :disabled="test_data.in_progress" placeholder="https://..." required>
                    </div>
                    <div class="control">
                      <button class="button is-primary" type="submit" :disabled="test_data.in_progress"
                        :class="{ 'is-loading': test_data.in_progress }">
                        <span class="icon"><i class="fa-solid fa-play" /></span>
                        <span>Test</span>
                      </button>
                    </div>
                  </div>
                </div>
                <span class="help is-bold">
                  <span class="icon"><i class="fa-solid fa-info" /></span>
                  <span>The url to test the filter against.</span>
                </span>
              </div>

              <div class="field">
                <label class="label is-inline" for="filter">
                  <span class="icon"><i class="fa-solid fa-filter" /></span>
                  Condition Filter
                </label>
                <div class="control">
                  <input type="text" class="input" id="filter" v-model="form.filter" :disabled="test_data.in_progress"
                    placeholder="availability = 'needs_auth' & channel_id = 'channel_id'" required>
                </div>
                <span class="help is-bold">
                  <span class="icon"><i class="fa-solid fa-info" /></span>
                  <span>yt-dlp <code>--match-filters</code> logic with <code>OR</code>, <code>||</code>
                    support.</span>
                </span>
              </div>

              <div class="field">
                <span class="is-bold" :class="{
                  'has-text-success': true === logic_test,
                  'has-text-danger': false === logic_test,
                }">
                  <span class="icon"><i class="fa-solid" :class="{
                    'fa-check': true === logic_test,
                    'fa-xmark': false === logic_test,
                    'fa-question': null === logic_test,
                  }" /></span>
                  Filter Status:
                  <template v-if="null === test_data?.data?.status">Not tested</template>
                  <template v-else>{{ logic_test ? 'Matched' : 'Not matched' }}</template>
                </span>
              </div>
              <div class="field">
                <pre style="height:60vh;"><code>{{ show_data() }}</code></pre>
              </div>
            </div>
          </div>
        </form>
      </Modal>
    </div>
    <Modal v-if="showOptions" @close="showOptions = false" :contentClass="'modal-content-max'">
      <YTDLPOptions />
    </Modal>
  </main>
</template>

<script setup lang="ts">
import { useStorage } from '@vueuse/core'
import TextareaAutocomplete from '~/components/TextareaAutocomplete.vue'
import type { AutoCompleteOptions } from '~/types/autocomplete';
import type { ConditionItem, ImportedConditionItem } from '~/types/conditions'

const emitter = defineEmits<{
  (e: 'cancel'): void
  (e: 'submit', payload: { reference: string | null | undefined, item: ConditionItem }): void
}>()

const props = defineProps<{
  reference?: string | null
  item: ConditionItem
  addInProgress?: boolean
}>()

const toast = useNotification()
const showImport = useStorage('showImport', false)
const box = useConfirm()
const config = useConfigStore()

const form = reactive<ConditionItem>(JSON.parse(JSON.stringify(props.item)))
const import_string = ref('')
const newExtraKey = ref('')
const newExtraValue = ref('')
const test_data = ref<{
  show: boolean,
  url: string,
  in_progress: boolean,
  changed: boolean,
  data: { status: boolean | null, data: Record<string, any> }
}>({ show: false, url: '', in_progress: false, changed: false, data: { status: null, data: {} } })
const showOptions = ref<boolean>(false)
const ytDlpOpt = ref<AutoCompleteOptions>([])

// Initialize extras if not present
if (!form.extras) {
  form.extras = {}
}

watch(() => config.ytdlp_options, newOptions => ytDlpOpt.value = newOptions
  .filter(opt => !opt.ignored)
  .flatMap(opt => opt.flags.filter(flag => flag.startsWith('--'))
    .map(flag => ({ value: flag, description: opt.description || '' }))),
  { immediate: true }
)

watch(() => form.filter, () => test_data.value.changed = true)

const checkInfo = async (): Promise<void> => {
  const required: (keyof ConditionItem)[] = ['name', 'filter']

  for (const key of required) {
    if (!form[key]) {
      toast.error(`The ${key} field is required.`)
      return
    }
  }

  if ((!form.cli || '' === form.cli.trim()) && Object.keys(form.extras).length < 1) {
    toast.error('Either command options for yt-dlp or at least one extra option is required.')
    return
  }

  if (form.cli && '' !== form.cli.trim()) {
    const options = await convertOptions(form.cli)
    if (options === null) {
      return
    }
    form.cli = form.cli.trim()
  }

  const copy: ConditionItem = JSON.parse(JSON.stringify(form))

  for (const key in copy) {
    if (typeof (copy as any)[key] !== 'string') {
      continue
    }
    (copy as any)[key] = (copy as any)[key].trim()
  }

  emitter('submit', { reference: toRaw(props.reference), item: toRaw(copy) })
}

const convertOptions = async (args: string): Promise<any | null> => {
  try {
    const response = await convertCliOptions(args)
    return response.opts
  } catch (e: any) {
    toast.error(e.message)
  }
  return null
}

const run_test = async (): Promise<void> => {
  if (!test_data.value.url) {
    toast.error('The URL is required for testing.', { force: true })
    return
  }

  try {
    new URL(test_data.value.url)
  } catch {
    toast.error('The URL is invalid.', { force: true })
    return
  }

  test_data.value.in_progress = true
  test_data.value.data.status = false

  try {
    const response = await request('/api/conditions/test', {
      method: 'POST',
      body: JSON.stringify({ url: test_data.value.url, condition: form.filter })
    })

    const json = await response.json()
    if (!response.ok) {
      toast.error(json.message || json.error || 'Unknown error', { force: true })
      return
    }

    test_data.value.data = json
    test_data.value.changed = false
  } catch (error: any) {
    toast.error(`Failed to test condition. ${error.message}`)
  } finally {
    test_data.value.in_progress = false
  }
}

const importItem = async (): Promise<void> => {
  const val = import_string.value.trim()
  if (!val) {
    toast.error('The import string is required.')
    return
  }

  try {
    const item = decode(val) as ImportedConditionItem

    if (!item?._type || item._type !== 'condition') {
      toast.error(`Invalid import string. Expected type 'condition', got '${item._type ?? 'unknown'}'.`)
      return
    }

    if ((form.filter || form.cli || Object.keys(form.extras).length > 0) && !(await box.confirm('Overwrite the current form fields?', true))) {
      return
    }

    if (item.name) {
      form.name = item.name
    }

    if (item.filter) {
      form.filter = item.filter
    }

    if (item.cli) {
      form.cli = item.cli
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

const show_data = (): string => {
  if (!test_data.value.data?.data || Object.keys(test_data.value.data.data).length === 0) {
    return 'No data to show.'
  }

  return JSON.stringify(test_data.value.data.data, null, 2)
}

const logic_test = computed(() => {
  if (Object.keys(test_data.value.data?.data ?? {}).length < 1) {
    return null
  }

  if (!test_data.value.changed) {
    return test_data.value.data.status
  }

  try {
    const st = match_str(form.filter, test_data.value.data.data)
    console.log('Logic test:', st, form.filter, test_data.value.data.data)
    return st
  } catch (e: any) {
    console.error(e)
    return false
  }
})

const validateKey = (key: string): boolean => /^[a-z][a-z0-9_]*$/.test(key)

const parseValue = (value: string): string | number | boolean => {
  if (!isNaN(Number(value)) && !isNaN(parseFloat(value))) {
    return Number(value)
  }

  if ('true' === value.toLowerCase()) {
    return true
  }
  if ('false' === value.toLowerCase()) {
    return false
  }

  return value
}

const addExtra = (): void => {
  const key = newExtraKey.value.trim()
  const value = newExtraValue.value.trim()

  if (!key || !value) {
    toast.error('Both key and value are required.')
    return
  }

  if (!validateKey(key)) {
    toast.error('Key must be lower_case.')
    return
  }

  if (form.extras[key]) {
    toast.error(`Key '${key}' already exists.`)
    return
  }

  form.extras[key] = parseValue(value)
  newExtraKey.value = ''
  newExtraValue.value = ''
}

const removeExtra = (key: string): void => {
  const { [key]: _, ...rest } = form.extras
  form.extras = rest
}

const updateExtraKey = (event: Event, oldKey: string): void => {
  const target = event.target as HTMLInputElement
  const newKey = target.value.trim()

  if (!newKey) {
    return
  }

  if (!validateKey(newKey)) {
    toast.error('Key must be lowercase and contain only letters, numbers, and underscores.')
    target.value = oldKey
    return
  }

  if (newKey !== oldKey) {
    if (form.extras[newKey]) {
      toast.error(`Key '${newKey}' already exists.`)
      target.value = oldKey
      return
    }

    const value = form.extras[oldKey]
    const { [oldKey]: _, ...rest } = form.extras
    form.extras = { ...rest, [newKey]: value }
  }
}

const updateExtraValue = (key: string, event: Event): void => {
  const target = event.target as HTMLInputElement
  const value = target.value.trim()
  form.extras[key] = value ? parseValue(value) : ''
}
</script>
