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
            <span class="icon"><i class="fa-solid fa-paper-plane" /></span>
            <span>Notifications</span>
          </span>
        </span>
        <div class="is-pulled-right" v-if="!toggleForm">
          <div class="field is-grouped">
            <p class="control">
              <button class="button is-primary" @click="resetForm(false); toggleForm = true"
                v-tooltip="'Add new notification target.'">
                <span class="icon"><i class="fas fa-add"></i></span>
              </button>
            </p>
            <p class="control" v-if="notifications.length > 0">
              <button class="button is-warning" @click="sendTest" v-tooltip="'Send test notification.'"
                :class="{ 'is-loading': isLoading }" :disabled="!socket.isConnected || isLoading">
                <span class="icon"><i class="fas fa-paper-plane"></i></span>
              </button>
            </p>
            <p class="control" v-if="notifications.length > 0">
              <button class="button is-info" @click="reloadContent" :class="{ 'is-loading': isLoading }"
                :disabled="!socket.isConnected || isLoading || notifications.length < 1">
                <span class="icon"><i class="fas fa-refresh"></i></span>
              </button>
            </p>
          </div>
        </div>
        <div class="is-hidden-mobile">
          <span class="subtitle">
            Send notifications to your servers based on specified events.
          </span>
        </div>
      </div>

      <div class="column is-12" v-if="toggleForm">
        <NotificationForm :addInProgress="addInProgress" :reference="targetRef" :item="target"
          @cancel="resetForm(true);" @submit="updateItem" :allowedEvents="allowedEvents" />
      </div>

      <div class="column is-12" v-if="!toggleForm">
        <div class="columns is-multiline" v-if="notifications && notifications.length > 0">
          <div class="column is-6" v-for="item in notifications" :key="item.id">
            <div class="card is-flex is-full-height is-flex-direction-column">
              <header class="card-header">
                <div class="card-header-title is-text-overflow is-block">
                  {{ item.request.method.toUpperCase() }}({{ ucFirst(item.request.type) }}) @
                  <NuxtLink target="_blank" :href="item.request.url">{{ item.name }}</NuxtLink>
                </div>
                <div class="card-header-icon">
                  <a class="has-text-info" v-tooltip="'Export target.'" @click.prevent="exportItem(item)">
                    <span class="icon"><i class="fa-solid fa-file-export" /></span>
                  </a>
                  <button @click="item.raw = !item.raw">
                    <span class="icon"><i class="fa-solid"
                        :class="{ 'fa-arrow-down': !item?.raw, 'fa-arrow-up': item?.raw }" /></span>
                  </button>
                </div>
              </header>
              <div class="card-content is-flex-grow-1">
                <div class="content">
                  <p>
                    <span class="icon"><i class="fa-solid fa-list-ul" /></span>
                    <span>On: {{ join_events(item.on) }}</span>
                  </p>
                  <p v-if="item.request?.headers && item.request.headers.length > 0">
                    <span class="icon"><i class="fa-solid fa-heading" /></span>
                    <span>{{item.request.headers.map(h => h.key).join(', ')}}</span>
                  </p>
                </div>
              </div>
              <div class="card-content" v-if="item?.raw">
                <div class="content">
                  <pre><code>{{ filterItem(item) }}</code></pre>
                </div>
              </div>
              <div class="card-footer mt-auto">
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
        <Message title="No Endpoints" class="is-background-warning-80 has-text-dark" icon="fas fa-exclamation-circle"
          v-if="!notifications || notifications.length < 1">
          There are no notifications endpoints configured to receive web notifications.
        </Message>
      </div>
    </div>

    <div class="column is-12" v-if="notifications && notifications.length > 0 && !toggleForm">
      <Message message_class="has-background-info-90 has-text-dark" title="Tips" icon="fas fa-info-circle">
        <ul>
          <li>
            When you export notification target, We remove <code>Authorization</code> header key by default,
            However this might not be enough to remove credentials from the exported data. it's your responsibility
            to ensure that the exported data does not contain any sensitive information for sharing.
          </li>
          <li>
            When you set the request type as <code>Form</code>, the event data will be JSON encoded and sent as the
            and sent as <code>...&data_key=json_string</code>, only the <code>data</code> field will be JSON encoded.
            The other keys <code>id</code>, <code>event</code> and <code>created_at</code> will be sent as they are.
          </li>
          <li>We also send two special headers <code>X-Event-ID</code> and <code>X-Event</code> with the request.</li>
          <li>Support for <code>Apprise URLs</code> is in beta and subject to many changes to come, currently the
            message field fallback to JSON encoded string of the event if there there is custom message set by us for
            that particular event.</li>
        </ul>
      </Message>
    </div>
  </div>
