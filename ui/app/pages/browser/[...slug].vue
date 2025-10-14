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
              <button class="button is-danger is-light" @click="toggleFilter">
                <span class="icon"><i class="fas fa-filter" /></span>
                <span v-if="!isMobile">Filter</span>
              </button>
            </div>

            <p class="control">
              <button class="button is-info is-light" @click="createDirectory(path)"
                v-if="config.app.browser_control_enabled">
                <span class="icon"><i class="fas fa-folder-plus" /></span>
                <span v-if="!isMobile">New Folder</span>
              </button>
            </p>
            <p class="control">
              <button class="button is-info" @click="reloadContent(path, true)" :class="{ 'is-loading': isLoading }"
                :disabled="!socket.isConnected || isLoading">
                <span class="icon"><i class="fas fa-refresh" /></span>
                <span v-if="!isMobile">Reload</span>
              </button>
            </p>
          </div>
        </div>
      </div>
    </div>

    <div class="columns is-multiline" v-if="config.app.browser_control_enabled">
      <div class="column is-half-mobile">
        <button type="button" class="button is-fullwidth is-danger" @click="deleteSelected"
          :disabled="selectedElms.length < 1 || isLoading || items.length < 1">
          <span class="icon-text is-block">
            <span class="icon"><i class="fa-solid fa-trash-can" /></span>
            <span>Delete {{ selectedElms.length > 0 ? selectedElms.length : '' }} items</span>
          </span>
        </button>
      </div>
      <div class="column is-half-mobile">
        <button type="button" class="button is-fullwidth is-link" @click="moveSelected"
          :disabled="selectedElms.length < 1 || isLoading || items.length < 1">
          <span class="icon-text is-block">
            <span class="icon"><i class="fa-solid fa-arrows-alt" /></span>
            <span>Move {{ selectedElms.length > 0 ? selectedElms.length : '' }} items</span>
          </span>
        </button>
      </div>
    </div>

    <div class="columns is-multiline">
      <div class="column is-12" v-if="items && items.length > 0">
        <div :class="{ 'table-container': table_container }">
          <table class="table is-striped is-hoverable is-fullwidth is-bordered"
            style="min-width: 1300px; table-layout: fixed;">
            <thead>
              <tr class="has-text-centered is-unselectable">
                <th width="5%" v-if="config.app.browser_control_enabled">
                  <input type="checkbox" v-model="masterSelectAll" />
                </th>
                <th width="6%" @click="changeSort('type')">
                  #
                  <span class="icon" v-if="'type' === sort_by">
                    <i class="fas"
                      :class="{ 'fa-sort-up': 'desc' === sort_order, 'fa-sort-down': 'asc' === sort_order }" />
                  </span>
                </th>
                <th width="65%" @click="changeSort('name')">
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
                <td class="has-text-centered is-text-overflow is-unselectable is-vcentered">
                  {{ 'file' === item.type ? formatBytes(item.size) : ucFirst(item.type) }}
                </td>
                <td class="has-text-centered is-text-overflow is-unselectable is-vcentered">
                  <span :data-datetime="item.mtime" v-tooltip="moment(item.mtime).format('MMMM Do YYYY, h:mm:ss a')">
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
    <ConfirmDialog v-if="dialog_confirm.visible" :visible="dialog_confirm.visible" :title="dialog_confirm.title"
      :message="dialog_confirm.message" :options="dialog_confirm.options" @confirm="dialog_confirm.confirm"
      :html_message="dialog_confirm.html_message" @cancel="dialog_confirm = reset_dialog()" />
  </div>
</template>

<script setup lang="ts">
import moment from 'moment'
import { useStorage } from '@vueuse/core'
import type { FileItem, FileBrowserResponse } from '~/types/filebrowser'

const route = useRoute()
const toast = useNotification()
const config = useConfigStore()
const socket = useSocketStore()
const isMobile = useMediaQuery({ maxWidth: 1024 })
const dialog = useDialog()

const bg_enable = useStorage('random_bg', true)
const bg_opacity = useStorage('random_bg_opacity', 0.95)
const sort_by = useStorage('sort_by', 'name')
const sort_order = useStorage('sort_order', 'asc')

const selectedElms = ref<string[]>([])
const masterSelectAll = ref(false)

const isLoading = ref<boolean>(false)
const initialLoad = ref<boolean>(true)
const items = ref<FileItem[]>([])
const path = ref<string>((() => {
  const slug = route.params.slug
  if (Array.isArray(slug) && slug.length > 0) {
    return '/' + slug.join('/')
  }
  return '/'
})())
const table_container = ref<boolean>(true)
const search = ref<string>('')
const show_filter = ref<boolean>(false)

const reset_dialog = () => ({
  visible: false,
  title: 'Confirm Action',
  confirm: (_opts: any) => { },
  message: '',
  html_message: '',
  options: [],
});

