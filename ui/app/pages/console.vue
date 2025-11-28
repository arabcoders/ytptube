<style>
.terminal {
  padding-left: 10px;
}
</style>

<template>
  <div class="mt-1 columns is-multiline">
    <div class="column is-12 is-clearfix">
      <h1 class="title is-4">
        <span class="icon-text">
          <span class="icon"><i class="fa-solid fa-terminal" /></span>
          <span>Console</span>
        </span>
      </h1>
      <div class="subtitle is-6 is-unselectable">
        You can use this page to run yt-dlp commands directly in a non-interactive way, bypassing the web interface and
        it's settings.
      </div>
    </div>
    <div class="column is-12">
      <div class="card">
        <header class="card-header">
          <p class="card-header-title">
            <span class="icon">
              <i class="fa-solid fa-desktop" />
            </span>
            <span class="ml-2">Output</span>
          </p>
          <p class="card-header-icon">
            <span v-tooltip.top="'Clear console window'" class="icon" @click="clearOutput()">
              <i class="fa-solid fa-broom" />
            </span>
          </p>
        </header>
        <section class="card-content p-0 m-0">
          <div ref="terminal_window" style="min-height: 60vh;max-height:70vh;" />
        </section>
        <section class="card-content p-1 m-1">
          <div class="field is-grouped">
            <div class="control is-expanded">
              <TextareaAutocomplete v-if="isMultiLineInput" ref="commandTextarea" v-model="command"
                :options="ytDlpOptions" :disabled="isLoading" placeholder="--help" @keydown="handleKeyDown" />
              <InputAutocomplete v-else v-model="command" ref="commandInput" :options="ytDlpOptions"
                :disabled="isLoading" placeholder="--help" @keydown="handleKeyDown" @paste="handlePaste"
                :multiple="true" :allowShortFlags="true" />
            </div>
            <p class="control">
              <button class="button is-primary" type="button" :disabled="isLoading || !hasValidCommand"
                @click="runCommand">
                <span class="icon">
                  <i class="fa-solid" :class="isLoading ? 'fa-spinner fa-spin' : 'fa-paper-plane'"/>
                </span>
              </button>
            </p>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@xterm/xterm/css/xterm.css'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { useStorage } from '@vueuse/core'
import { disableOpacity, enableOpacity } from '~/utils'
import InputAutocomplete from '~/components/InputAutocomplete.vue'
import TextareaAutocomplete from '~/components/TextareaAutocomplete.vue'
import type { AutoCompleteOptions } from '~/types/autocomplete'

const config = useConfigStore()
const socket = useSocketStore()
const toast = useNotification()

const terminal = ref<Terminal>()
const terminalFit = ref<FitAddon>()
const command = ref<string>('')
const terminal_window = useTemplateRef<HTMLDivElement>('terminal_window')
const commandInput = ref<InstanceType<typeof InputAutocomplete> | null>(null)
const commandTextarea = ref<InstanceType<typeof TextareaAutocomplete> | null>(null)
const isLoading = ref<boolean>(false)
const storedCommand = useStorage<string>('console_command', '')

const ytDlpOptions = computed<AutoCompleteOptions>(() => config.ytdlp_options.flatMap(opt => opt.flags
  .map(flag => ({ value: flag, description: opt.description || '' }))
))

const hasValidCommand = computed(() => command.value && command.value.trim().length > 0)
const isMultiLineInput = computed(() => !!command.value && command.value.includes('\n'))

watch(() => isLoading.value, async value => {
  if (value) {
    return
  }
  command.value = ''
  await nextTick();
  focusInput()
}, { immediate: true })

watch(() => config.app.console_enabled, async () => {
  if (config.app.console_enabled) {
    return
  }
  toast.error('Console is disabled in the configuration. Please enable it to use this feature.')
  await navigateTo('/')
})

