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
            <span class="icon"><i class="fa-solid fa-sliders" /></span>
            <span>Presets</span>
          </span>
        </span>
        <div class="is-pulled-right">
          <div class="field is-grouped">
            <p class="control">
              <button class="button is-primary" @click="
                resetForm(false);
              toggleForm = !toggleForm;
              ">
                <span class="icon"><i class="fas fa-add"></i></span>
              </button>
            </p>
            <p class="control">
              <button class="button is-info" @click="reloadContent" :class="{ 'is-loading': isLoading }"
                :disabled="!socket.isConnected || isLoading" v-if="presets && presets.length > 0">
                <span class="icon"><i class="fas fa-refresh"></i></span>
              </button>
            </p>
          </div>
        </div>
        <div class="is-hidden-mobile">
          <span class="subtitle">Custom presets. The presets are simply pre-defined yt-dlp settings
            that you want to apply to given download.</span>
        </div>
      </div>

      <div class="column is-12" v-if="toggleForm">
        <PresetForm :addInProgress="addInProgress" :reference="presetRef" :preset="preset" @cancel="resetForm(true)"
          @submit="updateItem" :presets="presets" />
      </div>

      <div class="column is-12" v-if="!toggleForm">
        <div class="columns is-multiline" v-if="presetsNoDefault && presetsNoDefault.length > 0">
          <div class="column is-6" v-for="item in presetsNoDefault" :key="item.id">
            <div class="card">
              <header class="card-header">
                <div class="card-header-title is-text-overflow is-block" v-text="item.name" />
                <div class="card-header-icon">
                  <a class="has-text-primary" v-tooltip="'Export preset.'" @click.prevent="exportItem(item)">
                    <span class="icon"><i class="fa-solid fa-file-export" /></span>
                  </a>
                  <button @click="item.raw = !item.raw">
                    <span class="icon"><i class="fa-solid" :class="{
                      'fa-arrow-down': !item?.raw,
                      'fa-arrow-up': item?.raw,
                    }" /></span>
                  </button>
                </div>
              </header>
              <div class="card-content">
                <div class="content">
                  <p class="is-text-overflow"
                    v-if="item?.format && false === ['default', 'not_set'].includes(item.format)">
                    <span class="icon"><i class="fa-solid fa-f" /></span>
                    <span v-text="item.format" />
                  </p>
                  <p class="is-text-overflow" v-if="item.folder">
                    <span class="icon"><i class="fa-solid fa-folder" /></span>
                    <span>{{ calcPath(item.folder) }}</span>
                  </p>
                  <p class="is-text-overflow" v-if="item.template">
                    <span class="icon"><i class="fa-solid fa-file" /></span>
                    <span>{{ item.template }}</span>
                  </p>
                  <p class="is-text-overflow" v-if="item.cli">
                    <span class="icon"><i class="fa-solid fa-terminal" /></span>
                    <span>{{ item.cli }}</span>
                  </p>
                  <p class="is-text-overflow" v-if="item.cookies">
                    <span class="icon"><i class="fa-solid fa-cookie" /></span>
                    <span>Has cookies</span>
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
                  <button class="button is-warning is-fullwidth" @click="editItem(item)">
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
              </div>
            </div>
          </div>
        </div>
        <Message title="No presets" message="There are no custom defined presets."
          class="is-background-warning-80 has-text-dark" icon="fas fa-exclamation-circle"
          v-if="!presets || presets.length < 1" />
      </div>
    </div>
    <div class="column is-12" v-if="presets && presets.length > 0 && !toggleForm">
      <Message message_class="has-background-info-90 has-text-dark" title="Tips" icon="fas fa-info-circle">
        <ul>
          <li>
            When you export preset, it doesn't include <code>Cookies</code> field for security reasons.
          </li>
        </ul>
      </Message>
    </div>
  </div>
</template>

<script setup>
import { request } from '~/utils/index'

const toast = useToast()
const config = useConfigStore()
const socket = useSocketStore()

const presets = ref([])
const preset = ref({})
const presetRef = ref("")
const toggleForm = ref(false)
const isLoading = ref(false)
const initialLoad = ref(true)
const addInProgress = ref(false)

const presetsNoDefault = computed(() =>
  presets.value.filter((t) => !t.default),
)

watch(
  () => config.app.basic_mode,
  async () => {
    if (!config.app.basic_mode) {
      return
    }
    await navigateTo("/")
  },
)

watch(
  () => socket.isConnected,
  async () => {
    if (socket.isConnected && initialLoad.value) {
      await reloadContent(true)
      initialLoad.value = false
    }
  },
)

const reloadContent = async (fromMounted = false) => {
  try {
    isLoading.value = true
    const response = await request("/api/presets")

    if (fromMounted && !response.ok) {
      return
    }

    const data = await response.json()
    if (data.length < 1) {
      return
    }

    presets.value = data
  } catch (e) {
    if (fromMounted) {
      return
    }
    console.error(e)
    toast.error("Failed to fetch tasks.")
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

const updatePresets = async (items) => {
  let data
  try {
    addInProgress.value = true

    const response = await request("/api/presets", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
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
  } catch (e) {
    toast.error(`Failed to update presets. ${data?.error}. ${e.message}`)
  } finally {
    addInProgress.value = false
  }
}

const deleteItem = async (item) => {
  if (true !== confirm(`Delete preset '${item.name}'?`)) {
    return
  }

  const index = presets.value.findIndex((t) => t?.id === item.id)
  if (index > -1) {
    presets.value.splice(index, 1)
  } else {
    toast.error("Preset not found.")
    return
  }

  const status = await updatePresets(presets.value)

  if (!status) {
    return
  }

  toast.success("Preset deleted.")
}

const updateItem = async ({ reference, preset }) => {
  if (reference) {
    const index = presets.value.findIndex((t) => t?.id === reference)
    if (index > -1) {
      presets.value[index] = preset
    }
  } else {
    presets.value.push(preset)
  }

  const status = await updatePresets(presets.value)
  if (!status) {
    return
  }

  toast.success(`Preset ${reference ? "updated" : "added"}.`)
  resetForm(true)
}

const filterItem = (item) => {
  const { raw, ...rest } = item
  return JSON.stringify(rest, null, 2)
}

const editItem = (item) => {
  preset.value = item
  presetRef.value = item.id
  toggleForm.value = true
}

onMounted(async () => (socket.isConnected ? await reloadContent(true) : ""))

const exportItem = item => {
  let data = JSON.parse(JSON.stringify(item))
  const keys = ["id", "default", "raw", "cookies"]
  keys.forEach(key => {
    if (key in data) {
      delete data[key]
    }
  })

  let userData = {}

  for (const key of Object.keys(data)) {
    if (!data[key]) {
      continue
    }
    userData[key] = data[key]
  }

  userData['_type'] = 'preset'
  userData['_version'] = '2.0'

  return copyText(base64UrlEncode(JSON.stringify(userData)))
}

const calcPath = (path) => {
  const loc = config.app.download_path || "/downloads"

  if (path) {
    return loc + "/" + sTrim(path, "/")
  }

  return loc
}
</script>
