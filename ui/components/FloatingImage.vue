<template>
  <vTooltip @show="loadContent" @hide="stopTimer">
    <slot />
    <template #popper class="p-0 m-0">
      <span class="icon" v-if="!url"><i class="fas fa-circle-notch fa-spin" /></span>
      <template v-else>
        <div style="max-width:650px" class="m-1">
          <div class="is-block" style="word-break: all;" v-text="props.title" v-if="props.title" />
          <figure class="image is-3by1">
            <img @load="e => pImg(e)" :src="url" :alt="props.title" @error="clearCache"
              :crossorigin="props.privacy ? 'anonymous' : 'use-credentials'"
              :referrerpolicy="props.privacy ? 'no-referrer' : 'origin'" />
          </figure>
        </div>
      </template>
    </template>
  </vTooltip>
</template>

<script setup>
import { request } from '~/utils/index'

const props = defineProps({
  image: {
    type: String,
    required: false,
  },
  title: {
    type: String,
    required: false
  },
  loader: {
    Type: Function,
    required: false,
  },
  privacy: {
    type: Boolean,
    required: false,
    default: true
  }
});

const cache = useSessionCache()
const toast = useToast()
const url = ref()
const error = ref(false)
const isPreloading = ref(false)

let loadTimer = null;
const cancelRequest = new AbortController();

const defaultLoader = async () => {
  try {
    if (cache.has(props.image)) {
      url.value = cache.get(props.image)
      return
    }

    const response = await request(props.image, { signal: cancelRequest.signal })

    if (200 !== response.status) {
      toast.error(`ImageView Request error. ${response.status}: ${response.statusText}`)
      return;
    }

    const objUrl = URL.createObjectURL(await response.blob());

    cache.set(props.image, objUrl)

    url.value = objUrl;
  } catch (e) {
    if ('not_needed' === e) {
      return
    }
    console.error(e)
    toast.error(`ImageView Request failure. ${e}`)
  } finally {
    isPreloading.value = false
  }
}

const stopTimer = async () => {
  if (error.value) {
    return
  }

  if (url.value) {
    isPreloading.value = false
    url.value = null;
    return;
  }

  await awaiter(() => isPreloading.value)
  clearTimeout(loadTimer)
  isPreloading.value = false
  url.value = null;
  cancelRequest.abort('not_needed')
}

const loadContent = async () => {
  if (props.loader) {
    return props.loader()
  }

  return defaultLoader()
}

const clearCache = async () => {
  cache.remove(props.image)
  url.value = '';
  return loadContent()
}

const pImg = e => e.target.naturalHeight > e.target.naturalWidth ? e.target.classList.add('image-portrait') : null
</script>
