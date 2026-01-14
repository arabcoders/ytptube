<template>
  <div>
    <div class="mt-1 columns is-multiline">
      <div class="column is-12 is-clearfix is-unselectable">
        <span class="title is-4">
          <span class="icon-text">
            <template v-if="toggleForm">
              <span class="icon"><i class="fa-solid" :class="{ 'fa-edit': targetRef, 'fa-plus': !targetRef }" /></span>
              <span>{{ targetRef ? `Edit - ${target.name}` : 'Add new notification target' }}</span>
            </template>
            <template v-else>
              <span class="icon"><i class="fa-solid fa-paper-plane" /></span>
              <span>Notifications</span>
            </template>
          </span>
        </span>
        <div class="is-pulled-right" v-if="!toggleForm">
          <div class="field is-grouped">
            <p class="control has-icons-left" v-if="toggleFilter && notifications && notifications.length > 0">
              <input type="search" v-model.lazy="query" class="input" id="filter"
                placeholder="Filter displayed content">
              <span class="icon is-left"><i class="fas fa-filter" /></span>
            </p>

            <p class="control" v-if="notifications && notifications.length > 0">
              <button class="button is-danger is-light" @click="toggleFilter = !toggleFilter">
                <span class="icon"><i class="fas fa-filter" /></span>
                <span v-if="!isMobile">Filter</span>
              </button>
            </p>

            <p class="control">
              <button class="button is-primary" @click="resetForm(false); toggleForm = true"
                v-tooltip="'Add new notification target.'">
                <span class="icon"><i class="fas fa-add" /></span>
                <span v-if="!isMobile">New Notification</span>
              </button>
            </p>
            <p class="control" v-if="notifications.length > 0">
              <button class="button is-warning" @click="sendTest" v-tooltip="'Send test notification.'"
                :class="{ 'is-loading': sendingTest }" :disabled="!notifications.length || sendingTest">
                <span class="icon"><i class="fas fa-paper-plane" /></span>
                <span v-if="!isMobile">Send Test</span>
              </button>
            </p>
            <p class="control" v-if="notifications.length > 0">
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

            <p class="control" v-if="notifications.length > 0">
              <button class="button is-info" @click="reloadContent()" :class="{ 'is-loading': isLoading }"
                :disabled="isLoading || notifications.length < 1">
                <span class="icon"><i class="fas fa-refresh" /></span>
                <span v-if="!isMobile">Reload</span>
              </button>
            </p>
          </div>
        </div>
        <div class="is-hidden-mobile" v-if="!toggleForm">
          <span class="subtitle">
            Send notifications to your webhooks based on specified events or presets.
          </span>
        </div>
      </div>

      <div class="column is-12" v-if="toggleForm">
        <NotificationForm :addInProgress="addInProgress" :reference="targetRef as string" :item="target"
          @cancel="resetForm(true);" @submit="updateItem" :allowedEvents="allowedEvents" />
      </div>
    </div>

    <div class="columns is-multiline" v-if="!isLoading && !toggleForm && filteredTargets && filteredTargets.length > 0">
      <template v-if="'list' === display_style">
        <div class="column is-12">
          <div class="table-container">
            <table class="table is-striped is-hoverable is-fullwidth is-bordered"
              style="min-width: 850px; table-layout: fixed;">
              <thead>
                <tr class="has-text-centered is-unselectable">
                  <th width="80%">
                    <span class="icon"><i class="fa-solid fa-paper-plane" /></span>
                    <span>Targets</span>
                  </th>
                  <th width="20%">
                    <span class="icon"><i class="fa-solid fa-gear" /></span>
                    <span>Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in filteredTargets" :key="item.id">
                  <td class="is-text-overflow is-vcentered">
                    <div class="is-bold">
                      {{ item.request.method.toUpperCase() }}({{ ucFirst(item.request.type) }}) @
                      <NuxtLink target="_blank" :href="item.request.url">{{ item.name }}</NuxtLink>
                    </div>
                    <div class="is-unselectable">
                      <span class="icon-text">
                        <span class="icon"><i class="fa-solid fa-list-ul" /></span>
                        <span>On: {{ join_events(item.on) }}</span>
                      </span>
                      &nbsp;
                      <span class="icon-text">
                        <span class="icon"><i class="fa-solid fa-sliders" /></span>
                        <span>Presets: {{ join_presets(item.presets) }}</span>
                      </span>
                      &nbsp;
                      <span class="icon-text is-clickable" @click="toggleEnabled(item)">
                        <span class="icon" :class="item.enabled ? 'has-text-success' : 'has-text-danger'"
                          v-tooltip="`Notification is ${item.enabled !== false ? 'enabled' : 'disabled'}. Click to toggle.`">
                          <i class="fa-solid fa-power-off" />
                        </span>
                        <span>{{ item.enabled ? 'Enabled' : 'Disabled' }}</span>
                      </span>
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
                          <span class="icon"><i class="fa-solid fa-edit" /></span>
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
        <div class="column is-6 is-12-mobile" v-for="item in filteredTargets" :key="item.id">
          <div class="card is-flex is-full-height is-flex-direction-column">
            <header class="card-header">
              <div class="card-header-title is-text-overflow is-block">
                {{ item.request.method.toUpperCase() }}({{ ucFirst(item.request.type) }}) @
                <NuxtLink target="_blank" :href="item.request.url">{{ item.name }}</NuxtLink>
              </div>
              <div class="card-header-icon">
                <div class="field is-grouped">
                  <div class="control" @click="toggleEnabled(item)">
                    <span class="icon" :class="item.enabled ? 'has-text-success' : 'has-text-danger'"
                      v-tooltip="`Notification is ${item.enabled !== false ? 'enabled' : 'disabled'}. Click to toggle.`">
                      <i class="fa-solid fa-power-off" />
                    </span>
                  </div>
                  <div class="control">
                    <a class="has-text-info" v-tooltip="'Export target.'" @click.prevent="exportItem(item)">
                      <span class="icon"><i class="fa-solid fa-file-export" /></span>
                    </a>
                  </div>
                  <div class="control">
                    <button @click="item.raw = !item.raw">
                      <span class="icon"><i class="fa-solid"
                          :class="{ 'fa-arrow-down': !item?.raw, 'fa-arrow-up': item?.raw }" /></span>
                    </button>
                  </div>
                </div>
              </div>
            </header>
            <div class="card-content is-flex-grow-1">
              <div class="content">
                <p>
                  <span class="icon"><i class="fa-solid fa-list-ul" /></span>
                  <span>On: {{ join_events(item.on) }}</span>
                </p>
                <p>
                  <span class="icon"><i class="fa-solid fa-sliders" /></span>
                  <span>Presets: {{ join_presets(item.presets) }}</span>
                </p>
                <p v-if="item.request?.headers && item.request.headers.length > 0">
                  <span class="icon"><i class="fa-solid fa-heading" /></span>
                  <span>Headers: {{item.request.headers.map(h => h.key).join(', ')}}</span>
                </p>
              </div>
            </div>
            <div class="card-content" v-if="item?.raw">
              <div class="content">
                <pre><code>{{ JSON.stringify(cleanObject(item, ['raw']), null, 2) }}</code></pre>
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
            </div>
          </div>
        </div>
      </template>
    </div>

    <div class="columns is-multiline"
      v-if="!toggleForm && (isLoading || !filteredTargets || filteredTargets.length < 1)">
      <div class="column is-12">
        <Message v-if="isLoading" class="is-info" title="Loading" icon="fas fa-spinner fa-spin">
          Loading data. Please wait...
        </Message>
        <Message title="No Results" class="is-warning" icon="fas fa-search" v-else-if="query" :useClose="true"
          @close="query = ''">
          <p>No results found for the query: <code>{{ query }}</code>.</p>
          <p>Please try a different search term.</p>
        </Message>
        <Message v-else title="No targets" class="is-warning" icon="fas fa-exclamation-circle">
          No notification targets found. Click on the <span class="icon"><i class="fas fa-add" /></span> <strong>New
            Notification</strong> button to add your first notification target.
        </Message>
      </div>
    </div>

    <div class="columns is-multiline" v-if="!toggleForm && filteredTargets && filteredTargets.length > 0">
      <div class="column is-12">
        <Message class="is-info" :body_class="'pl-0'">
          <ul>
            <li>
              When you export notification target, We remove <code>Authorization</code> header key by default,
              However this might not be enough to remove credentials from the exported data. it's your responsibility
              to ensure that the exported data does not contain any sensitive information for sharing.
            </li>
            <li>
              When you set the request type as <code>Form</code>, the event data will be JSON encoded and sent as
              <code>...&data_key=json_string</code>, only the <code>data</code> field will be JSON encoded.
              The other keys <code>id</code>, <code>event</code> and <code>created_at</code> will be sent as they are.
            </li>
            <li>We also send two special headers <code>X-Event-ID</code> and <code>X-Event</code> with the request.
            </li>
            <li>
              If you have selected specific presets or events, this will take priority, For example, if you limited
              the
              target to <code>default</code> preset and selected <code>ALL</code> events, only events that reference
              the
              <code>default</code> preset will be sent to that target. Like wise, if you have limited both events and
              presets, then ONLY events that satisfy both conditions will be sent to that target. Only the
              <code>test</code> events can bypass these conditions.
            </li>
          </ul>
        </Message>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useStorage } from '@vueuse/core'
