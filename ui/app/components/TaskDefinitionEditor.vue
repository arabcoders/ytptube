<template>
  <section class="card">
    <header class="card-header">
      <p class="card-header-title">
        <span class="icon-text">
          <span class="icon"><i class="fa-solid fa-pen-ruler" /></span>
          <span>{{ headerTitle }}</span>
        </span>
      </p>
      <div class="card-header-icon is-flex is-align-items-center">
        <button type="button" class="button is-small" @click="() => showImport = !showImport" :disabled="isBusy">
          <span class="icon"><i class="fa-solid"
              :class="{ 'fa-arrow-down': !showImport, 'fa-arrow-up': showImport }" /></span>
          <span>{{ showImport ? 'Hide import' : 'Show import' }}</span>
        </button>
        <div class="buttons has-addons ml-2">
          <button type="button" class="button is-small"
            :class="{ 'is-primary': 'gui' === mode, 'is-light': 'gui' !== mode }" @click="() => switchMode('gui')"
            :disabled="!guiSupported || isBusy">
            <span class="icon"><i class="fa-solid fa-sliders" /></span>
            <span>GUI</span>
          </button>
          <button type="button" class="button is-small"
            :class="{ 'is-primary': 'advanced' === mode, 'is-light': 'advanced' !== mode }"
            @click="() => switchMode('advanced')" :disabled="isBusy">
            <span class="icon"><i class="fa-solid fa-code" /></span>
            <span>Advanced</span>
          </button>
        </div>
      </div>
    </header>

    <div class="card-content">
      <div class="columns is-multiline" v-if="showImport">
        <div class="column is-12" v-if="availableDefinitions.length">
          <div class="field">
            <label class="label is-inline">
              <span class="icon"><i class="fa-solid fa-diagram-project" /></span>
              Import from existing
            </label>
            <div class="control">
              <div class="select is-fullwidth">
                <select v-model="selectedExisting" :disabled="isBusy" @change="importExisting">
                  <option value="">Select a definition</option>
                  <option v-for="item in availableDefinitions" :key="item.id" :value="item.id">
                    {{ item.name || item.id }}
                  </option>
                </select>
              </div>
            </div>
            <p class="help is-bold">
              <span class="icon-text">
                <span class="icon"><i class="fa-solid fa-info" /></span>
                <span>Loads an existing definition into the editor. Changes are not saved until you submit.</span>
              </span>
            </p>
          </div>
        </div>

        <div class="column is-12">
          <div class="field">
            <label class="label is-inline">
              <span class="icon"><i class="fa-solid fa-file-import" /></span>
              Import string
            </label>
            <div class="field has-addons">
              <div class="control is-expanded">
                <input class="input" type="text" v-model="importString" :disabled="isBusy" autocomplete="off">
              </div>
              <div class="control">
                <button class="button is-primary" type="button" @click="importFromString"
                  :disabled="isBusy || !importString.trim()">
                  <span class="icon"><i class="fa-solid fa-file-import" /></span>
                  <span>Import</span>
                </button>
              </div>
            </div>
            <p class="help is-bold">
              <span class="icon-text">
                <span class="icon"><i class="fa-solid fa-info" /></span>
                <span>Pastes a shared task definition string. Importing replaces the current editor contents.</span>
              </span>
            </p>
          </div>
        </div>
      </div>

      <Message v-if="!guiSupported" message_class="is-warning">
        <p>
          <span>
            <span class="icon"><i class="fa-solid fa-triangle-exclamation" /></span>
            <span>This task definition uses features that cannot be represented with the visual editor. You can still
              update it
              via the advanced view.</span>
          </span>
        </p>
      </Message>

      <div v-if="'gui' === mode">
        <div class="columns is-multiline">
          <div class="column is-6">
            <div class="field">
              <label class="label is-inline">
                <span class="icon"><i class="fa-solid fa-heading" /></span>
                Name
              </label>
              <div class="control">
                <input class="input" type="text" v-model="guiState.name" :disabled="isBusy">
              </div>
              <p class="help is-bold">
                <span class="icon"><i class="fa-solid fa-info" /></span>
                <span>Human readable label for this definition.</span>
              </p>
            </div>
          </div>

          <div class="column is-3">
            <div class="field">
              <label class="label is-inline">
                <span class="icon"><i class="fa-solid fa-sort-numeric-down" /></span>
                Priority
              </label>
              <div class="control">
                <input class="input" type="number" min="0" v-model.number="guiState.priority" :disabled="isBusy">
              </div>
              <p class="help is-bold">
                <span class="icon"><i class="fa-solid fa-info" /></span>
                <span>Lower values are evaluated first.</span>
              </p>
            </div>
          </div>

          <div class="column is-12">
            <div class="field">
              <label class="label is-inline">
                <span class="icon"><i class="fa-solid fa-filter" /></span>
                Match patterns
              </label>
              <div class="control">
                <textarea class="textarea" rows="3" v-model="guiState.matchText" :disabled="isBusy"
                  placeholder="https://example.com/*&#10;https://example.org/channel/*" />
              </div>
              <p class="help is-bold">
                <span class="icon"><i class="fa-solid fa-info" /></span>
                <span>One glob per line. Regex or object based rules are only supported in advanced mode.</span>
              </p>
            </div>
          </div>

          <div class="column is-6">
            <div class="field">
              <label class="label is-inline">
                <span class="icon"><i class="fa-solid fa-gears" /></span>
                Engine
              </label>
              <div class="control">
                <div class="select is-fullwidth">
                  <select v-model="guiState.engineType" :disabled="isBusy">
                    <option value="httpx">HTTPX</option>
                    <option value="selenium">Selenium</option>
                  </select>
                </div>
              </div>
              <p class="help is-bold">
                <span class="icon"><i class="fa-solid fa-info" /></span>
                <span>Choose the fetch engine. You should use HTTPX when possible.</span>
              </p>
            </div>
          </div>

          <div class="column is-6" v-if="'selenium' === guiState.engineType">
            <div class="field">
              <label class="label is-inline">
                <span class="icon"><i class="fa-solid fa-plug" /></span>
                Selenium Hub URL (Required)
              </label>
              <div class="control">
                <input class="input" type="url" v-model="guiState.engineUrl" :disabled="isBusy"
                  placeholder="http://selenium:4444/wd/hub">
              </div>
              <p class="help is-bold">
                <span class="icon"><i class="fa-solid fa-info" /></span>
                <span>Remote webdriver endpoint.</span>
              </p>
            </div>
          </div>

          <div class="column is-6">
            <div class="field">
              <label class="label is-inline">
                <span class="icon"><i class="fa-solid fa-server" /></span>
                Request Method
              </label>
              <div class="control">
                <div class="select is-fullwidth">
                  <select v-model="guiState.requestMethod" :disabled="isBusy">
                    <option value="GET">GET</option>
                    <option value="POST">POST</option>
                  </select>
                </div>
              </div>
              <p class="help is-bold">
                <span class="icon"><i class="fa-solid fa-info" /></span>
                <span>HTTP method to use when fetching the page.</span>
              </p>
            </div>
          </div>

          <div class="column is-6">
            <div class="field">
              <label class="label is-inline">
                <span class="icon"><i class="fa-solid fa-link" /></span>
                Request URL (optional)
              </label>
              <div class="control">
                <input class="input" type="url" v-model="guiState.requestUrl" :disabled="isBusy"
                  placeholder="https://example.com/feed">
              </div>
              <p class="help is-bold">
                <span class="icon"><i class="fa-solid fa-info" /></span>
                <span>Overrides the URL used to fetch the page. Useful for sites with separate feed URLs.</span>
              </p>
            </div>
          </div>

          <div class="column is-12">
            <article class="message is-info" v-if="guiLimitations">
              <div class="message-body">
                {{ guiLimitations }}
              </div>
            </article>
          </div>

          <div class="column is-12">
            <div>
              <h4 class="title is-6">Container selector</h4>
              <div class="columns is-multiline">
                <div class="column is-4">
                  <div class="field">
                    <label class="label is-inline">
                      <span class="icon"><i class="fa-solid fa-list" /></span>
                      Type
                    </label>
                    <div class="control">
                      <div class="select is-fullwidth">
                        <select v-model="guiState.containerType" :disabled="isBusy">
                          <option value="css">CSS</option>
                          <option value="xpath">XPath</option>
                          <option value="jsonpath">JSONPath</option>
                        </select>
                      </div>
                    </div>
                  </div>
                </div>
                <div class="column is-8">
                  <div class="field">
                    <label class="label is-inline">
                      <span class="icon"><i class="fa-solid fa-crosshairs" /></span>
                      Selector / Expression
                    </label>
                    <div class="control">
                      <input class="input" type="text" v-model="guiState.containerSelector" :disabled="isBusy"
                        placeholder="div.card">
                    </div>
                  </div>
                </div>
              </div>

              <h4 class="title is-6 mt-4">Extracted fields</h4>
              <div class="field">
                <button class="button is-small is-primary" type="button" @click="addField" :disabled="isBusy">
                  <span class="icon"><i class="fa-solid fa-plus" /></span>
                  <span>Add field</span>
                </button>
              </div>

              <div class="table-container">
                <table class="table is-fullwidth is-hoverable is-striped">
                  <thead>
                    <tr class="is-unselectable">
                      <th>Key</th>
                      <th>Type</th>
                      <th>Expression</th>
                      <th>Attribute</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-if="!guiState.fields.length">
                      <td colspan="5" class="has-text-centered">No extractor fields configured.</td>
                    </tr>
                    <tr v-for="(field, index) in guiState.fields" :key="field.key">
                      <td>
                        <input class="input" type="text" v-model="field.key" :disabled="isBusy">
                      </td>
                      <td>
                        <div class="select is-fullwidth">
                          <select v-model="field.type" :disabled="isBusy">
                            <option value="css">CSS</option>
                            <option value="xpath">XPath</option>
                            <option value="regex">Regex</option>
                            <option value="jsonpath">JSONPath</option>
                          </select>
                        </div>
                      </td>
                      <td>
                        <input class="input" type="text" v-model="field.expression" :disabled="isBusy">
                      </td>
                      <td>
                        <input class="input" type="text" v-model="field.attribute" :disabled="isBusy"
                          placeholder="Optional">
                      </td>
                      <td class="has-text-right">
                        <button class="button is-small is-danger" type="button" @click="removeField(index)"
                          :disabled="isBusy">
                          <span class="icon"><i class="fa-solid fa-trash" /></span>
                        </button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>

        <p v-if="guiError" class="help is-danger">
          <span class="icon-text">
            <span class="icon"><i class="fa-solid fa-circle-exclamation" /></span>
            <span>{{ guiError }}</span>
          </span>
        </p>
      </div>

      <div v-else>
        <textarea class="textarea is-family-monospace" rows="18" v-model="jsonText" :readonly="submitting"
          spellcheck="false" />
        <p v-if="errorMessage" class="help is-danger mt-2">
          <span class="icon-text">
            <span class="icon"><i class="fa-solid fa-circle-exclamation" /></span>
            <span>{{ errorMessage }}</span>
          </span>
        </p>
      </div>
    </div>

    <footer class="card-footer p-4">
      <div class="buttons">
        <button class="button is-primary" type="button" @click="submit" :disabled="isBusy">
          <span class="icon"><i class="fa-solid fa-floppy-disk" /></span>
          <span>Save</span>
        </button>
        <button class="button is-danger" type="button" @click="cancel" :disabled="submitting">
          <span class="icon"><i class="fa-solid fa-xmark" /></span>
          <span>Cancel</span>
        </button>
        <button class="button is-link" type="button" v-if="'advanced' === mode" @click="beautify" :disabled="isBusy">
          <span class="icon"><i class="fa-solid fa-wand-magic-sparkles" /></span>
          <span>Format</span>
        </button>
      </div>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'

