<template>
  <main class="columns mt-2">
    <div class="column is-12">
      <form autocomplete="off" @submit.prevent="addDownload">
        <div class="box">
          <div class="columns is-multiline is-mobile">
            <div class="column is-12">
              <label class=" label is-inline is-unselectable" for="url">
                <span class="icon"><i class="fa-solid fa-link" /></span>
                <span class="has-tooltip" v-tooltip="'Use Shift+Enter to switch to multiline input mode.'">
                  URLs separated by newlines or <span class="is-bold is-lowercase">{{ getSeparatorsName(separator)
                  }}</span>
                </span>
              </label>
              <div class="field is-grouped">
                <div class="control is-expanded">
                  <textarea v-if="isMultiLineInput" ref="urlTextarea" class="textarea" id="url"
                    :disabled="!socket.isConnected || addInProgress" v-model="form.url" @keydown="handleKeyDown"
                    @input="adjustTextareaHeight"
                    style="resize: none; overflow-y: auto; min-height: 38px; max-height: 300px;" />
                  <input v-else type="text" class="input" id="url" placeholder="URLs to download"
                    :disabled="!socket.isConnected || addInProgress" v-model="form.url" @keydown="handleKeyDown"
                    @paste="handlePaste">
                </div>
                <div class="control">
                  <button type="submit" class="button is-primary" :class="{ 'is-loading': addInProgress }"
                    :disabled="!socket.isConnected || addInProgress || !hasValidUrl">
                    <span class="icon"><i class="fa-solid fa-plus" /></span>
                    <span>Add</span>
                  </button>
                </div>
              </div>
            </div>

            <div class="column is-4-tablet is-12-mobile">
              <div class="field has-addons">
                <div class="control" @click="show_description = !show_description">
                  <label class="button is-static">
                    <span class="icon"><i class="fa-solid fa-sliders" /></span>
                    <span>Preset</span>
                  </label>
                </div>
                <div class="control is-expanded">
                  <div class="select is-fullwidth">
                    <select id="preset" class="is-fullwidth"
                      :disabled="!socket.isConnected || addInProgress || hasFormatInConfig" v-model="form.preset"
                      v-tooltip.bottom="hasFormatInConfig ? 'Presets are disabled. Format key is present in the command options for yt-dlp.' : ''">
                      <optgroup label="Custom presets" v-if="config?.presets.filter(p => !p?.default).length > 0">
                        <option v-for="cPreset in filter_presets(false)" :key="cPreset.name" :value="cPreset.name">
                          {{ cPreset.name }}
                        </option>
                      </optgroup>
                      <optgroup label="Default presets">
                        <option v-for="dPreset in filter_presets(true)" :key="dPreset.name" :value="dPreset.name">
                          {{ dPreset.name }}
                        </option>
                      </optgroup>
                    </select>
                  </div>
                </div>
              </div>
            </div>

            <div class="column is-6-tablet is-12-mobile">
              <div class="field has-addons" v-tooltip="'Folder relative to ' + config.app.download_path">
                <div class="control">
                  <label class="button is-static">
                    <span class="icon"><i class="fa-solid fa-folder" /></span>
                    <span>Save in</span>
                  </label>
                </div>
                <div class="control is-expanded">
                  <input type="text" class="input is-fullwidth" id="path" v-model="form.folder"
                    :placeholder="getDefault('folder', '/')" :disabled="!socket.isConnected || addInProgress"
                    list="folders">
                </div>
              </div>
            </div>

            <div class="column">
              <button type="button" class="button is-info" @click="showAdvanced = !showAdvanced"
                :disabled="!socket.isConnected">
                <span class="icon"><i class="fa-solid fa-cog" /></span>
                <span>Advanced Options</span>
              </button>
            </div>

            <div class="column is-12"
              v-if="show_description && !hasFormatInConfig && get_preset(form.preset)?.description">
              <div class="is-overflow-auto" style="max-height: 150px;">
                <div class="is-ellipsis is-clickable" @click="expand_description">
                  <span class="icon"><i class="fa-solid fa-info" /></span> {{ get_preset(form.preset)?.description }}
                </div>
              </div>
            </div>
          </div>

          <div class="columns is-multiline is-mobile" v-if="showAdvanced">
            <div class="column is-2-tablet is-12-mobile">
              <DLInput id="force_download" type="bool" label="Force download" icon="fa-solid fa-download"
                v-model="dlFields['--no-download-archive']" :disabled="!socket.isConnected || addInProgress"
                description="Ignore archive." />
            </div>

            <div class="column is-2-tablet is-12-mobile">
              <DLInput id="auto_start" type="bool" label="Auto start" v-model="auto_start" icon="fa-solid fa-play"
                :disabled="!socket.isConnected || addInProgress" description="Download automatically." />
            </div>

            <div class="column is-2-tablet is-12-mobile">
              <DLInput id="no_cache" type="bool" label="Bypass cache" icon="fa-solid fa-broom"
                v-model="dlFields['--no-continue']" :disabled="!socket.isConnected || addInProgress"
                description="Remove temporary files." />
            </div>

            <div class="column is-6-tablet is-12-mobile">
              <DLInput id="output_template" type="string" label="Output template" v-model="form.template"
                icon="fa-solid fa-file" :disabled="!socket.isConnected || addInProgress"
                :placeholder="getDefault('template', config.app.output_template || '%(title)s.%(ext)s')">
                <template #help>
                  <span class="help is-bold is-unselectable">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>All output template naming options can be found at <NuxtLink target="_blank"
                        to="https://github.com/yt-dlp/yt-dlp#output-template">this page</NuxtLink>.</span>
                  </span>
                </template>
              </DLInput>
            </div>

            <div class="column is-6-tablet is-12-mobile">
              <div class="field">
                <label class="label is-unselectable" for="cli_options">
                  <span class="icon"><i class="fa-solid fa-terminal" /></span>
                  <span>Command options for yt-dlp</span>
                </label>
                <TextareaAutocomplete id="cli_options" v-model="form.cli" :options="ytDlpOpt"
                  :placeholder="getDefault('cli', '')" :disabled="!socket.isConnected || addInProgress" />
                <span class="help is-bold">
                  <span class="icon"><i class="fa-solid fa-info" /></span>
                  <span>
                    <NuxtLink @click="showOptions = true">View all options</NuxtLink>. Not all options are supported
                    <NuxtLink target="_blank"
                      to="https://github.com/arabcoders/ytptube/blob/master/app/library/Utils.py#L26">some
                      are ignored</NuxtLink>. Use with caution.
                  </span>
                </span>
              </div>
            </div>

            <div class="column is-6-tablet is-12-mobile">
              <div class="field">
                <label class="label is-unselectable" for="ytdlpCookies">
                  <span class="icon"><i class="fa-solid fa-cookie" /></span>
                  <span>Cookies - <NuxtLink @click="cookiesDropzoneRef?.triggerFileSelect()">Upload file</NuxtLink>
                  </span>
                </label>
                <TextDropzone ref="cookiesDropzoneRef" id="ytdlpCookies" v-model="form.cookies"
                  :disabled="!socket.isConnected || addInProgress" @error="(msg: string) => toast.error(msg)"
                  :placeholder="getDefault('cookies', 'Leave empty to use default cookies. Or drag & drop a cookie file here.')" />
                <span class="help is-bold">
                  <span class="icon"><i class="fa-solid fa-info" /></span>
                  <span>Use the <NuxtLink target="_blank"
                      to="https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp">
                      Recommended addon</NuxtLink> by yt-dlp to export cookies. <span class="has-text-danger">The
                      cookies MUST be in Netscape HTTP Cookie format.</span>
                  </span>
                </span>
              </div>
            </div>
            <template v-if="config.dl_fields.length > 0">
              <div class="column is-6-tablet is-12-mobile" v-for="(fi, index) in sortedDLFields"
                :key="fi.id || `dlf-${index}`">
                <DLInput :id="fi?.id || `dlf-${index}`" :type="fi.kind" :description="fi.description" :label="fi.name"
                  :icon="fi.icon" v-model="dlFields[fi.field]" :field="fi.field"
                  :disabled="!socket.isConnected || addInProgress" />
              </div>
            </template>
            <div class="column is-12 is-hidden-tablet">
              <Dropdown icons="fa-solid fa-cogs" label="Actions">
                <NuxtLink class="dropdown-item" @click="() => showFields = true">
                  <span class="icon has-text-purple"><i class="fa-solid fa-plus" /></span>
                  <span>Custom Fields</span>
                </NuxtLink>
                <hr class="dropdown-divider" />

                <NuxtLink class="dropdown-item" @click="emitter('getInfo', form.url, form.preset, form.cli)">
                  <span class="icon has-text-info"><i class="fa-solid fa-info" /></span>
                  <span>yt-dlp Information</span>
                </NuxtLink>

                <hr class="dropdown-divider" v-if="config.app.console_enabled" />
                <NuxtLink class="dropdown-item" @click="runCliCommand" v-if="config.app.console_enabled">
                  <span class="icon has-text-warning"><i class="fa-solid fa-terminal" /></span>
                  <span>Run CLI</span>
                </NuxtLink>

                <NuxtLink class="dropdown-item" @click="testDownloadOptions" v-if="config.app.console_enabled">
                  <span class="icon has-text-success"><i class="fa-solid fa-flask" /></span>
                  <span>Show compiled yt-dlp options</span>
                </NuxtLink>

                <hr class="dropdown-divider" />
                <NuxtLink class="dropdown-item" @click="resetConfig">
                  <span class="icon has-text-danger"><i class="fa-solid fa-rotate-left" /></span>
                  <span>Reset local settings</span>
                </NuxtLink>
              </Dropdown>
            </div>
            <div class="column is-12">
              <div class="field is-grouped is-justify-self-end is-hidden-mobile">
                <div class="control">
                  <button type="button" class="button is-purple" @click="() => showFields = true"
                    :disabled="!socket.isConnected" v-tooltip="'Manage custom fields'">
                    <span class="icon"><i class="fa-solid fa-plus" /></span>
                  </button>
                </div>

                <div class="control" v-if="config.app.console_enabled" v-tooltip="'Run directly in console'">
                  <button type="button" class="button is-warning" @click="runCliCommand"
                    :disabled="!socket.isConnected || !hasValidUrl">
                    <span class="icon"><i class="fa-solid fa-terminal" /></span>
                  </button>
                </div>

                <div class="control">
                  <button type="button" class="button is-info"
                    v-tooltip="'Get yt-dlp information for the provided URL.'"
                    @click="emitter('getInfo', splitUrls(form.url || '')[0] || '', form.preset, form.cli)"
                    :disabled="!socket.isConnected || addInProgress || !hasValidUrl">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                  </button>
                </div>

                <div class="control" v-if="config.app.console_enabled">
                  <button type="button" class="button is-success" @click="testDownloadOptions"
                    :disabled="!socket.isConnected || !hasValidUrl" v-tooltip="'Show compiled yt-dlp options.'">
                    <span class="icon"><i class="fa-solid fa-flask" /></span>
                  </button>
                </div>

                <div class="control">
                  <button type="button" class="button is-danger" @click="resetConfig"
                    :disabled="!!(!socket.isConnected || form?.id)" v-tooltip="'Reset local settings'">
                    <span class="icon"><i class="fa-solid fa-rotate-left" /></span>
                  </button>
                </div>

              </div>
            </div>
          </div>
        </div>
      </form>
    </div>
    <datalist id="folders" v-if="config?.folders">
      <option v-for="dir in config.folders" :key="dir" :value="dir" />
    </datalist>

    <DLFields v-if="showFields" @cancel="() => showFields = false" />
    <Modal v-if="showOptions" @close="showOptions = false" :contentClass="'modal-content-max'">
      <YTDLPOptions />
    </Modal>

    <ModalText v-if="showTestResults" @closeModel="CloseTestResults" :data="testResultsData" />
  </main>
