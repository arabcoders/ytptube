<template>
  <div>
    <div class="mt-1 columns is-multiline">
      <div class="column is-12 is-clearfix is-unselectable">
        <span class="title is-4">
          <span class="icon-text">
            <template v-if="toggleForm">
              <span class="icon"><i class="fa-solid" :class="{ 'fa-edit': itemRef, 'fa-plus': !itemRef }" /></span>
              <span>{{ itemRef ? `Edit - ${item.name}` : 'Add new condition' }}</span>
            </template>
            <template v-else>
              <span class="icon"><i class="fa-solid fa-filter" /></span>
              <span>Conditions</span>
            </template>
          </span>
        </span>
        <div class="is-pulled-right" v-if="!toggleForm">
          <div class="field is-grouped">
            <p class="control">
              <button class="button is-primary" @click="resetForm(false); toggleForm = !toggleForm;">
                <span class="icon"><i class="fas fa-add" /></span>
                <span v-if="!isMobile">New Condition</span>
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
              <button class="button is-info" @click="reloadContent(false)" :class="{ 'is-loading': isLoading }"
                :disabled="isLoading" v-if="items && items.length > 0">
                <span class="icon"><i class="fas fa-refresh" /></span>
                <span v-if="!isMobile">Reload</span>
              </button>
            </p>
          </div>
        </div>
        <div class="is-hidden-mobile" v-if="!toggleForm">
          <span class="subtitle">
            Run yt-dlp custom match filter on returned info. and apply cli arguments if matched.
          </span>
        </div>
      </div>

      <div class="column is-12" v-if="toggleForm">
        <ConditionForm :addInProgress="addInProgress" :reference="itemRef" :item="item as ConditionItem"
          @cancel="resetForm(true)" @submit="updateItem" />
      </div>

      <div class="column is-12" v-if="!toggleForm">
        <div class="columns is-multiline" v-if="items.length > 0">
          <template v-if="'list' === display_style">
            <div class="column is-12">
              <div class="table-container">
                <table class="table is-striped is-hoverable is-fullwidth is-bordered"
                  style="min-width: 850px; table-layout: fixed;">
                  <thead>
                    <tr class="has-text-centered is-unselectable">
                      <th width="80%">
                        <span class="icon"><i class="fa-solid fa-filter" /></span>
                        <span>Condition</span>
                      </th>
                      <th width="20%">
                        <span class="icon"><i class="fa-solid fa-gear" /></span>
                        <span>Actions</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="cond in items" :key="cond.id">
                      <td class="is-vcentered">
                        <div class="is-text-overflow is-bold">
                          {{ cond.name }}
                        </div>
                        <div class="is-unselectable">
                          <span class="icon-text is-clickable" @click="toggleEnabled(cond)"
                            v-tooltip="'Click to ' + (cond.enabled !== false ? 'disable' : 'enable') + ' condition'">
                            <span class="icon">
                              <i class="fa-solid fa-power-off"
                                :class="{ 'has-text-success': cond.enabled !== false, 'has-text-danger': cond.enabled === false }" />
                            </span>
                            <span>{{ cond.enabled !== false ? 'Enabled' : 'Disabled' }}</span>
                          </span>
                          &nbsp;
                          <Popover :maxWidth="450">
                            <template #trigger>
                              <span class="is-clickable">
                                <span class="icon"> <i class="fa-solid fa-info-circle" /></span>
                                <span>Show Details</span>
                              </span>
                            </template>

                            <template #title><strong>Condition Details</strong></template>

                            <div v-if="cond.filter">
                              <span class="icon"><i class="fa-solid fa-filter" /></span>
                              <code>{{ cond.filter }}</code>
                            </div>

                            <div v-if="cond.cli">
                              <span class="icon"><i class="fa-solid fa-terminal" /></span>
                              <code>{{ cond.cli }}</code>
                            </div>

                            <span v-if="cond.extras && Object.keys(cond.extras).length > 0">
                              <template v-for="(value, key) in cond.extras" :key="key">
                                <div>
                                  <span class="icon"><i class="fa-solid fa-list" /></span>
                                  <code>{{ key }}: {{ value }}</code>
                                </div>
                              </template>
                            </span>
                          </Popover>
                          <template v-if="cond.priority > 0">
                            &nbsp;
                            <span class="icon-text">
                              <span class="icon"><i class="fa-solid fa-sort-numeric-down" /></span>
                              <span>Priority: {{ cond.priority }}</span>
                            </span>
                          </template>
                        </div>
                      </td>
                      <td class="is-vcentered is-items-center">
                        <div class="field is-grouped is-grouped-centered">
                          <div class="control">
                            <button class="button is-info is-small is-fullwidth" @click="exportItem(cond)">
                              <span class="icon"><i class="fa-solid fa-file-export" /></span>
                              <span v-if="!isMobile">Export</span>
                            </button>
                          </div>
                          <div class="control">
                            <button class="button is-warning is-small is-fullwidth" @click="editItem(cond)">
                              <span class="icon"><i class="fa-solid fa-edit" /></span>
                              <span v-if="!isMobile">Edit</span>
                            </button>
                          </div>
                          <div class="control">
                            <button class="button is-danger is-small is-fullwidth" @click="deleteItem(cond)">
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
            <div class="column is-6" v-for="cond in items" :key="cond.id">
              <div class="card is-flex is-full-height is-flex-direction-column">
                <header class="card-header">
                  <div class="card-header-title is-text-overflow is-block" v-text="cond.name" />
                  <div class="card-header-icon">
                    <div class="field is-grouped">
                      <div class="control" v-if="cond.priority > 0">
                        <span class="tag is-dark">
                          <span class="icon"><i class="fa-solid fa-sort-numeric-down" /></span>
                          <span v-text="cond.priority" />
                        </span>
                      </div>
                      <div class="control" @click="toggleEnabled(cond)">
                        <span class="icon" :class="cond.enabled ? 'has-text-success' : 'has-text-danger'"
                          v-tooltip="`Condition is ${cond.enabled !== false ? 'enabled' : 'disabled'}. Click to toggle.`">
                          <i class="fa-solid fa-power-off" />
                        </span>
                      </div>
                      <div class="control">
                        <a class="has-text-info" v-tooltip="'Export item'" @click.prevent="exportItem(cond)">
                          <span class="icon"><i class="fa-solid fa-file-export" /></span>
                        </a>
                      </div>
                    </div>
                  </div>
                </header>
                <div class="card-content is-flex-grow-1">
                  <div class="content">
                    <p class="is-text-overflow">
                      <span class="icon"><i class="fa-solid fa-filter" /></span>
                      <span v-text="cond.filter" />
                    </p>
                    <p class="is-text-overflow" v-if="cond.cli">
                      <span class="icon"><i class="fa-solid fa-terminal" /></span>
                      <span>{{ cond.cli }}</span>
                    </p>
                    <p class="is-text-overflow" v-if="cond.extras && Object.keys(cond.extras).length > 0">
                      <span class="icon"><i class="fa-solid fa-list" /></span>
                      <span>Extras:
                        <span v-for="(value, key) in cond.extras" :key="key" class="tag is-info mr-2">
                          <strong>{{ key }}</strong>: {{ value }}
                        </span>
                      </span>
                    </p>
                    <p class="is-clickable" :class="{ 'is-text-overflow': !isExpanded(cond.id, 'description') }"
                      v-if="cond.description" @click="toggleExpand(cond.id, 'description')">
                      <span class="icon"><i class="fa-solid fa-comment" /></span>
                      <span>{{ cond.description }}</span>
                    </p>
                  </div>
                </div>
                <div class="card-footer mt-auto">
                  <div class="card-footer-item">
                    <button class="button is-warning is-fullwidth" @click="editItem(cond)">
                      <span class="icon"><i class="fa-solid fa-edit" /></span>
                      <span>Edit</span>
                    </button>
                  </div>
                  <div class="card-footer-item">
                    <button class="button is-danger is-fullwidth" @click="deleteItem(cond)">
                      <span class="icon"><i class="fa-solid fa-trash" /></span>
                      <span>Delete</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </template>
        </div>
        <Message title="No items" message="There are no custom conditions defined."
          class="is-background-warning-80 has-text-dark" icon="fas fa-exclamation-circle"
          v-if="!items || items.length < 1" />
      </div>
    </div>
    <div class="column is-12" v-if="items && items.length > 0 && !toggleForm">
      <div class="message is-info">
        <div class="message-body content pl-0">
          <ul>
            <li>Filtering is based on yt-dlp’s <code>--match-filter</code> logic. Any expression that works with yt-dlp
              will also work here, including the same boolean operators. We added extended support for the
              <code>OR</code> ( <code>||</code> ) operator, which yt-dlp does not natively support. This allows you to combine
              multiple conditions more flexibly.
            </li>
            <li>
              The primary use case for this feature is to apply custom cli arguments to specific returned info.
            </li>
            <li>
              For example, i follow specific channel that sometimes region lock some videos, by using the following
              filter i am able to bypass it <code>availability = 'needs_auth' & channel_id = 'channel_id'</code>.
              and set proxy for that specific video, while leaving the rest of the videos to be downloaded normally.
            </li>
            <li>
              The data which the filter is applied on is the same data that yt-dlp returns, simply, click on the
              information button, and check the data to craft your filter. You will get instant feedback if the
              filter matches or not.
            </li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useStorage } from '@vueuse/core'