import Message from '~/components/Message.vue'
import { decode } from '~/utils'
import type { TaskDefinitionDocument, TaskDefinitionSummary } from '~/types/task_definitions'

type EditorMode = 'gui' | 'advanced'

type GuiField = {
  key: string
  type: string
  expression: string
  attribute: string
}

type GuiState = {
  name: string
  priority: number
  matchText: string
  engineType: 'httpx' | 'selenium'
  engineUrl: string
  requestMethod: string
  requestUrl: string
  containerType: 'css' | 'xpath' | 'jsonpath'
  containerSelector: string
  fields: GuiField[]
}

const props = defineProps<{
  title: string
  document: TaskDefinitionDocument | null
  loading?: boolean
  submitting?: boolean
  availableDefinitions?: readonly TaskDefinitionSummary[]
  initialShowImport?: boolean
}>()

const emit = defineEmits<{
  (e: 'submit', payload: TaskDefinitionDocument): void
  (e: 'cancel'): void
  (e: 'import-existing', id: string): void
}>()

const jsonText = ref<string>('')
const errorMessage = ref<string | null>(null)
const guiError = ref<string | null>(null)
const guiSupported = ref<boolean>(true)
const mode = ref<EditorMode>('gui')
const showImport = ref<boolean>(false)
const importString = ref<string>('')
const selectedExisting = ref<string>('')