</template>

<script setup lang="ts">
import 'assets/css/bulma-switch.css'
import { useStorage } from '@vueuse/core'
import TextareaAutocomplete from '~/components/TextareaAutocomplete.vue'
import TextDropzone from '~/components/TextDropzone.vue'
import type { item_request } from '~/types/item'
import type { AutoCompleteOptions } from '~/types/autocomplete'
import { navigateTo } from '#app'
import { useDialog } from '~/composables/useDialog'

const props = defineProps<{ item?: Partial<item_request> }>()
const emitter = defineEmits<{
  (e: 'getInfo', url: string, preset: string | undefined, cli: string | undefined): void
  (e: 'clear_form'): void
}>()
const config = useConfigStore()
const socket = useSocketStore()
const toast = useNotification()
const dialog = useDialog()

const showAdvanced = useStorage<boolean>('show_advanced', false)
const separator = useStorage<string>('url_separator', separators[0]?.value ?? ',')
const auto_start = useStorage<boolean>('auto_start', true)
const show_description = useStorage<boolean>('show_description', true)
const dlFields = useStorage<Record<string, any>>('dl_fields', {})
const storedCommand = useStorage<string>('console_command', '')

const addInProgress = ref<boolean>(false)
const showFields = ref<boolean>(false)
const showOptions = ref<boolean>(false)
const showTestResults = ref<boolean>(false)
const testResultsData = ref<any>(null)
const dlFieldsExtra = ['--no-download-archive', '--no-continue']
const ytDlpOpt = ref<AutoCompleteOptions>([])
const cookiesDropzoneRef = ref<InstanceType<typeof TextDropzone> | null>(null)
const urlTextarea = ref<HTMLTextAreaElement | null>(null)

