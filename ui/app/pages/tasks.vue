<template>
  <main>
    <div class="mt-1 columns is-multiline">
      <div class="column is-12 is-clearfix is-unselectable">
        <span class="title is-4">
          <span class="icon-text">
            <template v-if="toggleForm">
              <span class="icon"><i class="fa-solid" :class="{ 'fa-edit': taskRef, 'fa-plus': !taskRef }" /></span>
              <span>{{ taskRef ? `Edit - ${task.name}` : 'Add new task' }}</span>
            </template>
            <template v-else>
              <span class="icon"><i class="fa-solid fa-tasks" /></span>
              <span>Tasks</span>
            </template>
          </span>
        </span>
        <div class="is-pulled-right" v-if="!toggleForm">
          <div class="field is-grouped">
            <p class="control has-icons-left" v-if="toggleFilter && tasks && tasks.length > 0">
              <input type="search" v-model.lazy="query" class="input" id="filter"
                placeholder="Filter displayed content">
              <span class="icon is-left"><i class="fas fa-filter" /></span>
            </p>

            <p class="control" v-if="tasks && tasks.length > 0">
              <button class="button is-danger is-light" @click="toggleFilter = !toggleFilter">
                <span class="icon"><i class="fas fa-filter" /></span>
                <span v-if="!isMobile">Filter</span>
              </button>
            </p>

            <p class="control">
              <button class="button is-primary" @click="resetForm(false); toggleForm = !toggleForm">
                <span class="icon"><i class="fas fa-add" /></span>
                <span v-if="!isMobile"> New Task</span>
              </button>
            </p>

            <p class="control">
              <button class="button" @click="() => display_style = display_style === 'list' ? 'grid' : 'list'">
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
                :disabled="!socket.isConnected || isLoading" v-if="tasks && tasks.length > 0">
                <span class="icon"><i class="fas fa-refresh" /></span>
                <span v-if="!isMobile">Reload</span>
              </button>
            </p>
          </div>
        </div>
        <div class="is-hidden-mobile" v-if="!toggleForm">
          <span class="subtitle">
            The task runner is simple queue system that allows you to poll channels or playlists for new content at
            specified intervals.
          </span>
        </div>
      </div>
    </div>

    <div class="columns is-multiline" v-if="toggleForm">
      <div class="column is-12">
        <TaskForm :addInProgress="addInProgress" :reference="taskRef" :task="task as task_item"
          @cancel="resetForm(true);" @submit="updateItem" />
      </div>
    </div>

    <div class="columns is-multiline is-mobile" v-if="!toggleForm && filteredTasks && filteredTasks.length > 0">
      <div class="column">
        <button type="button" class="button is-fullwidth is-ghost is-inverted"
          @click="masterSelectAll = !masterSelectAll">
          <span class="icon-text is-block">
            <span class="icon">
              <i :class="!masterSelectAll ? 'fa-regular fa-square-check' : 'fa-regular fa-square'" />
            </span>
            <span v-if="!masterSelectAll">Select All</span>
            <span v-else>Unselect All</span>
          </span>
        </button>
      </div>

      <div class="column">
        <button class="button is-purple is-fullwidth" @click="runConfirm()"
          :disabled="selectedElms.length < 1 || massRun" :class="{ 'is-loading': massRun }">
          <span class="icon"><i class="fa-solid fa-up-right-from-square" /></span>
          <span>Run Selected</span>
        </button>
      </div>

      <div class="column">
        <button type="button" class="button is-fullwidth is-danger" @click="deleteConfirm()"
          :disabled="selectedElms.length < 1 || massDelete" :class="{ 'is-loading': massDelete }">
          <span class="icon-text is-block">
            <span class="icon"><i class="fa-solid fa-trash-can" /></span>
            <span>Remove Selected</span>
          </span>
        </button>
      </div>
    </div>

    <div class="columns is-multiline" v-if="!isLoading && !toggleForm && filteredTasks && filteredTasks.length > 0">
      <template v-if="'list' === display_style">
        <div class="column is-12">
          <div :class="{ 'table-container': table_container }">
            <table class="table is-striped is-hoverable is-fullwidth is-bordered"
              style="min-width: 850px; table-layout: fixed;">
              <thead>
                <tr class="has-text-centered is-unselectable">
                  <th width="5%">
                    <label class="checkbox is-block">
                      <input class="completed-checkbox" type="checkbox" v-model="masterSelectAll">
                    </label>
                  </th>
                  <th width="50%">
                    <span class="icon"><i class="fa-solid fa-tasks" /></span>
                    <span>Task</span>
                  </th>
                  <th width="30%">
                    <span class="icon"><i class="fa-solid fa-clock" /></span>
                    <span>Timer</span>
                  </th>
                  <th width="20%">
                    <span class="icon"><i class="fa-solid fa-gear" /></span>
                    <span>Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in filteredTasks" :key="item.id">
                  <td class="is-vcentered has-text-centered">
                    <label class="checkbox is-block">
                      <input class="completed-checkbox" type="checkbox" v-model="selectedElms" :value="item.id">
                    </label>
                  </td>
                  <td class="is-text-overflow is-vcentered">
                    <div class="is-inline is-pulled-right">
                      <span v-for="(tag, index) in get_tags(item.name)" :key="index" class="tag is-info">
                        {{ tag }}
                      </span>
                    </div>
                    <div>
                      <NuxtLink target="_blank" :href="item.url" class="is-bold">
                        {{ remove_tags(item.name) }}
                      </NuxtLink>
                    </div>
                    <div class="is-unselectable">
                      <span class="icon-text is-clickable" @click="toggleEnabled(item)"
                        v-tooltip="'Click to ' + (item.enabled !== false ? 'disable' : 'enable') + ' task'">
                        <span class="icon">
                          <i class="fa-solid fa-power-off"
                            :class="{ 'has-text-success': item.enabled !== false, 'has-text-danger': item.enabled === false }" />
                        </span>
                        <span>{{ item.enabled !== false ? 'Enabled' : 'Disabled' }}</span>
                      </span>
                      &nbsp;
                      <span class="icon-text">
                        <span class="icon">
                          <i class="fa-solid"
                            :class="{ 'fa-circle-pause': item.auto_start, 'fa-circle-play': !item.auto_start }" />
                        </span>
                        <span>
                          {{ item.auto_start ? 'Auto' : 'Manual' }}
                        </span>
                      </span>
                      &nbsp;
                      <span class="icon-text is-clickable" @click="toggleHandlerEnabled(item)"
                        v-tooltip="'Click to ' + (item.handler_enabled !== false ? 'disable' : 'enable') + ' task handler'">
                        <span class="icon">
                          <i class="fa-solid fa-rss"
                            :class="{ 'has-text-success': item.handler_enabled !== false, 'has-text-danger': item.handler_enabled === false }" />
                        </span>
                        <span>{{ item.handler_enabled !== false ? 'Enabled' : 'Disabled' }}</span>
                      </span>
                      &nbsp;
                      <span class="icon-text" v-if="item.preset">
                        <span class="icon"><i class="fa-solid fa-tv" /></span>
                        <span>{{ item.preset ?? config.app.default_preset }}</span>
                      </span>
                    </div>
                  </td>
                  <td class="is-vcentered has-text-centered">
                    <span v-if="item.timer" class="has-tooltip" v-tooltip="item.timer">
                      {{ tryParse(item.timer) }}
                    </span>
                    <span v-else-if="!willTaskBeProcessed(item)" class="has-text-danger">
                      <span class="icon"> <i class="fa-solid fa-exclamation" /> </span>
                      No timer or handler
                    </span>
                    <span v-else>
                      <span class="icon"> <i class="fa-solid fa-rss" /> </span>
                      Handler only
                    </span>
                  </td>
                  <td class="is-vcentered is-items-center">
                    <div class="field is-grouped is-grouped-centered">
                      <div class="control">
                        <button class="button is-warning is-small is-fullwidth" @click="editItem(item)">
                          <span class="icon"><i class="fa-solid fa-edit" /></span>
                        </button>
                      </div>
                      <div class="control">
                        <button class="button is-danger is-small is-fullwidth" @click="deleteItem(item)">
                          <span class="icon"><i class="fa-solid fa-trash" /></span>
                        </button>
                      </div>

                      <div class="control is-expanded">
                        <Dropdown icons="fa-solid fa-cogs" label="Actions" button_classes="is-small">
                          <NuxtLink class="dropdown-item has-text-purple" @click="runNow(item)">
                            <span class="icon"><i class="fa-solid fa-up-right-from-square" /></span>
                            <span>Run now</span>
                          </NuxtLink>

                          <NuxtLink class="dropdown-item" @click="generateMeta(item)">
                            <span class="icon"><i class="fa-solid fa-photo-film" /></span>
                            <span>Generate metadata</span>
                          </NuxtLink>

                          <hr class="dropdown-divider" />

                          <NuxtLink class="dropdown-item" @click="() => inspectTask = item">
                            <span class="icon"><i class="fa-solid fa-magnifying-glass" /></span>
                            <span>Inspect Handler</span>
                          </NuxtLink>

                          <hr class="dropdown-divider" />

                          <NuxtLink class="dropdown-item" @click="archiveAll(item)">
                            <span class="icon"><i class="fa-solid fa-box-archive" /></span>
                            <span>Archive All</span>
                          </NuxtLink>

                          <NuxtLink class="dropdown-item" @click="unarchiveAll(item)">
                            <span class="icon"><i class="fa-solid fa-box-archive" /></span>
                            <span>Unarchive All</span>
                          </NuxtLink>

                          <hr class="dropdown-divider" />

                          <NuxtLink class="dropdown-item has-text-info" @click="exportItem(item)">
                            <span class="icon"><i class="fa-solid fa-file-export" /></span>
                            <span>Export Task</span>
                          </NuxtLink>

                        </Dropdown>
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
        <div class="column is-6" v-for="item in filteredTasks" :key="item.id">
          <div class="card is-flex is-full-height is-flex-direction-column">
            <header class="card-header">
              <div class="card-header-title is-text-overflow is-block">
                <NuxtLink target="_blank" :href="item.url">
                  {{ remove_tags(item.name) }}
                </NuxtLink>
                <span class="icon" v-if="item.in_progress">
                  <i class="fa-solid fa-spinner fa-spin has-text-info" />
                </span>
                <span class="tag is-danger is-small ml-1" v-if="!item.enabled">Disabled</span>
              </div>
              <div class="card-header-icon">
                <div class="field is-grouped">
                  <div class="control" v-for="(tag, index) in get_tags(item.name)" :key="index">
                    <span class="tag is-info">
                      {{ tag }}
                    </span>
                  </div>
                  <div class="control">
                    <span class="icon" v-tooltip="`${item.auto_start ? 'Auto' : 'Manual'} start`">
                      <i class="fa-solid"
                        :class="{ 'fa-circle-pause has-text-success': item.auto_start, 'fa-circle-play has-text-danger': !item.auto_start }" />
                    </span>
                  </div>
                  <div class="control is-clickable" @click="toggleHandlerEnabled(item)">
                    <span class="icon"
                      v-tooltip="`Task handler is ${item.handler_enabled !== false ? 'enabled' : 'disabled'}. Click to toggle.`">
                      <i class="fa-solid fa-rss"
                        :class="{ 'has-text-success': item.handler_enabled !== false, 'has-text-danger': item.handler_enabled === false }" />
                    </span>
                  </div>
                  <div class="control is-clickable" @click="toggleEnabled(item)">
                    <span class="icon"
                      v-tooltip="`Task is ${item.enabled !== false ? 'enabled' : 'disabled'}. Click to toggle.`">
                      <i class="fa-solid fa-power-off"
                        :class="{ 'has-text-success': item.enabled !== false, 'has-text-danger': item.enabled === false }" />
                    </span>
                  </div>
                  <div class="control">
                    <a class="has-text-info" @click.prevent="exportItem(item)">
                      <span class="icon"><i class="fa-solid fa-file-export" /></span>
                    </a>
                  </div>
                  <div class="control">
                    <label class="checkbox is-block">
                      <input class="completed-checkbox" type="checkbox" v-model="selectedElms" :value="item.id">
                    </label>
                  </div>
                </div>
              </div>
            </header>
            <div class="card-content is-flex-grow-1">
              <div class="content">
                <p class="is-text-overflow">
                  <span class="icon">
                    <i class="fa-solid" :class="{
                      'fa-clock': item.timer,
                      'fa-rss': !item.timer && willTaskBeProcessed(item),
                      'has-text-danger fa-exclamation': !willTaskBeProcessed(item)
                    }" />
                  </span>
                  <span v-if="item.timer">
                    <NuxtLink target="_blank" :to="`https://crontab.guru/#${item.timer.replace(/ /g, '_')}`">
                      {{ item.timer }} - {{ tryParse(item.timer) }}
                    </NuxtLink>
                  </span>
                  <span v-else-if="willTaskBeProcessed(item)">Handler only</span>
                  <span v-else class="has-text-danger">No timer or handler</span>
                </p>
                <p class="is-text-overflow" v-if="item.folder">
                  <span class="icon"><i class="fa-solid fa-folder" /></span>
                  <span>{{ calcPath(item.folder) }}</span>
                </p>
                <p class="is-text-overflow" v-if="item.template">
                  <span class="icon"><i class="fa-solid fa-file" /></span>
                  <span>{{ item.template }}</span>
                </p>
                <p class="is-text-overflow">
                  <span class="icon"><i class="fa-solid fa-tv" /></span>
                  <span>{{ item.preset ?? config.app.default_preset }}</span>
                </p>
                <p class="is-text-overflow" v-if="item.cli">
                  <span class="icon"><i class="fa-solid fa-terminal" /></span>
                  <span>{{ item.cli }}</span>
                </p>
              </div>
            </div>
            <div class="card-footer mt-auto">
              <div class="card-footer-item">
                <button class="button is-warning is-fullwidth" @click="editItem(item);">
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

              <div class="card-footer-item">
                <Dropdown icons="fa-solid fa-cogs" label="Actions">
                  <NuxtLink class="dropdown-item has-text-purple" @click="runNow(item)">
                    <span class="icon"><i class="fa-solid fa-up-right-from-square" /></span>
                    <span>Run now</span>
                  </NuxtLink>

                  <NuxtLink class="dropdown-item" @click="generateMeta(item)">
                    <span class="icon"><i class="fa-solid fa-photo-film" /></span>
                    <span>Generate metadata</span>
                  </NuxtLink>

                  <hr class="dropdown-divider" />

                  <NuxtLink class="dropdown-item" @click="() => inspectTask = item">
                    <span class="icon"><i class="fa-solid fa-magnifying-glass" /></span>
                    <span>Inspect Handler</span>
                  </NuxtLink>

                  <hr class="dropdown-divider" />

                  <NuxtLink class="dropdown-item" @click="archiveAll(item)">
                    <span class="icon"><i class="fa-solid fa-box-archive" /></span>
                    <span>Archive All</span>
                  </NuxtLink>

                  <NuxtLink class="dropdown-item" @click="unarchiveAll(item)">
                    <span class="icon"><i class="fa-solid fa-box-archive" /></span>
                    <span>Unarchive All</span>
                  </NuxtLink>
                </Dropdown>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>

    <div class="columns is-multiline">
      <div class="column is-12">

      </div>
    </div>

    <div class="columns is-multiline" v-if="!filteredTasks || filteredTasks.length < 1">
      <div class="column is-12">

        <Message :newStyle="true" message_class="is-info" v-if="isLoading">
          <p><span class="icon"><i class="fas fa-spinner fa-spin" /></span> Loading data. Please wait...</p>
        </Message>
        <Message title="No Results" message_class="is-warning" icon="fas fa-search" v-else-if="query" :useClose="true"
          @close="query = ''" :newStyle="true">
          <p>No results found for the query: <strong>{{ query }}</strong>.</p>
          <p>Please try a different search term.</p>
        </Message>
        <Message message_class="is-warning" :newStyle="true" v-else>
          <p>
            <span class="icon"><i class="fa-solid fa-info-circle" /></span>
            <span>No tasks are defined.</span>
          </p>
        </Message>
      </div>
    </div>

    <div class="columns is-multiline" v-if="!toggleForm && tasks && tasks.length > 0">
      <div class="column is-12">
        <Message :newStyle="true" message_class="is-info">
          <ul>
            <li class="has-text-danger">
              <span class="icon">
                <i class="fas fa-triangle-exclamation" />
              </span>
              All tasks operations require <code>--download-archive</code> to be set in the <b>preset</b> or in the
              <b>command options for yt-dlp</b> for the task to be dispatched. If you have selected one of the built
              in presets it already includes this option and no further action is required.
            </li>
            <li>To avoid downloading all existing content from a channel/playlist, use <code><span class="icon"><i
                class="fa-solid fa-cogs" /></span> Actions > <span class="icon"><i
                class="fa-solid fa-box-archive" /></span> Archive All</code> to mark existing items as already
              downloaded.
            </li>
            <li><strong>Custom Handlers:</strong> Leave timer empty for custom handler definitions. The handler runs
              hourly and doesn't require timer.
            </li>
          </ul>
        </Message>
      </div>
    </div>

    <ConfirmDialog v-if="dialog_confirm.visible" :visible="dialog_confirm.visible" :title="dialog_confirm.title"
      :message="dialog_confirm.message" :options="dialog_confirm.options" @confirm="dialog_confirm.confirm"
      :html_message="dialog_confirm.html_message" @cancel="dialog_confirm = reset_dialog()" />

    <Modal v-if="inspectTask" @close="() => inspectTask = null" :contentClass="`modal-content-max`">
      <TaskInspect :url="inspectTask.url" :preset="inspectTask.preset" />
    </Modal>
  </main>
