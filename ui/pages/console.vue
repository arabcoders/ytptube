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
        You can use this console window to execute non-interactive commands. The interface is jailed to the
        <code>yt-dlp</code>
      </div>
    </div>
    <div class="column is-12">
      <div class="card">
        <header class="card-header">
          <p class="card-header-title">
            <span class="icon"><i class="fa-solid fa-terminal" /></span> Console Output
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
              <input type="text" class="input" v-model="command" placeholder="--help" autocomplete="off"
                ref="command_input" @keydown.enter="runCommand" :disabled="isLoading" id="command">
            </div>
            <p class="control">
              <button class="button is-primary" type="button" :disabled="isLoading || '' === command"
                @click="runCommand">
                <span class="icon">
                  <i class="fa-solid fa-spinner" spin v-if="isLoading" />
                  <i class="fa-solid fa-paper-plane" v-else />
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
import "@xterm/xterm/css/xterm.css"
import { Terminal } from "@xterm/xterm"
import { FitAddon } from "@xterm/addon-fit"
import { useStorage } from '@vueuse/core'

const config = useConfigStore()
const socket = useSocketStore()
const toast = useNotification()

const bg_enable = useStorage<boolean>('random_bg', true)
const bg_opacity = useStorage<number>('random_bg_opacity', 0.95)

const terminal = ref<Terminal>()
const terminalFit = ref<FitAddon>()
const command = ref<string>('')
const terminal_window = useTemplateRef<HTMLDivElement>('terminal_window')
const command_input = useTemplateRef<HTMLInputElement>('command_input')
const isLoading = ref<boolean>(false)

watch(() => isLoading.value, async value => {
  if (value) {
    return
  }
  command.value = ''
  await nextTick();
  focusInput()
}, { immediate: true })

watch(() => config.app.basic_mode, async () => {
  if (!config.app.basic_mode) {
    return
  }
  await navigateTo('/')
}, { immediate: true })

watch(() => config.app.console_enabled, async () => {
  if (config.app.console_enabled) {
    return
  }
  toast.error('Console is disabled in the configuration. Please enable it to use this feature.')
  await navigateTo('/')
}, { immediate: true })

const handle_event = () => {
  if (!terminal.value) {
    return
  }
  terminalFit.value?.fit()
}

const runCommand = async () => {
  if ('' === command.value) {
    return
  }

  if (command.value.startsWith('yt-dlp')) {
    command.value = command.value.replace(/^yt-dlp/, '').trim()
    await nextTick()
    if ('' === command.value) {
      return
    }
  }

  if (!terminal.value) {
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
    if (terminal_window.value) {
      terminal.value.open(terminal_window.value)
    }
    terminalFit.value.fit();
  }

  if ('clear' === command.value) {
    clearOutput(true)
    return
  }

  socket.emit('cli_post', command.value)
  isLoading.value = true
  terminal.value.writeln(`user@YTPTube ~`)
  terminal.value.writeln(`$ yt-dlp ${command.value}`)
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

const focusInput = () => {
  if (!command_input.value) {
    return
  }
  command_input.value.focus()
}

const writer = (s: string) => {
  if (!terminal.value) {
    return
  }

  const data = JSON.parse(s)

  terminal.value.writeln(data.line)
}

const loader = () => isLoading.value = false

watch(() => config.app.basic_mode, async () => {
  if (!config.app.basic_mode) {
    return
  }
  await navigateTo('/')
})

onMounted(async () => {
  document.addEventListener('resize', handle_event);
  focusInput()
  socket.off('cli_close', loader)
  socket.off('cli_output', writer)
  socket.on('cli_close', loader)
  socket.on('cli_output', writer)
  if (bg_enable.value) {
    document.querySelector('body')?.setAttribute("style", `opacity: 1.0`)
  }
})

onBeforeUnmount(() => {
  socket.off('cli_close', loader)
  socket.off('cli_output', writer)
  document.removeEventListener('resize', handle_event)
  if (bg_enable.value) {
    document.querySelector('body')?.setAttribute("style", `opacity: ${bg_opacity.value}`)
  }
});
</script>