const form = useStorage<item_request>('local_config_v1', {
  id: null,
  url: '',
  preset: config.app.default_preset,
  cookies: '',
  cli: '',
  template: '',
  folder: '',
  extras: {},
}) as Ref<item_request>


const is_valid_dl_field = (dl_field: string): boolean => {
  if (dlFieldsExtra.includes(dl_field)) {
    return true
  }

  if (config.dl_fields && config.dl_fields.length > 0) {
    return config.dl_fields.some(f => f.field === dl_field)
  }

  return false;
}

const adjustTextareaHeight = async (): Promise<void> => {
  await nextTick()
  if (urlTextarea.value) {
    urlTextarea.value.style.height = 'auto'
    const newHeight = Math.min(urlTextarea.value.scrollHeight, 300)
    urlTextarea.value.style.height = `${newHeight}px`
  }
}

const handleKeyDown = async (event: KeyboardEvent): Promise<void> => {
  const target = event.target as HTMLInputElement | HTMLTextAreaElement
  const isTextarea = target.tagName === 'TEXTAREA'
  if (event.key !== 'Enter') {
    return
  }

  if (event.ctrlKey && isTextarea && !hasValidUrl.value) {
    event.preventDefault()
    addDownload()
    return
  }

  if (event.shiftKey && !isTextarea) {
    event.preventDefault()
    const cursorPos = target.selectionStart || form.value.url.length
    form.value.url = form.value.url.substring(0, cursorPos) + '\n' + form.value.url.substring(target.selectionEnd || cursorPos)

    await nextTick()

    if (urlTextarea.value) {
      await adjustTextareaHeight()
      urlTextarea.value.setSelectionRange(cursorPos + 1, cursorPos + 1)
      urlTextarea.value.focus()
    }
  }
}

