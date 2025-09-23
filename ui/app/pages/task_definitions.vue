<template>
  <main>
    <div class="mt-1 columns is-multiline">
      <div class="column is-12 is-clearfix is-unselectable">
        <span class="title is-4">
          <span class="icon-text">
            <span class="icon"><i class="fa-solid fa-diagram-project" /></span>
            <span>Task Definitions</span>
          </span>
        </span>
        <div class="is-pulled-right">
          <div class="field is-grouped">

            <p class="control">
              <button class="button is-primary" @click="isEditorOpen ? closeEditor() : openCreate()">
                <span class="icon"><i class="fa-solid fa-add" /></span>
                <span v-if="!isMobile">New Definition</span>
              </button>
            </p>

            <p class="control">
              <button @click="() => inspect = true" class="button is-primary is-light">
                <span class="icon"><i class="fa-solid fa-magnifying-glass" /></span>
                <span v-if="!isMobile">Inspect</span>
              </button>
            </p>

            <p class="control">
              <button v-tooltip.bottom="'Change display style'" class="button has-tooltip-bottom"
                @click="() => display_style = display_style === 'list' ? 'grid' : 'list'">
                <span class="icon">
                  <i class="fa-solid"
                    :class="{ 'fa-table': display_style !== 'list', 'fa-table-list': display_style === 'list' }" /></span>
                <span v-if="!isMobile">
                  {{ display_style === 'list' ? 'List' : 'Grid' }}
                </span>
              </button>
            </p>

            <p class="control">
              <button class="button is-info" @click="async () => await loadDefinitions()"
                :class="{ 'is-loading': isLoading }">
                <span class="icon"><i class="fas fa-refresh" /></span>
                <span v-if="!isMobile">Reload</span>
              </button>
            </p>
          </div>
        </div>
        <div class="is-hidden-mobile">
          <span class="subtitle">
            Create definitions to turn any website into a downloadable feed of links.
          </span>
        </div>
      </div>
    </div>

    <div class="columns" v-if="'list' === display_style && definitions.length > 0 && !isEditorOpen">
      <div class="column is-12">
        <div class="table-container">
          <table class="table is-striped is-hoverable is-fullwidth is-bordered"
            style="min-width: 850px; table-layout: fixed;">
            <thead>
              <tr class="has-text-centered is-unselectable">
                <th width="40%">Name</th>
                <th width="20%">Priority</th>
                <th width="20%">Updated</th>
                <th width="20%">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="definition in definitions" :key="definition.id">
                <td class="is-vcentered is-text-overflow">
                  {{ definition.name || '(Unnamed definition)' }}
                </td>
                <td class="is-vcentered has-text-centered">{{ definition.priority }}</td>
                <td class="is-vcentered has-text-centered">
                  <span class="user-hint" :date-datetime="moment.unix(definition.updated_at).format('YYYY-M-DD H:mm Z')"
                    v-tooltip="moment.unix(definition.updated_at).format('YYYY-M-DD H:mm Z')"
                    v-rtime="definition.updated_at" />
                </td>
                <td class="is-vcentered is-items-center">
                  <div class="field is-grouped is-grouped-centered">
                    <div class="control">
                      <button class="button is-small is-info" type="button" @click="exportDefinition(definition)">
                        <span class="icon"><i class="fa-solid fa-file-export" /></span>
                        <span v-if="!isMobile">Export</span>
                      </button>
                    </div>
                    <div class="control">
                      <button class="button is-small is-warning" type="button" @click="openEdit(definition)">
                        <span class="icon"><i class="fa-solid fa-cog" /></span>
                        <span v-if="!isMobile">Edit</span>
                      </button>
                    </div>
                    <div class="control">
                      <button class="button is-small is-danger" type="button" @click="remove(definition)">
                        <span class="icon"><i class="fa-solid fa-trash" /></span>
                        <span v-if="!isMobile">Delete</span>
                      </button>
                    </div>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="columns is-multiline" v-if="'grid' === display_style && definitions.length > 0 && !isEditorOpen">
      <div class="column is-6" v-for="definition in definitions" :key="definition.id">
        <div class="card">
          <header class="card-header">
            <div class="card-header-title is-text-overflow is-block">
              {{ definition.name || '(Unnamed definition)' }}
            </div>
            <div class="card-header-icon">
              <button class="has-text-info" v-tooltip="'Export'" @click="exportDefinition(definition)">
                <span class="icon"><i class="fa-solid fa-file-export" /></span>
              </button>
            </div>
          </header>
          <div class="card-content">
            <div class="content">
              <p>
                <span class="icon-text">
                  <span class="icon"><i class="fa-solid fa-sort-numeric-down" /></span>
                  <span>Priority: {{ definition.priority }}</span>
                </span>
              </p>
              <p>
                <span class="icon-text">
                  <span class="icon"><i class="fa-solid fa-clock" /></span>
                  <span>Updated: <span class="user-hint"
                      :date-datetime="moment.unix(definition.updated_at).format('YYYY-M-DD H:mm Z')"
                      v-tooltip="moment.unix(definition.updated_at).format('YYYY-M-DD H:mm Z')"
                      v-rtime="definition.updated_at" />
                  </span>
                </span>
              </p>
            </div>
          </div>
          <footer class="card-footer mt-auto">
            <div class="card-footer-item">
              <button class="button is-warning is-fullwidth" @click="openEdit(definition)">
                <span class="icon-text">
                  <span class="icon"><i class="fa-solid fa-pen-to-square" /></span>
                  <span>Edit</span>
                </span>
              </button>
            </div>
            <div class="card-footer-item">
              <button class="button is-danger is-fullwidth" @click="remove(definition)">
                <span class="icon-text">
                  <span class="icon"><i class="fa-solid fa-trash" /></span>
                  <span>Delete</span>
                </span>
              </button>
            </div>
          </footer>
        </div>
      </div>
    </div>

    <div class="columns is-multiline" v-if="!definitions.length">
      <div class="column is-12">
        <Message message_class="has-background-info-90 has-text-dark" title="Loading" icon="fas fa-spinner fa-spin"
          message="Loading data. Please wait..." v-if="isLoading" />
        <Message title="No definitions" message="No task definitions are configured yet. Create one to get started."
          class="is-background-warning-80 has-text-dark" icon="fas fa-exclamation-circle" v-else />
      </div>
    </div>

    <div class="columns" v-if="isEditorOpen">
      <div class="column is-12">
        <TaskDefinitionEditor :title="editorTitle" :document="workingDefinition"
          :initial-show-import="'create' === editorMode" :available-definitions="definitions" :loading="editorLoading"
          :submitting="editorSubmitting" @submit="submitDefinition" @cancel="closeEditor"
          @import-existing="importExistingDefinition" />
      </div>
    </div>

    <Modal v-if="inspect" @close="() => inspect = false" :contentClass="`modal-content-max`">
      <TaskInspect />
    </Modal>

  </main>