const availableDefinitions = computed<readonly TaskDefinitionSummary[]>(() => props.availableDefinitions ?? [])

const guiState = reactive<GuiState>({
  name: '',
  priority: 0,
  matchText: '',
  engineType: 'httpx',
  engineUrl: '',
  requestMethod: 'GET',
  requestUrl: '',
  containerType: 'css',
  containerSelector: '',
  fields: [],
})

const loading = computed<boolean>(() => props.loading ?? false)
const submitting = computed<boolean>(() => props.submitting ?? false)
const isBusy = computed<boolean>(() => loading.value || submitting.value)
const headerTitle = computed<string>(() => props.title)

const guiLimitations = 'Only simple match globs, a single container selector and per-field extractors are exposed. ' +
  'More advanced constructs require raw view mode.'

const resetGuiState = (state: GuiState): void => {
  guiState.name = state.name
  guiState.priority = state.priority
  guiState.matchText = state.matchText
  guiState.engineType = state.engineType
  guiState.engineUrl = state.engineUrl
  guiState.requestMethod = state.requestMethod
  guiState.requestUrl = state.requestUrl
  guiState.containerType = state.containerType
  guiState.containerSelector = state.containerSelector
  guiState.fields = state.fields.map(field => ({ ...field }))
}

const defaultField = (): GuiField => ({ key: '', type: 'css', expression: '', attribute: '' })

