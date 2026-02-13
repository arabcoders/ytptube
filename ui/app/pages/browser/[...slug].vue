<template>
  <div>
    <div class="mt-1 columns is-multiline">
      <div class="column is-12 is-clearfix">
        <span class="title is-4">
          <nav class="breadcrumb is-inline-block">
            <ul>
              <li v-for="(item, index) in makeBreadCrumb(browserPath)" :key="item.link"
                :class="{ 'is-active': index === makeBreadCrumb(browserPath).length - 1 }">
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
              <input type="search" v-model.lazy="localSearch" class="input" id="search" placeholder="Filter">
              <span class="icon is-left">
                <i class="fas fa-filter"></i>
              </span>
            </div>

            <div class="control">
              <button class="button is-danger is-light" @click="toggleFilter">
                <span class="icon"><i class="fas fa-filter" /></span>
                <span v-if="!isMobile">Filter</span>
              </button>
            </div>

            <p class="control">
              <button class="button is-info is-light" @click="handleCreateDirectory"
                v-if="config.app.browser_control_enabled">
                <span class="icon"><i class="fas fa-folder-plus" /></span>
                <span v-if="!isMobile">New Folder</span>
              </button>
            </p>
            <p class="control">
              <button class="button" @click="() => display_style = display_style === 'list' ? 'grid' : 'list'">
                <span class="icon">
                  <i class="fa-solid"
                    :class="{ 'fa-table': display_style !== 'list', 'fa-table-list': display_style === 'list' }" /></span>
                <span v-if="!isMobile">
                  {{ display_style === 'list' ? 'List' : 'Grid' }}
                </span>
              </button>
            </p>
            <p class="control" v-if="filteredItems && filteredItems.length > 0">
              <Dropdown label="Sort&nbsp;&nbsp;" icons="fa-solid fa-sort" :hide_label_on_mobile="true">
                <NuxtLink class="dropdown-item" :class="{ 'is-active': 'type' === sort_by }"
                  @click="handleChangeSort('type')">
                  <span class="icon"><i class="fa-solid fa-hashtag" /></span>
                  <span>Type</span>
                  <span class="icon is-pulled-right" v-if="'type' === sort_by">
                    <i class="fas"
                      :class="{ 'fa-sort-up': 'desc' === sort_order, 'fa-sort-down': 'asc' === sort_order }" />
                  </span>
                </NuxtLink>

                <NuxtLink class="dropdown-item" :class="{ 'is-active': 'name' === sort_by }"
                  @click="handleChangeSort('name')">
                  <span class="icon"><i class="fa-solid fa-arrow-down-a-z" /></span>
                  <span>Name</span>
                  <span class="icon is-pulled-right" v-if="'name' === sort_by">
                    <i class="fas"
                      :class="{ 'fa-sort-up': 'desc' === sort_order, 'fa-sort-down': 'asc' === sort_order }" />
                  </span>
                </NuxtLink>

                <NuxtLink class="dropdown-item" :class="{ 'is-active': 'size' === sort_by }"
                  @click="handleChangeSort('size')">
                  <span class="icon"><i class="fa-solid fa-weight" /></span>
                  <span>Size</span>
                  <span class="icon is-pulled-right" v-if="'size' === sort_by">
                    <i class="fas"
                      :class="{ 'fa-sort-up': 'desc' === sort_order, 'fa-sort-down': 'asc' === sort_order }" />
                  </span>
                </NuxtLink>

                <NuxtLink class="dropdown-item" :class="{ 'is-active': 'date' === sort_by }"
                  @click="handleChangeSort('date')">
                  <span class="icon"><i class="fa-solid fa-calendar" /></span>
                  <span>Date</span>
                  <span class="icon is-pulled-right" v-if="'date' === sort_by">
                    <i class="fas"
                      :class="{ 'fa-sort-up': 'desc' === sort_order, 'fa-sort-down': 'asc' === sort_order }" />
                  </span>
                </NuxtLink>
              </Dropdown>
            </p>
            <p class="control">
              <button class="button is-info" @click="reloadContent(browserPath)" :class="{ 'is-loading': isLoading }"
                :disabled="isLoading">
                <span class="icon"><i class="fas fa-refresh" /></span>
                <span v-if="!isMobile">Reload</span>
              </button>
            </p>
          </div>
        </div>
      </div>
    </div>

    <div class="columns is-mobile is-multiline is-justify-content-flex-end"
      v-if="config.app.browser_control_enabled && filteredItems && filteredItems.length > 0">
      <div class="column is-narrow">
        <button type="button" class="button" @click="masterSelectAll = !masterSelectAll"
          :class="{ 'has-text-primary': !masterSelectAll, 'has-text-danger': masterSelectAll }"
          :disabled="isLoading || filteredItems.length < 1">
          <span class="icon">
            <i :class="!masterSelectAll ? 'fa-regular fa-square-check' : 'fa-regular fa-square'" />
          </span>
          <span v-if="!masterSelectAll">Select</span>
          <span v-else>Unselect</span>
          <span v-if="selectedElms.length > 0">
            &nbsp;(<u class="has-text-danger">{{ selectedElms.length }}</u>)
          </span>
        </button>
      </div>
      <div class="column is-2-tablet is-5-mobile">
        <Dropdown label="Actions" icons="fa-solid fa-list">
          <a class="dropdown-item has-text-danger"
            @click="(selectedElms.length > 0 && !isLoading) ? handleDeleteSelected() : null"
            :style="{ opacity: (selectedElms.length < 1 || isLoading) ? 0.5 : 1, cursor: (selectedElms.length < 1 || isLoading) ? 'not-allowed' : 'pointer' }">
            <span class="icon"><i class="fa-solid fa-trash-can" /></span>
            <span>Delete{{ selectedElms.length > 0 ? ` (${selectedElms.length})` : '' }}</span>
          </a>
          <a class="dropdown-item has-text-link"
            @click="(selectedElms.length > 0 && !isLoading) ? handleMoveSelected() : null"
            :style="{ opacity: (selectedElms.length < 1 || isLoading) ? 0.5 : 1, cursor: (selectedElms.length < 1 || isLoading) ? 'not-allowed' : 'pointer' }">
            <span class="icon"><i class="fa-solid fa-arrows-alt" /></span>
            <span>Move{{ selectedElms.length > 0 ? ` (${selectedElms.length})` : '' }}</span>
          </a>
        </Dropdown>
      </div>
    </div>

    <div class="columns is-multiline" v-if="pagination.total_pages > 1">
      <div class="column is-12">
        <Pager :page="pagination.page" :last_page="pagination.total_pages" :isLoading="isLoading"
          @navigate="handlePageChange" />
      </div>
    </div>

    <div class="columns is-multiline">
      <template v-if="'list' === display_style">
        <div class="column is-12" v-if="filteredItems && filteredItems.length > 0">
          <div class="table-container">
            <table class="table is-striped is-hoverable is-fullwidth is-bordered"
              style="min-width: 1300px; table-layout: fixed;">
              <thead>
                <tr class="has-text-centered is-unselectable">
                  <th :colspan="config.app.browser_control_enabled ? 2 : 1"
                    :width="config.app.browser_control_enabled ? '10%' : '5%'">
                    #
                    <span class="icon" v-if="'type' === sort_by">
                      <i class="fas"
                        :class="{ 'fa-sort-up': 'desc' === sort_order, 'fa-sort-down': 'asc' === sort_order }" />
                    </span>
                  </th>
                  <th width="65%">
                    Name
                    <span class="icon" v-if="'name' === sort_by">
                      <i class="fas"
                        :class="{ 'fa-sort-up': 'desc' === sort_order, 'fa-sort-down': 'asc' === sort_order }" />
                    </span>

                  </th>
                  <th width="10%">
                    Size
                    <span class="icon" v-if="'size' === sort_by">
                      <i class="fas"
                        :class="{ 'fa-sort-up': 'desc' === sort_order, 'fa-sort-down': 'asc' === sort_order }" />
                    </span>

                  </th>
                  <th width="15%">
                    Date
                    <span class="icon" v-if="'date' === sort_by">
                      <i class="fas"
                        :class="{ 'fa-sort-up': 'desc' === sort_order, 'fa-sort-down': 'asc' === sort_order }" />
                    </span>
                  </th>
                  <th width="15%" v-if="config.app.browser_control_enabled">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in filteredItems" :key="item.path">
                  <td class="has-text-centered is-vcentered" v-if="config.app.browser_control_enabled">
                    <input type="checkbox" v-model="selectedElms" :value="item.path" />
                  </td>
                  <td class="has-text-centered is-vcentered has-tooltip" v-tooltip="item.name">
                    <span class="icon"><i class="fas fa-2x fa-solid" :class="setIcon(item)" /></span>
                  </td>
                  <td class="is-text-overflow is-vcentered">
                    <div class="field is-grouped">
                      <div class="control is-text-overflow is-expanded">
                        <a :href="uri(`/browser/${item.path}`)" v-if="'dir' === item.content_type" v-tooltip="item.name"
                          @click.prevent="handleClick(item)">
                          {{ item.name }}
                        </a>
                        <a :href="makeDownload({}, { filename: item.path, folder: '' })" v-tooltip="item.name"
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
                  <td class="has-text-centered is-text-overflow is-unselectable is-vcentered">
                    {{ 'file' === item.type ? formatBytes(item.size) : ucFirst(item.type) }}
                  </td>
                  <td class="has-text-centered is-text-overflow is-unselectable is-vcentered">
                    <span :data-datetime="item.mtime" v-tooltip="moment(item.mtime).format('YYYY-MM-DD H:mm:ss Z')"
                      class="has-tooltip">
                      {{ moment(item.mtime).fromNow() }}
                    </span>
                  </td>
                  <td class="is-vcentered" v-if="config.app.browser_control_enabled">
                    <Dropdown icons="fa-solid fa-cogs" label="Actions">
                      <template v-if="'file' === item.type">
                        <a :href="makeDownload({}, { filename: item.path, folder: '' })"
                          :download="item.name.split('/').reverse()[0]" class="dropdown-item">
                          <span class="icon"><i class="fa-solid fa-download" /></span>
                          <span>Download</span>
                        </a>
                        <hr class="dropdown-divider" />
                      </template>

                      <NuxtLink class="dropdown-item" @click="handleAction('rename', item)">
                        <span class="icon"><i class="fa-solid fa-edit" /></span>
                        <span>Rename</span>
                      </NuxtLink>

                      <hr class="dropdown-divider" />

                      <NuxtLink class="dropdown-item" @click="handleAction('delete', item)">
                        <span class="icon has-text-danger"><i class="fa-solid fa-trash" /></span>
                        <span>Delete</span>
                      </NuxtLink>

                      <hr class="dropdown-divider" />

                      <NuxtLink class="dropdown-item" @click="handleAction('move', item)">
                        <span class="icon"><i class="fa-solid fa-arrows-alt" /></span>
                        <span>Move</span>
                      </NuxtLink>

                    </Dropdown>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>

      <template v-else>
        <div class="column is-6" v-for="item in filteredItems" :key="item.path">
          <div class="card is-flex is-full-height is-flex-direction-column">
            <header class="card-header">
              <div class="card-header-title is-text-overflow is-block">
                <span class="icon"> <i class="fas fa-solid" :class="setIcon(item)" /></span>
                <a :href="uri(`/browser/${item.path}`)" v-if="'dir' === item.content_type"
                  @click.prevent="handleClick(item)" v-tooltip="item.name">
                  {{ item.name }}
                </a>
                <a :href="makeDownload({}, { filename: item.path, folder: '' })" @click.prevent="handleClick(item)"
                  v-tooltip="item.name" v-else>
                  {{ item.name }}
                </a>
              </div>
              <div class="card-header-icon">
                <div class="field is-grouped">
                  <div class="control" v-if="'file' === item.type && config.app.browser_control_enabled">
                    <a :href="makeDownload({}, { filename: item.path, folder: '' })"
                      :download="item.name.split('/').reverse()[0]" class="has-text-link" v-tooltip="`Download File`">
                      <span class="icon"><i class="fa-solid fa-download" /></span>
                    </a>
                  </div>
                  <div class="control" v-if="config.app.browser_control_enabled">
                    <label class="checkbox is-block">
                      <input type="checkbox" v-model="selectedElms" :value="item.path">
                    </label>
                  </div>
                </div>
              </div>
            </header>
            <div class="card-footer mt-auto">
              <div class="card-footer-item" v-if="'file' === item.type && !config.app.browser_control_enabled">
                <a :href="makeDownload({}, { filename: item.path, folder: '' })"
                  :download="item.name.split('/').reverse()[0]" class="has-text-link" v-tooltip="`Download File`">
                  <span class="icon"><i class="fa-solid fa-download" /></span>
                  <span>Download</span>
                </a>
              </div>
              <div class="card-footer-item" v-if="config.app.browser_control_enabled">
                <a class="has-text-danger" @click="handleAction('delete', item)">
                  <span class="icon"><i class="fa-solid fa-trash" /></span>
                  <span>Delete</span>
                </a>
              </div>
              <div class="card-footer-item has-text-centered">
                <p class="is-text-overflow">
                  <span class="icon"><i class="fa-solid fa-calendar" /></span>
                  <span v-tooltip="moment(item.mtime).format('YYYY-MM-DD H:mm:ss Z')" class="has-tooltip">
                    {{ moment(item.mtime).fromNow() }}
                  </span>
                </p>
              </div>
              <div class="card-footer-item" v-if="config.app.browser_control_enabled">
                <Dropdown icons="fa-solid fa-cogs" label="Actions">
                  <NuxtLink class="dropdown-item" @click="handleAction('rename', item)">
                    <span class="icon"><i class="fa-solid fa-edit" /></span>
                    <span>Rename</span>
                  </NuxtLink>

                  <hr class="dropdown-divider" />

                  <NuxtLink class="dropdown-item" @click="handleAction('delete', item)">
                    <span class="icon has-text-danger"><i class="fa-solid fa-trash" /></span>
                    <span>Delete</span>
                  </NuxtLink>

                  <hr class="dropdown-divider" />

                  <NuxtLink class="dropdown-item" @click="handleAction('move', item)">
                    <span class="icon"><i class="fa-solid fa-arrows-alt" /></span>
                    <span>Move</span>
                  </NuxtLink>
                </Dropdown>
              </div>
            </div>
          </div>
        </div>
      </template>

      <div class="column is-12" v-if="localSearch && filteredItems.length < 1 && !isLoading">
        <Message class="is-warning" title="No results" icon="fas fa-filter" :useClose="true"
          @close="() => localSearch = ''">
          <p class="is-block">
            No results found for '<span class="is-underlined is-bold">{{ localSearch }}</span>'.
          </p>
        </Message>
      </div>

      <div class="column is-12" v-else-if="!filteredItems || filteredItems.length < 1">
        <Message title="Loading content" class="is-info" icon="fas fa-refresh fa-spin" v-if="isLoading">
          Loading file browser contents...
        </Message>
        <Message v-else title="No Content" class="is-warning" icon="fas fa-exclamation-circle">
          Directory is empty.
        </Message>
      </div>
      <div class="column is-12" v-if="!config.app.browser_control_enabled">
        <div class="message is-info">
          <p class="message-body">
            <span class="icon"> <i class="fas fa-info-circle" /></span>
            You can enable file controls such as rename, delete, move, and create directory by setting
            <code>YTP_BROWSER_CONTROL_ENABLED=true</code> in your environment configuration and restart the application.
          </p>
        </div>
      </div>
    </div>

    <div class="columns is-multiline" v-if="pagination.total_pages > 1">
      <div class="column is-12">
        <Pager :page="pagination.page" :last_page="pagination.total_pages" :isLoading="isLoading"
          @navigate="handlePageChange" />
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
    <ConfirmDialog v-if="dialog_confirm.visible" :visible="dialog_confirm.visible" :title="dialog_confirm.title"
      :message="dialog_confirm.message" :options="dialog_confirm.options" @confirm="dialog_confirm.confirm"
      :html_message="dialog_confirm.html_message" @cancel="dialog_confirm = reset_dialog()" />
  </div>