</template>

<script setup lang="ts">
import moment from 'moment'
import { computed, onMounted, ref } from 'vue'
import { useStorage } from '@vueuse/core'

import TaskDefinitionEditor from '~/components/TaskDefinitionEditor.vue'
import useTaskDefinitionsComposable from '~/composables/useTaskDefinitions'
import { useDialog } from '~/composables/useDialog'
import { useNotification } from '~/composables/useNotification'
import { copyText, encode } from '~/utils'
import { useMediaQuery } from '~/composables/useMediaQuery'

import type {
  TaskDefinitionDetailed,
  TaskDefinitionDocument,
  TaskDefinitionSummary,
} from '~/types/task_definitions'

const DEFAULT_DEFINITION: TaskDefinitionDocument = {
  name: 'New Definition',
  priority: 0,
  match: ['https://example.com/*'],
  parse: {
    items: {
      type: 'css',
      selector: 'body',
      fields: {
        link: { type: 'css', expression: 'a', attribute: 'href' },
        title: { type: 'css', expression: 'a', attribute: 'text' },
      },
    },
  },
}

const isMobile = useMediaQuery({ maxWidth: 1024 })

const taskDefs = useTaskDefinitionsComposable()
const definitionsRef = taskDefs.definitions
const isLoading = taskDefs.isLoading
const loadDefinitions = taskDefs.loadDefinitions
const getDefinition = taskDefs.getDefinition
const createDefinition = taskDefs.createDefinition
const updateDefinition = taskDefs.updateDefinition
const deleteDefinition = taskDefs.deleteDefinition

const definitions = computed(() => definitionsRef.value)

