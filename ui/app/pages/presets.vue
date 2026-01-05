<template>
  <main>
    <div class="mt-1 columns is-multiline">
      <div class="column is-12 is-clearfix is-unselectable">
        <span class="title is-4">
          <span class="icon-text">
            <template v-if="toggleForm">
              <span class="icon"><i class="fa-solid" :class="{ 'fa-edit': presetRef, 'fa-plus': !presetRef }" /></span>
              <span>{{ presetRef ? `Edit - ${preset.name}` : 'Add' }}</span>
            </template>
            <template v-else>
              <span class="icon"><i class="fa-solid fa-sliders" /></span>
              <span>Presets</span>
            </template>
          </span>
        </span>
        <div class="is-pulled-right" v-if="!toggleForm">
          <div class="field is-grouped">
            <p class="control">
              <button class="button is-primary" @click="resetForm(false); toggleForm = !toggleForm;"
                v-tooltip.bottom="'Toggle add form'">
                <span class="icon"><i class="fas fa-add" /></span>
                <span v-if="!isMobile">New Preset</span>
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
              <button class="button is-info" @click="reloadContent()" :class="{ 'is-loading': isLoading }"
                :disabled="isLoading" v-if="presets && presets.length > 0">
                <span class="icon"><i class="fas fa-refresh" /></span>
                <span v-if="!isMobile">Reload</span>
              </button>
            </p>
          </div>
        </div>
        <div class="is-hidden-mobile" v-if="!toggleForm">
          <span class="subtitle">Presets are pre-defined command options for yt-dlp that you want to apply to given
            download.</span>
        </div>
      </div>
    </div>

    <div class="columns" v-if="toggleForm">
      <div class="column is-12">
        <PresetForm :addInProgress="addInProgress" :reference="presetRef" :preset="preset" @cancel="resetForm(true)"
          @submit="updateItem" :presets="presets" />
      </div>
    </div>

    <template v-if="!toggleForm">
      <div class="columns is-multiline" v-if="presetsNoDefault && presetsNoDefault.length > 0">
        <template v-if="'list' === display_style">
          <div class="column is-12">
            <div class="table-container">
              <table class="table is-striped is-hoverable is-fullwidth is-bordered"
                style="min-width: 650px; table-layout: fixed;">
                <thead>
                  <tr class="has-text-centered is-unselectable">
                    <th width="80%">Preset</th>
                    <th width="20%">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in presetsNoDefault" :key="item.id">
                    <td class="is-text-overflow is-vcentered">
                      <div class="is-text-overflow is-bold">
                        {{ item.name }}
                      </div>
                      <div class="is-unselectable">
                        <span class="icon-text" :class="{ 'has-text-primary': item.cookies }">
                          <span class="icon"><i class="fa-solid fa-cookie" /></span>
                          <span>{{ item.cookies ? 'Has cookies' : 'No cookies' }}</span>
                        </span>
                        &nbsp;
                        <template v-if="item.priority > 0">
                          &nbsp;
                          <span class="icon-text">
                            <span class="icon"><i class="fa-solid fa-sort-numeric-down" /></span>
                            <span>Priority: {{ item.priority }}</span>
                          </span>
                        </template>
                      </div>
                    </td>
                    <td class="is-vcentered is-items-center">
                      <div class="field is-grouped is-grouped-centered">
                        <div class="control">
                          <button class="button is-info is-small is-fullwidth" @click="exportItem(item)">
                            <span class="icon"><i class="fa-solid fa-file-export" /></span>
                            <span v-if="!isMobile">Export</span>
                          </button>
                        </div>
                        <div class="control">
                          <button class="button is-warning is-small is-fullwidth" @click="editItem(item)">
                            <span class="icon"><i class="fa-solid fa-cog" /></span>
                            <span v-if="!isMobile">Edit</span>
                          </button>
                        </div>
                        <div class="control">
                          <button class="button is-danger is-small is-fullwidth" @click="deleteItem(item)">
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
        </template>

        <template v-else>
          <div class="column is-6" v-for="item in presetsNoDefault" :key="item.id">
            <div class="card is-flex is-full-height is-flex-direction-column">
              <header class="card-header">
                <div class="card-header-title is-block is-clickable"
                  :class="{ 'is-text-overflow': !isExpanded(item.id, 'title') }" @click="toggleExpand(item.id, 'title')"
                  :title="!isExpanded(item.id, 'title') ? 'Click to expand' : 'Click to collapse'" v-text="item.name" />
                <div class="card-header-icon">
                  <div class="field is-grouped">
                    <div class="control" v-if="item.priority > 0">
                      <span class="tag is-dark">
                        <span class="icon"><i class="fa-solid fa-sort-numeric-down" /></span>
                        <span v-text="item.priority" />
                      </span>
                    </div>
                    <div class="control" v-if="item.cookies" v-tooltip="'This preset has cookies'">
                      <span class="icon has-text-primary"><i class="fa-solid fa-cookie" /></span>
                    </div>
                    <div class="control">
                      <button class="has-text-info" v-tooltip="'Export preset'" @click="exportItem(item)">
                        <span class="icon"><i class="fa-solid fa-file-export" /></span>
                      </button>
                    </div>
                  </div>
                </div>
              </header>
              <div class="card-content is-flex-grow-1">
                <div class="content">
                  <template v-if="item.priority > 0">
                    <p>
                      <span class="icon"><i class="fa-solid fa-sort-numeric-down" /></span>
                      <span>Priority: {{ item.priority }}</span>
                    </p>
                  </template>
                  <p :class="{ 'is-text-overflow': !isExpanded(item.id, 'folder'), 'is-clickable': true }"
                    v-if="item.folder" @click="toggleExpand(item.id, 'folder')"
                    :title="!isExpanded(item.id, 'folder') ? 'Click to expand' : 'Click to collapse'">
                    <span class="icon"><i class="fa-solid fa-save" /></span>
                    <span>{{ calcPath(item.folder) }}</span>
                  </p>
                  <p :class="{ 'is-text-overflow': !isExpanded(item.id, 'template'), 'is-clickable': true }"
                    v-if="item.template" @click="toggleExpand(item.id, 'template')"
                    :title="!isExpanded(item.id, 'template') ? 'Click to expand' : 'Click to collapse'">
                    <span class="icon"><i class="fa-solid fa-file" /></span>
                    <span>{{ item.template }}</span>
                  </p>
                  <p :class="{ 'is-text-overflow': !isExpanded(item.id, 'cli'), 'is-clickable': true }" v-if="item.cli"
                    @click="toggleExpand(item.id, 'cli')"
                    :title="!isExpanded(item.id, 'cli') ? 'Click to expand' : 'Click to collapse'">
                    <span class="icon"><i class="fa-solid fa-terminal" /></span>
                    <span>{{ item.cli }}</span>
                  </p>
                  <p :class="{ 'is-text-overflow': !isExpanded(item.id, 'description'), 'is-clickable': true }"
                    v-if="item.description" @click="toggleExpand(item.id, 'description')"
                    :title="!isExpanded(item.id, 'cli') ? 'Click to expand' : 'Click to collapse'">
                    <span class="icon"><i class="fa-solid fa-d" /></span>
                    <span>{{ item.description }}</span>
                  </p>
                </div>
              </div>
              <div class="card-content content m-1 p-1 is-overflow-auto" style="max-height: 300px;"
                v-if="item?.toggle_description">
                <div class="is-pre-wrap">{{ item.description }}</div>
              </div>
              <div class="card-footer mt-auto">
                <div class="card-footer-item">
                  <button class="button is-warning is-fullwidth" @click="editItem(item)">
                    <span class="icon"><i class="fa-solid fa-edit" /></span>
                    <span>Edit</span>
                  </button>
                </div>
                <div class="card-footer-item">
                  <button class="button is-danger is-fullwidth" @click="deleteItem(item)">
                    <span class="icon"><i class="fa-solid fa-trash" /></span>
                    <span>Delete</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </template>
      </div>

      <div class="columns is-multiline" v-if="!presets || presets.length < 1">
        <div class="column is-12">
          <Message message_class="has-background-info-90 has-text-dark" title="Loading" icon="fas fa-spinner fa-spin"
            message="Loading data. Please wait..." v-if="isLoading" />
          <Message title="No presets" message="There are no custom defined presets."
            class="is-background-warning-80 has-text-dark" icon="fas fa-exclamation-circle" v-else />
        </div>
      </div>

      <div class="columns is-multiline" v-if="presets && presets.length > 0">
        <div class="column is-12">
          <div class="message is-info">
            <p class="message-body">
              <span class="icon"> <i class="fas fa-info-circle" /></span>
              When you export preset, it doesn't include the <strong>cookies</strong> field contents for security
              reasons.
            </p>
          </div>
        </div>
      </div>
    </template>
  </main>
