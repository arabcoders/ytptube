<template>
  <div>
    <div class="mt-1 columns is-multiline">
      <div class="column is-12 is-clearfix">
        <span class="title is-4">
          <nav class="breadcrumb is-inline-block">
            <ul>
              <li v-for="(item, index) in makeBreadCrumb(path)" :key="item.link"
                :class="{ 'is-active': index === makeBreadCrumb(path).length - 1 }">
                <a :href="item.link" @click.prevent="reloadContent(item.path)" v-text="item.name" />
              </li>
              <li class="is-active" v-if="isLoading">
                <NuxtLink>
                  <span class="icon"><i class="fas fa-spinner fa-spin"></i></span>
                </NuxtLink>
              </li>
            </ul>
          </nav>
        </span>
        <div class="is-pulled-right">
          <div class="field is-grouped">
            <p class="control">
              <button class="button is-info" @click="reloadContent(path, true)" :class="{ 'is-loading': isLoading }"
                :disabled="!socket.isConnected || isLoading">
                <span class="icon"><i class="fas fa-refresh" /></span>
              </button>
            </p>
          </div>
        </div>
        <div class="is-hidden-mobile">
          <span class="subtitle">Files Browser</span>
        </div>
      </div>
    </div>

    <div class="columns is-multiline">
      <div class="column is-12" v-if="items && items.length > 0">
        <div class="table-container is-responsive">
          <table class="table is-striped is-hoverable is-fullwidth is-bordered"
            style="min-width: 1300px; table-layout: fixed;">
            <thead>
              <tr class="has-text-centered is-unselectable">
                <th width="5%">#</th>
                <th width="55%">Name</th>
                <th width="10%">Size</th>
                <th width="15%">Created</th>
                <th width="15%">Modified</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in items" :key="item.path">
                <td class="has-text-centered is-vcentered">
                  <span class="icon">
                    <i class="fas fa-solid"
                      :class="{ 'fa-file': 'file' === item.type, 'fa-folder': 'dir' === item.type }" />
                  </span>
                </td>
                <td class="is-text-overflow is-vcentered">
                  <div class="field is-grouped">
                    <div class="control is-text-overflow is-expanded" v-tooltip="item.name">
                      <a :href="`/browser/${item.path}`" v-if="'dir' === item.type"
                        @click.prevent="reloadContent(item.path)">
                        {{ item.name }}
                      </a>
                      <a :href="makeDownload({}, { filename: item.path, folder: '' })"
                        @click.prevent="handleClick(item)" v-else>
                        {{ item.name }}
                      </a>
                    </div>
                    <div class="control" v-if="'file' === item.type">
                      <span class="icon">
                        <a :href="makeDownload({}, { filename: item.path, folder: '' })"
                          :download="item.name.split('/').reverse()[0]">
                          <i class="fas fa-download" />
                        </a>
                      </span>
                    </div>
                  </div>
                </td>
                <td class="has-text-centered is-text-overflow is-unselectable">
                  {{ 'file' === item.type ? formatBytes(item.size) : 'Dir' }}
                </td>
                <td class="has-text-centered is-text-overflow is-unselectable">
                  <span :data-datetime="item.ctime" v-tooltip="moment(item.ctime).format('MMMM Do YYYY, h:mm:ss a')">
                    {{ moment(item.ctime).fromNow() }}
                  </span>
                </td>
                <td class="has-text-centered is-text-overflow is-unselectable">
                  <span :data-datetime="item.mtime" v-tooltip="moment(item.mtime).format('MMMM Do YYYY, h:mm:ss a')">
                    {{ moment(item.mtime).fromNow() }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <div class="column is-12" v-else>
        <Message title="Loading content" class="is-background-info-80" icon="fas fa-refresh fa-spin" v-if="isLoading">
          Loading file browser contents...
        </Message>
        <Message v-else title="No Content" class="is-background-warning-80 has-text-dark"
          icon="fas fa-exclamation-circle">
          No content found in this directory.
        </Message>
      </div>
    </div>
    <div class="modal is-active" v-if="model_item">
      <div class="modal-background" @click="closeModel"></div>
      <div class="modal-content is-unbounded-model">
        <VideoPlayer type="default" :isMuted="false" autoplay="true" :isControls="true" :item="model_item"
          class="is-fullwidth" @closeModel="closeModel" v-if="'video' === model_item.type" />
        <GetInfo :link="model_item.filename" :useUrl="true" @closeModel="closeModel" :externalModel="true"
          v-if="'text' === model_item.type" />
        <ImageView :link="model_item.filename" @closeModel="closeModel" v-if="'image' === model_item.type" />
      </div>
      <button class="modal-close is-large" aria-label="close" @click="closeModel"></button>
    </div>
  </div>
</template>

<script setup>
import { request } from '~/utils/index'
import moment from 'moment'
import { useStorage } from '@vueuse/core'

const route = useRoute()
const toast = useToast()
const config = useConfigStore()
const socket = useSocketStore()

const isLoading = ref(false)
const initialLoad = ref(true)
const items = ref([])
const path = ref(`/${route.params.slug?.length > 0 ? route.params.slug?.join('/') : ''}`)

const bg_enable = useStorage('random_bg', true)
const bg_opacity = useStorage('random_bg_opacity', 0.85)

const model_item = ref()
const closeModel = () => model_item.value = null

watch(() => config.app.basic_mode, async () => {
  if (!config.app.basic_mode) {
    return
  }
  await navigateTo('/')
})

watch(() => config.app.browser_enabled, async () => {
  if (config.app.browser_enabled) {
    return
  }
  await navigateTo('/')
})

watch(() => socket.isConnected, async () => {
  if (socket.isConnected && initialLoad.value) {
    await reloadContent(path.value, true)
    initialLoad.value = false
  }
})

const handleClick = item => {
  if ('video' === item.content_type) {
    model_item.value = {
      "type": 'video',
      "filename": item.path,
      "folder": "",
      "extras": {},
    }
    return
  }

  if (['text', 'subtitle', 'metadata'].includes(item.content_type)) {
    model_item.value = {
      "type": 'text',
      "filename": makeDownload(config, { "filename": item.path }),
      "folder": "",
      "extras": {},
    }
    return
  }

  if ('image' === item.content_type) {
    model_item.value = {
      "type": 'image',
      "filename": makeDownload(config, { "filename": item.path }),
      "folder": "",
      "extras": {},
    }
    return
  }

  if ('dir' === item.content_type) {
    reloadContent(item.path)
    return
  }

  window.location = makeDownload(config, { "filename": item.path, "folder": "", "extras": {} })
}

const reloadContent = async (dir = '/', fromMounted = false) => {
  try {
    isLoading.value = true

    if (typeof dir !== 'string') {
      dir = '/'
    }

    dir = sTrim(dir, '/')

    const response = await request(`/api/file/browser/${sTrim(dir, '/')}`)

    if (fromMounted && !response.ok) {
      return
    }

    items.value = []

    const data = await response.json()

    if (data.length < 1) {
      return
    }

    if (!data?.contents || data.contents.length > 0) {
      items.value = data.contents
    }

    if (data?.path) {
      path.value = sTrim(data.path, '/')
    }

    const title = `File Browser: /${dir}`
    const stateUrl = `/browser/${dir}`

    if (false === fromMounted) {
      history.pushState({ path: dir, title: title }, title, stateUrl)
    }

    useHead({ title: title })
  } catch (e) {
    if (fromMounted) {
      return
    }
    console.error(e)
    toast.error('Failed to load file browser contents.')
  } finally {
    isLoading.value = false
  }
}

const popstateHandler = e => {

  if (!e.state) {
    return
  }

  if (e.state.path === path.value || e.state.path === window.location.pathname) {
    return
  }

  reloadContent(e.state.path, true)
}

onMounted(async () => {
  if (socket.isConnected && initialLoad.value) {
    await reloadContent(path.value, true)
  }

  window.addEventListener('popstate', popstateHandler)
})

onUnmounted(() => {
  window.removeEventListener('popstate', popstateHandler)
})

const makeBreadCrumb = path => {
  const baseLink = '/'

  path = path.replace(/^\/+/, '').replace(/\/+$/, '')

  let links = []
  links.push({
    name: 'Home',
    link: baseLink,
    path: baseLink
  })

  // -- explode path and create links
  let parts = path.split('/')
  parts.forEach((part, index) => {
    let path = baseLink + parts.slice(0, index + 1).join('/')
    links.push({
      name: part,
      link: path,
      path: path,
    })
  })

  return links
}


watch(model_item, v => {
  if (!bg_enable.value) {
    return
  }

  document.querySelector('body').setAttribute("style", `opacity: ${v ? 1 : bg_opacity.value}`)
})
</script>
