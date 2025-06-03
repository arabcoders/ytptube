<template>
  <main class="columns mt-2 is-multiline">
    <div class="column is-12">
      <form autocomplete="off" id="addForm" @submit.prevent="checkInfo()">
        <div class="card is-flex is-full-height is-flex-direction-column">
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
                <span>{{ showImport ? 'Hide' : 'Show' }} import</span>
              </button>
            </div>
          </div>

          <div class="card-content is-flex-grow-1">

            <div class="columns is-multiline is-mobile">

              <div class="column is-12" v-if="showImport || !reference">
                <label class="label is-inline" for="import_string">
                  <span class="icon"><i class="fa-solid fa-file-import" /></span>
                  Import string
                </label>

                <div class="field has-addons">
                  <div class="control is-expanded">
                    <input type="text" class="input" id="import_string" v-model="import_string" autocomplete="off">
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

              <div class="column is-12">
                <div class="field">
                  <label class="label is-inline" for="name">
                    <span class="icon"><i class="fa-solid fa-tag" /></span>
                    Name
                  </label>
                  <div class="control">
                    <input type="text" class="input" id="name" v-model="form.name" :disabled="addInProgress"
                      placeholder="For the problematic channel or video name.">
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>The name that refers to this condition.</span>
                  </span>
                </div>
              </div>

              <div class="column is-12">
                <div class="field">
                  <label class="label is-inline" for="filter">
                    <span class="icon"><i class="fa-solid fa-filter" /></span>
                    Filter
                  </label>
                  <div class="control">
                    <input type="text" class="input" id="filter" v-model="form.filter" :disabled="addInProgress"
                      placeholder="availability = 'needs_auth' & channel_id = 'channel_id'">
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>The yt-dlp <code>[--match-filters]</code> filter logic.</span>
                  </span>
                </div>
              </div>

              <div class="column is-12">
                <div class="field">
                  <label class="label is-inline" for="cli_options">
                    <span class="icon"><i class="fa-solid fa-terminal" /></span>
                    Command arguments for yt-dlp
                  </label>
                  <div class="control">
                    <textarea class="textarea is-pre" v-model="form.cli" id="cli_options" :disabled="addInProgress"
                      placeholder="command options to use, e.g. --proxy 1.2.3.4:3128" />
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>If the filter is matched, these options will be used.
                      <span class="has-text-danger">This will override the cli arguments given with the URL. it's
                        recommended to use presets and keep the cli with url empty if you plan to use this
                        feature.</span>
                    </span>
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div class="card-footer mt-auto">
            <div class="card-footer-item">
              <button class="button is-fullwidth is-primary" :disabled="addInProgress" type="submit"
                :class="{ 'is-loading': addInProgress }" form="addForm">
                <span class="icon"><i class="fa-solid fa-save" /></span>
                <span>Save</span>
              </button>
            </div>
            <div class="card-footer-item">
              <button class="button is-fullwidth is-danger" @click="emitter('cancel')" :disabled="addInProgress"
                type="button">
                <span class="icon"><i class="fa-solid fa-times" /></span>
                <span>Cancel</span>
              </button>
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

const props = defineProps({
  reference: {
    type: String,
    required: false,
    default: null,
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

const toast = useNotification()
const box = useConfirm()
const form = reactive(JSON.parse(JSON.stringify(props.item)))
const import_string = ref('')
const showImport = useStorage('showImport', false);

const checkInfo = async () => {
  const required = ['name', 'filter', 'cli'];

  for (const key of required) {
    if (!form[key]) {
      toast.error(`The ${key} field is required.`);
      return
    }
  }

  if (form?.cli && '' !== form.cli) {
    const options = await convertOptions(form.cli);
    if (null === options) {
      return
    }
    form.cli = form.cli.trim()
  }

  let copy = JSON.parse(JSON.stringify(form));

  for (const key in copy) {
    if (typeof copy[key] !== 'string') {
      continue
    }
    copy[key] = copy[key].trim()
  }

  emitter('submit', { reference: toRaw(props.reference), item: toRaw(copy) });
}

const convertOptions = async args => {
  try {
    const response = await convertCliOptions(args)
    return response.opts
  } catch (e) {
    toast.error(e.message)
  }
  return null;
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

    if (!item?._type || 'condition' !== item._type) {
      toast.error(`Invalid import string. Expected type 'condition', got '${item._type ?? 'unknown'}'.`)
      return
    }

    if ((form.filter || form.cli) && false === box.confirm('This will overwrite the current data. Are you sure?', true)) {
      return
    }

    if (item.name) {
      form.name = item.name
    }

    if (item.filter) {
      form.filter = item.filter
    }

    if (item.cli) {
      form.cli = item.cli
    }

    import_string.value = ''
    showImport.value = false
  } catch (e) {
    console.error(e)
    toast.error(`Failed to parse import string. ${e.message}`)
  }
}
</script>