</template>

<script setup lang="ts">
import moment from 'moment'
import { useStorage } from '@vueuse/core'
import { CronExpressionParser } from 'cron-parser'
import Modal from '~/components/Modal.vue'
import { useConfirm } from '~/composables/useConfirm'
import TaskInspect from '~/components/TaskInspect.vue'
import type { task_item, exported_task, error_response } from '~/types/tasks'
import { sleep } from '~/utils'
import { useSessionCache } from '~/utils/cache'

const box = useConfirm()
const toast = useNotification()
const config = useConfigStore()
const socket = useSocketStore()
const { confirmDialog: cDialog } = useDialog()
const sessionCache = useSessionCache()
const display_style = useStorage<string>("tasks_display_style", "cards")
const isMobile = useMediaQuery({ maxWidth: 1024 })

const tasks = ref<Array<task_item>>([])
const task = ref<task_item | Record<string, unknown>>({})
const taskRef = ref<string>('')
const toggleForm = ref<boolean>(false)
const isLoading = ref<boolean>(true)
const initialLoad = ref<boolean>(true)
const addInProgress = ref<boolean>(false)
const selectedElms = ref<Array<string>>([])
const masterSelectAll = ref(false)
const massRun = ref<boolean>(false)
const massDelete = ref<boolean>(false)
const table_container = ref(false)
const inspectTask = ref<task_item | null>(null)

