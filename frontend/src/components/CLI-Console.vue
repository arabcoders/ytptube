<template>
  <div class="mt-1 columns is-multiline">
    <div class="column is-12 is-clearfix">
      <h1 class="title is-4">Console</h1>
      <div class="subtitle is-6">
        You can execute <strong>non-interactive</strong> commands here. The interface jailed to the <code>yt-dlp</code>
        command.
      </div>
    </div>
    <div class="column is-12">

      <div class="card">
        <header class="card-header">
          <p class="card-header-title">
            <span class="icon"><font-awesome-icon icon="fa-solid fa-terminal" /></span> Terminal
          </p>
          <p class="card-header-icon">
            <span v-tooltip.top="'Clear console window'" class="icon" @click="clearOutput"><font-awesome-icon
                icon="fa-solid fa-broom" /></span>
          </p>
        </header>
        <section class="card-content p-0 m-0">
          <div ref="terminal_window" style="min-height: 60vh;max-height:70vh;" />
        </section>
        <section class="card-content p-1 m-1">
          <div class="field is-grouped">
            <div class="control">
              <span class="icon-text input is-unselectable">
                <span class="icon"><font-awesome-icon icon="fa-solid fa-terminal" /></span>
                <span>yt-dlp</span>
              </span>
            </div>
            <div class="control is-expanded">
              <input type="text" class="input" v-model="command" placeholder="ls -la" autocomplete="off"
                ref="command_input" @keydown.enter="runCommand" :disabled="props.isLoading" id="command">
            </div>
            <p class="control">
              <button class="button is-primary" type="button" :disabled="props.isLoading || '' === command"
                @click="runCommand">
                <span class="icon">
                  <font-awesome-icon icon="fa-solid fa-spinner" spin v-if="props.isLoading" />
                  <font-awesome-icon icon="fa-solid fa-paper-plane" v-else />
                </span>
              </button>
            </p>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, defineProps, onMounted, defineEmits, onUnmounted, nextTick } from 'vue'
import "@xterm/xterm/css/xterm.css"
import { Terminal } from "@xterm/xterm"
import { FitAddon } from "@xterm/addon-fit"

const emitter = defineEmits(['runCommand', 'cli_clear']);

const terminal = ref()
const terminalFit = ref()

const command = ref('')
const terminal_window = ref()
const command_input = ref()

const props = defineProps({
  isLoading: {
    type: Boolean,
    required: false,
    default: false
  },
  cli_output: {
    type: Array,
    required: false,
    default: () => []
  }
})

watch(() => props.isLoading, async value => {
  if (value) {
    return
  }
  command.value = ''
  await nextTick();
  focusInput()
}, { immediate: true })

watch(() => props.cli_output, v => {
  if (!terminal.value) {
    return
  }

  if (!v.length) {
    return
  }

  // -- display last output
  const data = v.slice(-1)
  terminal.value.writeln(data[0].line)

}, {
  deep: true
})

const reSizeTerminal = () => {
  if (!terminal.value) {
    return
  }
  terminalFit.value.fit()
}

const runCommand = async () => {
  if ('' === command.value) {
    return
  }

  if (!terminal.value) {
    terminal.value = new Terminal({
      fontSize: 14,
      fontFamily: "'JetBrains Mono', monospace",
      cursorBlink: false,
      cursorStyle: 'underline',
      cols: 108,
      rows: 10,
      buffer: 1000,
      disableStdin: true,
      scrollback: 1000,
    })
    terminalFit.value = new FitAddon()
    terminal.value.loadAddon(terminalFit.value)
    terminal.value.open(terminal_window.value)
    terminalFit.value.fit();
  }

  if ('clear' === command.value) {
    clearOutput(true)
    return
  }

  emitter('runCommand', command.value)
  terminal.value.writeln(`user@YTPTube ~`)
  terminal.value.writeln(`$ yt-dlp ${command.value}`)
}

const clearOutput = async (withCommand = false) => {
  if (terminal.value) {
    terminal.value.clear()
  }

  emitter('cli_clear', {})
  if (true === withCommand) {
    command.value = ''
  }
  focusInput()
}

onMounted(async () => {
  window.addEventListener('resize', reSizeTerminal);
  focusInput()
})


const focusInput = () => {
  if (!command_input.value) {
    return
  }
  command_input.value.focus()
}

onUnmounted(() => window.removeEventListener('resize', reSizeTerminal));
</script>