import type { ConditionItem, ImportedConditionItem } from '~/types/conditions'
import { useConfirm } from '~/composables/useConfirm'

type ConditionItemWithUI = ConditionItem & { raw?: boolean }

const toast = useNotification()
const socket = useSocketStore()
const box = useConfirm()
const isMobile = useMediaQuery({ maxWidth: 1024 })
const display_style = useStorage<'list' | 'grid'>('conditions_display_style', 'grid')

const items = ref<ConditionItemWithUI[]>([])
const item = ref<Partial<ConditionItem>>({})
const itemRef = ref<string | null | undefined>("")
const toggleForm = ref(false)
const isLoading = ref(false)
const initialLoad = ref(true)
const addInProgress = ref(false)
const remove_keys = ['raw', 'toggle_description']
const expandedItems = ref<Record<string, Set<string>>>({})

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


const reloadContent = async (fromMounted = false): Promise<void> => {
  try {
    isLoading.value = true
    const response = await request('/api/conditions')

    if (fromMounted && !response.ok) {
      return
    }
    const data = await response.json()
    if (data.length < 1) {
      return
    }

    items.value = data
  } catch (e) {
    if (!fromMounted) {
      console.error(e)
      toast.error('Failed to fetch page content.')
    }
  } finally {
    isLoading.value = false
  }
}