const reset_dialog = () => ({
  visible: false,
  title: 'Confirm Action',
  confirm: (_opts: any) => { },
  message: '',
  html_message: '',
  options: [],
});

const dialog_confirm = ref(reset_dialog())

const remove_keys = ['in_progress']

const query = ref()
const toggleFilter = ref(false)

watch(toggleFilter, () => {
  if (!toggleFilter.value) {
    query.value = ''
  }
});

watch(query, () => {
  masterSelectAll.value = false
  selectedElms.value = []
})

watch(masterSelectAll, value => {
  if (!value) {
    selectedElms.value = []
    return
  }
  for (const key in filteredTasks.value) {
    const element = filteredTasks.value[key] as task_item
    selectedElms.value.push(element.id)
  }
})

watch(() => socket.isConnected, async () => {
  if (socket.isConnected && initialLoad.value) {
    socket.on('item_status', statusHandler)
    await reloadContent(true)
    initialLoad.value = false
  }
})

const CACHE_KEY = 'tasks:handler_support'
const taskHandlerSupport = ref<Record<string, boolean>>(sessionCache.get(CACHE_KEY) || {})
watch(taskHandlerSupport, (newValue) => sessionCache.set(CACHE_KEY, newValue), { deep: true })

const getCacheKey = (task: task_item): string => `${task.id}:${task.url}`

