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
                <span class="help">
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
                  <span class="help">
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
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>The URL to send the notification to.</span>
                  </span>
                </div>
              </div>

              <div class="column is-6-tablet is-12-mobile">
                <div class="field">
                  <label class="label is-inline" for="method">
                    Request method
                  </label>
                  <div class="control has-icons-left">
                    <div class="select is-fullwidth">
                      <select id="method" class="is-fullwidth" v-model="form.request.method" :disabled="addInProgress">
                        <option v-for="item, index in requestMethods" :key="`${index}-${item}`" :value="item">
                          {{ item }}
                        </option>
                      </select>
                    </div>
                    <span class="icon is-small is-left"><i class="fa-solid fa-tv" /></span>
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>
                      The request method to use when sending the notification. This can be any of the standard HTTP
                      methods.
                    </span>
                  </span>
                </div>
              </div>

              <div class="column is-6-tablet is-12-mobile">
                <div class="field">
                  <label class="label is-inline" for="type">
                    Request Type
                  </label>
                  <div class="control has-icons-left">
                    <div class="select is-fullwidth">
                      <select id="type" class="is-fullwidth" v-model="form.request.type" :disabled="addInProgress">
                        <option v-for="item, index in requestType" :key="`${index}-${item}`" :value="item">
                          {{ ucFirst(item) }}
                        </option>
                      </select>
                    </div>
                    <span class="icon is-small is-left"><i class="fa-solid fa-tv" /></span>
                  </div>
                  <span class="help">
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
                        <option v-for="item, index in allowedEvents" :key="`${index}-${item}`" :value="item">
                          {{ item }}
                        </option>
                      </select>
                    </div>
                    <span class="icon is-small is-left"><i class="fa-solid fa-paper-plane" /></span>
                  </div>
                  <span class="help">
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
                  <label class="label is-inline" for="data_key">
                    Data field
                  </label>
                  <div class="control has-icons-left">
                    <input type="text" class="input" id="data_key" v-model="form.request.data_key"
                      :disabled="addInProgress" required>
                    <span class="icon is-small is-left"><i class="fa-solid fa-key" /></span>
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>
                      The field name to use when sending the notification. This is used to identify the data in the
                      request. The default is <code>data</code>.
                    </span>
                  </span>
                </div>
              </div>

              <div class="column is-12">
                <div class="field">
                  <label class="label is-inline is-unselectable">
                    Optional Headers - <button type="button" class="has-text-link"
                      @click="form.request.headers.push({ key: '', value: '' });">Add Header
                    </button>
                  </label>
                  <div class="columns is-multiline is-mobile">
                    <template v-for="_, key in form.request.headers" :key="key">
                      <div class="column is-5">
                        <div class="field">
                          <div class="control has-icons-left">
                            <input type="text" class="input" v-model="form.request.headers[key].key"
                              :disabled="addInProgress" required>
                            <span class="icon is-small is-left"><i class="fa-solid fa-key" /></span>
                          </div>
                        </div>
                        <span class="help">
                          <span class="icon"><i class="fa-solid fa-info" /></span>
                          <span>The header key to send with the notification.</span>
                        </span>
                      </div>
                      <div class="column is-6">
                        <div class="field">
                          <div class="control has-icons-left">
                            <input type="text" class="input" v-model="form.request.headers[key].value"
                              :disabled="addInProgress" required>
                            <span class="icon is-small is-left"><i class="fa-solid fa-v" /></span>
                          </div>
                        </div>
                        <span class="help">
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
                  <span class="help">
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

<script setup>
import { useStorage } from '@vueuse/core'
const emitter = defineEmits(['cancel', 'submit']);
const toast = useNotification();
const props = defineProps({
  reference: {
    type: String,
    required: false,
    default: null,
  },
  allowedEvents: {
    type: Array,
    required: true,
  },
  item: {
    type: Object,
    required: true,
  },
  addInProgress: {
    type: Boolean,
    required: false,
    default: false,
  },
})

const form = reactive(props.item);
const requestMethods = ['POST', 'PUT'];
const requestType = ['json', 'form'];
const showImport = useStorage('showImport', false);
const import_string = ref('');

const checkInfo = async () => {
  const required = ['name', 'request.url', 'request.method', 'request.type', 'request.data_key'];
  for (const key of required) {
    if (key.includes('.')) {
      const [parent, child] = key.split('.');
      if (!form[parent][child]) {
        toast.error(`The field ${parent}.${child} is required.`);
        return;
      }
    } else if (!form[key]) {
      toast.error(`The field ${key} is required.`);
      return;
    }
  }

  try {
    new URL(form.request.url);
  } catch (e) {
    toast.error('Invalid URL');
    return;
  }

  let headers = []

  for (const header of form.request.headers) {
    if (!header.key || !header.value) {
      continue
    }
    headers.push({ key: String(header.key).trim(), value: String(header.value).trim() })
  }

  form.request.headers = headers;
  emitter('submit', { reference: toRaw(props.reference), item: toRaw(form) });
}


const importItem = async () => {
  let val = import_string.value.trim()
  if (!val) {
    toast.error('The import string is required.')
    return
  }

  if (false === val.startsWith('{')) {
    try {
      val = base64UrlDecode(val)
    } catch (e) {
      console.error(e)
      toast.error(`Failed to decode string. ${e.message}`)
      return
    }
  }

  try {
    const item = JSON.parse(val)

    if ('notification' !== item._type) {
      toast.error(`Invalid import string. Expected type 'notification', got '${item._type}'.`)
      import_string.value = ''
      return
    }

    if (form.target) {
      if (false === confirm('This will overwrite the current form fields. Are you sure?')) {
        return
      }
    }

    if (item.name) {
      form.name = item.name
    }

    if (item.url) {
      form.url = item.url
    }

    if (item.request) {
      form.request = item.request
    }

    if (item.data_key) {
      form.data_key = item.data_key
    }

    if (item.on) {
      form.on = item.on
    }

    import_string.value = ''
  } catch (e) {
    console.error(e)
    toast.error(`Failed to import task. ${e.message}`)
  }
}
</script>
