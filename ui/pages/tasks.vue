<style scoped>
table.is-fixed {
  table-layout: fixed;
}

div.table-container {
  overflow: hidden;
}

div.is-centered {
  justify-content: center;
}
</style>

<template>
  <div>
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
              <button class="button is-primary" @click="resetForm(false); toggleForm = !toggleForm">
                <span class="icon"><i class="fas fa-add"></i></span>
              </button>
            </p>
            <p class="control">
              <button class="button is-info" @click="reloadContent" :class="{ 'is-loading': isLoading }"
                :disabled="!socket.isConnected || isLoading" v-if="tasks && tasks.length > 0">
                <span class="icon"><i class="fas fa-refresh"></i></span>
              </button>
            </p>
          </div>
        </div>
        <div class="is-hidden-mobile">
          <span class="subtitle">
            The task runner is simply queuing given urls at the specified time. It's basically doing what you are doing
            when you click the add button on the WebGUI, this just fancy way to automate that.
          </span>
        </div>
      </div>

      <div class="column is-12" v-if="toggleForm">
        <TaskForm :addInProgress="addInProgress" :reference="taskRef" :task="task" @cancel="resetForm(true);"
          @submit="updateItem" />
      </div>

      <div class="column is-12" v-if="!toggleForm">
        <div class="columns is-multiline" v-if="tasks && tasks.length > 0">
          <div class="column is-6" v-for="item in tasks" :key="item.id">
            <div class="card">
              <header class="card-header">
                <div class="card-header-title is-text-overflow is-block">
                  <NuxtLink target="_blank" :href="item.url">{{ item.name }}</NuxtLink>
                </div>
                <div class="card-header-icon">
                  <a :href="item.url" class="has-text-primary" v-tooltip="'Copy url.'"
                    @click.prevent="copyText(item.url)">
                    <span class="icon"><i class="fa-solid fa-copy" /></span>
                  </a>
                  <button @click="item.raw = !item.raw">
                    <span class="icon"><i class="fa-solid"
                        :class="{ 'fa-arrow-down': !item?.raw, 'fa-arrow-up': item?.raw }" /></span>
                  </button>
                </div>
              </header>
              <div class="card-content">
                <div class="content">
                  <p>
                    <span class="icon"><i class="fa-solid fa-clock" /></span>
                    <span>
                      {{ tryParse(item.timer) }} - {{ item.timer }}
                    </span>
                  </p>
                  <p>
                    <span class="icon"><i class="fa-solid fa-folder" /></span>
                    <span>{{ calcPath(item.folder) }}</span>
                  </p>
                  <p>
                    <span class="icon"><i class="fa-solid fa-file" /></span>
                    <span>{{ item.template ?? config.app.output_template }}</span>
                  </p>
                  <p>
                    <span class="icon"><i class="fa-solid fa-tv" /></span>
                    <span>{{ item.preset ?? config.app.default_preset }}</span>
                  </p>
                </div>
              </div>
              <div class="card-content" v-if="item?.raw">
                <div class="content">
                  <pre><code>{{ filterItem(item) }}</code></pre>
                </div>
              </div>
              <div class="card-footer">
                <div class="card-footer-item">
                  <button class="button is-warning is-fullwidth" @click="editItem(item);">
                    <span class="icon"><i class="fa-solid fa-trash-can" /></span>
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
        </div>
        <Message title="No tasks" message="No tasks are defined." class="is-background-warning-80 has-text-dark"
          icon="fas fa-exclamation-circle" v-if="!tasks || tasks.length < 1" />
      </div>
    </div>
  </div>
</template>

<script setup>
import moment from 'moment'
import { parseExpression } from 'cron-parser'
import { request } from '~/utils/index'

const toast = useToast()
const config = useConfigStore()
const socket = useSocketStore()

const tasks = ref([])
const task = ref({})
const taskRef = ref('')
const toggleForm = ref(false)
const isLoading = ref(false)
const initialLoad = ref(true)
const addInProgress = ref(false)

watch(() => config.app.basic_mode, async () => {
  if (!config.app.basic_mode) {
    return
  }
  await navigateTo('/')
})

watch(() => socket.isConnected, async () => {
  if (socket.isConnected && initialLoad.value) {
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
  try {
    addInProgress.value = true

    const response = await request('/api/tasks', {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(items),
    })

    const data = await response.json()

    if (200 !== response.status) {
      toast.error(`Failed to update task. ${data.error}`);
      return false
    }

    tasks.value = data
    resetForm(true)
    return true
  } catch (e) {
    toast.error(`Failed to update task. ${data.error}`);
  } finally {
    addInProgress.value = false
  }
}

const deleteItem = async item => {
  if (true !== confirm(`Are you sure you want to delete (${item.name})?`)) {
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

const filterItem = item => {
  const { raw, ...rest } = item
  return JSON.stringify(rest, null, 2)
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

onMounted(async () => socket.isConnected ? await reloadContent(true) : '')

const tryParse = expression => {
  try {
    return moment(parseExpression(expression).next().toISOString()).fromNow()
  } catch (e) {
    return "Invalid"
  }
}
</script>