const cleanStaleCache = (currentTasks: Array<task_item>) => {
  const validKeys = new Set(currentTasks.map(task => getCacheKey(task)))
  const cacheKeys = Object.keys(taskHandlerSupport.value)

  for (const key of cacheKeys) {
    if (!validKeys.has(key)) {
      taskHandlerSupport.value[key] = undefined as any
    }
  }
}

const recheckHandlerSupport = async (updatedTasks: Array<task_item>) => {
  for (const task of updatedTasks) {
    if (!task.timer && false !== task.handler_enabled) {
      await checkHandlerSupport(task)
    }
  }
}

const checkHandlerSupport = async (task: task_item): Promise<boolean> => {
  const cacheKey = getCacheKey(task)

  if (undefined !== taskHandlerSupport.value[cacheKey]) {
    return taskHandlerSupport.value[cacheKey] as boolean
  }

  try {
    const response = await request('/api/tasks/inspect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: task.url, static_only: true })
    })
    const data = await response.json()
    const supported = true === data?.matched
    taskHandlerSupport.value[cacheKey] = supported
    return supported
  } catch {
    taskHandlerSupport.value[cacheKey] = false
    return false
  }
}

const willTaskBeProcessed = (task: task_item): boolean => {
  if (false === task.enabled) {
    return false
  }

  const hasTimer = !!(task.timer && task.timer.trim())
  const cacheKey = getCacheKey(task)
  const hasHandler = false !== task.handler_enabled && true === taskHandlerSupport.value[cacheKey]

  return hasTimer || hasHandler
}

