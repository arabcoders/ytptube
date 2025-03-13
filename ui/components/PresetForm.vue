<template>
  <main class="columns mt-2 is-multiline">
    <div class="column is-12">
      <h1 class="is-pointer is-unselectable title is-5" @click="importExpanded = !importExpanded">
        <span class="icon-text">
          <span class="icon"><i class="fa-solid" :class="importExpanded ? 'fa-arrow-up' : 'fa-arrow-down'" /></span>
          <span>Import preset.</span>
        </span>
      </h1>

      <form id="importForm" @submit.prevent="importPreset()" v-if="importExpanded">
        <div class="box">
          <label class="label" for="json_preset">
            Base64 encoded JSON string.
          </label>

          <div class="field has-addons">

            <div class="control has-icons-left is-expanded">
              <input type="text" class="input" id="json_preset" v-model="json_preset" autocomplete="off">
              <span class="icon is-small is-left"><i class="fa-solid fa-t" /></span>
            </div>

            <div class="control">
              <button form="importForm" class="button is-primary" :disabled="!json_preset" type="submit">
                <span class="icon"><i class="fa-solid fa-add" /></span>
                <span>Import</span>
              </button>
            </div>

          </div>
        </div>
      </form>
    </div>

    <div class="column is-12">
      <h1 class="is-unselectable is-pointer title is-5" @click="convertExpanded = !convertExpanded">
        <span class="icon-text">
          <span class="icon"><i class="fa-solid" :class="convertExpanded ? 'fa-arrow-up' : 'fa-arrow-down'" /></span>
          <span>Convert yt-dlp cli options.</span>
        </span>
      </h1>

      <form autocomplete="off" id="convertOpts" @submit.prevent="convertOptions()" v-if="convertExpanded">
        <div class="box">

          <label class="label" for="opts">
            yt-dlp CLI options
          </label>

          <div class="field has-addons">

            <div class="control has-icons-left is-expanded">
              <input type="text" class="input" id="opts" v-model="opts"
                placeholder="-x --audio-format mp3 -f bestaudio">
              <span class="icon is-small is-left"><i class="fa-solid fa-n" /></span>
            </div>

            <div class="control">
              <button form="convertOpts" class="button is-primary" :disabled="convertInProgress || !opts" type="submit"
                :class="{ 'is-loading': convertInProgress }">
                <span class="icon"><i class="fa-solid fa-cog" /></span>
                <span>Convert</span>
              </button>
            </div>

          </div>
          <p class="help">
            <span class="icon"><i class="fa-solid fa-info" /></span>
            <span>Convert yt-dlp CLI options to JSON format. This will overwrite the current form fields.</span>
          </p>
        </div>
      </form>
    </div>

    <div class="column is-12">
      <form id="presetForm" @submit.prevent="checkInfo()">
        <div class="card">
          <div class="card-header">
            <div class="card-header-title">
              <span class="icon-text">
                <span class="icon"><i class="fa-solid" :class="reference ? 'fa-cog' : 'fa-plus'" /></span>
                <span>{{ reference ? 'Edit' : 'Add' }}</span>
              </span>
            </div>
          </div>
          <div class="card-content">
            <div class="columns is-multiline is-mobile">
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
                    <code>not_set</code>
                    to use the default yt-dlp format.
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

              <div class="column is-6-tablet is-12-mobile">
                <div class="field">
                  <label class="label is-inline" for="args" v-tooltip="'Extends current global yt-dlp config. (JSON)'">
                    JSON yt-dlp config
                  </label>
                  <div class="control">
                    <textarea class="textarea" id="args" v-model="form.args" :disabled="addInProgress"
                      placeholder="{}" />
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>Extends current global yt-dlp config with given options. Some fields are ignored like
                      <code>cookiefile</code>, <code>paths</code>, and <code>outtmpl</code> etc. Warning: Use with
                      caution
                      some of those options can break yt-dlp or the frontend.</span>
                  </span>
                </div>
              </div>

              <div class="column is-6-tablet is-12-mobile">
                <div class="field">
                  <label class="label is-inline" for="postprocessors"
                    v-tooltip="'Things to do after download is done.'">
                    JSON yt-dlp Post-Processors
                  </label>
                  <div class="control">
                    <textarea class="textarea" id="postprocessors" v-model="form.postprocessors"
                      :disabled="addInProgress" placeholder="[]" />
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>
                      Post-processing operations, refer to <NuxtLink
                        href="https://github.com/yt-dlp/yt-dlp/tree/master/yt_dlp/postprocessor" target="blank">this url
                      </NuxtLink> for more info. It's easier for you to use the <b>Convert CLI options</b> to get what
                      you
                      want and it will auto-populate the fields if necessary.
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
        </div>
      </form>
    </div>
    <datalist id="folders" v-if="config?.folders">
      <option v-for="dir in config.folders" :key="dir" :value="dir" />
    </datalist>
  </main>
