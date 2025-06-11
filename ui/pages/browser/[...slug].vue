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
            <div class="control has-icons-left" v-if="show_filter">
              <input type="search" v-model.lazy="search" class="input" id="search" placeholder="Filter">
              <span class="icon is-left">
                <i class="fas fa-filter"></i>
              </span>
            </div>

            <div class="control">
              <button class="button is-danger is-light" @click="toggleFilter" v-tooltip.bottom="'Filter content'">
                <span class="icon"><i class="fas fa-filter" /></span>
              </button>
            </div>

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
                <th width="5%" @click="changeSort('type')">
                  #
                  <span class="icon" v-if="'type' === sort_by">
                    <i class="fas"
                      :class="{ 'fa-sort-up': 'desc' === sort_order, 'fa-sort-down': 'asc' === sort_order }" />
                  </span>
                </th>
                <th width="70%" @click="changeSort('name')">
                  Name
                  <span class="icon" v-if="'name' === sort_by">
                    <i class="fas"
                      :class="{ 'fa-sort-up': 'desc' === sort_order, 'fa-sort-down': 'asc' === sort_order }" />
                  </span>

                </th>
                <th width="10%" @click="changeSort('size')">
                  Size
                  <span class="icon" v-if="'size' === sort_by">
                    <i class="fas"
                      :class="{ 'fa-sort-up': 'desc' === sort_order, 'fa-sort-down': 'asc' === sort_order }" />
                  </span>

                </th>
                <th width="15%" @click="changeSort('date')">
                  Date
                  <span class="icon" v-if="'date' === sort_by">
                    <i class="fas"
                      :class="{ 'fa-sort-up': 'desc' === sort_order, 'fa-sort-down': 'asc' === sort_order }" />
                  </span>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in filteredItems" :key="item.path">
                <td class="has-text-centered is-vcentered user-hint" v-tooltip="item.name">
                  <span class="icon"><i class="fas fa-2x fa-solid" :class="setIcon(item)" /></span>
                </td>
                <td class="is-text-overflow is-vcentered">
                  <div class="field is-grouped">
                    <div class="control is-text-overflow is-expanded">
                      <a :href="uri(`/browser/${item.path}`)" v-if="'dir' === item.content_type"
                        @click.prevent="handleClick(item)">
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
                  {{ 'file' === item.type ? formatBytes(item.size) : ucFirst(item.type) }}
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
        <Message title="Loading content" class="has-background-info-90 has-text-dark" icon="fas fa-refresh fa-spin"
          v-if="isLoading">
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
const toast = useNotification()
const config = useConfigStore()
const socket = useSocketStore()

const isLoading = ref(false)
const initialLoad = ref(true)
const items = ref([])
const path = ref(`/${route.params.slug?.length > 0 ? route.params.slug?.join('/') : ''}`)

const bg_enable = useStorage('random_bg', true)
const bg_opacity = useStorage('random_bg_opacity', 0.85)

const sort_by = useStorage('sort_by', 'name')
const sort_order = useStorage('sort_order', 'asc')

const search = ref('')
const show_filter = ref(false)

const filteredItems = computed(() => {
  if (!search.value) {
    return sortedItems(items.value)
  }

  const searchLower = search.value.toLowerCase()
  return sortedItems(items.value.filter(item => {
    return item.name.toLowerCase().includes(searchLower)
  }))
})

const sortedItems = items => {

  if (!items || items.length < 1) {
    return []
  }

  if ('name' === sort_by.value) {
    return items.sort((a, b) => {
      return 'asc' === sort_order.value ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name)
    })
  }

  if (sort_by.value === 'size') {
    return items.sort((a, b) => {
      return 'asc' === sort_order.value ? a.size - b.size : b.size - a.size
    })
  }

  if (sort_by.value === 'date') {
    return items.sort((a, b) => {
      let aDate = new Date(a.mtime)
      let bDate = new Date(b.mtime)
      return 'asc' === sort_order.value ? aDate - bDate : bDate - aDate
    })
  }

  if (sort_by.value === 'type') {
    return items.sort((a, b) => {
      return 'asc' === sort_order.value ? a.content_type.localeCompare(b.content_type) : b.content_type.localeCompare(a.content_type)
    })
  }

  return items
}


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
    if (search.value) {
      search.value = ''
      show_filter.value = false
    }

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
    const stateUrl = uri(`/browser/${dir}`)

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

const setIcon = item => {
  if ('link' === item.type) {
    return 'fa-link'
  }
  if ('dir' === item.content_type) {
    return 'fa-folder'
  }

  if (['video', 'audio'].includes(item.content_type)) {
    return 'fa-file-video'
  }

  if (['text', 'subtitle', 'metadata'].includes(item.content_type)) {
    return 'fa-file-alt'
  }

  if (['image'].includes(item.content_type)) {
    return 'fa-file-image'
  }

  return 'fa-file'
}

const changeSort = by => {
  if (!['name', 'size', 'date', 'type'].includes(by)) {
    return
  }

  if (by !== sort_by.value) {
    sort_by.value = by
  }

  sort_order.value = 'asc' === sort_order.value ? 'desc' : 'asc'
}

const toggleFilter = () => {
  show_filter.value = !show_filter.value
  if (!show_filter.value) {
    search.value = ''
    return
  }

  awaitElement('#search', e => e.focus())
}

</script>