const filteredTasks = computed<task_item[]>(() => {
  const q = query.value?.toLowerCase();
  if (!q) return tasks.value;

  return tasks.value.filter(
    task => Object.values(task).some(value => typeof value === 'string' && value.toLowerCase().includes(q))
  );
});

const reloadContent = async (fromMounted: boolean = false) => {
  try {
    isLoading.value = true
    const response = await request('/api/tasks')

    if (fromMounted && !response.ok) {
      return
    }

    const data = await response.json()
    if (data.length < 1) {
      return
    }

    tasks.value = data
    cleanStaleCache(data)
    await recheckHandlerSupport(data)
  } catch (e) {
    if (fromMounted) {
      return
    }
    console.error(e)
    toast.error('Failed to fetch tasks.')
  } finally {
    isLoading.value = false
  }
}

const resetForm = (closeForm: boolean = false) => {
  task.value = {
    name: '',
    url: '',
    timer: '',
    preset: '',
    folder: '',
    template: '',
    cli: '',
    auto_start: true,
    handler_enabled: true,
    enabled: true
  }
  taskRef.value = ''
  addInProgress.value = false
  if (closeForm) {
    toggleForm.value = false
  }
}

const updateTasks = async (items: Array<task_item>) => {
  try {
    addInProgress.value = true

    const response = await request('/api/tasks', {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(items.map(item => cleanObject(toRaw(item), remove_keys))),
    })

    const data: Array<task_item> | error_response = await response.json()

    if ("error" in data) {
      toast.error(`Failed to update tasks. ${data.error}`);
      return false
    }

    tasks.value = data
    cleanStaleCache(data)
    await recheckHandlerSupport(data)
    resetForm(true)
    return true
  } catch (e: any) {
    toast.error(`Failed to update tasks. ${e.message}`);
  } finally {
    addInProgress.value = false
  }
}

