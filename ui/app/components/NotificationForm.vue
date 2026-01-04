<template>
  <main class="columns mt-2 is-multiline">
    <div class="column is-12">
      <form autocomplete="off" id="taskForm" @submit.prevent="checkInfo()">
        <div class="card">

          <div class="card-header">
            <div class="card-header-title is-text-overflow is-block">
              <span class="icon-text">
                <span class="icon"><i class="fa-solid" :class="reference ? 'fa-cog' : 'fa-plus'" /></span>
                <span>{{ reference ? 'Edit' : 'Add' }}</span>
              </span>
            </div>

            <div class="card-header-icon" v-if="reference">
              <button type="button" @click="showImport = !showImport">
                <span class="icon"><i class="fa-solid" :class="{
                  'fa-arrow-down': !showImport,
                  'fa-arrow-up': showImport,
                }" /></span>
                <span>
                  <span v-if="showImport">Hide</span>
                  <span v-else>Show</span>
                  import
                </span>
              </button>
            </div>
          </div>

          <div class="card-content">
            <div class="columns is-multiline is-mobile">

              <div class="column is-12" v-if="showImport || !reference">
                <label class="label is-inline" for="import_string">
                  Import string
                </label>

                <div class="field has-addons">
                  <div class="control has-icons-left is-expanded">
                    <input type="text" class="input" id="import_string" v-model="import_string" autocomplete="off">
                    <span class="icon is-small is-left"><i class="fa-solid fa-t" /></span>
                  </div>

                  <div class="control">
                    <button class="button is-primary" :disabled="!import_string" type="button" @click="importItem">
                      <span class="icon"><i class="fa-solid fa-add" /></span>
                      <span>Import</span>
                    </button>
                  </div>
                </div>
                <span class="help is-bold">
                  <span class="icon"><i class="fa-solid fa-info" /></span>
                  <span>You can use this field to populate the data, using shared string.</span>
                </span>
              </div>

              <div class="column is-6-tablet is-12-mobile">
                <div class="field">
                  <label class="label is-inline" for="name">
                    Target name
                  </label>
                  <div class="control has-icons-left">
                    <input type="text" class="input" id="name" v-model="form.name" :disabled="addInProgress" required>
                    <span class="icon is-small is-left"><i class="fa-solid fa-user" /></span>
                  </div>
                  <span class="help is-bold">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>The notification target name, this is used to identify the target in the logs and
                      notifications.</span>
                  </span>
                </div>
              </div>

              <div class="column is-6-tablet is-12-mobile">
                <div class="field">
                  <label class="label is-inline" for="url">
                    Target URL
                  </label>
                  <div class="control has-icons-left">
                    <input type="url" class="input" id="url" v-model="form.request.url" :disabled="addInProgress"
                      required>
                    <span class="icon is-small is-left"><i class="fa-solid fa-link" /></span>
                  </div>
                  <span class="help is-bold">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>
                      The URL to send the notification to. It can be regular http/https endpoint. or <NuxtLink
                        target="blank" href="https://github.com/caronc/apprise?tab=readme-ov-file#readme">Apprise
                      </NuxtLink> URL.
                    </span>
                  </span>
                </div>
              </div>

              <div class="column is-6-tablet is-12-mobile" v-if="!isApprise">
                <div class="field">
                  <label class="label is-inline" for="method">
                    Request method
                  </label>
                  <div class="control has-icons-left">
                    <div class="select is-fullwidth">
                      <select id="method" class="is-fullwidth" v-model="form.request.method" :disabled="addInProgress">
                        <option v-for="rMethod, index in requestMethods" :key="`${index}-${rMethod}`" :value="rMethod">
                          {{ rMethod }}
                        </option>
                      </select>
                    </div>
                    <span class="icon is-small is-left"><i class="fa-solid fa-tv" /></span>
                  </div>
                  <span class="help is-bold">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>
                      The request method to use when sending the notification. This can be any of the standard HTTP
                      methods.
                    </span>
                  </span>
                </div>
              </div>

              <div class="column is-6-tablet is-12-mobile" v-if="!isApprise">
                <div class="field">
                  <label class="label is-inline" for="type">
                    Request Type
                  </label>
                  <div class="control has-icons-left">
                    <div class="select is-fullwidth">
                      <select id="type" class="is-fullwidth" v-model="form.request.type" :disabled="addInProgress">
                        <option v-for="rType, index in requestType" :key="`${index}-${rType}`" :value="rType">
                          {{ ucFirst(rType) }}
                        </option>
                      </select>
                    </div>
                    <span class="icon is-small is-left"><i class="fa-solid fa-tv" /></span>
                  </div>
                  <span class="help is-bold">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>
                      The request type to use when sending the notification. This can be <code>JSON</code> or
                      <code>FORM</code> request.
                    </span>
                  </span>
                </div>
              </div>

              <div class="column is-6-tablet is-12-mobile">
                <div class="field">
                  <label class="label is-inline" for="on">
                    Select Events
                    <template v-if="form.on.length > 0">
                      - <NuxtLink @click="form.on = []">Clear selection</NuxtLink>
                    </template>
                  </label>
                  <div class="control has-icons-left">
                    <div class="select is-multiple is-fullwidth">
                      <select id="on" class="is-fullwidth" v-model="form.on" :disabled="addInProgress" multiple>
                        <option v-for="aEvent, index in allowedEvents" :key="`${index}-${aEvent}`" :value="aEvent">
                          {{ aEvent }}
                        </option>
                      </select>
                    </div>
                    <span class="icon is-small is-left"><i class="fa-solid fa-paper-plane" /></span>
                  </div>
                  <span class="help is-bold">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>
                      Subscribe to the events you want to listen for. When the event is triggered, the notification will
                      be sent to the target URL. If no events are selected, the notification will be sent for all
                      events.
                    </span>
                  </span>
                </div>
              </div>

              <div class="column is-6-tablet is-12-mobile">
                <div class="field">
                  <label class="label is-inline" for="on">
                    Select Presets
                    <template v-if="form.presets.length > 0">
                      - <NuxtLink @click="form.presets = []">Clear selection</NuxtLink>
                    </template>
                  </label>
                  <div class="control has-icons-left">
                    <div class="select is-multiple is-fullwidth">
                      <select id="on" class="is-fullwidth" v-model="form.presets" :disabled="addInProgress" multiple>
                        <optgroup label="Custom presets" v-if="config?.presets.filter(p => !p?.default).length > 0">
                          <option v-for="cPreset in filter_presets(false)" :key="cPreset.id" :value="cPreset.name">
                            {{ cPreset.name }}
                          </option>
                        </optgroup>
                        <optgroup label="Default presets">
                          <option v-for="dPreset in filter_presets(true)" :key="dPreset.id" :value="dPreset.name">
                            {{ dPreset.name }}
                          </option>
                        </optgroup>
                      </select>
                    </div>
                    <span class="icon is-small is-left"><i class="fa-solid fa-sliders" /></span>
                  </div>
                  <span class="help is-bold">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>
                      Select the presets you want to listen for. If you select presets, only events that reference those
                      presets will trigger the notification. If no presets are selected, the notification will be sent
                      for all presets.
                    </span>
                  </span>
                </div>
              </div>

              <div class="column" :class="isApprise ? 'is-12' : 'is-6-tablet is-12-mobile'">
                <div class="field">
                  <label class="label is-inline" for="enabled">
                    <span class="icon"><i class="fa-solid fa-power-off" /></span>
                    Enabled
                  </label>
                  <div class="control is-unselectable">
                    <input id="enabled" type="checkbox" v-model="form.enabled" :disabled="addInProgress"
                      class="switch is-success" />
                    <label for="enabled" class="is-unselectable">
                      {{ form.enabled ? 'Yes' : 'No' }}
                    </label>
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span class="is-bold">Whether the notification target is enabled.</span>
                  </span>
                </div>
              </div>

              <div class="column is-6-tablet is-12-mobile" v-if="!isApprise">
                <div class="field">
                  <label class="label is-inline" for="data_key">
                    Data field
                  </label>
                  <div class="control has-icons-left">
                    <input type="text" class="input" id="data_key" v-model="form.request.data_key"
                      :disabled="addInProgress" required>
                    <span class="icon is-small is-left"><i class="fa-solid fa-key" /></span>
                  </div>
                  <span class="help is-bold">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>
                      The field name to use when sending the notification. This is used to identify the data in the
                      request. The default is <code>data</code>.
                    </span>
                  </span>
                </div>
              </div>

              <div class="column is-12" v-if="!isApprise">
                <div class="field">
                  <label class="label is-inline is-unselectable">
                    Optional Headers - <button type="button" class="has-text-link"
                      @click="form.request.headers.push({ key: '', value: '' });">Add Header
                    </button>
                  </label>
                  <div class="columns is-multiline is-mobile">
                    <template v-for="_, key in form.request.headers" :key="key">
                      <div class="column is-5" v-if="form.request.headers[key]">
                        <div class="field">
                          <div class="control has-icons-left">
                            <input type="text" class="input" v-model="form.request.headers[key].key"
                              :disabled="addInProgress" required>
                            <span class="icon is-small is-left"><i class="fa-solid fa-key" /></span>
                          </div>
                        </div>
                        <span class="help is-bold">
                          <span class="icon"><i class="fa-solid fa-info" /></span>
                          <span>The header key to send with the notification.</span>
                        </span>
                      </div>
                      <div class="column is-6" v-if="form.request.headers[key]">
                        <div class="field">
                          <div class="control has-icons-left">
                            <input type="text" class="input" v-model="form.request.headers[key].value"
                              :disabled="addInProgress" required>
                            <span class="icon is-small is-left"><i class="fa-solid fa-v" /></span>
                          </div>
                        </div>
                        <span class="help is-bold">
                          <span class="icon"><i class="fa-solid fa-info" /></span>
                          <span>The header value to send with the notification.</span>
                        </span>
                      </div>
                      <div class="column is-1">
                        <div class="control">
                          <button type="button" class="button is-danger" @click="form.request.headers.splice(key, 1)"
                            :disabled="addInProgress">
                            <span class="icon"><i class="fa-solid fa-trash" /></span>
                          </button>
                        </div>
                      </div>
                    </template>
                  </div>
                  <span class="help is-bold">
                    <span class="icon"><i class="fa-solid fa-exclamation" /></span>
                    <span class="has-text-danger">
                      If header key or value is empty, the header will not be sent.
                    </span>
                  </span>
                </div>
              </div>
            </div>

            <div class="card-footer">
              <p class="card-footer-item">
                <button class="button is-fullwidth is-primary" :disabled="addInProgress" type="submit"
                  :class="{ 'is-loading': addInProgress }" form="taskForm">
                  <span class="icon"><i class="fa-solid fa-save" /></span>
                  <span>Save</span>
                </button>
              </p>
              <p class="card-footer-item">
                <button class="button is-fullwidth is-danger" @click="emitter('cancel')" :disabled="addInProgress"
                  type="button">
                  <span class="icon"><i class="fa-solid fa-times" /></span>
                  <span>Cancel</span>
                </button>
              </p>
            </div>
          </div>
        </div>
      </form>
    </div>
  </main>