const handlePaste = async (event: ClipboardEvent): Promise<void> => {
  const pastedText = event.clipboardData?.getData('text') || ''
  if (!pastedText.includes('\n')) {
    return
  }

  event.preventDefault()

  const target = event.target as HTMLInputElement
  const currentValue = form.value.url || ''
  const start = target.selectionStart || currentValue.length
  const end = target.selectionEnd || currentValue.length
  form.value.url = currentValue.substring(0, start) + pastedText + currentValue.substring(end)

  await nextTick()

  if (urlTextarea.value) {
    await adjustTextareaHeight()
    const newPos = start + pastedText.length
    urlTextarea.value.setSelectionRange(newPos, newPos)
    urlTextarea.value.focus()
  }
}

const splitUrls = (urlString: string): Array<string> => {
  const lines = urlString.split('\n')
  const urls: string[] = []

  lines.forEach(line => line.split(separator.value).forEach(url => {
    const trimmed = url.trim()
    if (trimmed) {
      urls.push(trimmed)
    }
  }))

  return urls
}

const addDownload = async () => {
  if (' ' === form.value?.folder) {
    toast.warning('The download folder contain only spaces. Resetting to default.')
    form.value.folder = ''
    await nextTick()
  }

  if (form.value.folder) {
    form.value.folder = form.value.folder.trim()
  }

  let form_cli = (form.value?.cli || '').trim()

  if (dlFields.value && Object.keys(dlFields.value).length > 0) {
    const joined = []
    for (const [key, value] of Object.entries(dlFields.value)) {
      if (false === is_valid_dl_field(key)) {
        continue
      }

      if ([undefined, null, '', false].includes(value as any)) {
        continue
      }

      const keyRegex = new RegExp(`(^|\\s)${key}(\\s|$)`);
      if (form_cli && keyRegex.test(form_cli)) {
        continue;
      }

      joined.push(true === value ? `${key}` : `${key} ${value}`)
    }

    if (joined.length > 0) {
      form_cli = form_cli ? `${form_cli} ${joined.join(' ')}` : joined.join(' ')
    }

  }

  if (form_cli && form_cli.trim()) {
    const options = await convertOptions(form_cli)
    if (null === options) {
      return
    }
  }

  const request_data = [] as Array<item_request>

  splitUrls(form.value.url).forEach(async (url: string) => {
    const data = {
      url: url,
      preset: form.value.preset || config.app.default_preset,
      folder: form.value.folder,
      template: form.value.template,
      cookies: form.value.cookies,
      cli: form_cli,
      auto_start: auto_start.value
    } as item_request

    if (form.value?.extras && Object.keys(form.value.extras).length > 0) {
      data.extras = form.value.extras
    }

    request_data.push(data)
  })

  try {
    addInProgress.value = true
    const response = await request('/api/history', {
      method: 'POST',
      body: JSON.stringify(request_data),
    })

    const data = await response.json()
    if (!response.ok) {
      toast.error(`Error: ${data.error || 'Failed to add download.'}`)
      return
    }

    let had_errors = false

    data.forEach((item: Record<string, any>) => {
      if (false !== item.status) {
        return
      }

      had_errors = true

      if (item?.hidden) {
        return
      }

      toast.error(`Error: ${item.msg || 'Failed to add download.'}`)
    })

    if (false === had_errors) {
      form.value.url = ''
      emitter('clear_form')
    }
  }
  catch (e: any) {
    console.error(e)
    toast.error(`Error: ${e.message}`)
  } finally {
    addInProgress.value = false
  }
}

