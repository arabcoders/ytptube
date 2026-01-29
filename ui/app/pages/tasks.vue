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
                :disabled="isLoading" v-if="tasks && tasks.length > 0">
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
        <TaskForm :addInProgress="addInProgress" :reference="taskRef" :task="(task as Task)" @cancel="resetForm(true);"
          @submit="updateItem" />
      </div>
    </div>

    <div class="columns is-multiline is-mobile is-justify-content-flex-end"
      v-if="!isLoading && !toggleForm && filteredTasks && filteredTasks.length > 0">
      <div class="column is-narrow">
        <button type="button" class="button" @click="masterSelectAll = !masterSelectAll"
          :class="{ 'has-text-primary': !masterSelectAll, 'has-text-danger': masterSelectAll }">
          <span class="icon">
            <i :class="!masterSelectAll ? 'fa-regular fa-square-check' : 'fa-regular fa-square'" />
          </span>
          <span v-if="!masterSelectAll">Select</span>
          <span v-else>Unselect</span>
          <span v-if="selectedElms.length > 0">
            &nbsp;(<u class="has-text-danger">{{ selectedElms.length }}</u>)
          </span>
        </button>
      </div>

      <div class="column is-2-tablet is-5-mobile">
        <Dropdown label="Actions" icons="fa-solid fa-list">
          <a class="dropdown-item has-text-purple" @click="(selectedElms.length > 0 && !massRun) ? runSelected() : null"
            :style="{ opacity: (selectedElms.length < 1 || massRun) ? 0.5 : 1, cursor: (selectedElms.length < 1 || massRun) ? 'not-allowed' : 'pointer' }">
            <span class="icon"><i class="fa-solid fa-up-right-from-square" /></span>
            <span>Run Selected</span>
          </a>
          <a class="dropdown-item has-text-danger"
            @click="(selectedElms.length > 0 && !massDelete) ? deleteSelected() : null"
            :style="{ opacity: (selectedElms.length < 1 || massDelete) ? 0.5 : 1, cursor: (selectedElms.length < 1 || massDelete) ? 'not-allowed' : 'pointer' }">
            <span class="icon"><i class="fa-solid fa-trash-can" /></span>
            <span>Remove Selected</span>
          </a>
        </Dropdown>
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
                  <span class="icon"><i class="fa-solid fa-save" /></span>
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

    <div class="columns is-multiline" v-if="!toggleForm && (isLoading || !filteredTasks || filteredTasks.length < 1)">
      <div class="column is-12">
        <Message class="is-info" title="Loading" icon="fas fa-spinner fa-spin" v-if="isLoading">
          Loading data. Please wait...
        </Message>
        <Message title="No Results" class="is-warning" icon="fas fa-search" v-else-if="query" :useClose="true"
          @close="query = ''">
          <p>No results found for the query: <code>{{ query }}</code>.</p>
          <p>Please try a different search term.</p>
        </Message>
        <Message class="is-warning" icon="fa-solid fa-info-circle" title="No tasks." v-else>
          There are no tasks defined yet. Click the <span class="icon"><i class="fas fa-add" /></span> <strong>New
            Task</strong> button to create your first automated download task.
        </Message>
      </div>
    </div>

    <div class="columns is-multiline" v-if="!toggleForm && tasks && tasks.length > 0">
      <div class="column is-12">
        <Message class="is-info">
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
            <li><strong>Generate metadata:</strong> will attempt first to save metadata based on the task <code>Download
            path</code> if not set, it will fallback to the <code>Output template</code> with the
              priority of <code>task</code>, <code>preset</code> and then finally to <code>YTP_OUTPUT_TEMPLATE</code>.
              The final path must resolve inside <code>{{ config.app.download_path }}</code>.
            </li>
          </ul>
        </Message>
      </div>
    </div>

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
import { useTasks } from '~/composables/useTasks'
import TaskInspect from '~/components/TaskInspect.vue'
import type { Task, ExportedTask } from '~/types/tasks'
import type { WSEP } from '~/types/sockets'
import { sleep } from '~/utils'
import { useSessionCache } from '~/utils/cache'
import type { item_request } from '~/types/item'

type TaskWithUI = Task & { in_progress?: boolean }

const box = useConfirm()
const toast = useNotification()
const config = useConfigStore()
const socket = useSocketStore()
const stateStore = useStateStore()
const { confirmDialog } = useDialog()
const sessionCache = useSessionCache()
const display_style = useStorage<string>("tasks_display_style", "cards")
const isMobile = useMediaQuery({ maxWidth: 1024 })

const tasksComposable = useTasks()
const { tasks, isLoading, addInProgress } = tasksComposable

