<style scoped>
table.is-fixed {
  table-layout: fixed;
}

div.is-centered {
  justify-content: center;
}
</style>

<template>
  <main>
    <div class="mt-1 columns is-multiline">
      <div class="column is-12 is-clearfix is-unselectable">
        <span class="title is-4">
          <span class="icon-text">
            <span class="icon"><i class="fa-solid fa-tasks" /></span>
            <span>Tasks</span>
          </span>
        </span>
        <div class="is-pulled-right">
          <div class="field is-grouped">
            <p class="control">
              <button class="button is-primary" @click="resetForm(false); toggleForm = !toggleForm"
                v-tooltip.bottom="'Toggle Add form'">
                <span class="icon"><i class="fas fa-add" /></span>
              </button>
            </p>

            <p class="control">
              <button v-tooltip.bottom="'Change display style'" class="button has-tooltip-bottom"
                @click="() => display_style = display_style === 'cards' ? 'list' : 'cards'">
                <span class="icon"><i class="fa-solid"
                    :class="{ 'fa-table': display_style === 'cards', 'fa-table-list': display_style === 'list' }" /></span>
              </button>
            </p>

            <p class="control">
              <button class="button is-info" @click="reloadContent" :class="{ 'is-loading': isLoading }"
                :disabled="!socket.isConnected || isLoading" v-if="tasks && tasks.length > 0">
                <span class="icon"><i class="fas fa-refresh" /></span>
              </button>
            </p>
          </div>
        </div>
        <div class="is-hidden-mobile">
          <span class="subtitle">
            The task runner is simple queue system that allows you to schedule downloads to run at the specific time.
          </span>
        </div>
      </div>
    </div>

    <div class="columns is-multiline" v-if="toggleForm">
      <div class="column is-12">
        <TaskForm :addInProgress="addInProgress" :reference="taskRef" :task="task" @cancel="resetForm(true);"
          @submit="updateItem" />
      </div>
    </div>

    <div class="columns is-multiline" v-if="!isLoading && !toggleForm && tasks && tasks.length > 0">
      <template v-if="'list' === display_style">
        <div class="column is-12">
          <div class="table-container">
            <table class="table is-striped is-hoverable is-fullwidth is-bordered"
              style="min-width: 850px; table-layout: fixed;">
              <thead>
                <tr class="has-text-centered is-unselectable">
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
                <tr v-for="item in tasks" :key="item.id">
                  <td class="is-vcentered">
                    <div class="is-text-overflow">
                      <NuxtLink target="_blank" :href="item.url" class="is-bold">
                        {{ item.name }}
                      </NuxtLink>
                    </div>
                    <div v-if="item.preset">
                      <span class="icon"><i class="fa-solid fa-tv" /></span>
                      <span>{{ item.preset ?? config.app.default_preset }}</span>
                    </div>
                  </td>
                  <td class="is-vcentered has-text-centered">
                    <span v-if="item.timer" class="has-tooltip" v-tooltip="item.timer">
                      {{ tryParse(item.timer) }}
                    </span>
                    <span v-else class="has-text-danger">
                      <span class="icon"><i class="fa-solid fa-exclamation-triangle" /></span>
                      <span>No timer is set</span>
                    </span>
                  </td>
                  <td class="is-vcentered is-items-center">
                    <div class="field is-grouped is-grouped-centered">

                      <div class="control">
                        <button class="button is-purple is-small is-fullwidth" v-tooltip="'Run now'"
                          @click="runNow(item)" :class="{ 'is-loading': item?.in_progress }">
                          <span class="icon"><i class="fa-solid fa-up-right-from-square" /></span>
                        </button>
                      </div>

                      <div class="control">
                        <button class="button is-primary is-small is-fullwidth" v-tooltip="'Export'"
                          @click="exportItem(item)">
                          <span class="icon"><i class="fa-solid fa-file-export" /></span>
                        </button>
                      </div>
                      <div class="control">
                        <button class="button is-warning is-small is-fullwidth" v-tooltip="'Edit'"
                          @click="editItem(item)">
                          <span class="icon"><i class="fa-solid fa-cog" /></span>
                        </button>
                      </div>
                      <div class="control">
                        <button class="button is-danger is-small is-fullwidth" v-tooltip="'Delete'"
                          @click="deleteItem(item)">
                          <span class="icon"><i class="fa-solid fa-trash" /></span>
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
        <div class="column is-6" v-for="item in tasks" :key="item.id">
          <div class="card is-flex is-full-height is-flex-direction-column">
            <header class="card-header">
              <div class="card-header-title is-text-overflow is-block">
                <NuxtLink target="_blank" :href="item.url">{{ item.name }}</NuxtLink>
              </div>
              <div class="card-header-icon">
                <a class="has-text-primary" v-tooltip="'Export task.'" @click.prevent="exportItem(item)">
                  <span class="icon"><i class="fa-solid fa-file-export" /></span>
                </a>
              </div>
            </header>
            <div class="card-content is-flex-grow-1">
              <div class="content">
                <p class="is-text-overflow">
                  <span class="icon"><i class="fa-solid fa-clock" /></span>
                  <span v-if="item.timer">{{ tryParse(item.timer) }} - {{ item.timer }}</span>
                  <span v-else>No timer is set</span>
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
                  <span class="icon"><i class="fa-solid fa-cog" /></span>
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
                <button class="button is-purple is-fullwidth" @click="runNow(item)"
                  :class="{ 'is-loading': item?.in_progress }">
                  <span class="icon"><i class="fa-solid fa-up-right-from-square" /></span>
                  <span>Run now</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>

    <div class="columns is-multiline" v-if="!tasks || tasks.length < 1">
      <div class="column is-12">
        <Message message_class="has-background-info-90 has-text-dark" title="Loading" icon="fas fa-spinner fa-spin"
          message="Loading data. Please wait..." v-if="isLoading" />
        <Message title="No tasks" message="No tasks are defined." class="is-background-warning-80 has-text-dark"
          icon="fas fa-exclamation-circle" v-else />
      </div>
    </div>
  </main>
