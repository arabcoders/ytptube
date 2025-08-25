<template>
  <div>
    <div class="mt-1 columns is-multiline">
      <div class="column is-12 is-clearfix is-unselectable">
        <span class="title is-4">
          <span class="icon-text">
            <span class="icon"><i class="fa-solid fa-download" /></span>
            <span>Downloads</span>
          </span>
        </span>

        <div class="is-pulled-right" v-if="socket.isConnected">
          <div class="field is-grouped">
            <p class="control has-icons-left" v-if="toggleFilter">
              <input type="search" v-model.lazy="query" class="input" id="filter"
                placeholder="Filter displayed content">
              <span class="icon is-left"><i class="fas fa-filter" /></span>
            </p>

            <p class="control">
              <button class="button is-danger is-light" @click="toggleFilter = !toggleFilter">
                <span class="icon"><i class="fas fa-filter" /></span>
                <span v-if="!isMobile">Filter</span>
              </button>
            </p>

            <p class="control" v-if="!config.app.basic_mode && false === config.app.basic_mode">
              <button class="button is-warning" @click="pauseDownload" v-if="false === config.paused">
                <span class="icon"><i class="fas fa-pause" /></span>
                <span v-if="!isMobile">Pause</span>
              </button>
              <button class="button is-danger" @click="socket.emit('resume', {})" v-else
                v-tooltip.bottom="'Resume downloading.'">
                <span class="icon"><i class="fas fa-play" /></span>
                <span v-if="!isMobile">Resume</span>
              </button>
            </p>

            <p class="control" v-if="!config.app.basic_mode && false === config.app.basic_mode">
              <button class="button is-primary has-tooltip-bottom" @click="config.showForm = !config.showForm">
                <span class="icon"><i class="fa-solid fa-plus" /></span>
                <span v-if="!isMobile">New Download</span>
              </button>
            </p>

            <p class="control">
              <button v-tooltip.bottom="'Change display style'" class="button has-tooltip-bottom"
                @click="() => changeDisplay()">
                <span class="icon"><i class="fa-solid"
                    :class="{ 'fa-table': display_style === 'cards', 'fa-table-list': display_style === 'list' }" /></span>
                <span v-if="!isMobile">
                  {{ display_style === 'cards' ? 'Cards' : 'List' }}
                </span>
              </button>
            </p>
          </div>
        </div>
        <div v-if="!isMobile">
          <span class="subtitle">
            Queued and completed downloads are displayed here.
          </span>
        </div>
      </div>
    </div>

    <NewDownload v-if="config.showForm || config.app.basic_mode"
      @getInfo="(url: string, preset: string = '') => view_info(url, false, preset)" :item="item_form"
      @clear_form="item_form = {}" @remove_archive="" />
    <Queue @getInfo="(url: string, preset: string = '') => view_info(url, false, preset)" :thumbnails="show_thumbnail"
      :query="query" @getItemInfo="(id: string) => view_info(`/api/history/${id}`, true)" @clear_search="query = ''" />
    <History @getInfo="(url: string, preset: string = '') => view_info(url, false, preset)"
      @add_new="(item: Partial<StoreItem>) => toNewDownload(item)" :query="query" :thumbnails="show_thumbnail"
      @getItemInfo="(id: string) => view_info(`/api/history/${id}`, true)" @clear_search="query = ''" />
    <GetInfo v-if="info_view.url" :link="info_view.url" :preset="info_view.preset" :useUrl="info_view.useUrl"
      @closeModel="close_info()" />
    <ConfirmDialog v-if="dialog_confirm.visible" :visible="dialog_confirm.visible" :title="dialog_confirm.title"
      :html_message="dialog_confirm.html_message" :options="dialog_confirm.options" @confirm="dialog_confirm.confirm"
      @cancel="() => dialog_confirm.visible = false" />
  </div>
</template>

<script setup lang="ts">
import { useStorage } from '@vueuse/core'
import type { item_request } from '~/types/item'
import type { StoreItem } from '~/types/store'

const config = useConfigStore()
const stateStore = useStateStore()
const socket = useSocketStore()
const bg_enable = useStorage<boolean>('random_bg', true)
const bg_opacity = useStorage<number>('random_bg_opacity', 0.95)
const display_style = useStorage<string>('display_style', 'cards')
const show_thumbnail = useStorage<boolean>('show_thumbnail', true)

const info_view = ref({
  url: '',
  preset: '',
  useUrl: false,
}) as Ref<{ url: string, preset: string, useUrl: boolean }>
const item_form = ref<item_request | object>({})
const query = ref()
const toggleFilter = ref(false)
const dialog_confirm = ref({
  visible: false,
  title: 'Confirm Action',
  confirm: () => { },
  html_message: '',
  options: [],
})

const isMobile = useMediaQuery({ maxWidth: 1024 })

watch(toggleFilter, () => {
  if (!toggleFilter.value) {
    query.value = ''
  }
});

onMounted(() => {
  if (!config.app.ui_update_title) {
    useHead({ title: 'YTPTube' })
    return
  }
  useHead({ title: `YTPTube: ( ${Object.keys(stateStore.queue).length || 0}/${config.app.max_workers} | ${Object.keys(stateStore.history).length || 0} )` })
})

watch(() => stateStore.history, () => {
  if (!config.app.ui_update_title) {
    return
  }
  useHead({ title: `YTPTube: ( ${Object.keys(stateStore.queue).length || 0}/${config.app.max_workers}  | ${Object.keys(stateStore.history).length || 0} )` })
}, { deep: true })

watch(() => stateStore.queue, () => {
  if (!config.app.ui_update_title) {
    return
  }
  useHead({ title: `YTPTube: ( ${Object.keys(stateStore.queue).length || 0}/${config.app.max_workers}  | ${Object.keys(stateStore.history).length || 0} )` })
}, { deep: true })


const pauseDownload = () => {
  dialog_confirm.value.visible = true
  dialog_confirm.value.html_message = `
  <span class="icon-text">
    <span class="icon"><i class="fa-solid fa-exclamation-triangle"></i></span>
    <span class="is-bold">Pause All non-active downloads?</span>
  </span>
  <br>
  <span class="has-text-danger">
    <ul>
      <li>This will not stop downloads that are currently in progress.</li>
      <li>If you are in middle of adding a playlist/channel, it will break and stop adding more items.</li>
    </ul>
  </span>`
  dialog_confirm.value.confirm = () => {
    socket.emit('pause', {})
    dialog_confirm.value.visible = false
  }
}

const close_info = () => {
  info_view.value.url = ''
  info_view.value.preset = ''
  info_view.value.useUrl = false
}

const view_info = (url: string, useUrl: boolean = false, preset: string = '') => {
  info_view.value.url = url
  info_view.value.useUrl = useUrl
  info_view.value.preset = preset
}

watch(() => info_view.value.url, v => {
  if (!bg_enable.value) {
    return
  }

  document.querySelector('body')?.setAttribute("style", `opacity: ${v ? 1 : bg_opacity.value}`)
})

const changeDisplay = () => display_style.value = display_style.value === 'cards' ? 'list' : 'cards'

const toNewDownload = async (item: item_request | Partial<StoreItem>) => {
  if (!item) {
    return
  }

  if (config.showForm) {
    config.showForm = false
    await nextTick()
  }

  item_form.value = item

  await nextTick()
  config.showForm = true
}
</script>