const resetConfig = async () => {
  const { status } = await dialog.confirmDialog({
    title: 'Confirm Action',
    message: `Reset local configuration?`,
    confirmColor: 'is-danger',
  })
  if (!status) {
    return
  }

  form.value = {
    url: '',
    preset: config.app.default_preset,
    cookies: '',
    cli: '',
    template: '',
    folder: '',
    extras: {},
  } as item_request
  dlFields.value = {}
  showAdvanced.value = false
  toast.success('Local configuration has been reset.')
}

const convertOptions = async (args: string) => {
  try {
    const response = await convertCliOptions(args)

    if (response.output_template) {
      form.value.template = response.output_template
    }

    if (response.download_path) {
      form.value.folder = response.download_path
    }

    return response.opts
  } catch (e: any) {
    toast.error(e.message)
  }

  return null;
}

onUpdated(async () => {
  await nextTick()

  if ('' === form.value?.preset) {
    form.value.preset = config.app.default_preset
  }

  if (config.isLoaded() && form.value?.preset && !config.presets.some(p => p.name === form.value.preset)) {
    form.value.preset = config.app.default_preset
  }
})

watch(() => config.ytdlp_options, newOptions => ytDlpOpt.value = newOptions
  .filter(opt => !opt.ignored)
  .flatMap(opt => opt.flags
    .filter(flag => flag.startsWith('--'))
    .map(flag => ({ value: flag, description: opt.description || '' }))),
  { immediate: true }
)