const deleteConfirm = () => {
  if (selectedElms.value.length < 1) {
    toast.error('No tasks selected.')
    return
  }
  dialog_confirm.value.visible = true
  dialog_confirm.value.title = 'Delete Selected Tasks'
  dialog_confirm.value.message = `Delete ${selectedElms.value.length} task/s?`
  dialog_confirm.value.confirm = async () => await deleteSelected()
}

const deleteSelected = async () => {
  if (selectedElms.value.length < 1) {
    toast.error('No tasks selected.')
    return
  }

  massDelete.value = true
  dialog_confirm.value = reset_dialog()

  const itemsToDelete = tasks.value.filter(t => selectedElms.value.includes(t.id))
  if (itemsToDelete.length < 1) {
    toast.error('No tasks found to delete.')
    return
  }

  for (const item of itemsToDelete) {
    const index = tasks.value.findIndex(t => t?.id === item.id)
    if (index > -1) {
      tasks.value.splice(index, 1)
    }
  }

  await nextTick()
  const status = await updateTasks(tasks.value)
  selectedElms.value = []

  if (!status) {
    return
  }

  toast.success('Tasks deleted.')
  setTimeout(async () => {
    await nextTick()
    massDelete.value = false
  }, 500)
}

const deleteItem = async (item: task_item) => {
  if (true !== (await box.confirm(`Delete '${item.name}' task?`))) {
    return
  }

  const index = tasks.value.findIndex((t) => t?.id === item.id)
  if (index > -1) {
    tasks.value.splice(index, 1)
  } else {
    toast.error('Task not found')
    return
  }

  const status = await updateTasks(tasks.value)

  if (!status) {
    return
  }

  toast.success('Task deleted.')
}

