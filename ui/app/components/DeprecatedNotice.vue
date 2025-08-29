<template>
  <div v-if="isLoaded && !isDismissed">
    <Message :message_class="messageClass" :title="title" :icon="icon" :useClose="true" @close="dismiss">
      <slot />
    </Message>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watchEffect } from 'vue'
import { useStorage, type RemovableRef } from '@vueuse/core'
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
const isLoaded = computed(() => config.is_loaded)

const storageKeyComputed = computed<string>(() => `${props.storageKey}:${props.version}`)

const dismissedDev = ref<boolean>(false)
let dismissedProd: RemovableRef<boolean> | null = null

watchEffect(() => {
  if (!isLoaded.value || isDev.value) {
    return
  }
  dismissedProd = useStorage<boolean>(storageKeyComputed, false)
})

const isDismissed = computed(() => {
  // include dependencies so recompute on env/load/version changes
  void isLoaded.value; void isDev.value; void storageKeyComputed.value
  return isDev.value ? dismissedDev.value : (dismissedProd?.value ?? false)
})

const dismiss = () => {
  if (isDev.value) dismissedDev.value = true
  else if (dismissedProd) dismissedProd.value = true
}

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
</script>