onMounted(async () => {
  await nextTick()

  if ('' === form.value?.preset) {
    form.value.preset = config.app.default_preset
  }

  if (' ' === form.value?.folder) {
    toast.warning('The download folder contain only spaces. Resetting to default.')
    form.value.folder = ''
    await nextTick()
  }

  if (form.value.folder) {
    form.value.folder = form.value.folder.trim()
  }

  if (config.isLoaded() && form.value?.preset && !config.presets.some(p => p.name === form.value.preset)) {
    form.value.preset = config.app.default_preset
  }

  if (props?.item) {
    const updates: Partial<item_request> = {}
    const keys = Object.keys(props.item) as (keyof item_request)[]
    for (const key of keys) {
      const value = props.item[key]
      updates[key] = key === 'extras' ? JSON.parse(JSON.stringify(value)) : value!
    }
    form.value = { ...form.value, ...updates }
    emitter('clear_form')
  }

  await nextTick()

  if (!separators.some(s => s.value === separator.value)) {
    separator.value = separators[0]?.value ?? ','
  }

  if (isMultiLineInput.value && urlTextarea.value) {
    await adjustTextareaHeight()
  }
})

const runCliCommand = async (): Promise<void> => {
  if (!form.value.url) {
    toast.warning('Please enter a URL first')
    return
  }

  const { status } = await dialog.confirmDialog({
    title: 'Run CLI Command',
    message: `This will generate a yt-dlp command and run it in the console. Continue?`,
  })

  if (!status) {
    return
  }

  let form_cli = (form.value?.cli || '').trim()

  if (dlFields.value && Object.keys(dlFields.value).length > 0) {
    const joined = []
    for (const [key, value] of Object.entries(dlFields.value)) {
      if (false === is_valid_dl_field(key)) {
        continue
      }

      if ([undefined, null, '', false].includes(value as any)) {
        continue
      }

      const keyRegex = new RegExp(`(^|\\s)${key}(\\s|$)`);
      if (form_cli && keyRegex.test(form_cli)) {
        continue;
      }

      joined.push(true === value ? `${key}` : `${key} ${value}`)
    }

    if (joined.length > 0) {
      form_cli = form_cli ? `${form_cli} ${joined.join(' ')}` : joined.join(' ')
    }
  }

  if (form_cli && form_cli.trim()) {
    const options = await convertOptions(form_cli)
    if (null === options) {
      return
    }
  }

  try {
    const resp = await request('/api/yt-dlp/command', {
      method: 'POST',
      body: JSON.stringify({
        url: splitUrls(form.value.url).join(' '),
        preset: form.value.preset,
        folder: form.value.folder,
        cookies: form.value.cookies,
        template: form.value.template,
        cli: form_cli,
      })
    })

    const json = await resp.json() as { command?: string; error?: string }

    if (!resp.ok) {
      toast.error(`Error: ${json.error || 'Failed to generate command.'}`)
      return
    }

    storedCommand.value = json.command

    await nextTick()
    await navigateTo('/console')
  } catch (error) {
    toast.error(error instanceof Error ? error.message : 'Failed to create and navigate to command')
  }
}