const toggleEnabled = async (item: task_item) => {
  const newStatus = !item.enabled
  const actionText = newStatus ? 'enable' : 'disable'

  try {
    const response = await request(`/api/tasks/${item.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: newStatus })
    })
    const data = await response.json()

    if (data?.error) {
      toast.error(data.error)
      return
    }

    item.enabled = data.enabled
    const func = data.enabled ? 'success' : 'warning'
    toast[func](`Task '${item.name}' ${data.enabled ? 'enabled' : 'disabled'}.`)
  } catch (e: any) {
    toast.error(`Failed to ${actionText} task. ${e.message || 'Unknown error.'}`)
  }
}

const toggleHandlerEnabled = async (item: task_item) => {
  const newStatus = !item.handler_enabled
  const actionText = newStatus ? 'enable' : 'disable'

  try {
    const response = await request(`/api/tasks/${item.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ handler_enabled: newStatus })
    })
    const data = await response.json()

    if (data?.error) {
      toast.error(data.error)
      return
    }

    item.handler_enabled = data.handler_enabled
    const func = data.handler_enabled ? 'success' : 'warning'
    toast[func](`Task handler for '${item.name}' ${data.handler_enabled ? 'enabled' : 'disabled'}.`)
  } catch (e: any) {
    toast.error(`Failed to ${actionText} task handler. ${e.message || 'Unknown error.'}`)
  }
}

const updateItem = async ({ reference, task, archive_all }: { reference?: string | null | undefined, task: task_item, archive_all?: boolean }) => {
  if (reference) {
    // -- find the task index.
    const index = tasks.value.findIndex((t) => t?.id === reference)
    if (index > -1) {
      tasks.value[index] = task
    }
  } else {
    tasks.value.push(task)
  }

  const status = await updateTasks(tasks.value)
  if (!status) {
    return
  }

  toast.success('Task updated.')

  if (!reference && true === archive_all) {
    const newTask = tasks.value[tasks.value.length - 1]
    if (newTask) {
      await sleep(1)
      await nextTick()
      await archiveAll(newTask, true)
    }
  }

  resetForm(true)
}

const editItem = (item: task_item) => {
  task.value = item
  taskRef.value = item.id
  toggleForm.value = true
}

const calcPath = (path: string) => {
  const loc = config.app.download_path || '/downloads'

  if (path) {
    return loc + '/' + sTrim(path, '/')
  }

  return loc
}

onMounted(async () => {
  if (!socket.isConnected) {
    return;
  }
  socket.on('item_status', statusHandler)
  await reloadContent(true)
});

const tryParse = (expression: string) => {
  try {
    return moment(CronExpressionParser.parse(expression).next().toISOString()).fromNow()
  } catch {
    return "Invalid"
  }
}

const runConfirm = () => {
  if (selectedElms.value.length < 1) {
    toast.error('No tasks selected.')
    return
  }
  dialog_confirm.value.visible = true
  dialog_confirm.value.title = 'Run Selected Tasks'

  dialog_confirm.value.html_message = `Run the following tasks?<ul>` + selectedElms.value.map(id => {
    const item = tasks.value.find(t => t.id === id)
    return item ? `<li>${item.name}</li>` : ''
  }).join('') + `</ul>`

  dialog_confirm.value.confirm = async () => await runSelected()
}

const runSelected = async () => {
  if (selectedElms.value.length < 1) {
    toast.error('No tasks selected.')
    return
  }

  dialog_confirm.value = reset_dialog()

  massRun.value = true

  for (const id of selectedElms.value) {
    const item = tasks.value.find(t => t.id === id)
    if (!item) {
      continue

    }
    await runNow(item, true)
  }

  selectedElms.value = []
  toast.success('Dispatched selected tasks.')
  setTimeout(async () => {
    await nextTick()
    massRun.value = false
  }, 500)
}

const runNow = async (item: task_item, mass: boolean = false) => {
  if (!mass && true !== (await box.confirm(`Run '${item.name}' now? it will also run at the scheduled time.`))) {
    return
  }

  if (false === mass) {
    item.in_progress = true
  }

  const data = {
    url: item.url,
    preset: item.preset,
  } as task_item

  if (item.folder) {
    data.folder = item.folder
  }

  if (item.template) {
    data.template = item.template
  }

  if (item.cli) {
    data.cli = item.cli
  }

  if (item?.auto_start !== undefined) {
    data.auto_start = item.auto_start
  }

  socket.emit('add_url', data)

  if (true === mass) {
    return
  }

  setTimeout(async () => {
    await nextTick()
    item.in_progress = false
  }, 500)
}