const addField = (): void => {
  guiState.fields.push(defaultField())
}

const removeField = (index: number): void => {
  guiState.fields.splice(index, 1)
}

const splitMatches = (text: string): string[] => {
  return text.split(/\r?\n/).map(item => item.trim()).filter(Boolean)
}

const toGui = (document: TaskDefinitionDocument): GuiState | null => {
  if (!document || Array.isArray(document) || 'object' !== typeof document) {
    return null
  }

  const entry = document
  const match = entry.match
  if (!Array.isArray(match) || match.some(item => 'string' !== typeof item)) {
    return null
  }

  const parse = entry.parse
  if (!parse || Array.isArray(parse) || 'object' !== typeof parse) {
    return null
  }

  const parseRecord = parse as Record<string, unknown>
  const items = parseRecord.items
  if (!items || Array.isArray(items) || 'object' !== typeof items) {
    return null
  }

  const itemRecord = items as Record<string, unknown>
  const fields = itemRecord.fields
  if (!fields || Array.isArray(fields) || 'object' !== typeof fields) {
    return null
  }

  const fieldRecord = fields as Record<string, unknown>
  const guiFields: GuiField[] = []
  for (const [key, value] of Object.entries(fieldRecord)) {
    if (!value || Array.isArray(value) || 'object' !== typeof value) {
      return null
    }
    const rule = value as Record<string, unknown>
    if ('string' !== typeof rule.type || 'string' !== typeof rule.expression) {
      return null
    }
    if (Object.keys(rule).some(prop => !['type', 'expression', 'attribute'].includes(prop))) {
      return null
    }
    guiFields.push({
      key,
      type: String(rule.type),
      expression: String(rule.expression),
      attribute: 'string' === typeof rule.attribute ? String(rule.attribute) : '',
    })
  }

  const engine = entry.engine as Record<string, unknown> | undefined
  const engineType = (engine?.type === 'selenium') ? 'selenium' : 'httpx'
  const engineUrl = 'string' === typeof engine?.options && engineType === 'selenium'
    ? ''
    : (engine?.options as Record<string, unknown> | undefined)?.url as string | undefined

  if (engineUrl && engineType === 'selenium' && 'string' !== typeof engineUrl) {
    return null
  }

  const request = entry.request as Record<string, unknown> | undefined

  const selectorType = String(itemRecord.type ?? 'css') as GuiState['containerType']
  const selectorSource = (itemRecord.selector ?? itemRecord.expression) as string | undefined
  if (!selectorSource || 'string' !== typeof selectorSource) {
    return null
  }

  return {
    name: 'string' === typeof entry.name ? entry.name : '',
    priority: Number(entry.priority ?? 0) || 0,
    matchText: match.join('\n'),
    engineType,
    engineUrl: engineType === 'selenium' ? String(engineUrl ?? '') : '',
    requestMethod: 'string' === typeof request?.method ? String(request?.method) : 'GET',
    requestUrl: 'string' === typeof request?.url ? String(request?.url) : '',
    containerType: selectorType,
    containerSelector: selectorSource,
    fields: guiFields.length ? guiFields : [defaultField()],
  }
}

