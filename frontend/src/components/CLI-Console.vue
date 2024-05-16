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
      <form @submit.prevent="$emit('runCommand', command)">
        <div class="field">
          <div class="field-body">
            <div class="field is-grouped">
              <p class="control is-expanded has-icons-left">
                <input type="text" class="input" v-model="command" placeholder="--help" autocomplete="off" autofocus
                  :disabled="props.isLoading">
                <span class="icon is-left">
                  <font-awesome-icon icon="fa-solid fa-terminal" />
                </span>
              </p>
              <p class="control">
                <button class="button is-primary" type="submit" :disabled="props.isLoading"
                  :class="{ 'is-loading': props.isLoading }">
                  <span class="icon-text">
                    <span class="icon"><font-awesome-icon icon="fa-solid fa-server" /></span>
                    <span>Run</span>
                  </span>
                </button>
              </p>
              <p class="control">
                <button class="button is-info" type="button" v-tooltip="'Clear output'" @click="$emit('cli_clear')">
                  <span class="icon-text">
                    <span class="icon"><font-awesome-icon icon="fa-solid fa-broom" /></span>
                    <span>Clear</span>
                  </span>
                </button>
              </p>
            </div>
          </div>
        </div>
      </form>
    </div>
    <div class="column is-12">
      <pre ref="outputConsole"
        style="min-height: 60vh;max-height:65vh; overflow-y: scroll"><code><div v-for="(item, index) in props.cli_output" :key="'log_line-' + index" :class="{ 'has-text-danger': 'stderr' === item.type }">{{ item.line }}</div></code></pre>
    </div>
  </div>
</template>

<script setup>
import { defineEmits, defineProps, ref } from 'vue'

const props = defineProps({
  cli_output: {
    type: Array,
    default: () => []
  },
  isLoading: {
    type: Boolean,
    default: false
  }
});

defineEmits(['runCommand','cli_clear']);

const command = ref('')
</script>