</template>

<script setup lang="ts">
import moment from 'moment'
import { useStorage } from '@vueuse/core'
import type { FileItem } from '~/types/filebrowser'

const route = useRoute()
const toast = useNotification()
const config = useConfigStore()
const dialog = useDialog()
const browser = useBrowser()
const isMobile = useMediaQuery({ maxWidth: 1024 })

const bg_enable = useStorage('random_bg', true)
const bg_opacity = useStorage('random_bg_opacity', 0.95)
const display_style = useStorage<string>('browser_display_style', 'list')
const show_filter = ref<boolean>(false)
const localSearch = ref<string>('')

const items = browser.items
const browserPath = browser.path
const pagination = browser.pagination
const isLoading = browser.isLoading
const selectedElms = browser.selectedElms
const masterSelectAll = browser.masterSelectAll
const sort_by = browser.sort_by
const sort_order = browser.sort_order
const filteredItems = browser.filteredItems

const initialPath = (() => {
  const slug = route.params.slug
  if (Array.isArray(slug) && slug.length > 0) {
    return '/' + slug.join('/')
  }
  return '/'
})()

const isUpdating = ref(false)

const buildStateUrl = (dir: string, page?: number): string => {
  const params = new URLSearchParams()
  const p = page ?? pagination.value.page
  if (p > 1) {
    params.set('page', String(p))
  }
  if (sort_by.value !== 'name') {
    params.set('sort_by', sort_by.value)
  }
  if (sort_order.value !== 'asc') {
    params.set('sort_order', sort_order.value)
  }
  if (localSearch.value) {
    params.set('search', localSearch.value)
  }
  const queryString = params.toString()
  const normalizedDir = dir.replace(/^\/+/, '').replace(/\/+$/, '')
  const basePath = normalizedDir ? `/browser/${normalizedDir}` : '/browser'
  return queryString ? `${basePath}?${queryString}` : basePath
}

