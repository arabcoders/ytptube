<template>
  <div>
    <div class="mt-1 columns is-multiline">
      <div class="column is-12 is-clearfix is-unselectable">
        <span class="title is-4">
          <span class="icon-text">
            <span class="icon"><i class="fa-solid fa-filter" /></span>
            <span>Conditions</span>
          </span>
        </span>
        <div class="is-pulled-right">
          <div class="field is-grouped">
            <p class="control">
              <button class="button is-primary" @click="resetForm(false); toggleForm = !toggleForm;">
                <span class="icon"><i class="fas fa-add" /></span>
              </button>
            </p>
            <p class="control">
              <button class="button is-info" @click="reloadContent" :class="{ 'is-loading': isLoading }"
                :disabled="!socket.isConnected || isLoading" v-if="items && items.length > 0">
                <span class="icon"><i class="fas fa-refresh" /></span>
              </button>
            </p>
          </div>
        </div>
        <div class="is-hidden-mobile">
          <span class="subtitle">Run yt-dlp custom match filter on returned info. and apply cli arguments if matched.
            This is an advanced feature and should be used with caution.</span>
        </div>
      </div>

      <div class="column is-12" v-if="toggleForm">
        <ConditionForm :addInProgress="addInProgress" :reference="itemRef" :item="item" @cancel="resetForm(true)"
          @submit="updateItem" />
      </div>

      <div class="column is-12" v-if="!toggleForm">
        <div class="columns is-multiline" v-if="items.length > 0">
          <div class="column is-6" v-for="cond in items" :key="cond.id">
            <div class="card is-flex is-full-height is-flex-direction-column">
              <header class="card-header">
                <div class="card-header-title is-text-overflow is-block" v-text="cond.name" />
                <div class="card-header-icon">
                  <a class="has-text-primary" v-tooltip="'Export item.'" @click.prevent="exportItem(cond)">
                    <span class="icon"><i class="fa-solid fa-file-export" /></span>
                  </a>
                  <button @click="cond.raw = !cond.raw">
                    <span class="icon"><i class="fa-solid" :class="{
                      'fa-arrow-down': !cond?.raw,
                      'fa-arrow-up': cond?.raw,
                    }" /></span>
                  </button>
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
                </div>
              </div>
              <div class="card-content" v-if="cond?.raw">
                <div class="content">
                  <pre><code>{{ JSON.stringify(cleanObject(cond, remove_keys), null, 2) }}</code></pre>
                </div>
              </div>
              <div class="card-footer mt-auto">
                <div class="card-footer-item">
                  <button class="button is-warning is-fullwidth" @click="editItem(cond)">
                    <span class="icon"><i class="fa-solid fa-cog" /></span>
                    <span>Edit</span>
                  </button>
                </div>
                <div class="card-footer-item">
                  <button class="button is-danger is-fullwidth" @click="deleteItem(cond)">
                    <span class="icon"><i class="fa-solid fa-trash" /></span>
                    <span>Delete</span>
                  </button>
                </div>
                <div class="card-footer-item">
                  <button class="button is-purple is-fullwidth" @click="TestCondition(cond)"
                    :class="{ 'is-loading': cond?.in_progress }">
                    <span class="icon"><i class="fa-solid fa-play" /></span>
                    <span>Test</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
        <Message title="No items" message="There are no custom conditions defined."
          class="is-background-warning-80 has-text-dark" icon="fas fa-exclamation-circle"
          v-if="!items || items.length < 1" />
      </div>
    </div>
    <div class="column is-12" v-if="items && items.length > 0 && !toggleForm">
      <Message message_class="has-background-info-90 has-text-dark" title="Tips" icon="fas fa-info-circle">
        <ul>
          <li>The filtering rely on yt-dlp <code>--match-filter</code> logic, whatever works there works here as well
            and uses the same logic boolean and operators.</li>
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
            information button, and check the data to craft your filter.
          </li>
        </ul>
      </Message>
    </div>
  </div>
</template>