const task = ref<Partial<TaskWithUI>>({})
const taskRef = ref<number | null>(null)
const toggleForm = ref<boolean>(false)
const selectedElms = ref<Array<number>>([])
const masterSelectAll = ref(false)
const massRun = ref<boolean>(false)
const massDelete = ref<boolean>(false)
const table_container = ref(false)
const inspectTask = ref<TaskWithUI | null>(null)
const query = ref()
const toggleFilter = ref(false)
const CACHE_KEY = 'tasks:handler_support'
const taskHandlerSupport = ref<Record<string, boolean>>(sessionCache.get(CACHE_KEY) || {})

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
    const element = filteredTasks.value[key] as Task
    if (element.id) {
      selectedElms.value.push(element.id)
    }
  }

})

watch(() => socket.isConnected, async () => {
  if (!socket.isConnected) {
    return
  }
  socket.on('item_status', statusHandler)
})

watch(taskHandlerSupport, newValue => sessionCache.set(CACHE_KEY, newValue), { deep: true })

const getCacheKey = (task: Task): string => `${task.id}:${task.url}`

const cleanStaleCache = (currentTasks: ReadonlyArray<Task>) => {
  const validKeys = new Set(currentTasks.map(task => getCacheKey(task)))
  const cacheKeys = Object.keys(taskHandlerSupport.value)

  for (const key of cacheKeys) {
    if (!validKeys.has(key)) {
      taskHandlerSupport.value[key] = undefined as any
    }
  }
}

const recheckHandlerSupport = async (updatedTasks: ReadonlyArray<Task>) => {
  for (const task of updatedTasks) {
    if (!task.timer && false !== task.handler_enabled) {
      await checkHandlerSupport(task)
    }
  }
}

const checkHandlerSupport = async (task: Task): Promise<boolean> => {
  const cacheKey = getCacheKey(task)

  if (undefined !== taskHandlerSupport.value[cacheKey]) {
    return taskHandlerSupport.value[cacheKey] as boolean
  }

  try {
    const result = await tasksComposable.inspectTaskHandler({
      url: task.url,
      static_only: true
    })
    const supported = true === result?.matched
    taskHandlerSupport.value[cacheKey] = supported
    return supported
  } catch {
    taskHandlerSupport.value[cacheKey] = false
    return false
  }
}

const willTaskBeProcessed = (task: Task): boolean => {
  if (false === task.enabled) {
    return false
  }

  const hasTimer = !!(task.timer && task.timer.trim())
  const cacheKey = getCacheKey(task)
  const hasHandler = false !== task.handler_enabled && true === taskHandlerSupport.value[cacheKey]

  return hasTimer || hasHandler
}

const filteredTasks = computed(() => {
  const q = query.value?.toLowerCase();
  if (!q) return tasks.value;

  return tasks.value.filter(task => deepIncludes(task, q, new WeakSet()));
}) as ComputedRef<Array<TaskWithUI>>;