</template>

<script setup lang="ts">
import { useStorage } from '@vueuse/core'
import type { Preset } from '~/types/presets'
import { useConfirm } from '~/composables/useConfirm'

type PresetWithUI = Preset & { raw?: boolean, toggle_description?: boolean }

const toast = useNotification()
const config = useConfigStore()
const socket = useSocketStore()
const box = useConfirm()

const display_style = useStorage<string>('preset_display_style', 'cards')
const isMobile = useMediaQuery({ maxWidth: 1024 })

const presets = ref<PresetWithUI[]>([])
const preset = ref<Partial<Preset>>({})
const presetRef = ref<string | null>('')
const toggleForm = ref(false)
const isLoading = ref(true)
const initialLoad = ref(true)
const addInProgress = ref(false)
const remove_keys = ['raw', 'toggle_description']
const expandedItems = ref<Record<string, Set<string>>>({})

const presetsNoDefault = computed(() => presets.value.filter((t) => !t.default))

const toggleExpand = (itemId: string | undefined, field: string) => {
  if (!itemId) return

  if (!expandedItems.value[itemId]) {
    expandedItems.value[itemId] = new Set()
  }

  if (expandedItems.value[itemId].has(field)) {
    expandedItems.value[itemId].delete(field)
  } else {
    expandedItems.value[itemId].add(field)
  }
}