onBeforeUnmount(() => socket.off('item_status', statusHandler))

const statusHandler = async (stream: string) => {
  const json = JSON.parse(stream)
  const { status, msg } = json.data

  if ('error' === status) {
    toast.error(msg)
    return
  }
}

const exportItem = async (item: task_item) => {
  const info = JSON.parse(JSON.stringify(item))

  const data = {
    name: info.name,
    url: info.url,
    preset: info.preset,
    timer: info.timer,
    folder: info.folder,
    auto_start: info?.auto_start ?? true,
    handler_enabled: info?.handler_enabled ?? true,
    enabled: info?.enabled ?? true,
  } as exported_task

  if (info.template) {
    data.template = info.template
  }

  if (info.cli) {
    data.cli = info.cli
  }

  data._type = 'task'
  data._version = '2.0'

  return copyText(encode(data));
}

const get_tags = (name: string): Array<string> => {
  const regex = /\[(.*?)\]/g;
  const matches = name.match(regex);
  return !matches ? [] : matches.map(tag => tag.replace(/[[\]]/g, '').trim());
}

const remove_tags = (name: string): string => name.replace(/\[(.*?)\]/g, '').trim();

const archiveAll = async (item: task_item, by_pass: boolean = false) => {
  try {

    if (true !== by_pass) {
      const { status } = await cDialog({
        message: `Mark all '${item.name}' items as downloaded in download archive?`
      })

      if (true !== status) {
        return;
      }
    }

    item.in_progress = true

    const response = await request(`/api/tasks/${item.id}/mark`, { method: 'POST' })
    const data = await response.json()

    if (data?.error) {
      toast.error(data.error)
      return
    }

    toast.success(data.message)
  } catch (e: any) {
    toast.error(`Failed to archive items. ${e.message || 'Unknown error.'}`)
    return
  } finally {
    item.in_progress = false
  }
}

const unarchiveAll = async (item: task_item) => {
  try {
    const { status } = await cDialog({
      message: `Remove all '${item.name}' items from download archive?`
    })

    if (true !== status) {
      return;
    }

    item.in_progress = true

    const response = await request(`/api/tasks/${item.id}/mark`, { method: 'DELETE' })
    const data = await response.json()

    if (data?.error) {
      toast.error(data.error)
      return
    }

    toast.success(data.message)
  } catch (e: any) {
    toast.error(`Failed to remove items from archive. ${e.message || 'Unknown error.'}`)
    return
  } finally {
    item.in_progress = false
  }
}

const generateMeta = async (item: task_item) => {
  try {
    let path = '/';
    if (item.folder) {
      path = `/${sTrim(item.folder, '/')}`
    }
    const { status } = await cDialog({
      rawHTML: `
      <p>
        Generate '${item.name}' metadata in '<b class="has-text-danger">${path}</b>'? you will be notified when it is done.
      </p>
      <p>
        <b>This action will generate:</b>
        <ul>
          <li><strong>tvshow.nfo</strong> - for media center compatibility</li>
          <li><strong>title [id].info.json</strong> - yt-dlp metadata file</li>
          <li>
          <strong>Thumbnails</strong>: poster.jpg, fanart.jpg, thumb.jpg, banner.jpg, icon.jpg, landscape.jpg
          <u>if they are available</u>.
          </li>
        </ul>
      </p>
      <p class="has-text-danger">
          <span class="icon"><i class="fa-solid fa-triangle-exclamation"></i></span>
          <span>Warning</span>: This will overwrite existing metadata files if they exist.
      </p>`

    })

    if (true !== status) {
      return;
    }

    item.in_progress = true
    const response = await request(`/api/tasks/${item.id}/metadata`, { method: 'POST' })
    const data = await response.json()

    if (data?.error) {
      toast.error(data.error)
      return
    }

    toast.success('Metadata generation completed.')
  } catch (e: any) {
    toast.error(`Failed to generate metadata. ${e.message || 'Unknown error.'}`)
    return
  } finally {
    item.in_progress = false
  }
}
</script>
