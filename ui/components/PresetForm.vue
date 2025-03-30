<template>
  <main class="columns mt-2 is-multiline">
    <div class="column is-12">
      <form autocomplete="off" id="presetForm" @submit.prevent="checkInfo()">
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
                <span>{{ showImport ? 'Hide' : 'Show' }} import</span>
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
                  <label class="label is-inline" for="name" v-text="'Name'" />
                  <div class="control has-icons-left">
                    <input type="text" class="input" id="name" v-model="form.name" :disabled="addInProgress">
                    <span class="icon is-small is-left"><i class="fa-solid fa-n" /></span>
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>The name to refers to this custom settings.</span>
                  </span>
                </div>
              </div>

              <div class="column is-6-tablet is-12-mobile">
                <div class="field">
                  <label class="label is-inline" for="format" v-text="'Format'" />
                  <div class="control has-icons-left">
                    <input type="text" class="input" id="format" v-model="form.format" :disabled="addInProgress">
                    <span class="icon is-small is-left"><i class="fa-solid fa-f" /></span>
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>The yt-dlp <code>[--format, -f]</code> video format code. see <NuxtLink
                        href="https://github.com/yt-dlp/yt-dlp?tab=readme-ov-file#format-selection" target="blank">this
                        url</NuxtLink> for more info.</span>. Note, as this key is required, you can set the value to
                    <code>default</code> to let <code>yt-dlp</code> choose the best format.
                  </span>
                </div>
              </div>

              <div class="column is-6-tablet is-12-mobile">
                <div class="field">
                  <label class="label is-inline" for="folder">
                    Default Download path
                  </label>
                  <div class="control has-icons-left">
                    <input type="text" class="input" id="folder" placeholder="Leave empty to use default download path"
                      v-model="form.folder" :disabled="addInProgress" list="folders">
                    <span class="icon is-small is-left"><i class="fa-solid fa-folder" /></span>
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>Use this folder if non is given with URL. Leave empty to use default download path. Default
                      download path <code>{{ config.app.download_path }}</code>.</span>
                  </span>
                </div>
              </div>

              <div class="column is-6-tablet is-12-mobile">
                <div class="field">
                  <label class="label is-inline" for="output_template">
                    Default Output template
                  </label>
                  <div class="control has-icons-left">
                    <input type="text" class="input" id="output_template" :disabled="addInProgress"
                      placeholder="Leave empty to use default template." v-model="form.template">
                    <span class="icon is-small is-left"><i class="fa-solid fa-file" /></span>
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>Use this output template if non are given with URL. if not set, it will defaults to
                      <code>{{ config.app.output_template }}</code>.
                      For more information <NuxtLink href="https://github.com/yt-dlp/yt-dlp#output-template"
                        target="_blank">visit this url</NuxtLink>.
                    </span>
                  </span>
                </div>
              </div>

              <div class="column is-12">
                <div class="field">
                  <label class="label is-inline" for="cli_options">
                    Command arguments for yt-dlp
                  </label>
                  <div class="control">
                    <input type="text" class="input" v-model="form.cli" id="cli_options" :disabled="addInProgress"
                      placeholder="command options to use, e.g. --no-embed-metadata --no-embed-thumbnail">
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>yt-dlp cli arguments. Check <NuxtLink target="_blank"
                        to="https://github.com/yt-dlp/yt-dlp?tab=readme-ov-file#general-options">this page</NuxtLink>.
                      For more info. <span class="has-text-danger">Not all options are supported some are ignored. Use
                        with caution those arguments can break yt-dlp or the frontend.</span>
                    </span>
                  </span>
                </div>
              </div>

              <div class="column is-12">
                <div class="field">
                  <label class="label is-inline" for="cookies"
                    v-tooltip="'Netscape HTTP Cookie format.'">Cookies</label>
                  <div class="control">
                    <textarea class="textarea is-pre" id="cookies" v-model="form.cookies" :disabled="addInProgress"
                      placeholder="Leave empty to use default cookies" />
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>Use this cookies if non are given with the URL. Use the <NuxtLink target="_blank"
                        to="https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp">
                        Recommended addon</NuxtLink> by yt-dlp to export cookies. The cookies MUST be in Netscape HTTP
                      Cookie format.
                    </span>
                  </span>
                </div>
              </div>
              <div class="column is-12" v-if="has_data(form?.args) || has_data(form?.postprocessors)">
                <Message title="Deprecation Warning" class="is-background-warning-80 has-text-dark"
                  icon="fas fa-exclamation-circle">
                  <ul>
                    <li>
                      The <code>JSON yt-dlp config</code> and <code>JSON yt-dlp Post-Processors</code> fields are
                      deprecated and will be removed in the future. Please use the <b>Command arguments for yt-dlp</b>
                      field instead. The deprecated fields will still be working for now but they will stop, we suggest
                      that you migrate to the new field. as soon as possible to avoid any issues. No support will be
                      given for the deprecated fields.
                    </li>
                    <li>
                      If both fields are set, the <b>Command arguments for yt-dlp</b> field will take precedence over
                      the deprecated fields. and when you click save it will remove the deprecated fields.
                    </li>
                  </ul>
                </Message>
              </div>
              <div class="column is-6-tablet is-12-mobile" v-if="has_data(form?.args)">
                <div class="field">
                  <label class="label is-inline" for="args" v-tooltip="'Extends current global yt-dlp config. (JSON)'">
                    JSON yt-dlp config <span class="has-text-danger">(DEPRECATED)</span>
                  </label>
                  <div class="control">
                    <textarea class="textarea" id="args" v-model="form.args" :disabled="addInProgress"
                      placeholder="{}" />
                  </div>
                  <span class="help has-text-danger">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>Deprecated, use <b>Command arguments for yt-dlp</b> field instead. </span>
                  </span>
                </div>
              </div>

              <div class="column is-6-tablet is-12-mobile" v-if="has_data(form?.postprocessors)">
                <div class="field">
                  <label class="label is-inline" for="postprocessors"
                    v-tooltip="'Things to do after download is done.'">
                    JSON yt-dlp Post-Processors <span class="has-text-danger">(DEPRECATED)</span>
                  </label>
                  <div class="control">
                    <textarea class="textarea" id="postprocessors" v-model="form.postprocessors"
                      :disabled="addInProgress" placeholder="[]" />
                  </div>
                  <span class="help has-text-danger">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>Deprecated, use <b>Command arguments for yt-dlp</b> field instead. </span>
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div class="card-footer">
            <div class="card-footer-item">
              <button class="button is-fullwidth is-primary" :disabled="addInProgress" type="submit"
                :class="{ 'is-loading': addInProgress }" form="presetForm">
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

    <datalist id="folders" v-if="config?.folders">
      <option v-for="dir in config.folders" :key="dir" :value="dir" />
    </datalist>
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
  preset: {
    type: Object,
    required: true,
  },
  addInProgress: {
    type: Boolean,
    required: false,
    default: false,
  },
  presets: {
    type: Array,
    required: false,
    default: () => [],
  },
})