const isExpanded = (itemId: string | undefined, field: string): boolean => {
  if (!itemId) return false
  return expandedItems.value[itemId]?.has(field) ?? false
}

watch(() => socket.isConnected, async () => {
  if (socket.isConnected && initialLoad.value) {
    await reloadContent(true)
    initialLoad.value = false
  }
})

const reloadContent = async (fromMounted = false) => {
  try {
    isLoading.value = true
    const response = await request('/api/presets')

    if (fromMounted && !response.ok) {
      return
    }

    const data = await response.json()
    if (0 === data.length) {
      return
    }

    presets.value = data
  } catch (e: any) {
    if (fromMounted) {
      return
    }
    console.error(e)
    toast.error('Failed to fetch page content.')
  } finally {
    isLoading.value = false
  }
}

const resetForm = (closeForm = false) => {
  preset.value = {}
  presetRef.value = null
  addInProgress.value = false
  if (closeForm) {
    toggleForm.value = false
  }
}

const updatePresets = async (items: Preset[]): Promise<boolean | undefined> => {
  let data: any
  try {
    addInProgress.value = true

    const response = await request('/api/presets', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(items.filter((t) => !t.default)),
    })

    data = await response.json()

    if (200 !== response.status) {
      toast.error(`Failed to update presets. ${data.error}`)
      return false
    }

    presets.value = data
    resetForm(true)
    return true
  } catch (e: any) {
    toast.error(`Failed to update presets. ${data?.error}. ${e.message}`)
  } finally {
    addInProgress.value = false
  }
}

const deleteItem = async (item: Preset) => {
  if (true !== (await box.confirm(`Delete preset '${item.name}'?`))) {
    return
  }

  const index = presets.value.findIndex((t) => t?.id === item.id)
  if (-1 === index) {
    toast.error('Preset not found.')
    return
  }

  presets.value.splice(index, 1)

  const status = await updatePresets(presets.value)
  if (!status) {
    return
  }

  toast.success('Preset deleted.')
}

const updateItem = async ({
  reference,
  preset: item,
}: {
  reference: string | null
  preset: Preset
}) => {
  item = cleanObject(item, remove_keys) as Preset
  if (reference) {
    const index = presets.value.findIndex((t) => t?.id === reference)
    if (-1 !== index) {
      presets.value[index] = item
    }
  } else {
    presets.value.push(item)
  }

  const status = await updatePresets(presets.value)
  if (!status) {
    return
  }

  toast.success(`Preset ${reference ? 'updated' : 'added'}.`)
  resetForm(true)
}

const filterItem = (item: Preset) => {
  const rest = cleanObject(item, remove_keys)
  if ('default' in rest) {
    delete rest.default
  }
  return JSON.stringify(rest, null, 2)
}

const editItem = (item: Preset) => {
  preset.value = JSON.parse(filterItem(item))
  presetRef.value = item.id ?? null
  toggleForm.value = true
}

onMounted(async () => (socket.isConnected ? await reloadContent(true) : ''))

const exportItem = (item: Preset) => {
  const keys = ['id', 'default', 'raw', 'cookies', 'toggle_description']
  const data = JSON.parse(JSON.stringify(item))

  for (const key of keys) {
    if (key in data) {
      const { [key]: _, ...rest } = data
      Object.assign(data, rest)
    }
  }

  const userData: Record<string, any> = {}
  for (const key of Object.keys(data)) {
    if (data[key]) {
      userData[key] = data[key]
    }
  }

  userData['_type'] = 'preset'
  userData['_version'] = '2.5'

  copyText(encode(userData))
}

const calcPath = (path?: string): string => {
  const loc = config.app.download_path || '/downloads'
  return path ? loc + '/' + sTrim(path, '/') : loc
}
</script>