const resetForm = (closeForm = false): void => {
  item.value = {}
  itemRef.value = null
  addInProgress.value = false
  if (closeForm) {
    toggleForm.value = false
  }
}

const updateItems = async (newItems: ConditionItem[]): Promise<boolean> => {
  let data: any

  try {
    addInProgress.value = true

    const validItems = newItems.map(({ id, name, filter, cli, extras, enabled, priority, description }) => {
      if (!name || !filter) {
        throw new Error('Name and filter are required.')
      }
      return { id, name, filter, cli, extras, enabled, priority, description }
    })

    const response = await request('/api/conditions', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(validItems),
    })

    data = await response.json() as ConditionItem[]

    if (response.status !== 200) {
      toast.error(`Failed to update items. ${data.error}`)
      return false
    }

    items.value = data
    resetForm(true)
    return true
  } catch (e: any) {
    toast.error(`Failed to update items. ${data?.error ?? ''} ${e.message}`)
  } finally {
    addInProgress.value = false
  }

  return false
}

const deleteItem = async (cond: ConditionItem): Promise<void> => {
  if (true !== (await box.confirm(`Delete '${cond.name}'?`))) {
    return
  }

  const index = items.value.findIndex(t => t?.id === cond.id)
  if (-1 === index) {
    toast.error('Item not found.')
    return
  }

  items.value.splice(index, 1)
  const status = await updateItems(items.value)
  if (status) {
    toast.success('Item deleted.')
  }
}

const updateItem = async ({ reference, item: updatedItem, }: {
  reference: string | null | undefined,
  item: ConditionItem
}): Promise<void> => {
  updatedItem = cleanObject(updatedItem, remove_keys) as ConditionItem

  if (reference) {
    const index = items.value.findIndex(t => t?.id === reference)
    if (index !== -1) {
      items.value[index] = updatedItem
    }
  } else {
    items.value.push(updatedItem)
  }

  const status = await updateItems(items.value)
  if (!status) {
    return
  }

  toast.success(`Item ${reference ? 'updated' : 'added'}.`)
  resetForm(true)
}

const editItem = (_item: ConditionItem): void => {
  item.value = { ..._item }
  itemRef.value = _item.id
  toggleForm.value = true
}

const toggleEnabled = async (cond: ConditionItem): Promise<void> => {
  const index = items.value.findIndex(t => t?.id === cond.id)
  if (-1 === index) {
    toast.error('Item not found.')
    return
  }

  const item = items.value[index]
  if (!item) {
    toast.error('Item not found.')
    return
  }

  item.enabled = !item.enabled
  const status = await updateItems(items.value)
  if (status) {
    toast[item.enabled ? 'success' : 'warning'](`Condition is ${item.enabled ? 'enabled' : 'disabled'}.`)
  }
}

const exportItem = (cond: ConditionItem): void => {
  const clone: Partial<ImportedConditionItem> = JSON.parse(JSON.stringify(cond))
  delete clone.id

  const userData: ImportedConditionItem = {
    ...Object.fromEntries(Object.entries(clone).filter(([_, v]) => !!v)),
    _type: 'condition',
    _version: '1.1',
  } as ImportedConditionItem

  copyText(encode(userData))
}

onMounted(async () => {
  if (socket.isConnected) {
    await reloadContent(true)
  }
})
</script>
