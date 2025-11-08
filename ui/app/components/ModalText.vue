<style scoped>
code {
  color: var(--bulma-code) !important
}
</style>

<template>
  <div>
    <div class="modal is-active" v-if="false === externalModel">
      <div class="modal-background" @click="emitter('closeModel')"></div>
      <div class="modal-content modal-content-max">
        <div style="font-size:30vh; width: 99%" class="has-text-centered" v-if="isLoading">
          <i class="fas fa-circle-notch fa-spin" />
        </div>
        <div v-else>
          <div class="content p-0 m-0" style="position: relative">
            <pre :class="[code_classes, custom_classes]"><code class="p-4 is-block" v-text="data" />
              <div class="m-4 is-flex" style="position: absolute; top:0; right:0;">
                  <button class="button is-small is-purple mr-3" @click="() => toggleClass('is-pre-wrap-force')">
                    <span class="icon"><i class="fas fa-text-width" /></span>
                  </button>
                  <button class="button is-info is-small" @click="() => copyText(JSON.stringify(data, null, 2))" >
                    <span class="icon"><i class="fas fa-copy" /></span>
                  </button>
              </div>
            </pre>
          </div>
        </div>
      </div>
      <button class="modal-close is-large" aria-label="close" @click="emitter('closeModel')"></button>
    </div>
    <div class="modal-content-max" style="height: 80vh;" v-else>
      <div class="content p-0 m-0" style="position: relative">
        <pre :class="[code_classes, custom_classes]"><code class="p-4 is-block" v-text="data" /></pre>
        <div class="m-4 is-flex" style="position: absolute; top:0; right:0;">
          <button class="button is-small is-purple mr-3" @click="() => toggleClass('is-pre-wrap-force')">
            <span class="icon"><i class="fas fa-text-width" /></span>
          </button>
          <button class="button is-info is-small" @click="() => copyText(JSON.stringify(data, null, 2))">
            <span class="icon"><i class="fas fa-copy" /></span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useStorage } from '@vueuse/core'
import { disableOpacity, enableOpacity } from '~/utils';

const emitter = defineEmits<{ (e: 'closeModel'): void }>()

withDefaults(defineProps<{ externalModel?: boolean, data: any, code_classes?: string, isLoading?: boolean }>(), {
  code_classes: '',
  isLoading: false,
  externalModel: false,
})

const custom_classes = useStorage<string>('modal_text_classes', '')

const handle_event = (e: KeyboardEvent): void => {
  if (e.key === 'Escape') {
    emitter('closeModel')
  }
}

onMounted(async (): Promise<void> => {
  disableOpacity()
  document.addEventListener('keydown', handle_event)
})

onBeforeUnmount(() => {
  enableOpacity()
  document.removeEventListener('keydown', handle_event)
})

const toggleClass = (className: string) => {
  if (custom_classes.value.includes(className)) {
    custom_classes.value = custom_classes.value.replace(className, '').trim()
  } else {
    custom_classes.value += ` ${className}`
  }
}
</script>
