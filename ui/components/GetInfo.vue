<template>
  <div>
    <div class="modal is-active">
      <div class="modal-background" @click="closeModal"></div>
      <div class="modal-content" style="width:60vw;">
        <div style="font-size:30vh; width: 99%" class="has-text-centered" v-if="isLoading">
          <i class="fas fa-circle-notch fa-spin"></i>
        </div>
        <div v-else>
          <div class="p-0 m-0" style="position: relative">
            <div class="content" style="white-space: pre;">
              <code class="p-4 is-block" v-text="data" />
              <button class="button is-small m-4" @click="() => copyText(JSON.stringify(data, null, 4))"
                style="position: absolute; top:0; right:0;">
                <span class="icon"><i class="fas fa-copy"></i></span>
              </button>
            </div>
          </div>
        </div>
      </div>
      <button class="modal-close is-large" aria-label="close" @click="closeModal"></button>
    </div>
  </div>
</template>

<script setup>
const config = useConfigStore()
const emitter = defineEmits(['closeModel'])
const isLoading = ref(false)
const data = ref({})

const props = defineProps({
  link: {
    type: String,
    default: ''
  },
})

const closeModal = () => emitter('closeModel')

const eventFunc = e => {
  if (e.key === 'Escape') {
    emitter('closeModel')
  }
}

onMounted(async () => {
  window.addEventListener('keydown', eventFunc)
  const url = config.app.url_host + config.app.url_prefix + 'api/url/info?url=' + encodePath(props.link)
  try {
    isLoading.value = true
    const response = await fetch(url);
    data.value = await response.json();
  } catch (e) {
    console.log(e)
  }
  finally {
    isLoading.value = false
  }
})

onUnmounted(() => window.removeEventListener('keydown', eventFunc))
</script>