</template>

<script setup lang="ts">
import { useStorage } from '@vueuse/core'
import type { notification, notificationImport } from '~/types/notification'
import { useConfirm } from '~/composables/useConfirm'

const emitter = defineEmits(['cancel', 'submit'])
const toast = useNotification()
const box = useConfirm()
const config = useConfigStore()

const props = defineProps({
  reference: {
    type: String,
    required: false,
    default: null,
  },
  allowedEvents: {
    type: Array as () => string[],
    required: true,
  },
  item: {
    type: Object as () => notification,
    required: true,
  },
  addInProgress: {
    type: Boolean,
    required: false,
    default: false,
  },
})

const form = reactive<notification>({ ...props.item })
const requestMethods = ['POST', 'PUT']
const requestType = ['json', 'form']
const showImport = useStorage('showImport', false)
const import_string = ref('')

onMounted(() => {
  if (!form.request.data_key) {
    form.request.data_key = 'data'
  }
  if (form.enabled === undefined) {
    form.enabled = true
  }
})

const checkInfo = async () => {
  let required: string[]

  if (!isApprise.value) {
    required = ['name', 'request.url', 'request.method', 'request.type', 'request.data_key']
  } else {
    required = ['name', 'request.url']
  }

  for (const key of required) {
    if (key.includes('.')) {
      const [parent, child] = key.split('.') as [keyof typeof form, string]
      const parentObj = form[parent] as Record<string, any> | undefined

      if (!parentObj || !parentObj[child]) {
        toast.error(`The field ${parent}.${child} is required.`)
        return
      }
    } else {
      const value = (form as Record<string, any>)[key]
      if (!value) {
        toast.error(`The field ${key} is required.`)
        return
      }
    }
  }

  if (!isApprise.value) {
    try {
      new URL(form.request.url)
    } catch {
      toast.error('Invalid URL')
      return
    }
  }

  const headers = []
  for (const header of form.request.headers) {
    if (!header.key || !header.value) {
      continue
    }
    headers.push({ key: String(header.key).trim(), value: String(header.value).trim() })
  }
  form.request.headers = headers

  emitter('submit', { reference: toRaw(props.reference), item: toRaw(form) })
}

