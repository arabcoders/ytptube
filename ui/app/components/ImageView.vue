<style scoped>
img {
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
      <img :src="image">
    </div>
  </div>
</template>

<script setup lang="ts">
const toast = useNotification()
const emitter = defineEmits(['closeModel'])

const isLoading = ref<boolean>(false)
const image = ref<string>('')

const props = defineProps({
  link: {
    type: String,
    required: true,
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

  const url = props.link.startsWith('/') ? props.link : '/api/thumbnail?url=' + encodePath(props.link)

  try {
    isLoading.value = true

    const imgRequest = await request(url, { credentials: 'include' })
    if (200 !== imgRequest.status) {
      return
    }

    image.value = URL.createObjectURL(await imgRequest.blob())
  } catch (e: any) {
    console.error(e)
    toast.error(`Error: ${e.message}`)
  } finally {
    isLoading.value = false
  }
})

onBeforeUnmount(() => document.removeEventListener('keydown', handle_event))
</script>