const testDownloadOptions = async (): Promise<void> => {
  if (!form.value.url) {
    toast.warning('Please enter a URL first')
    return
  }

  let form_cli = (form.value?.cli || '').trim()
  if (' ' === form.value?.folder) {
    form.value.folder = ''
  }

  if (dlFields.value && Object.keys(dlFields.value).length > 0) {
    const joined = []
    for (const [key, value] of Object.entries(dlFields.value)) {
      if (false === is_valid_dl_field(key)) {
        continue
      }

      if ([undefined, null, '', false].includes(value as any)) {
        continue
      }

      const keyRegex = new RegExp(`(^|\\s)${key}(\\s|$)`);
      if (form_cli && keyRegex.test(form_cli)) {
        continue;
      }

      joined.push(true === value ? `${key}` : `${key} ${value}`)
    }

    if (joined.length > 0) {
      form_cli = form_cli ? `${form_cli} ${joined.join(' ')}` : joined.join(' ')
    }
  }

  try {
    const resp = await request('/api/yt-dlp/command?full=true', {
      method: 'POST',
      body: JSON.stringify({
        url: form.value.url,
        preset: form.value.preset,
        folder: form.value.folder,
        cookies: form.value.cookies,
        template: form.value.template,
        cli: form_cli,
      })
    })

    const json = await resp.json()

    if (!resp.ok) {
      toast.error(`Error: ${json.error || 'Failed to generate command.'}`)
      return
    }

    testResultsData.value = {
      command: json.command,
      yt_dlp: json.ytdlp,
    }
    showTestResults.value = true
  } catch (error) {
    toast.error(error instanceof Error ? error.message : 'Failed to test download options')
  }
}

const CloseTestResults = () => {
  showTestResults.value = false
  testResultsData.value = null
}

const isMultiLineInput = computed(() => !!form.value.url && form.value.url.includes('\n'))
const hasFormatInConfig = computed((): boolean => !!form.value.cli?.match(/(?<!\S)(-f|--format)(=|\s)(\S+)/))

const filter_presets = (flag: boolean = true) => config.presets.filter(item => item.default === flag)
const get_preset = (name: string | undefined) => config.presets.find(item => item.name === name)
const expand_description = (e: Event) => toggleClass(e.target as HTMLElement, ['is-ellipsis', 'is-pre-wrap'])

const getDefault = (type: 'cookies' | 'cli' | 'template' | 'folder', ret: string = '') => {
  if (false !== hasFormatInConfig.value || !form.value.preset) {
    return ret
  }

  const preset = config.presets.find(p => p.name === form.value.preset)

  if (!preset) {
    return ret
  }

  if (type === 'cookies' && preset.cookies) {
    return preset.cookies
  }

  if (type === 'cli' && preset.cli) {
    return preset.cli
  }

  if (type === 'template' && preset.template) {
    return preset.template
  }

  if (type === 'folder' && preset.folder) {
    return preset.folder.replace(config.app.download_path, '') || ret
  }

  return ret
}

const sortedDLFields = computed(() => [...config.dl_fields].sort((a, b) => (a.order || 0) - (b.order || 0)))
const hasValidUrl = computed(() => form.value.url && form.value.url.trim().length > 0)

watch(isMultiLineInput, async newValue => {
  await nextTick()
  if (newValue) {
    await adjustTextareaHeight()
    urlTextarea.value?.focus()
    return
  }
  const inputElement = document.getElementById('url') as HTMLInputElement
  inputElement?.focus()
})
</script>