const fromGui = (state: GuiState): TaskDefinitionDocument => {
  if (!state.name.trim()) {
    throw new Error('Name is required.')
  }

  const matches = splitMatches(state.matchText)
  if (!matches.length) {
    throw new Error('At least one match pattern is required.')
  }

  if (!state.containerSelector.trim()) {
    throw new Error('Container selector is required.')
  }

  const formattedFields: Record<string, Record<string, string>> = {}
  state.fields.forEach(field => {
    if (!field.key.trim()) {
      return
    }
    if (!field.expression.trim()) {
      throw new Error(`Expression is required for field "${field.key}".`)
    }
    formattedFields[field.key.trim()] = {
      type: field.type || 'css',
      expression: field.expression,
      ...(field.attribute ? { attribute: field.attribute } : {}),
    }
  })

  if (!Object.keys(formattedFields).length) {
    throw new Error('Configure at least one extractor field.')
  }

  const doc: Record<string, unknown> = {
    name: state.name.trim(),
    priority: Number(state.priority) || 0,
    match: matches,
    parse: {
      items: {
        type: state.containerType,
        selector: state.containerType === 'jsonpath' ? undefined : state.containerSelector,
        expression: state.containerType === 'jsonpath' ? state.containerSelector : undefined,
        fields: formattedFields,
      },
    },
  }

  if ('httpx' !== state.engineType || state.engineUrl) {
    doc.engine = {
      type: state.engineType,
      ...(state.engineType === 'selenium' && state.engineUrl
        ? { options: { url: state.engineUrl } }
        : {}),
    }
  }

  const request: Record<string, string> = {}
  if (state.requestMethod && 'GET' !== state.requestMethod) {
    request.method = state.requestMethod
  }
  if (state.requestUrl) {
    request.url = state.requestUrl
  }
  if (Object.keys(request).length) {
    doc.request = request
  }

  return doc as unknown as TaskDefinitionDocument
}

const parseImportedDocument = (payload: unknown): TaskDefinitionDocument => {
  if (!payload || Array.isArray(payload) || 'object' !== typeof payload) {
    throw new Error('Import payload is not a task definition object.')
  }

  const record = payload as Record<string, unknown>
  const candidate = record.definition
  if ('_type' in record && record._type !== undefined && record._type !== 'task_definition') {
    throw new Error('Import string is not a task definition export.')
  }
  let base: TaskDefinitionDocument

  if (candidate && !Array.isArray(candidate) && 'object' === typeof candidate) {
    base = candidate as TaskDefinitionDocument
  }
  else {
    base = payload as TaskDefinitionDocument
  }

  const clone = JSON.parse(JSON.stringify(base)) as TaskDefinitionDocument
  const cloneRecord = clone

  if ('name' in record && 'string' === typeof record.name) {
    cloneRecord.name = record.name
  }

  if ('priority' in record && record.priority !== undefined) {
    cloneRecord.priority = Number(record.priority) || 0
  }

  return clone
}

const parseDocument = (): TaskDefinitionDocument | null => {
  try {
    if (!jsonText.value.trim()) {
      throw new Error('Definition cannot be empty.')
    }
    const parsed = JSON.parse(jsonText.value) as unknown
    if (!parsed || Array.isArray(parsed) || 'object' !== typeof parsed) {
      throw new Error('Definition must be a JSON object.')
    }
    errorMessage.value = null
    return parsed as TaskDefinitionDocument
  }
  catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Invalid JSON document.'
    return null
  }
}