const importItem = async () => {
  const val = import_string.value.trim()
  if (!val) {
    toast.error('The import string is required.')
    return
  }

  try {
    const item = decode(val) as notificationImport

    if ('notification' !== item._type) {
      toast.error(`Invalid import string. Expected type 'notification', got '${item._type}'.`)
      import_string.value = ''
      return
    }

    if (form.name || form.request?.url) {
      if (false === (await box.confirm('Overwrite the current form fields?'))) {
        return
      }
    }

    if (item.name) {
      form.name = item.name
    }

    if (!form.request) {
      form.request = {} as any
    }

    if (item.request) {
      form.request = item.request
    }

    if (item.request?.data_key) {
      form.request.data_key = item.request.data_key
    }

    if (item.on) {
      form.on = item.on
    }

    if (item.presets) {
      item.presets.forEach(p => {
        if (!config.presets.find(cp => cp.name === p)) {
          return
        }
        if (!form.presets.includes(p)) {
          form.presets.push(p)
        }
      })
    }

    if (item.enabled !== undefined) {
      form.enabled = item.enabled
    }

    import_string.value = ''
  } catch (e: any) {
    console.error(e)
    toast.error(`Failed to import task. ${e.message}`)
  }
}

const isApprise = computed(() => form.request.url && !form.request.url.startsWith('http'))
const filter_presets = (flag: boolean = true) => config.presets.filter(item => item.default === flag)
</script>
