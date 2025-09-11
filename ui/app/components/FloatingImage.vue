<template>
  <vTooltip @show="loadContent" @hide="stopTimer">
    <slot />
    <template #popper>
      <span class="icon" v-if="!url"><i class="fas fa-circle-notch fa-spin" /></span>
      <div v-else>
        <div style="min-width: 300px; width: 25vw; height: auto;" class="m-1">
          <div class="is-block" style="word-break: all;" v-if="props.title">
            <span style="font-size: 120%;">{{ props.title }}</span>
          </div>
          <figure class="image is-3by1 is-hidden-mobile">
            <img @load="e => pImg(e)" :src="url" :alt="props.title" @error="clearCache"
              :crossorigin="props.privacy ? 'anonymous' : 'use-credentials'"
              :referrerpolicy="props.privacy ? 'no-referrer' : 'origin'" />
          </figure>
        </div>
      </div>
    </template>
  </vTooltip>
</template>

<script setup lang="ts">
import { disableOpacity, enableOpacity } from '~/utils'

const props = defineProps<{
  image?: string
  title?: string
  loader?: () => Promise<void>
  privacy?: boolean
}>()

const cache = useSessionCache()
const toast = useNotification()
const url = ref<string | null>(null)
const error = ref(false)
const isPreloading = ref(false)

const loadTimer: ReturnType<typeof setTimeout> | null = null
const cancelRequest = new AbortController()

const defaultLoader = async (): Promise<void> => {
  try {
    if (!props.image) {
      return
    }

    if (cache.has(props.image)) {
      url.value = cache.get(props.image)
      return
    }

    const response = await request(props.image, { signal: cancelRequest.signal })

    if (!response.ok) {
      toast.error(`ImageView Request error. ${response.status}: ${response.statusText}`)
      return
    }

    const objUrl = URL.createObjectURL(await response.blob())
    cache.set(props.image, objUrl)
    url.value = objUrl
  } catch (e: any) {
    if (e === 'not_needed') {
      return
    }
    console.error(e)
    toast.error(`ImageView Request failure. ${e}`)
  } finally {
    isPreloading.value = false
  }
}

const stopTimer = async (): Promise<void> => {
  if (error.value) {
    return
  }

  if (url.value) {
    isPreloading.value = false
    url.value = null
    return
  }

  await awaiter(() => isPreloading.value)
  if (loadTimer !== null) {
    clearTimeout(loadTimer)
  }

  isPreloading.value = false
  url.value = null
  cancelRequest.abort('not_needed')
}

const loadContent = async (): Promise<void> => {
  if (props.loader) {
    return props.loader()
  }

  return defaultLoader()
}

const clearCache = async (): Promise<void> => {
  if (!props.image) return

  cache.remove(props.image)
  url.value = ''
  return loadContent()
}

const pImg = (e: Event): void => {
  const target = e.target as HTMLImageElement
  if (target.naturalHeight > target.naturalWidth) {
    target.classList.add('image-portrait')
  }
}
onMounted(() => disableOpacity())
onBeforeUnmount(() => {
  enableOpacity()
  if (null !== loadTimer) {
    clearTimeout(loadTimer)
  }
  cancelRequest.abort('not_needed')
})

</script>
