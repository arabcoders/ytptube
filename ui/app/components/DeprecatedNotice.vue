<template>
  <Message :message_class="messageClass" :title="title" :icon="icon" :useClose="true" @close="() => dismissed = true"
    v-if="!isDismissed">
    <slot />
  </Message>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useStorage } from '@vueuse/core'
import Message from "~/components/Message.vue";

const props = withDefaults(defineProps<{
  version: string
  storageKey?: string
  title?: string
  icon?: string
  tone?: 'warning' | 'danger' | 'info' | 'success'
}>(), {
  storageKey: 'deprecated-notice',
  title: 'Deprecated Feature',
  icon: 'fas fa-exclamation-triangle',
  tone: 'warning',
})

const config = useConfigStore()
const isDev = computed(() => 'development' === config.app?.app_env)

const storageKeyComputed = computed<string>(() => `${props.storageKey}:${props.version}`)
const dismissed = useStorage<boolean>(storageKeyComputed, false)
const isDismissed = computed(() => dismissed.value)

const messageClass = computed(() => {
  switch (props.tone) {
    case 'danger':
      return 'is-danger has-background-danger-90 has-text-dark'
    case 'info':
      return 'is-info has-background-info-90 has-text-dark'
    case 'success':
      return 'is-success has-background-success-90 has-text-dark'
    case 'warning':
    default:
      return 'is-warning has-background-warning-90 has-text-dark'
  }
})

onMounted(() => {
  if (!isDev.value) {
    return
  }
  document.addEventListener('keydown', handle_event)
})

onBeforeUnmount(() => {
  if (!isDev.value) {
    return
  }
  document.removeEventListener('keydown', handle_event)
})

const handle_event = (e: KeyboardEvent) => {
  if (e.ctrlKey && e.altKey && 'd' === e.key.toLowerCase()) {
    e.preventDefault()
    dismissed.value = !dismissed.value
  }
}
</script>