<script setup>
import { request } from '~/utils/index'

const toast = useNotification()
const config = useConfigStore()
const socket = useSocketStore()
const box = useConfirm()

const items = ref([])
const item = ref({})
const itemRef = ref("")
const toggleForm = ref(false)
const isLoading = ref(false)
const initialLoad = ref(true)
const addInProgress = ref(false)
const remove_keys = ['in_progress', 'raw']

watch(() => config.app.basic_mode, async () => {
  if (!config.app.basic_mode) {
    return
  }
  await navigateTo("/")
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
    const response = await request("/api/conditions")

    if (fromMounted && !response.ok) {
      return
    }

    const data = await response.json()
    if (data.length < 1) {
      return
    }

    items.value = data
  } catch (e) {
    if (fromMounted) {
      return
    }
    console.error(e)
    toast.error("Failed to fetch page content.")
  } finally {
    isLoading.value = false
  }
}

const resetForm = (closeForm = false) => {
  item.value = {}
  itemRef.value = null
  addInProgress.value = false
  if (closeForm) {
    toggleForm.value = false
  }
}

const updateItems = async items => {
  let data
  try {
    addInProgress.value = true

    const local_items = []
    for (const item of items) {
      const { id, name, filter, cli } = item
      if (!name || !filter || !cli) {
        toast.error("Name, filter and cli are required.")
        return false
      }
      local_items.push({ id, name, filter, cli })
    }

    const response = await request("/api/conditions", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(local_items),
    })

    data = await response.json()

    if (200 !== response.status) {
      toast.error(`Failed to update items. ${data.error}`)
      return false
    }

    items.value = data
    resetForm(true)
    return true
  } catch (e) {
    toast.error(`Failed to update items. ${data?.error}. ${e.message}`)
  } finally {
    addInProgress.value = false
  }
}

const deleteItem = async (item) => {
  if (true !== box.confirm(`Delete '${item.name}'?`, true)) {
    return
  }

  const index = items.value.findIndex((t) => t?.id === item.id)
  if (index > -1) {
    items.value.splice(index, 1)
  } else {
    toast.error("Item not found.")
    return
  }

  const status = await updateItems(items.value)

  if (!status) {
    return
  }

  toast.success("Item deleted.")
}

const updateItem = async ({ reference, item }) => {
  item = cleanObject(item, remove_keys)
  if (reference) {
    const index = items.value.findIndex(t => t?.id === reference)
    if (index > -1) {
      items.value[index] = item
    }
  } else {
    items.value.push(item)
  }

  const status = await updateItems(items.value)
  if (!status) {
    return
  }

  toast.success(`Item ${reference ? "updated" : "added"}.`)
  resetForm(true)
}

const filterItem = i => JSON.stringify(cleanObject(i, remove_keys), null, 2)

const editItem = _item => {
  item.value = _item
  itemRef.value = _item.id
  toggleForm.value = true
}

onMounted(async () => (socket.isConnected ? await reloadContent(true) : ""))

const exportItem = item => {
  let data = JSON.parse(JSON.stringify(item))
  if ("id" in data) {
    delete data['id']
  }

  let userData = {}

  for (const key of Object.keys(data)) {
    if (!data[key]) {
      continue
    }
    userData[key] = data[key]
  }

  userData['_type'] = 'condition'
  userData['_version'] = '1.0'

  return copyText(base64UrlEncode(JSON.stringify(userData)))
}

const TestCondition = async (item) => {
  const url = box.prompt("Enter URL to test condition against:")
  if (!url) {
    return
  }

  item.in_progress = true

  try {
    const response = await request("/api/conditions/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: url, condition: item.id || item.name }),
    })

    const data = await response.json()
    if (!response.ok) {
      toast.error(`Failed to test condition. ${data.error}`)
      return
    }

    toast.success(data?.message || "Condition tested successfully.")
  } catch (e) {
    toast.error(`Failed to test condition. ${e.message}`)
  } finally {
    item.in_progress = false
  }
}
</script>