const syncFromUrl = (): { page: number } => {
  const query = route.query
  const page = parseInt(query.page as string, 10) || 1

  if (query.sort_by && ['name', 'size', 'date', 'type'].includes(query.sort_by as string)) {
    browser.setSortBy(query.sort_by as string)
  }
  if (query.sort_order && ['asc', 'desc'].includes(query.sort_order as string)) {
    browser.setSortOrder(query.sort_order as string)
  }
  if (query.search && typeof query.search === 'string') {
    browser.setSearchValue(query.search)
    localSearch.value = query.search
    show_filter.value = true
  }

  return { page }
}

const reset_dialog = () => ({
  visible: false,
  title: 'Confirm Action',
  confirm: (_opts: any) => { },
  message: '',
  html_message: '',
  options: [],
})

const dialog_confirm = ref(reset_dialog())
const model_item = ref<any>()

watch(masterSelectAll, v => {
  if (v) {
    selectedElms.value = filteredItems.value.map(i => i.path)
  } else {
    selectedElms.value = []
  }
})

watch(localSearch, async (val) => {
  if (isUpdating.value) return
  await browser.setSearch(val)
  updateUrl(browserPath.value, 1)
})

const closeModel = (): void => { model_item.value = null }

const updateUrl = (dir: string, page?: number): void => {
  const normalizedDir = dir.replace(/^\/+/, '').replace(/\/+$/, '')
  const displayDir = normalizedDir ? normalizedDir : '/'
  const title = `File Browser: /${sTrim(displayDir, '/')}`
  const stateUrl = buildStateUrl(dir, page)
  const fullUrl = window.location.origin + stateUrl
  if (fullUrl !== window.location.href) {
    history.replaceState({ path: normalizedDir || '/', title: title }, title, stateUrl)
  }
  useHead({ title: decodeURIComponent(title) })
}