const { confirmDialog } = useDialog()
const toast = useNotification()

const isEditorOpen = ref<boolean>(false)
const editorMode = ref<'create' | 'edit'>('create')
const editorLoading = ref<boolean>(false)
const editorSubmitting = ref<boolean>(false)
const workingDefinition = ref<TaskDefinitionDocument | null>(null)
const workingId = ref<string | null>(null)
const inspect = ref<boolean>(false)
const display_style = useStorage<'list' | 'grid'>('task-definitions:display', 'grid')

const currentSummary = computed<TaskDefinitionSummary | undefined>(() => {
  if ('edit' !== editorMode.value || !workingId.value) {
    return undefined
  }

  return definitions.value.find(item => item.id === workingId.value)
})

const editorTitle = computed<string>(() => {
  return 'create' === editorMode.value
    ? 'Create Task Definition'
    : `Edit ${currentSummary.value?.name || 'Task Definition'}`
})

const cloneDocument = (document: TaskDefinitionDocument): TaskDefinitionDocument => {
  return JSON.parse(JSON.stringify(document)) as TaskDefinitionDocument
}

const openCreate = (): void => {
  editorMode.value = 'create'
  workingId.value = null
  workingDefinition.value = cloneDocument(DEFAULT_DEFINITION)
  isEditorOpen.value = true
  editorLoading.value = false
  editorSubmitting.value = false
}

const openEdit = async (summary: TaskDefinitionSummary): Promise<void> => {
  editorMode.value = 'edit'
  workingId.value = summary.id
  workingDefinition.value = null
  editorLoading.value = true
  editorSubmitting.value = false
  isEditorOpen.value = true

  const detailed: TaskDefinitionDetailed | null = await getDefinition(summary.id)
  if (!detailed) {
    isEditorOpen.value = false
    editorLoading.value = false
    return
  }

  const document = cloneDocument(detailed.definition)
  const docRecord = document
  if ('priority' in docRecord) {
    docRecord.priority = Number(docRecord.priority)
  }
  else {
    docRecord.priority = detailed.priority
  }

  workingDefinition.value = document
  editorLoading.value = false
}

const importExistingDefinition = async (id: string): Promise<void> => {
  const detailed = await getDefinition(id)
  if (!detailed) {
    toast.error('Failed to load task definition for import.')
    return
  }

  const document = cloneDocument(detailed.definition)
  const docRecord = document
  if ('priority' in docRecord) {
    docRecord.priority = Number(docRecord.priority)
  }
  else {
    docRecord.priority = detailed.priority
  }

  workingDefinition.value = document
  if ('create' === editorMode.value) {
    workingId.value = null
  }
  editorLoading.value = false
}

const closeEditor = (): void => {
  if (editorSubmitting.value) {
    return
  }

  isEditorOpen.value = false
  workingDefinition.value = null
  workingId.value = null
  editorLoading.value = false
}

const submitDefinition = async (definition: TaskDefinitionDocument): Promise<void> => {
  editorSubmitting.value = true
  try {
    if ('create' === editorMode.value) {
      const created = await createDefinition(definition)
      if (created) {
        isEditorOpen.value = false
        workingDefinition.value = null
        workingId.value = null
      }
    }
    else if (workingId.value) {
      const updated = await updateDefinition(workingId.value, definition)
      if (updated) {
        isEditorOpen.value = false
        workingDefinition.value = null
        workingId.value = null
      }
    }
  }
  finally {
    editorSubmitting.value = false
  }
}

const remove = async (summary: TaskDefinitionSummary): Promise<void> => {
  const result = await confirmDialog({
    title: 'Delete Task Definition',
    message: `Are you sure you want to delete “${summary.name || summary.id}”?`,
    confirmColor: 'is-danger',
  })

  if (!result.status) {
    return
  }

  await deleteDefinition(summary.id)
}

const exportDefinition = async (summary: TaskDefinitionSummary): Promise<void> => {
  const detailed = await getDefinition(summary.id)
  if (!detailed) {
    return
  }

  const payload = {
    _type: 'task_definition',
    _version: '1.0',
    name: detailed.name,
    priority: detailed.priority,
    definition: detailed.definition,
  }

  return copyText(encode(payload))
}

onMounted(async () => {
  if (!definitions.value.length) {
    await loadDefinitions()
  }
})
</script>