</template>

<script setup>
import moment from 'moment'
import { useStorage } from '@vueuse/core'
import { CronExpressionParser } from 'cron-parser'
import { request } from '~/utils/index'

const toast = useNotification()
const config = useConfigStore()
const socket = useSocketStore()
const box = useConfirm()

const tasks = ref([])
const task = ref({})
const taskRef = ref('')
const toggleForm = ref(false)
const isLoading = ref(true)
const initialLoad = ref(true)
const addInProgress = ref(false)
const display_style = useStorage("tasks_display_style", "cards")
const remove_keys = ['in_progress']

watch(() => config.app.basic_mode, async () => {
  if (!config.app.basic_mode) {
    return
  }
  await navigateTo('/')
})

watch(() => socket.isConnected, async () => {
  if (socket.isConnected && initialLoad.value) {
    socket.on('status', statusHandler)
    await reloadContent(true)
    initialLoad.value = false
  }
})

const reloadContent = async (fromMounted = false) => {
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

const resetForm = (closeForm = false) => {
  task.value = {}
  taskRef.value = null
  addInProgress.value = false
  if (closeForm) {
    toggleForm.value = false
  }
}

const updateTasks = async items => {
  let data = {}

  try {
    addInProgress.value = true

    const response = await request('/api/tasks', {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(items.map(item => cleanObject(toRaw(item), remove_keys))),
    })

    data = await response.json()

    if (200 !== response.status) {
      toast.error(`Failed to update task. ${data.error}`);
      return false
    }

    tasks.value = data
    resetForm(true)
    return true
  } catch (e) {
    toast.error(`Failed to update task. ${data?.error ?? e.message}`);
  } finally {
    addInProgress.value = false
  }
}

const deleteItem = async item => {
  if (true !== box.confirm(`Delete '${item.name}' task?`, true)) {
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

const updateItem = async ({ reference, task }) => {
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

  toast.success('Task updated')
  resetForm(true)
}

const editItem = item => {
  task.value = item
  taskRef.value = item.id
  toggleForm.value = true
}

const calcPath = path => {
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
  socket.on('status', statusHandler)
  await reloadContent(true)
});

const tryParse = expression => {
  try {
    return moment(CronExpressionParser.parse(expression).next().toISOString()).fromNow()
  } catch (e) {
    return "Invalid"
  }
}

const runNow = async item => {
  if (true !== box.confirm(`Run '${item.name}' now? it will also run at the scheduled time.`)) {
    return
  }

  item.in_progress = true

  let data = {
    url: item.url,
    preset: item.preset,
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

  socket.emit('add_url', data)

  setTimeout(async () => {
    await nextTick()
    item.in_progress = false
  }, 500)
}

onUnmounted(() => socket.off('status', statusHandler))

const statusHandler = async stream => {
  const { status, msg } = JSON.parse(stream)

  if ('error' === status) {
    toast.error(msg)
    return
  }
}

const exportItem = async item => {
  const info = JSON.parse(JSON.stringify(item))

  let data = {
    name: info.name,
    url: info.url,
    preset: info.preset,
    timer: info.timer,
    folder: info.folder,
  }

  if (info.template) {
    data.template = info.template
  }

  if (info.cli) {
    data.cli = info.cli
  }

  data['_type'] = 'task'
  data['_version'] = '2.0'

  return copyText(base64UrlEncode(JSON.stringify(data)));
}


</script>