const handleClick = (item: FileItem): void => {
  if (true === ['video', 'audio'].includes(item.content_type)) {
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
    if (localSearch.value) {
      localSearch.value = ''
      show_filter.value = false
    }

    reloadContent(item.path)
    return
  }

  window.location.href = makeDownload(config, { "filename": item.path, "folder": "", "extras": {} })
}

const reloadContent = async (dir: string = '/', fromMounted: boolean = false): Promise<void> => {
  isUpdating.value = true
  try {
    const page = fromMounted ? syncFromUrl().page : 1
    const success = await browser.loadContents(dir, page)

    if (fromMounted && !success) {
      return
    }

    updateUrl(dir, page)
  } finally {
    isUpdating.value = false
  }
}

const handlePageChange = async (page: number): Promise<void> => {
  await browser.changePage(page)
  updateUrl(browserPath.value, page)
}

const handleChangeSort = async (by: string): Promise<void> => {
  await browser.changeSort(by)
  updateUrl(browserPath.value, 1)
}

const event_handler = (e: Event): void => {
  const evt = e as PopStateEvent
  if (!evt.state) {
    return
  }

  if (evt.state.path === browserPath.value && window.location.search === route.fullPath.split('?')[1]) {
    return
  }

  reloadContent(evt.state.path, true)
}

