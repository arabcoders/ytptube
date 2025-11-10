<template>
  <ModalText :isLoading="isLoading" :data="data" :externalModel="externalModel"
    @closeModel="() => emitter('closeModel')" :code_classes="code_classes" />
</template>

<script setup lang="ts">
const toast = useNotification()
const emitter = defineEmits<{ (e: 'closeModel'): void }>()

const props = defineProps<{
  link?: string
  preset?: string
  cli?: string
  useUrl?: boolean
  externalModel?: boolean
  code_classes?: string
}>()

const isLoading = ref<boolean>(true)
const data = ref<any>({})

onMounted(async (): Promise<void> => {
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
</script>