const applyDocument = (document: TaskDefinitionDocument | null): void => {
  const shouldShowImport = props.initialShowImport ?? !document
  showImport.value = shouldShowImport
  importString.value = ''
  selectedExisting.value = ''

  if (!document) {
    jsonText.value = ''
    guiSupported.value = true
    resetGuiState({
      name: '',
      priority: 0,
      matchText: '',
      engineType: 'httpx',
      engineUrl: '',
      requestMethod: 'GET',
      requestUrl: '',
      containerType: 'css',
      containerSelector: '',
      fields: [defaultField()],
    })
    return
  }

  try {
    jsonText.value = JSON.stringify(document, null, 2)
    const gui = toGui(document)
    if (gui) {
      guiSupported.value = true
      resetGuiState(gui)
      guiError.value = null
      if ('gui' !== mode.value) {
        mode.value = 'gui'
      }
    }
    else {
      guiSupported.value = false
      mode.value = 'advanced'
    }
  }
  catch (error) {
    console.error('Failed to prepare definition for editing.', error)
    jsonText.value = ''
    guiSupported.value = false
    mode.value = 'advanced'
    errorMessage.value = 'Failed to prepare definition for editing.'
  }
}

const importFromString = (): void => {
  if (isBusy.value) {
    return
  }

  if (!importString.value.trim()) {
    guiError.value = 'Import string cannot be empty.'
    return
  }

  try {
    const decoded = decode(importString.value.trim())
    const document = parseImportedDocument(decoded)
    applyDocument(document)
    guiError.value = null
    errorMessage.value = null
    importString.value = ''
    showImport.value = false
  }
  catch (error) {
    guiError.value = error instanceof Error ? error.message : 'Unable to import definition.'
  }
}

const importExisting = (): void => {
  if (!selectedExisting.value || isBusy.value) {
    return
  }

  emit('import-existing', selectedExisting.value)
  selectedExisting.value = ''
}

watch(() => props.document, (doc) => applyDocument(doc), { immediate: true })

const switchMode = (next: EditorMode): void => {
  if (isBusy.value || next === mode.value) {
    return
  }

  if ('gui' === next) {
    if (!guiSupported.value) {
      return
    }

    const parsed = parseDocument()
    if (!parsed) {
      return
    }

    const gui = toGui(parsed)
    if (!gui) {
      guiSupported.value = false
      return
    }
    resetGuiState(gui)
    guiSupported.value = true
  }

  if ('advanced' === next) {
    try {
      const doc = fromGui(guiState)
      jsonText.value = JSON.stringify(doc, null, 2)
      errorMessage.value = null
      guiError.value = null
    }
    catch (error) {
      guiError.value = error instanceof Error ? error.message : 'Failed to serialize GUI changes.'
      return
    }
  }

  mode.value = next
}

const submit = (): void => {
  if (isBusy.value) {
    return
  }

  if ('gui' === mode.value) {
    try {
      const doc = fromGui(guiState)
      emit('submit', doc)
      guiError.value = null
    }
    catch (error) {
      guiError.value = error instanceof Error ? error.message : 'Unable to build definition.'
    }
    return
  }

  const parsed = parseDocument()
  if (!parsed) {
    return
  }
  emit('submit', parsed)
}

const beautify = (): void => {
  if ('advanced' !== mode.value) {
    return
  }
  const parsed = parseDocument()
  if (!parsed) {
    return
  }
  jsonText.value = JSON.stringify(parsed, null, 2)
  errorMessage.value = null
}

const cancel = (): void => {
  if (submitting.value) {
    return
  }
  emit('cancel')
}

defineExpose({ submit, beautify })
</script>

<style scoped>
.textarea {
  min-height: 16rem;
  font-family: var(--font-monospace, 'JetBrains Mono', monospace);
}

.card-footer .buttons {
  width: 100%;
  justify-content: flex-end;
}

.buttons.has-addons .button {
  border-radius: 4px;
}

.buttons.has-addons .button:first-child {
  border-top-right-radius: 0;
  border-bottom-right-radius: 0;
}

.buttons.has-addons .button:last-child {
  border-top-left-radius: 0;
  border-bottom-left-radius: 0;
}

.table td,
.table th {
  vertical-align: middle;
}
</style>
