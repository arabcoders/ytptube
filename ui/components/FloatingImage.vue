<template>
  <vTooltip @show="loadContent" @hide="stopTimer">
    <slot />
    <template #popper>
      <span class="icon" v-if="!url"><i class="fas fa-circle-notch fa-spin"></i></span>
      <template v-else>
        <div>
          <h1 v-if="props.title" class="is-4">{{ props.title }}</h1>
          <img :src="url" style="width:720px; height: auto" class="card-image" :alt="props.title" @error="clearCache"
            :crossorigin="props.privacy ? 'anonymous' : 'use-credentials'"
            :referrerpolicy="props.privacy ? 'no-referrer' : 'origin'" />
        </div>
      </template>
    </template>
  </vTooltip>
</template>

<script setup>
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
const config = useConfigStore()
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

    const response = await fetch(config.app.url_host + config.app.url_prefix + 'api/thumbnail?url=' + encodePath(props.image), {
      signal: cancelRequest.signal
    })

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
</script>
