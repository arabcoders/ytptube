<template>
  <div>
    <div class="modal is-active" v-if="false === externalModel">
      <div class="modal-background" @click="emitter('closeModel')"></div>
      <div class="modal-content" style="width:60vw;">
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
    <div style="width:70vw; height: 80vh;" v-else>
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

<style scoped>
code {
  color: var(--bulma-code) !important
}
</style>
<script setup lang="ts">
import { request } from '~/utils/index'

const toast = useNotification()

const emitter = defineEmits(['closeModel'])
const isLoading = ref<Boolean>(false)
const data = ref<any>({})

const props = defineProps({
  link: {
    type: String,
    default: '',
    required: false,
  },
  useUrl: {
    type: Boolean,
    default: false,
    required: false,
  },
  externalModel: {
    type: Boolean,
    default: false,
    required: false,
  },
})

const handle_event = (e: KeyboardEvent) => {
  if (e.key !== 'Escape') {
    return
  }
  emitter('closeModel')
}

onMounted(async () => {
  document.addEventListener('keydown', handle_event)

  const url = props.useUrl ? props.link : '/api/yt-dlp/url/info?url=' + encodePath(props.link)

  try {
    isLoading.value = true
    const response = await request(url, { credentials: 'include' })
    const body = await response.text()

    try {
      data.value = JSON.parse(body)
    } catch (e) {
      data.value = body
    }

  } catch (e: any) {
    console.error(e)
    toast.error(`Error: ${e.message}`)
  } finally {
    isLoading.value = false
  }
})

onBeforeUnmount(() => document.removeEventListener('keydown', handle_event))
</script>