import type { notification, notificationImport } from '~/types/notification'
import { useConfirm } from '~/composables/useConfirm'

type notificationItemWithUI = notification & { raw?: boolean }

const toast = useNotification()
const socket = useSocketStore()
const box = useConfirm()
const display_style = useStorage<string>("tasks_display_style", "cards")
const isMobile = useMediaQuery({ maxWidth: 1024 })

const allowedEvents = ref<string[]>([])
const notifications = ref<notificationItemWithUI[]>([])

const defaultState = (): notification => ({
  name: '',
  on: [],
  presets: [],
  enabled: true,
  request: { method: 'POST', url: '', type: 'json', headers: [], data_key: 'data' },
})

const target = ref<notification>(defaultState())
const targetRef = ref<string | null>('')
const toggleForm = ref(false)
const isLoading = ref(false)
const initialLoad = ref(true)
const addInProgress = ref(false)
const sendingTest = ref(false)

const query = ref<string>('')
const toggleFilter = ref(false)

const filteredTargets = computed<notificationItemWithUI[]>(() => {
  const q = query.value?.toLowerCase();
  if (!q) return notifications.value;
  return notifications.value.filter((item: notificationItemWithUI) => deepIncludes(item, q, new WeakSet()));
});

watch(toggleFilter, (val) => {
  if (!val) {
    query.value = ''
  }
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
  target.value = defaultState()
  targetRef.value = null
  if (closeForm) {
    toggleForm.value = false
  }
}

const updateData = async (items: notification[]) => {
  const response = await request('/api/notifications', {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(items),
  })

  const data = await response.json()

  if (200 !== response.status) {
    toast.error(`Failed to update notifications. ${data.error}`)
    return false
  }

  notifications.value = data.notifications
  return true
}

const deleteItem = async (item: notification) => {
  if (true !== (await box.confirm(`Delete '${item.name}'?`))) {
    return
  }

  const index = notifications.value.findIndex(i => i?.id === item.id)
  if (0 <= index) {
    notifications.value.splice(index, 1)
  } else {
    toast.error('Notification target not found.')
    await reloadContent()
    return
  }

  const status = await updateData(notifications.value)
  if (!status) return

  toast.success('Notification target deleted.')
}

const toggleEnabled = async (item: notification) => {
  const index = notifications.value.findIndex(i => i?.id === item.id)
  if (-1 === index) {
    toast.error('Notification target not found.')
    return
  }

  const target = notifications.value[index]
  if (!target) {
    toast.error('Notification target not found.')
    return
  }

  target.enabled = !target.enabled
  const status = await updateData(notifications.value)
  if (status) {
    toast[target.enabled ? 'success' : 'warning'](`Notification is ${target.enabled ? 'enabled' : 'disabled'}.`)
  }
}

const updateItem = async ({ reference, item }: { reference: string | null, item: notification }) => {
  if (reference) {
    const index = notifications.value.findIndex(i => i?.id === reference)
    if (0 <= index) {
      notifications.value[index] = item
    }
  } else {
    notifications.value.push(item)
  }

  try {
    const status = await updateData(notifications.value)
    if (!status) return

    toast.success(`Notification target ${reference ? 'updated' : 'added'}.`)
    resetForm(true)
  } finally {
    addInProgress.value = false
  }
}

const editItem = (item: notification) => {
  target.value = item
  targetRef.value = item.id ?? null
  toggleForm.value = true
}

const join_events = (events: Array<string>) => !events || events.length < 1 ? 'ALL' : events.map(e => ucFirst(e)).join(', ')
const join_presets = (presets: Array<string>) => !presets || presets.length < 1 ? 'ALL' : presets.map(e => ucFirst(e)).join(', ')

const sendTest = async () => {
  if (true !== (await box.confirm('Send test notification?'))) {
    return
  }

  try {
    sendingTest.value = true
    const response = await request('/api/notifications/test', { method: 'POST' })

    if (200 !== response.status) {
      const data = await response.json()
      toast.error(`Failed to send test notification. ${data.error}`)
      return
    }

    toast.success('Test notification sent.')
  } catch (e: any) {
    console.error(e)
    toast.error(`Failed to send test notification. ${e.message}`)
  } finally {
    sendingTest.value = false
  }
}

onMounted(async () => socket.isConnected ? await reloadContent(true) : '')

const exportItem = async (item: notification) => {
  const data: notificationImport = {
    ...JSON.parse(JSON.stringify(item)),
    _type: 'notification',
    _version: '1.0',
  }

  const keys = ['id', 'raw'] as const
  keys.forEach(k => {
    if (Object.prototype.hasOwnProperty.call(data, k)) {
      const { [k]: _, ...rest } = data as any
      Object.assign(data, rest)
    }
  })

  if (data.request?.headers?.length) {
    data.request.headers = data.request.headers.filter(
      h => 'authorization' !== h.key.toLowerCase(),
    )
  }

  copyText(encode(data))
}
</script>
