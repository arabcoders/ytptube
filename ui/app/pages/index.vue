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
              <button class="button is-danger" @click="resumeDownload" v-else v-tooltip.bottom="'Resume downloading.'">
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
                    :class="{ 'fa-table': display_style !== 'list', 'fa-table-list': display_style === 'list' }" /></span>
                <span v-if="!isMobile">
                  {{ display_style === 'list' ? 'List' : 'Grid' }}
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

    <div v-if="config.is_loaded" class="columns is-multiline">
      <div class="column is-12">
        <DeprecatedNotice :version="config.app.app_version" title="Deprecation Notice" tone="warning"
          icon="fas fa-exclamation-triangle fa-fade fa-spin-10">
          <p>
            The following environment variables and features are deprecated and will be removed in
            <strong class="has-text-danger">v0.10.x</strong>
          </p>
          <ul>
            <li>
              The following ENVs <strong>YTP_KEEP_ARCHIVE</strong> and <strong>YTP_SOCKET_TIMEOUT</strong> will be
              removed.
              Their behavior will be part of the <strong>default presets</strong>. To keep your current behavior
              <strong>and avoid re-downloading</strong>, please add the following <strong>Command options for
                yt-dlp</strong> to your presets:
              <code>--socket-timeout 30 --download-archive %(config_path)s/archive.log</code>
            </li>
            <li>
              The global yt-dlp config file <strong>/config/ytdlp.cli</strong> will be removed. Please migrate to
              presets.
            </li>
            <li>The <strong>archive.manual.log</strong> feature has been removed.</li>
          </ul>
          <p>
            These changes help reduce confusion from multiple sources of truth. Going forward, <strong>presets</strong>
            and the <strong>Command options for yt-dlp</strong> will be the single source of truth.
          </p>
          <p>
            Notable changes in <strong>v0.10.x</strong>:
          </p>
          <ul>
            <li>
              The file browser feature is going to be enabled by default. and the associated ENV
              <strong>YTP_BROWSER_ENABLED</strong> will be removed, <strong>YTP_BROWSER_CONTROL_ENABLED</strong> will
              remain and
              will default to <strong>false</strong>.
            </li>
            <li>
              The <strong>Basic mode</strong> (which limited the interface to just the new download form) along it's
              associated ENV <strong>YTP_BASIC_MODE</strong> is being removed. Everything except what is available
              behind configurable flag will become part of the standard interface.
            </li>
          </ul>
        </DeprecatedNotice>
      </div>
    </div>

    <NewDownload v-if="config.showForm || config.app.basic_mode"
      @getInfo="(url: string, preset: string = '', cli: string = '') => view_info(url, false, preset, cli)"
      :item="item_form" @clear_form="item_form = {}" />
    <Queue @getInfo="(url: string, preset: string = '', cli: string = '') => view_info(url, false, preset, cli)"
      :thumbnails="show_thumbnail" :query="query" @getItemInfo="(id: string) => view_info(`/api/history/${id}`, true)"
      @clear_search="query = ''" />
    <History @getInfo="(url: string, preset: string = '', cli: string = '') => view_info(url, false, preset, cli)"
      @add_new="(item: Partial<StoreItem>) => toNewDownload(item)" :query="query" :thumbnails="show_thumbnail"
      @getItemInfo="(id: string) => view_info(`/api/history/${id}`, true)" @clear_search="query = ''" />
    <GetInfo v-if="info_view.url" :link="info_view.url" :preset="info_view.preset" :cli="info_view.cli"
      :useUrl="info_view.useUrl" @closeModel="close_info()" />
    <ConfirmDialog v-if="dialog_confirm.visible" :visible="dialog_confirm.visible" :title="dialog_confirm.title"
      :html_message="dialog_confirm.html_message" :options="dialog_confirm.options" @confirm="dialog_confirm.confirm"
      @cancel="() => dialog_confirm.visible = false" />
  </div>
</template>

<script setup lang="ts">
import { useStorage } from '@vueuse/core'
import DeprecatedNotice from '~/components/DeprecatedNotice.vue'
import type { item_request } from '~/types/item'
import type { StoreItem } from '~/types/store'

const config = useConfigStore()
const stateStore = useStateStore()
const socket = useSocketStore()
const bg_enable = useStorage<boolean>('random_bg', true)
const bg_opacity = useStorage<number>('random_bg_opacity', 0.95)
const display_style = useStorage<string>('display_style', 'grid')
const show_thumbnail = useStorage<boolean>('show_thumbnail', true)
const isMobile = useMediaQuery({ maxWidth: 1024 })

const info_view = ref({
  url: '',
  preset: '',
  cli: '',
  useUrl: false,
}) as Ref<{ url: string, preset: string, cli: string, useUrl: boolean }>
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


const resumeDownload = async () => await request('/api/system/resume', { method: 'POST' })

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
  dialog_confirm.value.confirm = async () => {
    await request('/api/system/pause', { method: 'POST' })
    dialog_confirm.value.visible = false
  }
}

const close_info = () => {
  info_view.value.url = ''
  info_view.value.preset = ''
  info_view.value.useUrl = false
}

const view_info = (url: string, useUrl: boolean = false, preset: string = '', cli: string = '') => {
  info_view.value.url = url
  info_view.value.useUrl = useUrl
  info_view.value.preset = preset
  info_view.value.cli = cli
}

watch(() => info_view.value.url, v => {
  if (!bg_enable.value) {
    return
  }

  document.querySelector('body')?.setAttribute("style", `opacity: ${v ? 1 : bg_opacity.value}`)
})

const changeDisplay = () => display_style.value = display_style.value === 'grid' ? 'list' : 'grid'

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