const dialog_confirm = ref(reset_dialog())

watch(masterSelectAll, v => {
  if (v) {
    selectedElms.value = filteredItems.value.map(i => i.path)
  } else {
    selectedElms.value = []
  }
})

const filteredItems = computed<FileItem[]>(() => {
  if (!search.value) {
    return sortedItems(items.value)
  }

  const searchLower = search.value.toLowerCase()
  return sortedItems(items.value.filter((item: FileItem) => {
    return item.name.toLowerCase().includes(searchLower)
  }))
})

const sortedItems = (items: FileItem[]): FileItem[] => {

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
      const aDate = new Date(a.mtime)
      const bDate = new Date(b.mtime)
      return 'asc' === sort_order.value ? aDate.getTime() - bDate.getTime() : bDate.getTime() - aDate.getTime()
    })
  }

  if (sort_by.value === 'type') {
    return items.sort((a, b) => {
      return 'asc' === sort_order.value ? a.content_type.localeCompare(b.content_type) : b.content_type.localeCompare(a.content_type)
    })
  }

  return items
}

const model_item = ref<any>()
const closeModel = (): void => { model_item.value = null }

watch(() => socket.isConnected, async () => {
  if (socket.isConnected && initialLoad.value) {
    await reloadContent(path.value, true)
    initialLoad.value = false
  }
})