const handleKeyDown = async (event: KeyboardEvent): Promise<void> => {
  const target = event.target as HTMLInputElement | HTMLTextAreaElement
  const isTextarea = 'TEXTAREA' === target.tagName

  if (event.key !== 'Enter') {
    return
  }

  if (((event.ctrlKey && isTextarea) || !isTextarea) && hasValidCommand.value) {
    event.preventDefault()
    runCommand()
    return
  }

  if (event.shiftKey && !isTextarea) {
    event.preventDefault()
    const cursorPos = target.selectionStart || command.value.length
    command.value = command.value.substring(0, cursorPos) + '\n' + command.value.substring(target.selectionEnd || cursorPos)
    await nextTick()
    if (commandTextarea.value) {
      const textarea = commandTextarea.value.$el?.querySelector('textarea') as HTMLTextAreaElement
      if (textarea) {
        textarea.setSelectionRange(cursorPos + 1, cursorPos + 1)
        textarea.focus()
      }
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
  const currentValue = command.value || ''
  const start = target.selectionStart || currentValue.length
  const end = target.selectionEnd || currentValue.length
  command.value = currentValue.substring(0, start) + pastedText + currentValue.substring(end)
  await nextTick()

  if (!commandTextarea.value) {
    return
  }

  const textarea = commandTextarea.value.$el?.querySelector('textarea') as HTMLTextAreaElement
  if (textarea) {
    const newPos = start + pastedText.length
    textarea.setSelectionRange(newPos, newPos)
    textarea.focus()
  }
}

const handle_event = () => {
  if (!terminal.value) {
    return
  }
  terminalFit.value?.fit()
}

const ensureTerminal = async () => {
  if (terminal.value) {
    return
  }

  terminal.value = new Terminal({
    fontSize: 14,
    fontFamily: "'JetBrains Mono', monospace",
    cursorBlink: false,
    cursorStyle: 'underline',
    cols: 108,
    rows: 10,
    disableStdin: true,
    scrollback: 1000,
  })

  terminalFit.value = new FitAddon()
  terminal.value.loadAddon(terminalFit.value)

  await nextTick()

  if (terminal_window.value) {
    terminal.value.open(terminal_window.value)
  }

  terminalFit.value.fit();
}

const runCommand = async () => {
  if (!hasValidCommand.value) {
    return
  }

  if (true !== config.app.console_enabled) {
    await navigateTo('/')
    toast.error('Console is disabled in the configuration. Please enable it to use this feature.')
    return
  }

  let cmd = command.value.trim().replace(/\n/g, ' ').trim()

  if (cmd.startsWith('yt-dlp')) {
    cmd = cmd.replace(/^yt-dlp/, '').trim()
    await nextTick()
    if ('' === cmd) {
      return
    }
  }

  await ensureTerminal()

  if ('clear' === cmd) {
    clearOutput(true)
    return
  }

  socket.emit('cli_post', cmd)
  isLoading.value = true
  terminal.value?.writeln(`user@YTPTube ~`)
  terminal.value?.writeln(`$ yt-dlp ${command.value}`)
  storedCommand.value = ''
}

const clearOutput = async (withCommand: boolean = false) => {
  if (terminal.value) {
    terminal.value.clear()
  }

  if (true === withCommand) {
    command.value = ''
  }

  focusInput()
}

const focusInput = async () => {
  await nextTick()
  let elm;
  if (isMultiLineInput.value) {
    elm = commandTextarea.value?.$el?.querySelector('textarea') as HTMLTextAreaElement
  } else {
    elm = commandInput.value?.$el?.querySelector('input') as HTMLInputElement
  }

  elm?.focus()
}

const writer = (s: string) => {
  if (!terminal.value) {
    return
  }
  terminal.value.writeln(JSON.parse(s).data.line)
}

const loader = () => isLoading.value = false

watch(isMultiLineInput, () => focusInput())

onMounted(async () => {
  document.addEventListener('resize', handle_event);
  focusInput()
  socket.off('cli_close', loader)
  socket.off('cli_output', writer)
  socket.on('cli_close', loader)
  socket.on('cli_output', writer)

  disableOpacity()

  await ensureTerminal()

  if (storedCommand.value) {
    command.value = storedCommand.value
    await nextTick()
  }
})

onBeforeUnmount(() => {
  socket.off('cli_close', loader)
  socket.off('cli_output', writer)
  document.removeEventListener('resize', handle_event)
  enableOpacity()
});
</script>
