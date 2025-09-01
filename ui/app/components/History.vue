<template>
  <h1 class="mt-3 is-size-3 is-clickable is-unselectable" @click="showCompleted = !showCompleted">
    <span class="icon-text title is-4">
      <span class="icon">
        <i :class="showCompleted ? 'fa-solid fa-arrow-up' : 'fa-solid fa-arrow-down'" />
      </span>
      <span>
        History <span v-if="hasItems">({{ stateStore.count('history') }})</span>
        <span v-if="selectedElms.length > 0">&nbsp;- Selected: {{ selectedElms.length }}</span>
      </span>
    </span>
  </h1>

  <div v-if="showCompleted">
    <div class="columns is-multiline is-mobile has-text-centered" v-if="hasItems">
      <div class="column is-half-mobile" v-if="display_style === 'cards'">
        <button type="button" class="button is-fullwidth is-ghost is-inverted"
          @click="masterSelectAll = !masterSelectAll">
          <span class="icon-text is-block">
            <span class="icon">
              <i :class="!masterSelectAll ? 'fa-regular fa-square-check' : 'fa-regular fa-square'" />
            </span>
            <span v-if="!masterSelectAll">Select All</span>
            <span v-else>Unselect All</span>
          </span>
        </button>
      </div>
      <div class="column is-half-mobile">
        <button type="button" class="button is-fullwidth is-link" @click="downloadSelected"
          :disabled="!hasDownloaded || !hasSelected"
          v-tooltip="!hasSelected || !hasDownloaded ? '' : 'Download items as zip'">
          <span class="icon-text is-block">
            <span class="icon"><i class="fa-solid fa-compress-alt" /></span>
            <span>Download</span>
          </span>
        </button>
      </div>
      <div class="column is-half-mobile">
        <button type="button" class="button is-fullwidth is-danger" @click="deleteSelectedItems"
          :disabled="!hasSelected">
          <span class="icon-text is-block">
            <span class="icon"><i class="fa-solid fa-trash-can" /></span>
            <span>{{ config.app.remove_files ? 'Remove' : 'Clear' }}</span>
          </span>
        </button>
      </div>
      <div class="column is-half-mobile" v-if="hasCompleted">
        <button type="button" class="button is-fullwidth is-primary is-inverted" @click="clearCompleted">
          <span class="icon-text is-block">
            <span class="icon"><i class="fa-solid fa-circle-check" /></span>
            <span>Clear Completed</span>
          </span>
        </button>
      </div>
      <div class="column is-half-mobile" v-if="hasIncomplete">
        <button type="button" class="button is-fullwidth is-info is-inverted" @click="clearIncomplete">
          <span class="icon-text is-block">
            <span class="icon"><i class="fa-solid fa-circle-xmark" /></span>
            <span>Clear Incomplete</span>
          </span>
        </button>
      </div>
      <div class="column is-half-mobile" v-if="hasIncomplete">
        <button type="button" class="button is-fullwidth is-warning is-inverted" @click="retryIncomplete">
          <span class="icon-text is-block">
            <span class="icon"><i class="fa-solid fa-rotate-right" /></span>
            <span>Retry Incomplete</span>
          </span>
        </button>
      </div>
      <div class="column is-1-tablet">
        <button type="button" class="button is-fullwidth" @click="direction = direction === 'desc' ? 'asc' : 'desc'">
          <span class="icon-text is-block">
            <span class="icon">
              <i class="fa-solid" :class="direction === 'desc' ? 'fa-arrow-down-a-z' : 'fa-arrow-up-a-z'" />
            </span>
          </span>
        </button>
      </div>
    </div>

    <div class="columns is-multiline" v-if="'list' === display_style">
      <div class="column is-12" v-if="hasItems">
        <div :class="{ 'table-container': table_container }">
          <table class="table is-striped is-hoverable is-fullwidth is-bordered"
            style="min-width: 1300px; table-layout: fixed;">
            <thead>
              <tr class="has-text-centered is-unselectable">
                <th width="5%" v-tooltip="masterSelectAll ? 'Unselect all' : 'Select all'">
                  <a href="#" @click.prevent="masterSelectAll = !masterSelectAll">
                    <span class="icon-text is-block">
                      <span class="icon">
                        <i class="fa-regular"
                          :class="{ 'fa-square-check': !masterSelectAll, 'fa-square': masterSelectAll }" />
                      </span>
                    </span>
                  </a>
                </th>
                <th width="40%">Video Title</th>
                <th width="15%">Status</th>
                <th width="15%">Created</th>
                <th width="10%">Size/Starts</th>
                <th width="20%">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in sortCompleted" :key="item._id">
                <td class="is-vcentered has-text-centered">
                  <label class="checkbox is-block">
                    <input class="completed-checkbox" type="checkbox" v-model="selectedElms"
                      :id="'checkbox-' + item._id" :value="item._id">
                  </label>
                </td>
                <td class="is-text-overflow is-vcentered">
                  <div class="is-inline is-pulled-right" v-if="item.extras?.duration">
                    <span class="tag is-info" v-if="item.extras?.duration">
                      {{ formatTime(item.extras.duration) }}
                    </span>
                  </div>
                  <div v-if="showThumbnails && item.extras.thumbnail">
                    <FloatingImage
                      :image="uri('/api/thumbnail?id=' + item._id + '&url=' + encodePath(item.extras.thumbnail))"
                      :title="`[${item.preset}] - ${item.title}`">
                      <div class="is-text-overflow">
                        <NuxtLink target="_blank" :href="item.url">{{ item.title }}</NuxtLink>
                      </div>
                    </FloatingImage>
                  </div>
                  <template v-else>
                    <div class="is-text-overflow" v-tooltip="`[${item.preset}] - ${item.title}`">
                      <NuxtLink target="_blank" :href="item.url">{{ item.title }}</NuxtLink>
                    </div>
                  </template>
                  <div v-if="item.error" class="is-text-overflow is-pointer" @click="toggle_class($event)">
                    <span class="has-text-danger">{{ item.error }}</span>
                  </div>
                  <div v-if="showMessage(item)" class="is-text-overflow is-pointer" @click="toggle_class($event)">
                    <span class="has-text-danger">{{ item.msg }}</span>
                  </div>
                </td>
                <td class="is-vcentered has-text-centered is-unselectable">
                  <span class="icon" :class="setIconColor(item)"><i :class="[setIcon(item), is_queued(item)]" /></span>
                  <span>{{ setStatus(item) }}</span>
                </td>
                <td class="is-vcentered has-text-centered is-unselectable">
                  <span class="user-hint" :date-datetime="item.datetime"
                    v-tooltip="moment(item.datetime).format('YYYY-M-DD H:mm Z')" v-rtime="item.datetime" />
                </td>
                <td class="is-vcentered has-text-centered is-unselectable"
                  v-if="item.live_in && 'not_live' === item.status">
                  <span :date-datetime="item.live_in" class="user-hint"
                    v-tooltip="'Will automatically be retried at: ' + moment(item.live_in).format('YYYY-M-DD H:mm Z')"
                    v-rtime="item.live_in" />
                </td>
                <td class="is-vcentered has-text-centered is-unselectable" v-else>
                  {{ item.file_size ? formatBytes(item.file_size) : '-' }}
                </td>
                <td class="is-vcentered is-items-center">
                  <div class="field is-grouped is-grouped-centered">
                    <div class="control" v-if="item.status != 'finished' || !item.filename">
                      <button class="button is-warning is-fullwidth is-small" v-tooltip="'Retry download'"
                        @click="() => retryItem(item, true)">
                        <span class="icon"><i class="fa-solid fa-rotate-right" /></span>
                      </button>
                    </div>
                    <div class="control" v-if="item.filename && item.status === 'finished'">
                      <a class="button is-link is-fullwidth is-small" :href="makeDownload(config, item)"
                        v-tooltip="'Download video'" :download="item.filename?.split('/').reverse()[0]">
                        <span class="icon"><i class="fa-solid fa-download" /></span>
                      </a>
                    </div>
                    <div class="control">
                      <button class="button is-danger is-fullwidth is-small" @click="removeItem(item)"
                        v-tooltip="config.app.remove_files ? 'Remove video' : 'Clear video'">
                        <span class="icon"><i class="fa-solid fa-trash-can" /></span>
                      </button>
                    </div>
                    <div class="control is-expanded" v-if="item.url && !config.app.basic_mode">
                      <Dropdown icons="fa-solid fa-cogs" @open_state="s => table_container = !s"
                        :button_classes="'is-small'" label="Actions">
                        <template v-if="'finished' === item.status && item.filename">
                          <NuxtLink @click="playVideo(item)" class="dropdown-item">
                            <span class="icon"><i class="fa-solid fa-play" /></span>
                            <span>Play video</span>
                          </NuxtLink>
                          <hr class="dropdown-divider" />
                        </template>
                        <template v-else-if="isEmbedable(item.url)">
                          <NuxtLink class="dropdown-item has-text-danger"
                            @click="embed_url = getEmbedable(item.url) as string">
                            <span class="icon"><i class="fa-solid fa-play" /></span>
                            <span>Play video</span>
                          </NuxtLink>
                          <hr class="dropdown-divider" />
                        </template>
                        <NuxtLink class="dropdown-item" @click="emitter('getInfo', item.url, item.preset, item.cli)">
                          <span class="icon"><i class="fa-solid fa-info" /></span>
                          <span>yt-dlp Information</span>
                        </NuxtLink>

                        <NuxtLink class="dropdown-item" @click="emitter('getItemInfo', item._id)">
                          <span class="icon"><i class="fa-solid fa-info-circle" /></span>
                          <span>Local Information</span>
                        </NuxtLink>

                        <hr class="dropdown-divider" />
                        <NuxtLink class="dropdown-item" @click="retryItem(item, true)">
                          <span class="icon"><i class="fa-solid fa-rotate-right" /></span>
                          <span>Add to download form</span>
                        </NuxtLink>

                        <template v-if="item.is_archivable && !item.is_archived">
                          <hr class="dropdown-divider" />
                          <NuxtLink class="dropdown-item has-text-danger" @click="addArchiveDialog(item)">
                            <span class="icon"><i class="fa-solid fa-box-archive" /></span>
                            <span>Add to archive</span>
                          </NuxtLink>
                        </template>

                        <template v-if="item.is_archivable && item.is_archived">
                          <hr class="dropdown-divider" />
                          <NuxtLink class="dropdown-item has-text-danger" @click="removeFromArchiveDialog(item)">
                            <span class="icon"><i class="fa-solid fa-box-archive" /></span>
                            <span>Remove from archive</span>
                          </NuxtLink>
                        </template>
                      </Dropdown>
                    </div>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="columns is-multiline" v-else>
      <LateLoader :unrender="true" :min-height="showThumbnails ? 410 : 210" class="column is-6"
        v-for="item in filteredItems(sortCompleted)" :key="item._id">
        <div class="card is-flex is-full-height is-flex-direction-column"
          :class="{ 'is-bordered-danger': item.status === 'error', 'is-bordered-info': item.live_in || item.is_live }">
          <header class="card-header">
            <div class="card-header-title is-text-overflow is-block" v-tooltip="item.title">
              <NuxtLink target="_blank" :href="item.url">{{ item.title }}</NuxtLink>
            </div>

            <div class="card-header-icon">
              <div class="field is-grouped">
                <div class="control">
                  <span class="tag is-info" v-if="item.extras?.duration">
                    {{ formatTime(item.extras.duration) }}
                  </span>
                </div>
                <div class="control">
                  <button @click="hideThumbnail = !hideThumbnail" v-if="thumbnails">
                    <span class="icon"><i class="fa-solid"
                        :class="{ 'fa-arrow-down': hideThumbnail, 'fa-arrow-up': !hideThumbnail, }" /></span>
                  </button>
                </div>
                <div class="control">
                  <label class="checkbox is-block">
                    <input class="completed-checkbox" type="checkbox" v-model="selectedElms"
                      :id="'checkbox-' + item._id" :value="item._id">
                  </label>
                </div>

              </div>
            </div>
          </header>
          <div v-if="showThumbnails" class="card-image">
            <figure class="image is-3by1">
              <span v-if="'finished' === item.status && item.filename" @click="playVideo(item)" class="play-overlay">
                <div class="play-icon"></div>
                <img @load="e => pImg(e)"
                  :src="uri('/api/thumbnail?id=' + item._id + '&url=' + encodePath(item.extras.thumbnail))"
                  v-if="item.extras?.thumbnail" />
                <img v-else src="/images/placeholder.png" />
              </span>
              <span v-else-if="isEmbedable(item.url)" @click="embed_url = getEmbedable(item.url) as string"
                class="play-overlay">
                <div class="play-icon embed-icon"></div>
                <img @load="e => pImg(e)"
                  :src="uri('/api/thumbnail?id=' + item._id + '&url=' + encodePath(item.extras.thumbnail))"
                  v-if="item.extras?.thumbnail" />
                <img v-else src="/images/placeholder.png" />
              </span>
              <template v-else>
                <img @load="e => pImg(e)" v-if="item.extras?.thumbnail"
                  :src="uri('/api/thumbnail?id=' + item._id + '&url=' + encodePath(item.extras.thumbnail))" />
                <img v-else src="/images/placeholder.png" />
              </template>
            </figure>
          </div>
          <div class="card-content">
            <div class="columns is-mobile is-multiline">
              <div class="column is-half-mobile has-text-centered is-text-overflow is-unselectable">
                <span class="icon" :class="setIconColor(item)"><i :class="[setIcon(item), is_queued(item)]" /></span>
                <span>{{ setStatus(item) }}</span>
              </div>
              <div class="column is-half-mobile has-text-centered is-text-overflow is-unselectable">
                <span class="icon"><i class="fa-solid fa-sliders" /></span>
                <span v-tooltip="`Preset: ${item.preset}`" class="user-hint">{{ item.preset }}</span>
              </div>
              <div class="column is-half-mobile has-text-centered is-text-overflow is-unselectable"
                v-if="'not_live' === item.status && (item.live_in || item.extras?.release_in)">
                <span :date-datetime="item.live_in || item.extras?.release_in" class="user-hint"
                  v-tooltip="'Will be downloaded at: ' + moment(item.live_in || item.extras?.release_in).format('YYYY-M-DD H:mm Z')"
                  v-rtime="item.live_in || item.extras?.release_in" />
              </div>
              <div class="column is-half-mobile has-text-centered is-text-overflow is-unselectable">
                <span class="user-hint" :date-datetime="item.datetime"
                  v-tooltip="moment(item.datetime).format('YYYY-M-DD H:mm Z')" v-rtime="item.datetime" />
              </div>
              <div class="column is-half-mobile has-text-centered is-text-overflow is-unselectable"
                v-if="item.file_size">
                <span class="has-tooltip" v-tooltip="`Path: ${makePath(item)}`">{{
                  formatBytes(item.file_size) }}</span>
              </div>
            </div>
            <div class="columns is-mobile is-multiline">
              <div class="column is-half-mobile" v-if="item.status != 'finished' || !item.filename">
                <a class="button is-warning is-fullwidth" @click="() => retryItem(item, false)">
                  <span class="icon-text is-block">
                    <span class="icon"><i class="fa-solid fa-rotate-right" /></span>
                    <span>Retry</span>
                  </span>
                </a>
              </div>

              <div class="column is-half-mobile" v-if="item.filename && item.status === 'finished'">
                <a class="button is-link is-fullwidth" :href="makeDownload(config, item)"
                  :download="item.filename?.split('/').reverse()[0]">
                  <span class="icon-text is-block">
                    <span class="icon"><i class="fa-solid fa-download" /></span>
                    <span>Download</span>
                  </span>
                </a>
              </div>

              <div class="column is-half-mobile">
                <a class="button is-danger is-fullwidth" @click="removeItem(item)">
                  <span class="icon-text is-block">
                    <span class="icon"><i class="fa-solid fa-trash-can" /></span>
                    <span>{{ config.app.remove_files ? 'Remove' : 'Clear' }}</span>
                  </span>
                </a>
              </div>

              <div class="column" v-if="!config.app.basic_mode">
                <Dropdown icons="fa-solid fa-cogs" label="Actions">
                  <template v-if="'finished' === item.status && item.filename">
                    <NuxtLink @click="playVideo(item)" class="dropdown-item">
                      <span class="icon"><i class="fa-solid fa-play" /></span>
                      <span>Play video</span>
                    </NuxtLink>
                    <hr class="dropdown-divider" />
                  </template>

                  <template v-else-if="isEmbedable(item.url)">
                    <NuxtLink class="dropdown-item has-text-danger"
                      @click="embed_url = getEmbedable(item.url) as string">
                      <span class="icon"><i class="fa-solid fa-play" /></span>
                      <span>Play video</span>
                    </NuxtLink>
                    <hr class="dropdown-divider" />
                  </template>

                  <NuxtLink class="dropdown-item" @click="emitter('getInfo', item.url, item.preset, item.cli)"
                    v-if="!config.app.basic_mode">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>yt-dlp Information</span>
                  </NuxtLink>

                  <NuxtLink class="dropdown-item" @click="emitter('getItemInfo', item._id)"
                    v-if="!config.app.basic_mode">
                    <span class="icon"><i class="fa-solid fa-info-circle" /></span>
                    <span>Local Information</span>
                  </NuxtLink>

                  <hr class="dropdown-divider" />
                  <NuxtLink class="dropdown-item" @click="retryItem(item, true)">
                    <span class="icon"><i class="fa-solid fa-rotate-right" /></span>
                    <span>Add to download form</span>
                  </NuxtLink>

                  <template v-if="item.is_archivable && !item.is_archived">
                    <hr class="dropdown-divider" />
                    <NuxtLink class="dropdown-item has-text-danger" @click="addArchiveDialog(item)">
                      <span class="icon"><i class="fa-solid fa-box-archive" /></span>
                      <span>Archive Item</span>
                    </NuxtLink>
                  </template>

                  <template v-if="item.is_archivable && item.is_archived">
                    <hr class="dropdown-divider" />
                    <NuxtLink class="dropdown-item has-text-danger" @click="removeFromArchiveDialog(item)">
                      <span class="icon"><i class="fa-solid fa-box-archive" /></span>
                      <span>Remove from archive</span>
                    </NuxtLink>
                  </template>
                </Dropdown>
              </div>

            </div>
            <div class="columns is-mobile is-multiline" v-if="item.error || showMessage(item)">
              <div class="column is-12" v-if="item.error">
                <div class="is-text-overflow is-pointer" @click="toggle_class($event)">
                  <span class="has-text-danger">{{ item.error }}</span>
                </div>
              </div>
              <div class="column is-12" v-if="showMessage(item)">
                <div class="is-text-overflow is-pointer" @click="toggle_class($event)">
                  <span class="has-text-danger">{{ item.msg }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </LateLoader>
    </div>

    <div class="columns is-multiline" v-if="!hasItems">
      <div class="column is-12">
        <Message message_class="has-background-warning-90 has-text-dark" title="No results for downloaded items."
          icon="fas fa-search" :useClose="true" @close="() => emitter('clear_search')" v-if="query">
          <span class="is-block">No results found for '<span class="is-underlined is-bold">{{ query }}</span>'.</span>
        </Message>
        <Message message_class="has-background-success-90 has-text-dark" title="No records in history."
          icon="fas fa-circle-check" v-else-if="socket.isConnected" />
        <Message message_class="has-background-info-90 has-text-dark" title="Connecting.." icon="fas fa-spinner fa-spin"
          v-else />
      </div>
    </div>

    <div class="modal is-active" v-if="video_item">
      <div class="modal-background" @click="closeVideo"></div>
      <div class="modal-content is-unbounded-model">
        <VideoPlayer type="default" :isMuted="false" autoplay="true" :isControls="true" :item="video_item"
          class="is-fullwidth" @closeModel="closeVideo" />
      </div>
      <button class="modal-close is-large" aria-label="close" @click="closeVideo"></button>
    </div>

    <div class="modal is-active" v-if="embed_url">
      <div class="modal-background" @click="embed_url = ''"></div>
      <div class="modal-content is-unbounded-model">
        <EmbedPlayer :url="embed_url" @closeModel="embed_url = ''" />
      </div>
      <button class="modal-close is-large" aria-label="close" @click="embed_url = ''"></button>
    </div>

    <ConfirmDialog v-if="dialog_confirm.visible" :visible="dialog_confirm.visible" :title="dialog_confirm.title"
      :message="dialog_confirm.message" :options="dialog_confirm.options" @confirm="dialog_confirm.confirm"
      @cancel="() => dialog_confirm.visible = false" />
  </div>
</template>
<script setup lang="ts">
import moment from 'moment'
import { useStorage } from '@vueuse/core'
import type { StoreItem } from '~/types/store'

const emitter = defineEmits<{
  (e: 'getInfo', url: string, preset: string, cli: string): void
  (e: 'add_new', item: Partial<StoreItem>): void
  (e: 'getItemInfo', id: string): void
  (e: 'clear_search'): void
}>()

const props = defineProps<{
  thumbnails?: boolean
  query?: string
}>()

const config = useConfigStore()
const stateStore = useStateStore()
const socket = useSocketStore()
const toast = useNotification()
const box = useConfirm()

const showCompleted = useStorage<boolean>('showCompleted', true)
const hideThumbnail = useStorage<boolean>('hideThumbnailHistory', false)
const direction = useStorage<'asc' | 'desc'>('sortCompleted', 'desc')
const display_style = useStorage<'cards' | 'list'>('display_style', 'cards')
const bg_enable = useStorage<boolean>('random_bg', true)
const bg_opacity = useStorage<number>('random_bg_opacity', 0.95)

const selectedElms = ref<string[]>([])
const masterSelectAll = ref(false)
const table_container = ref(false)
const embed_url = ref('')
const video_item = ref<StoreItem | null>(null)
const dialog_confirm = ref<{
  visible: boolean
  title: string
  confirm: (opts?: any) => void
  message: string
  options: { key: string; label: string }[]
}>({
  visible: false,
  title: 'Confirm Action',
  confirm: () => { },
  message: '',
  options: [],
})

const showThumbnails = computed(() => (props.thumbnails || true) && !hideThumbnail.value)

const playVideo = (item: StoreItem) => { video_item.value = item }
const closeVideo = () => { video_item.value = null }

const filteredItems = (items: StoreItem[]) => !props.query ? items : items.filter(filterItem)

const filterItem = (item: StoreItem) => {
  const q = props.query?.toLowerCase()
  if (!q) {
    return true
  }
  return Object.values(item).some(v =>
    typeof v === 'string' && v.toLowerCase().includes(q)
  )
}

watch(masterSelectAll, (value) => {
  if (value) {
    selectedElms.value = Object.values(stateStore.history).map((element: StoreItem) => element._id)
  } else {
    selectedElms.value = []
  }
})

const sortCompleted = computed(() => {
  const thisDirection = direction.value
  return Object.values(stateStore.history as Record<string, StoreItem>).sort((a, b) => {
    if ('asc' === thisDirection) {
      return new Date(a.datetime).getTime() - new Date(b.datetime).getTime()
    }
    return new Date(b.datetime).getTime() - new Date(a.datetime).getTime()
  })
})

const hasSelected = computed(() => selectedElms.value.length > 0)
const hasItems = computed(() => filteredItems(sortCompleted.value as StoreItem[]).length > 0)

const showMessage = (item: StoreItem) => {
  if (!item?.msg || item.msg === item?.error) {
    return false
  }
  return (item.msg?.length || 0) > 0
}

const hasIncomplete = computed(() => {
  if (Object.keys(stateStore.history)?.length < 0) {
    return false
  }
  for (const key in stateStore.history) {
    const element = stateStore.history[key] as StoreItem
    if (element.status !== 'finished') {
      return true
    }
  }
  return false
})

const hasCompleted = computed(() => {
  if (Object.keys(stateStore.history)?.length < 0) {
    return false
  }
  for (const key in stateStore.history) {
    const element = stateStore.history[key] as StoreItem
    if (element.status === 'finished') {
      return true
    }
  }
  return false
})

const hasDownloaded = computed(() => {
  if (Object.keys(stateStore.history)?.length < 0) {
    return false
  }
  for (const key in stateStore.history) {
    const element = stateStore.history[key] as StoreItem
    if (element.status === 'finished' && element.filename) {
      return true
    }
  }
  return false
})

const deleteSelectedItems = async () => {
  if (selectedElms.value.length < 1) {
    toast.error('No items selected.')
    return
  }
  let msg = `${config.app.remove_files ? 'Remove' : 'Clear'} '${selectedElms.value.length}' items?`
  if (true === config.app.remove_files) {
    msg += ' This will remove any associated files if they exists.'
  }
  if (false === (await box.confirm(msg, config.app.remove_files))) {
    return
  }
  for (const key in selectedElms.value) {
    const item_id = selectedElms.value[key]
    if (!item_id) {
      continue
    }
    const item = stateStore.get('history', item_id, {} as StoreItem) as StoreItem
    socket.emit('item_delete', {
      id: item._id,
      remove_file: config.app.remove_files,
    })
  }
  selectedElms.value = []
}

const clearCompleted = async () => {
  let msg = 'Clear all completed downloads?'
  if (false === (await box.confirm(msg))) {
    return
  }
  for (const key in stateStore.history) {
    if ('finished' === ag(stateStore.get('history', key, {} as StoreItem), 'status')) {
      socket.emit('item_delete', { id: stateStore.history[key]?._id, remove_file: false, })
    }
  }
}

const clearIncomplete = async () => {
  if (false === (await box.confirm('Clear all in-complete downloads?'))) {
    return
  }
  for (const key in stateStore.history) {
    if ((stateStore.history[key] as StoreItem).status !== 'finished') {
      socket.emit('item_delete', {
        id: stateStore.history[key]?._id,
        remove_file: false,
      })
    }
  }
}

const setIcon = (item: StoreItem) => {
  if ('finished' === item.status) {
    if (!item.filename) {
      return 'fa-solid fa-exclamation'
    }
    if (item.extras?.is_premiere) {
      return 'fa-solid fa-star'
    }
    return item.is_live ? 'fa-solid fa-globe' : 'fa-solid fa-circle-check'
  }
  if ('error' === item.status) {
    return 'fa-solid fa-circle-xmark'
  }
  if ('cancelled' === item.status) {
    return 'fa-solid fa-eject'
  }
  if ('not_live' === item.status) {
    return item.extras?.is_premiere ? 'fa-solid fa-star' : 'fa-solid fa-headset'
  }
  if ('skip' === item.status) {
    return 'fa-solid fa-ban'
  }
  return 'fa-solid fa-circle'
}

const setIconColor = (item: StoreItem) => {
  if ('finished' === item.status) {
    if (!item.filename) {
      return 'has-text-warning'
    }
    return 'has-text-success'
  }
  if ('not_live' === item.status) {
    return 'has-text-info'
  }
  if ('cancelled' === item.status || "skip" === item.status) {
    return 'has-text-warning'
  }
  return 'has-text-danger'
}

const setStatus = (item: StoreItem) => {
  if ('finished' === item.status) {
    if (item.extras?.is_premiere) {
      return 'Premiered'
    }
    return item.is_live ? 'Streamed' : 'Completed'
  }
  if ('error' === item.status) {
    return 'Error'
  }
  if ('cancelled' === item.status) {
    return 'Cancelled'
  }
  if ('not_live' === item.status) {
    if (item.extras?.is_premiere) {
      return 'Premiere'
    }
    return display_style.value === 'cards' ? 'Stream' : 'Live'
  }
  if ('skip' === item.status) {
    return 'Skipped'
  }
  return item.status
}

const retryIncomplete = async () => {
  if (false === (await box.confirm('Retry all incomplete downloads?'))) {
    return false
  }
  for (const key in stateStore.history) {
    const item = stateStore.get('history', key, {} as StoreItem) as StoreItem
    if ('finished' === item.status) {
      continue
    }
    retryItem(item)
  }
}

const addArchiveDialog = (item: StoreItem) => {
  dialog_confirm.value.visible = true
  dialog_confirm.value.title = 'Archive Item'
  dialog_confirm.value.message = `Archive '${item.title || item.id || item.url || '??'}'?`
  dialog_confirm.value.options = [{ key: 'remove_history', label: 'Also, Remove from history.' }]
  dialog_confirm.value.confirm = (opts: any) => archiveItem(item, opts)
}

const archiveItem = async (item: StoreItem, opts = {}) => {
  try {
    const req = await request(`/api/history/${item._id}/archive`, { method: 'POST' })
    const data = await req.json()
    dialog_confirm.value.visible = false
    if (!req.ok) {
      toast.error(data.error)
      return
    }
    toast.success(data.message ?? `Archived '${item.title || item.id || item.url || '??'}'.`)
  } catch (e: any) {
    console.error(e)
  }
  if (!(opts as any)?.remove_history) {
    return
  }
  socket.emit('item_delete', { id: item._id, remove_file: false })
}

const removeItem = async (item: StoreItem) => {
  let msg = `${config.app.remove_files ? 'Remove' : 'Clear'} '${item.title || item.id || item.url || '??'}'?`
  if (item.status === 'finished' && config.app.remove_files) {
    msg += ' This will remove any associated files if they exists.'
  }
  if (false === (await box.confirm(msg, Boolean(item.filename && config.app.remove_files)))) {
    return false
  }
  socket.emit('item_delete', {
    id: item._id,
    remove_file: config.app.remove_files
  })
}

const retryItem = (item: StoreItem, re_add = false) => {
  let item_req: Partial<StoreItem> = {
    url: item.url,
    preset: item.preset,
    folder: item.folder,
    cookies: item.cookies,
    template: item.template,
    cli: item?.cli,
    extras: toRaw(item?.extras || {}) ?? {},
    auto_start: item.auto_start,
  }

  socket.emit('item_delete', { id: item._id, remove_file: false })
  if (true === re_add) {
    toast.info('Cleared the item from history, and added it to the new download form.')
    emitter('add_new', item_req)
    return
  }
  socket.emit('add_url', item_req)
}

const pImg = (e: Event) => {
  const target = e.target as HTMLImageElement
  target.naturalHeight > target.naturalWidth && target.classList.add('image-portrait')
}

watch(video_item, v => {
  if (!bg_enable.value) {
    return
  }
  document.querySelector('body')?.setAttribute("style", `opacity: ${v ? 1 : bg_opacity.value}`)
})

watch(embed_url, v => {
  if (!bg_enable.value) {
    return
  }
  document.querySelector('body')?.setAttribute("style", `opacity: ${v ? 1 : bg_opacity.value}`)
})

const downloadSelected = async () => {
  if (selectedElms.value.length < 1) {
    toast.error('No items selected.')
    return
  }
  let files_list: string[] = []
  for (const key in selectedElms.value) {
    const item_id = selectedElms.value[key]
    if (!item_id) {
      continue
    }
    const item = stateStore.get('history', item_id, {} as StoreItem) as StoreItem
    if ('finished' !== item.status || !item.filename) {
      continue
    }
    files_list.push(item.folder ? item.folder + '/' + item.filename : item.filename)
  }
  selectedElms.value = []
  try {
    const response = await request('/api/file/download', {
      method: 'POST',
      body: JSON.stringify(files_list)
    })
    const json = await response.json()
    if (!response.ok) {
      toast.error(json.error || 'Failed to start download.')
      return
    }
    const token = json.token
    const body = document.querySelector('body')
    const link = document.createElement('a')
    link.href = uri(`/api/file/download/${token}`)
    link.setAttribute('target', '_blank')
    body?.appendChild(link)
    link.click()
    body?.removeChild(link)
  } catch (e: any) {
    console.error(e)
    toast.error(`Error: ${e.message}`)
    return
  }
}

const toggle_class = (e: Event) => ['is-text-overflow', 'is-word-break'].forEach(c => (e.currentTarget as HTMLElement).classList.toggle(c))

const removeFromArchiveDialog = (item: StoreItem) => {
  dialog_confirm.value.visible = true
  dialog_confirm.value.title = 'Remove from Archive'
  dialog_confirm.value.message = `Remove '${item.title || item.id || item.url || '??'}' from archive?`
  dialog_confirm.value.options = [
    { key: 'remove_history', label: 'Also, Remove from history.' },
    { key: 're_add', label: 'Re-add to download form.' },
  ]
  dialog_confirm.value.confirm = (opts: any) => removeFromArchive(item, opts)
}

const removeFromArchive = async (item: StoreItem, opts?: { re_add?: boolean, remove_history?: boolean }) => {
  try {
    const req = await request(`/api/history/${item._id}/archive`, { method: 'DELETE' })
    const data = await req.json()
    if (!req.ok) {
      toast.error(data.error)
    } else {
      toast.success(data.message || `Removed '${item.title || item.id || item.url || '??'}' from archive.`)
    }
  } catch (e: any) {
    console.error(e)
    toast.error(`Error: ${e.message}`)
  } finally {
    dialog_confirm.value.visible = false
  }

  if (opts?.re_add) {
    retryItem(item, true)
    return
  }

  if (opts?.remove_history) {
    socket.emit('item_delete', { id: item._id, remove_file: false })
  }
}

const is_queued = (item: StoreItem) => {
  if (!item?.status || 'not_live' !== item.status) {
    return ''
  }
  return item.live_in || item.extras?.live_in || item.extras?.release_in ? 'fa-spin fa-spin-10' : ''
}

const makePath = (item: StoreItem) => {
  if (!item?.filename) {
    return ''
  }
  const real_path = eTrim(item.download_dir, '/') + '/' + sTrim(item.filename, '/')
  return real_path.replace(config.app.download_path, '').replace(/^\//, '')
}
</script>
