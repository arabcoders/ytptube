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
          <i class="fas fa-circle-notch fa-spin"></i>
        </div>
        <div v-else>
          <div class="content p-0 m-0" style="position: relative">
            <pre><code class="p-4 is-block" v-text="data" />
              <button class="button m-4" @click="() => copyText(JSON.stringify(data, null, 4))"
                style="position: absolute; top:0; right:0;">
                <span class="icon"><i class="fas fa-copy"></i></span>
              </button>
            </pre>
          </div>
        </div>
      </div>
      <button class="modal-close is-large" aria-label="close" @click="emitter('closeModel')"></button>
    </div>
    <div class="modal-content-max" style="height: 80vh;" v-else>
      <div class="content p-0 m-0" style="position: relative">
        <pre><code class="p-4 is-block" v-text="data" /></pre>
        <button class="button m-4" @click="() => copyText(JSON.stringify(data, null, 4))"
          style="position: absolute; top:0; right:0;">
          <span class="icon"><i class="fas fa-copy"></i></span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { disableOpacity, enableOpacity } from '~/utils';

const toast = useNotification()
const emitter = defineEmits<{ (e: 'closeModel'): void }>()

const props = defineProps<{
  link?: string
  preset?: string
  cli?: string
  useUrl?: boolean
  externalModel?: boolean
}>()

const isLoading = ref<boolean>(false)
const data = ref<any>({})

const handle_event = (e: KeyboardEvent): void => {
  if (e.key === 'Escape') {
    emitter('closeModel')
  }
}

onMounted(async (): Promise<void> => {
  disableOpacity()
  document.addEventListener('keydown', handle_event)

  let url = props.useUrl ? props.link || '' : '/api/yt-dlp/url/info'

  if (!props.useUrl) {
    const params = new URLSearchParams()
    if (props.preset) {
      params.append('preset', props.preset)
    }
    if (props.cli) {
      params.append('args', props.cli)
    }
    params.append('url', props.link || '')
    url += '?' + params.toString()
  }

  try {
    isLoading.value = true
    const response = await request(url)
    const body = await response.text()

    try {
      data.value = JSON.parse(body)
    } catch {
      data.value = body
    }
  } catch (e: any) {
    console.error(e)
    toast.error(`Error: ${e.message}`)
  } finally {
    isLoading.value = false
  }
})

onBeforeUnmount(() => {
  enableOpacity()
  document.removeEventListener('keydown', handle_event)
})
</script>