onMounted(async () => {
  document.addEventListener('popstate', event_handler as EventListener)
  await reloadContent(initialPath, true)
})

onBeforeUnmount(() => document.removeEventListener('popstate', event_handler as EventListener))

const makeBreadCrumb = (path: string): { name: string, link: string, path: string }[] => {
  const baseLink = '/'

  path = path.replace(/^\/+/, '').replace(/\/+$/, '')

  const links = []
  links.push({
    name: 'Home',
    link: baseLink,
    path: baseLink
  })

  const parts = path.split('/')
  parts.forEach((part, index) => {
    const path = baseLink + parts.slice(0, index + 1).join('/')
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

  document.querySelector('body')?.setAttribute("style", `opacity: ${v ? 1 : bg_opacity.value}`)
})

const setIcon = (item: FileItem): string => {
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

const toggleFilter = (): void => {
  show_filter.value = !show_filter.value
  if (!show_filter.value) {
    localSearch.value = ''
    return
  }

  awaitElement('#search', (e: Element) => (e as HTMLElement).focus())
}

const handleCreateDirectory = async (): Promise<void> => {
  if (!config.app.browser_control_enabled) {
    return
  }

  const { status, value: newDir } = await dialog.promptDialog({
    title: 'Create New Directory',
    message: `Enter name for new directory in '${browserPath.value || '/'}':`,
    initial: '',
    confirmText: 'Create',
    cancelText: 'Cancel',
  })

  if (true !== status || !newDir) {
    return
  }

  const success = await browser.createDirectory(browserPath.value, newDir)
  if (success) {
    await reloadContent(browserPath.value, true)
  }
}

const handleAction = async (action: string, item: FileItem): Promise<void> => {
  if (!config.app.browser_control_enabled) {
    return
  }

  if ('rename' === action) {
    const moveSideCars = 'file' === item.type ? ' (and its sidecars)' : ''
    const { status, value: newName } = await dialog.promptDialog({
      title: 'Rename Item',
      message: `Enter new name for '${item.name}'${moveSideCars}:`,
      initial: item.name,
      confirmText: 'Rename',
      cancelText: 'Cancel',
    })
    if (true !== status) {
      return
    }

    const success = await browser.renameItem(item, newName)
    if (success) {
      await reloadContent(browserPath.value, true)
    }
    return
  }

  if ('delete' === action) {
    const msg = item.is_dir ? `Delete '${item.name}' and all its contents?` : `Delete file '${item.name}'?`
    const { status } = await dialog.confirmDialog({
      title: 'Delete Confirmation',
      message: msg,
      confirmText: 'Delete',
      cancelText: 'Cancel',
      confirmColor: 'is-danger',
    })

    if (true !== status) {
      return
    }

    await browser.deleteItem(item)
    return
  }

  if ('move' === action) {
    const moveSideCars = 'file' === item.type ? ' (and its sidecars)' : ''
    const { status, value: newPath } = await dialog.promptDialog({
      title: 'Move Item',
      message: `Enter new path for '${item.name}'${moveSideCars}:`,
      initial: item.path.replace(/[^/]+$/, '') || '/',
      confirmText: 'Move',
      cancelText: 'Cancel',
    })

    if (true !== status) {
      return
    }

    const success = await browser.moveItem(item, newPath)
    if (success) {
      await reloadContent(browserPath.value, true)
    }
    return
  }
}

const handleDeleteSelected = async () => {
  if (selectedElms.value.length < 1) {
    toast.error('No items selected.')
    return
  }

  const rawHTML = `<ul>` + selectedElms.value.map(p => {
    const item = items.value.find(i => i.path === p)
    if (!item) {
      return ''
    }
    const color = 'dir' === item.type ? 'has-text-danger is-bold' : ''

    return `<li><span class="icon"><i class="fa-solid ${setIcon(item)}"></i></span> <span class="${color}">${item.name}</span></li>`
  }).join('') + `</ul>`

  const { status } = await dialog.confirmDialog({
    title: 'Delete Confirmation',
    message: `Delete the following items?`,
    rawHTML: rawHTML,
    confirmText: 'Delete',
    cancelText: 'Cancel',
    confirmColor: 'is-danger',
  })

  if (true !== status) {
    selectedElms.value = []
    return
  }

  await browser.deleteSelected()
}

const handleMoveSelected = async () => {
  if (selectedElms.value.length < 1) {
    toast.error('No items selected.')
    return
  }

  const { status, value: newPath } = await dialog.promptDialog({
    title: 'Move Items',
    message: `Enter new path for selected items:`,
    initial: browserPath.value || '/',
    confirmText: 'Move',
    confirmColor: 'is-danger',
    cancelText: 'Cancel',
  })

  if (true !== status || !newPath || newPath === browserPath.value) {
    selectedElms.value = []
    return
  }

  await browser.moveSelected(newPath)
}
</script>
