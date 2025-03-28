<style>
.is-image {
  max-width: 100%;
  max-height: 100%;
  margin: auto;
  display: block;
}
</style>
<template>
  <div>
    <div style="font-size:30vh; width: 99%" class="has-text-centered" v-if="isLoading">
      <i class="fas fa-circle-notch fa-spin"></i>
    </div>
    <div v-else>
      <img :src="image" class="is-image">
    </div>
  </div>
</template>

<script setup>
import { request } from '~/utils/index'

const emitter = defineEmits(['closeModel'])
const isLoading = ref(false)
const data = ref({})
const toast = useToast()
const image = ref('')

const props = defineProps({
  link: {
    type: String,
    required: true,
  },
})

const eventFunc = e => {
  if ('Escape' === e.key) {
    emitter('closeModel')
  }
}

onMounted(async () => {
  window.addEventListener('keydown', eventFunc)


  const url = props.link.startsWith('/') ? props.link : '/api/thumbnail?url=' + encodePath(props.link)

  try {
    isLoading.value = true

    const imgRequest = await request(url, { credentials: 'include' })
    if (200 !== imgRequest.status) {
      return
    }

    image.value = URL.createObjectURL(await imgRequest.blob())
  } catch (e) {
    console.error(e)
    toast.error(`Error: ${e.message}`)
  } finally {
    isLoading.value = false
  }
})

onUnmounted(() => window.removeEventListener('keydown', eventFunc))
</script>