</template>

<script setup>
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
const convertInProgress = ref(false)
const form = reactive(JSON.parse(JSON.stringify(props.preset)))
const opts = ref('')
const json_preset = ref('')
const importExpanded = ref(false)
const convertExpanded = ref(false)

onMounted(() => {
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

  if (typeof copy.args === 'object') {
    copy.args = JSON.stringify(copy.args, null, 2);
  }

  if (typeof copy.postprocessors === 'object') {
    copy.postprocessors = JSON.stringify(copy.postprocessors, null, 2);
  }

  if (copy.args) {
    try {
      copy.args = JSON.parse(copy.args)
    } catch (e) {
      toast.error(`Invalid JSON yt-dlp config. ${e.message}`)
      return;
    }
  }

  if (copy.postprocessors) {
    try {
      copy.postprocessors = JSON.parse(copy.postprocessors)
    } catch (e) {
      toast.error(`Invalid JSON yt-dlp Post-Processors. ${e.message}`)
      return;
    }
  }

  emitter('submit', { reference: toRaw(props.reference), preset: toRaw(copy) });
}

const convertOptions = async () => {
  if (convertInProgress.value) {
    return
  }

  if (form.format || form.args || form.postprocessors || form.template || form.folder) {
    if (false === confirm('This will overwrite the current form fields. Are you sure?')) {
      return
    }
  }

  try {
    convertInProgress.value = true
    const response = await convertCliOptions(opts.value)

    if (!response.opts) {
      toast.error('Failed to convert options.')
      return
    }

    if (response.opts.format) {
      form.format = response.opts.format
      delete response.opts.format
    }

    if (response.output_template) {
      form.template = response.output_template
    }

    if (response.download_path) {
      form.folder = response.download_path
    }

    if (response.opts.postprocessors) {
      form.postprocessors = JSON.stringify(response.opts.postprocessors, null, 2)
      delete response.opts.postprocessors
    }

    form.args = JSON.stringify(response.opts, null, 2)
    opts.value = ''
  } catch (e) {
    toast.error(e.message)
  } finally {
    convertInProgress.value = false
  }
}

const importPreset = async () => {
  let val = json_preset.value.trim()
  if (!val) {
    toast.error('The preset import string is required.')
    return
  }

  if (false === val.startsWith('{')) {
    try {
      val = base64UrlDecode(val)
    } catch (e) {
      toast.error('Invalid base64 string.', e)
      return
    }
  }

  try {
    const preset = JSON.parse(val)

    if (form.format || form.args || form.postprocessors) {
      if (false === confirm('This will overwrite the current form fields. Are you sure?')) {
        return
      }
    }

    if (preset.name) {
      form.name = preset.name
    }

    if (preset.format) {
      form.format = preset.format
    }

    if (preset.args) {
      form.args = JSON.stringify(preset.args, null, 2)
    }

    if (preset.postprocessors) {
      form.postprocessors = JSON.stringify(preset.postprocessors, null, 2)
    }

    if (preset.output_template) {
      form.template = preset.output_template
    }

    if (preset.folder) {
      form.folder = preset.folder
    }

    json_preset.value = ''
    importExpanded.value = false
  } catch (e) {
    console.error(e)
    toast.error(`Failed to import preset. ${e.message}`)
  }
}
</script>
