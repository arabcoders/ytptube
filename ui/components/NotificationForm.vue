<template>
  <main class="columns mt-2">
    <div class="column">
      <form id="taskForm" @submit.prevent="checkInfo()">
        <div class="box">
          <div class="columns is-multiline is-mobile">
            <div class="column is-12">
              <h1 class="title is-6" style="border-bottom: 1px solid #dbdbdb;">
                <span class="icon-text">
                  <span class="icon"><i class="fa-solid" :class="reference ? 'fa-cog' : 'fa-plus'" /></span>
                  <span>{{ reference ? 'Edit' : 'Add' }}</span>
                </span>
              </h1>
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

            <div class="column is-12 is-clearfix">
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
                    be sent to the target URL. If no events are selected, the notification will be sent for all events.
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

            <div class="column is-12">
              <div class="field is-grouped is-grouped-right">
                <p class="control">
                  <button class="button is-primary" :disabled="addInProgress" type="submit"
                    :class="{ 'is-loading': addInProgress }" form="taskForm">
                    <span class="icon"><i class="fa-solid fa-save" /></span>
                    <span>Save</span>
                  </button>
                </p>
                <p class="control">
                  <button class="button is-danger" @click="emitter('cancel')" :disabled="addInProgress" type="button">
                    <span class="icon"><i class="fa-solid fa-times" /></span>
                    <span>Cancel</span>
                  </button>
                </p>
              </div>
            </div>

          </div>
        </div>
      </form>
    </div>
  </main>
</template>

<script setup>
import { request } from '~/utils/index'

const emitter = defineEmits(['cancel', 'submit']);
const toast = useToast();
const addInProgress = ref(false);
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
  }
})

const form = reactive(props.item);
const requestMethods = ['POST', 'PUT'];
const requestType = ['json', 'form'];

const checkInfo = async () => {
  const required = ['name', 'request.url', 'request.method', 'request.type'];
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

  // -- validate headers

  for (const header of form.request.headers) {
    if (!header.key || !header.value) {
      form.request.headers.splice(form.request.headers.indexOf(header), 1);
      return;
    }
  }

  addInProgress.value = true;
  emitter('submit', { reference: toRaw(props.reference), item: toRaw(form) });
}

</script>