</template>

<script setup>
const toast = useNotification()
const config = useConfigStore()
const socket = useSocketStore()
const box = useConfirm()

const allowedEvents = ref([])
const notifications = ref([])
const target = ref({})
const targetRef = ref('')
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
    const response = await request('/api/notifications')

    if (fromMounted && !response.ok) {
      return
    }

    notifications.value = []

    const data = await response.json()
    if (data.length < 1) {
      return
    }

    allowedEvents.value = data.allowedTypes
    notifications.value = data.notifications
  } catch (e) {
    if (fromMounted) {
      return
    }
    console.error(e)
    toast.error('Failed to fetch notifications.')
  } finally {
    isLoading.value = false
  }
}

const resetForm = (closeForm = false) => {
  target.value = {
    name: '',
    on: [],
    request: {
      method: 'POST',
      url: '',
      type: 'json',
      headers: [],
    },
  }
  targetRef.value = null
  if (closeForm) {
    toggleForm.value = false
  }
}

const updateData = async notifications => {
  const response = await request('/api/notifications', {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(notifications),
  })

  const data = await response.json()

  if (200 !== response.status) {
    toast.error(`Failed to update notifications. ${data.error}`)
    return false
  }

  notifications.value = data.notifications
  return true
}

const deleteItem = async item => {
  if (true !== box.confirm(`Delete '${item.name}'?`)) {
    return
  }

  const index = notifications.value.findIndex(i => i?.id === item.id)
  if (index > -1) {
    notifications.value.splice(index, 1)
  } else {
    toast.error('Notification target not found.')
    await reloadContent()
    return
  }

  const status = await updateData(notifications.value)

  if (!status) {
    return
  }

  toast.success('Notification target deleted.')
}

const updateItem = async ({ reference, item }) => {
  if (reference) {
    const index = notifications.value.findIndex(i => i?.id === reference)
    if (index > -1) {
      notifications.value[index] = item
    }
  } else {
    notifications.value.push(item)
  }

  try {
    const status = await updateData(notifications.value)

    if (!status) {
      return
    }

    toast.success(`Notification target ${reference ? 'updated' : 'added'}.`)
    resetForm(true)
  } finally {
    addInProgress.value = false
  }
}

const filterItem = item => {
  const { raw, ...rest } = item
  return JSON.stringify(rest, null, 2)
}

const editItem = item => {
  target.value = item
  targetRef.value = item.id
  toggleForm.value = true
}

const join_events = events => (!events || events.length < 1) ? 'ALL' : events.map(e => ucFirst(e)).join(', ')

const sendTest = async () => {
  if (true !== box.confirm('Send test notification?')) {
    return
  }

  try {
    isLoading.value = true
    const response = await request('/api/notifications/test', { method: 'POST' })

    if (200 !== response.status) {
      const data = await response.json()
      toast.error(`Failed to send test notification. ${data.error}`)
      return
    }

    toast.success('Test notification sent.')
  } catch (e) {
    console.error(e)
    toast.error(`Failed to send test notification. ${e.message}`)
  } finally {
    isLoading.value = false
  }
}

onMounted(async () => socket.isConnected ? await reloadContent(true) : '')

const exportItem = async item => {
  let data = JSON.parse(JSON.stringify(item))
  const keys = ['id', 'raw']
  keys.forEach(k => {
    if (data.hasOwnProperty(k)) {
      delete data[k]
    }
  })

  // -- Remove authorization headers
  if (data.request?.headers && data.request.headers.length > 0) {
    data.request.headers = data.request.headers.filter(h => h.key.toLowerCase() !== 'authorization')
  }

  data['_type'] = 'notification'
  data['_version'] = '1.0'

  return copyText(encode(data))
}
</script>