const reloadContent = async (fromMounted: boolean = false) => {
  try {
    await tasksComposable.loadTasks()

    if (tasks.value.length > 0) {
      cleanStaleCache(tasks.value)
      await recheckHandlerSupport(tasks.value)
    }
  } catch (e) {
    if (!fromMounted) {
      console.error(e)
    }
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
  taskRef.value = null
  if (closeForm) {
    toggleForm.value = false
  }
}

const deleteSelected = async () => {
  if (selectedElms.value.length < 1) {
    toast.error('No tasks selected.')
    return
  }

  const { status } = await confirmDialog({
    title: 'Delete Selected Tasks',
    rawHTML: `Delete <strong class="has-text-danger">${selectedElms.value.length}</strong> task/s?<ul>` + selectedElms.value.map(id => {
      const item = tasks.value.find(t => t.id === id)
      return item ? `<li>${item.id}: ${item.name}</li>` : ''
    }).join('') + `</ul>`,
    confirmText: 'Delete',
    confirmColor: 'is-danger'
  })

  if (true !== status) {
    return
  }

  const itemsToDelete = tasks.value.filter(t => t.id && selectedElms.value.includes(t.id))
  if (itemsToDelete.length < 1) {
    toast.error('No tasks found to delete.')
    return
  }

  massDelete.value = true

  for (const item of itemsToDelete) {
    if (!item.id) {
      continue
    }
    await tasksComposable.deleteTask(item.id)
  }

  selectedElms.value = []

  setTimeout(async () => {
    await nextTick()
    massDelete.value = false
  }, 500)
}

const deleteItem = async (item: Task) => {
  if (!item.id || true !== (await box.confirm(`Delete '${item.name}' task?`))) {
    return
  }
  await tasksComposable.deleteTask(item.id)
}

const toggleEnabled = async (item: Task) => {
  if (!item.id) {
    toast.error('Task ID is missing')
    return
  }

  const updated = await tasksComposable.patchTask(item.id, { enabled: !item.enabled })
  if (updated) {
    item.enabled = updated.enabled
    if (updated.enabled) {
      await checkHandlerSupport(updated)
    }
  }
}

const toggleHandlerEnabled = async (item: Task) => {
  if (!item.id) {
    toast.error('Task ID is missing')
    return
  }

  const updated = await tasksComposable.patchTask(item.id, { handler_enabled: !item.handler_enabled })
  if (updated) {
    item.handler_enabled = updated.handler_enabled
    if (updated.handler_enabled) {
      await checkHandlerSupport(updated)
    }
  }
}

const updateItem = async ({ reference, task, archive_all }: { reference?: number | null | undefined, task: Task, archive_all?: boolean }) => {
  let createdOrUpdated: Task | null = null

  if (reference) {
    createdOrUpdated = await tasksComposable.updateTask(reference, task)
  } else {
    createdOrUpdated = await tasksComposable.createTask(task)
  }

  if (!createdOrUpdated) {
    return
  }

  await checkHandlerSupport(createdOrUpdated)

  if (!reference && true === archive_all && createdOrUpdated.id) {
    await sleep(1)
    await nextTick()
    await archiveAll(createdOrUpdated, true)
  }

  resetForm(true)
}

const editItem = (item: Task) => {
  task.value = { ...item }
  taskRef.value = item.id ?? null
  toggleForm.value = true
}

const calcPath = (path: string) => {
  const loc = shortPath(config.app.download_path || '/downloads')

  if (path) {
    return eTrim(loc, '/') + '/' + sTrim(path, '/')
  }

  return loc
}

onMounted(async () => {
  if (socket.isConnected) {
    socket.on('item_status', statusHandler)
  }
  await reloadContent(true)
});

const tryParse = (expression: string) => {
  try {
    return moment(CronExpressionParser.parse(expression).next().toISOString()).fromNow()
  } catch {
    return "Invalid"
  }
}

const runSelected = async () => {
  if (selectedElms.value.length < 1) {
    toast.error('No tasks selected.')
    return
  }

  const { status } = await confirmDialog({
    rawHTML: `Run the following tasks?<ul>` + selectedElms.value.map(id => {
      const item = tasks.value.find(t => t.id === id)
      return item ? `<li>${item.name}</li>` : ''
    }).join('') + `</ul>`
  })

  if (true !== status) {
    return
  }

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

const runNow = async (item: TaskWithUI, mass: boolean = false) => {
  if (!mass && true !== (await box.confirm(`Run '${item.name}' now? it will also run at the scheduled time.`))) {
    return
  }

  if (false === mass) {
    item.in_progress = true
  }

  const data: item_request = {
    url: item.url,
    preset: item.preset,
    extras: {
      source_name: item.name,
      source_id: item.id,
      source_handler: "Web",
    }
  }

  if (item.folder) {
    data.folder = item.folder
  }

  if (item.template) {
    data.template = item.template
  }

  if (item.cli) {
    data.cli = item.cli
  }

  if (undefined !== item?.auto_start) {
    data.auto_start = item.auto_start
  }

  await stateStore.addDownload(data)

  if (true === mass) {
    return
  }

  setTimeout(async () => {
    await nextTick()
    item.in_progress = false
  }, 500)
}

onBeforeUnmount(() => socket.off('item_status', statusHandler))

const statusHandler = async (payload: WSEP['item_status']) => {
  const { status, msg } = payload.data || {}

  if ('error' === status) {
    toast.error(msg ?? 'Unknown error')
    return
  }
}

const exportItem = async (item: Task) => {
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
  } as ExportedTask

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

const archiveAll = async (item: TaskWithUI, by_pass: boolean = false) => {
  if (!item.id) {
    toast.error('Task ID is missing')
    return
  }

  try {
    if (true !== by_pass) {
      const { status } = await confirmDialog({
        message: `Mark all '${item.name}' items as downloaded in download archive?`
      })

      if (true !== status) {
        return;
      }
    }

    item.in_progress = true
    await tasksComposable.markTaskItems(item.id)
  } catch (e: any) {
    toast.error(`Failed to archive items. ${e.message || 'Unknown error.'}`)
    return
  } finally {
    item.in_progress = false
  }
}

const unarchiveAll = async (item: TaskWithUI) => {
  if (!item.id) {
    toast.error('Task ID is missing')
    return
  }

  try {
    const { status } = await confirmDialog({
      message: `Remove all '${item.name}' items from download archive?`
    })

    if (true !== status) {
      return;
    }

    item.in_progress = true
    await tasksComposable.unmarkTaskItems(item.id)
  } catch (e: any) {
    toast.error(`Failed to remove items from archive. ${e.message || 'Unknown error.'}`)
    return
  } finally {
    item.in_progress = false
  }
}

const generateMeta = async (item: TaskWithUI) => {
  if (!item.id) {
    toast.error('Task ID is missing')
    return
  }

  try {
    const { status } = await confirmDialog({
      rawHTML: `
      <p>
        Generate '${item.name}' metadata? you will be notified when it is done.
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
    await tasksComposable.generateTaskMetadata(item.id)
  } catch (e: any) {
    toast.error(`Failed to generate metadata. ${e.message || 'Unknown error.'}`)
    return
  } finally {
    item.in_progress = false
  }
}
</script>