const config = useConfigStore()
const toast = useToast()
const form = reactive(JSON.parse(JSON.stringify(props.preset)))
const import_string = ref('')
const showImport = useStorage('showImport', false);

onMounted(() => {
  if (props.preset?.cli && '' !== props.preset?.cli) {
    return
  }

  if (props.preset?.args && (typeof props.preset.args === 'object')) {
    form.args = JSON.stringify(props.preset.args, null, 2)
  }

  if (props.preset?.postprocessors && (typeof props.preset.postprocessors === 'object')) {
    form.postprocessors = JSON.stringify(props.preset.postprocessors, null, 2)
  }
})

const checkInfo = async () => {
  const required = ['name', 'format'];
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

  let usedName = false;
  let name = String(form.name).trim().toLowerCase();

  props.presets.forEach(p => {
    if (p.id === props.reference) {
      return;
    }

    if (String(p.name).toLowerCase() === name) {
      usedName = true;
    }
  });

  if (true === usedName) {
    toast.error('The preset name is already in use.');
    return;
  }

  if (form?.cli && '' !== form.cli) {
    if ((has_data(copy?.args) || has_data(copy?.postprocessors))) {
      if (false === confirm('cli options are set, this will remove the JSON yt-dlp config and Post-Processors. Are you sure?')) {
        toast.warning('User cancelled the operation.')
        return
      }
    }

    if (copy?.args) {
      delete copy.args
    }

    if (copy?.postprocessors) {
      delete copy.postprocessors
    }
  }
  else {
    if (typeof copy.args === 'object') {
      copy.args = JSON.stringify(copy.args, null, 2);
    }

    if (typeof copy.postprocessors === 'object') {
      copy.postprocessors = JSON.stringify(copy.postprocessors, null, 2);
    }

    if (copy?.args) {
      try {
        copy.args = JSON.parse(copy.args)
      } catch (e) {
        toast.error(`Invalid JSON yt-dlp config. ${e.message}`)
        return;
      }
    }

    if (copy?.postprocessors) {
      try {
        copy.postprocessors = JSON.parse(copy.postprocessors)
      } catch (e) {
        toast.error(`Invalid JSON yt-dlp Post-Processors. ${e.message}`)
        return;
      }
    }
  }

  // trim all fields in copy only if they are strings
  for (const key in copy) {
    if (typeof copy[key] === 'string') {
      copy[key] = copy[key].trim()
    }
  }

  emitter('submit', { reference: toRaw(props.reference), preset: toRaw(copy) });
}

const convertOptions = async args => {
  try {
    const response = await convertCliOptions(args)

    if (response.output_template) {
      form.template = response.output_template
    }

    if (response.download_path) {
      form.folder = response.download_path
    }

    if (response.format) {
      form.format = response.format
    }

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

    console.log(item)

    if ('preset' !== item._type) {
      toast.error(`Invalid import string. Expected type 'preset', got '${item._type}'.`)
      import_string.value = ''
      return
    }

    if (form.format || form.cli) {
      if (false === confirm('This will overwrite the current form fields. Are you sure?')) {
        return
      }
    }

    if (item.name) {
      form.name = item.name
    }

    if (item.format) {
      form.format = item.format
    }

    if (item.cli) {
      form.cli = item.cli
    }

    if (item.template) {
      form.template = item.output_template
    }

    if (item.folder) {
      form.folder = item.folder
    }

    import_string.value = ''
    showImport.value = false
  } catch (e) {
    console.error(e)
    toast.error(`Failed to string. ${e.message}`)
  }
}

</script>