const handleClick = (item: FileItem): void => {
  if (true === ['video','audio'].includes(item.content_type)) {
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

  window.location.href = makeDownload(config, { "filename": item.path, "folder": "", "extras": {} })
}

const reloadContent = async (dir: string = '/', fromMounted: boolean = false): Promise<void> => {
  try {
    isLoading.value = true

    if (typeof dir !== 'string') {
      dir = '/'
    }

    dir = encodePath(sTrim(dir, '/'))

    const response = await request(`/api/file/browser/${sTrim(dir, '/')}`)

    if (fromMounted && !response.ok) {
      return
    }

    items.value = []
    search.value = ''
    selectedElms.value = []
    show_filter.value = false
    masterSelectAll.value = false

    const data = await response.json() as FileBrowserResponse

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

    useHead({ title: decodeURIComponent(title) })
  } catch (e: any) {
    if (fromMounted) {
      return
    }
    console.error(e)
    toast.error('Failed to load file browser contents.')
  } finally {
    isLoading.value = false
  }
}

const event_handler = (e: Event): void => {
  const evt = e as PopStateEvent
  if (!evt.state) {
    return
  }

  if (evt.state.path === path.value || evt.state.path === window.location.pathname) {
    return
  }

  reloadContent(evt.state.path, true)
}

onMounted(async () => {
  if (socket.isConnected && initialLoad.value) {
    await reloadContent(path.value, true)
  }

  document.addEventListener('popstate', event_handler as EventListener)
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

  // -- explode path and create links
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

const changeSort = (by: string): void => {
  if (!['name', 'size', 'date', 'type'].includes(by)) {
    return
  }

  if (by !== sort_by.value) {
    sort_by.value = by
  }

  sort_order.value = 'asc' === sort_order.value ? 'desc' : 'asc'
}

const toggleFilter = (): void => {
  show_filter.value = !show_filter.value
  if (!show_filter.value) {
    search.value = ''
    return
  }

  awaitElement('#search', (e: Element) => (e as HTMLElement).focus())
}

const createDirectory = async (dir: string): Promise<void> => {
  if (!config.app.browser_control_enabled) {
    return
  }

  const { status, value: newDir } = await dialog.promptDialog({
    title: 'Create New Directory',
    message: `Enter name for new directory in '${dir || '/'}':`,
    initial: '',
    confirmText: 'Create',
    cancelText: 'Cancel',
  })

  if (true !== status || !newDir) {
    return
  }

  const new_dir = sTrim(newDir, '/')
  if (!new_dir || new_dir === dir) {
    return
  }

  await actionRequest({ path: dir || '/' } as FileItem, 'directory', { new_dir: new_dir }, (_item, _action, _data) => {
    reloadContent(path.value, true)
    toast.success(`Successfully created '${new_dir}'.`)
  })
}

const handleAction = async (action: string, item: FileItem): Promise<void> => {
  if (!config.app.browser_control_enabled) {
    return
  }

  if ('rename' === action) {
    const { status, value: newName } = await dialog.promptDialog({
      title: 'Rename Item',
      message: `Enter new name for '${item.name}':`,
      initial: item.name,
      confirmText: 'Rename',
      cancelText: 'Cancel',
    })
    if (true !== status) {
      return
    }

    const new_name = newName.trim()
    if (!new_name || new_name === item.name) {
      return
    }

    await actionRequest(item, 'rename', { new_name: new_name }, (item, _, data) => {
      item.name = data.new_name
      item.path = item.path.replace(/[^/]+$/, data.new_name)
      toast.success(`Renamed '${item.name}'.`)
    })
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

    await actionRequest(item, 'delete', {}, (item, _action, _data) => {
      items.value = items.value.filter(i => i.path !== item.path)
      toast.warning(`Deleted '${item.name}'.`)
    })

    return
  }

  if ('move' === action) {
    const { status, value: newPath } = await dialog.promptDialog({
      title: 'Move Item',
      message: `Enter new path for '${item.name}':`,
      initial: item.path.replace(/[^/]+$/, '') || '/',
      confirmText: 'Move',
      cancelText: 'Cancel',
    })

    if (true !== status) {
      return
    }

    const new_path = sTrim(newPath, '/') || '/'
    if (!new_path || new_path === item.path) {
      return
    }

    await actionRequest(item, 'move', { new_path: new_path }, (item, action, data) => {
      items.value = items.value.filter(i => i.path !== item.path)
      toast.success(`Moved '${item.name}' to '${data.new_path}'.`)
    })

    return
  }
}

const actionRequest = async (
  item: FileItem,
  action: string,
  data: Record<string, any>,
  cb: (item: FileItem, action: string, data: any) => void
): Promise<any> => {
  if (!config.app.browser_control_enabled) {
    return
  }

  if (!item || !action || !data) {
    return
  }

  try {
    const response = await request(`/api/file/actions`, {
      method: 'POST',
      body: JSON.stringify([{
        path: item.path,
        action: action,
        ...data
      }]),
    })

    if (!response.ok) {
      const error = await response.json()
      toast.error(`Failed to perform action: ${error.error || 'Unknown error'}`)
      return
    }

    const json = await response.json() as Array<{ path: string, status: boolean, error?: string }>
    json.forEach(i => {
      if (i.path !== item.path) {
        return
      }

      if (true !== i.status) {
        toast.error(`Failed to perform action: ${i.error || 'Unknown error'}`)
        return
      }

      if (cb && typeof cb === 'function') {
        cb(item, action, data)
      }
    });

    return response
  } catch (error: any) {
    console.error(error)
    toast.error(`Failed to perform action: ${error.message}`)
  }
}

const massAction = async (items: Array<{ path: string, action: string }>, cb: (item: any) => void): Promise<any> => {
  if (!config.app.browser_control_enabled) {
    return
  }

  if (!items || items.length < 1) {
    return
  }

  try {
    const response = await request(`/api/file/actions`, {
      method: 'POST',
      body: JSON.stringify(items),
    })

    if (!response.ok) {
      const error = await response.json()
      toast.error(`Failed to perform action: ${error.error || 'Unknown error'}`)
      return
    }

    const json = await response.json() as Array<{ path: string, status: boolean, error?: string }>
    json.forEach(i => {
      if (true !== i.status) {
        toast.error(`Failed to perform action on '${i.path}': ${i.error || 'Unknown error'}`)
        return
      }

      if (cb && typeof cb === 'function') {
        cb(i)
      }
    });

    return response
  } catch (error: any) {
    console.error(error)
    toast.error(`Failed to perform action: ${error.message}`)
  }
}

const deleteSelected = async () => {
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

  const actions = [] as Array<{ action: string, path: string }>
  selectedElms.value.forEach(p => {
    const item = items.value.find(i => i.path === p)
    if (!item) {
      return;
    }

    actions.push({ path: item.path, action: 'delete' })
  })

  await massAction(actions, i => {
    const item = items.value.find(it => it.path === i.path)
    if (!item) {
      return
    }
    items.value = items.value.filter(it => it.path !== i.path)
    toast.warning(`Deleted '${item.name}'.`)
  })
}

const moveSelected = async () => {
  if (selectedElms.value.length < 1) {
    toast.error('No items selected.')
    return
  }

  const { status, value: newPath } = await dialog.promptDialog({
    title: 'Move Items',
    message: `Enter new path for selected items:`,
    initial: path.value || '/',
    confirmText: 'Move',
    confirmColor: 'is-danger',
    cancelText: 'Cancel',
  })

  if (true !== status || !newPath || newPath === path.value) {
    selectedElms.value = []
    return
  }

  const actions = [] as Array<{ action: string, path: string, new_path: string }>
  selectedElms.value.forEach(p => {
    const item = items.value.find(i => i.path === p)
    if (!item) {
      return;
    }

    actions.push({
      path: item.path,
      action: 'move',
      new_path: sTrim(newPath, '/') || '/',
    })
  })

  await massAction(actions, i => {
    items.value = items.value.filter(it => it.path !== i.path)
    toast.success(`Moved '${i.path}' to '${sTrim(newPath, '/')}'.`)
  })
}

</script>
