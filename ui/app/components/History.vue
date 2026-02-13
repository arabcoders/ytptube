<template>
  <div class="columns is-multiline is-mobile has-text-centered is-justify-content-flex-end" v-if="hasItems">
    <div class="column is-narrow">
      <button type="button" class="button is-fullwidth" @click="masterSelectAll = !masterSelectAll"
        :class="{ 'has-text-primary': !masterSelectAll, 'has-text-danger': masterSelectAll }">
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
        <a class="dropdown-item has-text-link" @click="(hasDownloaded && hasSelected) ? downloadSelected() : null"
          :style="{ opacity: (!hasDownloaded || !hasSelected) ? 0.5 : 1, cursor: (!hasDownloaded || !hasSelected) ? 'not-allowed' : 'pointer' }"
          v-tooltip="!hasSelected || !hasDownloaded ? '' : 'Download items as zip'">
          <span class="icon"><i class="fa-solid fa-compress-alt" /></span>
          <span>Download</span>
        </a>
        <a class="dropdown-item has-text-danger" @click="hasSelected ? deleteSelectedItems() : null"
          :style="{ opacity: !hasSelected ? 0.5 : 1, cursor: !hasSelected ? 'not-allowed' : 'pointer' }">
          <span class="icon"><i class="fa-solid fa-trash-can" /></span>
          <span>{{ config.app.remove_files ? 'Remove' : 'Clear' }}</span>
        </a>
        <hr class="dropdown-divider" v-if="hasCompleted || hasIncomplete">
        <a v-if="hasCompleted" class="dropdown-item has-text-primary" @click="clearCompleted">
          <span class="icon"><i class="fa-solid fa-circle-check" /></span>
          <span>Clear Completed</span>
        </a>
        <a v-if="hasIncomplete" class="dropdown-item has-text-info" @click="clearIncomplete">
          <span class="icon"><i class="fa-solid fa-circle-xmark" /></span>
          <span>Clear Incomplete</span>
        </a>
        <a v-if="hasIncomplete" class="dropdown-item has-text-warning" @click="retryIncomplete">
          <span class="icon"><i class="fa-solid fa-rotate-right" /></span>
          <span>Retry Incomplete</span>
        </a>
      </Dropdown>
    </div>
    <div class="column is-narrow">
      <button type="button" class="button" @click="direction = direction === 'desc' ? 'asc' : 'desc'">
        <span class="icon-text is-block">
          <span class="icon">
            <i class="fa-solid" :class="direction === 'desc' ? 'fa-arrow-down-a-z' : 'fa-arrow-up-a-z'" />
          </span>
        </span>
      </button>
    </div>
  </div>

  <div class="columns is-multiline" v-if="paginationInfo.isLoading && !hasItems">
    <div class="column is-12">
      <div class="message is-info">
        <div class="message-body">
          <span class="icon-text">
            <span class="icon"> <i class="fa-solid fa-spinner fa-spin fa-2x" /> </span>
            <span class="ml-3">Loading history...</span>
          </span>
        </div>
      </div>
    </div>
  </div>

  <div class="columns is-multiline" v-if="'list' === display_style">
    <div class="column is-12" v-if="hasItems">
      <div class="table-container">
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
              <th width="40%">Title</th>
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
                  <input class="completed-checkbox" type="checkbox" v-model="selectedElms" :id="'checkbox-' + item._id"
                    :value="item._id">
                </label>
              </td>
              <td class="is-text-overflow is-vcentered">
                <div class="is-inline is-pulled-right" v-if="item.extras?.duration || show_popover">
                  <span class="tag is-info is-unselectable" v-if="item.extras?.duration">
                    {{ formatTime(item.extras.duration) }}
                  </span>

                  <Popover :showDelay="400" :maxWidth="450" v-if="show_popover">
                    <template #trigger>
                      <span class="icon is-pointer"><i class="fa-solid fa-info-circle" /></span>
                    </template>
                    <template #title>
                      <strong>
                        {{ item.title }}
                        <span class="tag is-info is-unselectable">{{ item.preset }}</span>
                      </strong>
                    </template>
                    <p v-if="getPath(config.app.download_path, item)">
                      <b>Path:</b> {{ getPath(config.app.download_path, item) }}
                    </p>
                    <hr
                      v-if="(showThumbnails && getImage(config.app.download_path, item, false)) || item.description" />
                    <img v-if="showThumbnails && getImage(config.app.download_path, item, false)"
                      :src="getImage(config.app.download_path, item, false)" class="card-image mt-2 mb-2" />
                    <p v-if="item.description">{{ item.description }}</p>
                  </Popover>
                </div>
                <div v-if="show_popover">
                  <div class="is-text-overflow">
                    <NuxtLink class="is-text-overflow" v-tooltip="`${item.preset}: ${item.title}`" target="_blank"
                      :href="item.url">
                      {{ item.title }}</NuxtLink>
                  </div>
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
                <span class="has-tooltip" :date-datetime="item.datetime"
                  v-tooltip="moment(item.datetime).format('YYYY-M-DD H:mm Z')" v-rtime="item.datetime" />
              </td>
              <td class="is-vcentered has-text-centered is-unselectable"
                v-if="'not_live' === item.status && (item.live_in || item.extras?.release_in)">
                <span :date-datetime="item.live_in || item.extras?.release_in" class="has-tooltip"
                  v-tooltip="`Retry at: ${moment(item.live_in || item.extras?.release_in).format('YYYY-M-DD H:mm Z')}`"
                  v-rtime="item.live_in || item.extras?.release_in" />
              </td>
              <td class="is-vcentered has-text-centered is-unselectable" v-else>
                {{ item.file_size ? formatBytes(item.file_size) : 'N/A' }}
              </td>
              <td class="is-vcentered is-items-center">
                <div class="field is-grouped is-grouped-centered">
                  <div class="control" v-if="!item.filename">
                    <button class="button is-warning is-fullwidth is-small" v-tooltip="'Retry download'"
                      @click="async () => await retryItem(item, true)">
                      <span class="icon"><i class="fa-solid fa-rotate-right" /></span>
                    </button>
                  </div>
                  <div class="control" v-if="item.filename">
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
                  <div class="control is-expanded" v-if="item.url">
                    <Dropdown icons="fa-solid fa-cogs" :button_classes="'is-small'" label="Actions">
                      <template v-if="item.filename">
                        <NuxtLink @click="playVideo(item)" class="dropdown-item">
                          <span class="icon"><i class="fa-solid fa-play" /></span>
                          <span>Play video</span>
                        </NuxtLink>
                        <template v-if="'error' === item.status">
                          <hr class="dropdown-divider" />
                          <NuxtLink class="dropdown-item has-text-warning"
                            @click="async () => await retryItem(item, true)">
                            <span class="icon"><i class="fa-solid fa-rotate-right" /></span>
                            <span>Retry download</span>
                          </NuxtLink>
                        </template>
                        <hr class="dropdown-divider" />
                        <NuxtLink class="dropdown-item has-text-info" @click="generateNfo(item)">
                          <span class="icon"><i class="fa-solid fa-file-code" /></span>
                          <span>Generate NFO</span>
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
                      <NuxtLink class="dropdown-item" @click="async () => await retryItem(item, true)">
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
          <div class="card-header-title is-text-overflow is-block">
            <NuxtLink target="_blank" v-tooltip="item.title" :href="item.url">{{ item.title }}</NuxtLink>
          </div>

          <div class="card-header-icon">
            <div class="field is-grouped">
              <div class="control">
                <span class="tag is-info is-unselectable" v-if="item.extras?.duration">
                  {{ formatTime(item.extras.duration) }}
                </span>
              </div>

              <div class="control" v-if="show_popover && getPath(config.app.download_path, item)">
                <Popover :showDelay="400" :maxWidth="550" v-if="show_popover">
                  <template #trigger>
                    <span class="icon"><i class="fa-solid fa-info-circle" /></span>
                  </template>
                  <template #title><strong>{{ item.title }}</strong></template>
                  <p v-if="getPath(config.app.download_path, item)">
                    <b>Path:</b> {{ getPath(config.app.download_path, item) }}
                  </p>
                  <template v-if="item.description">
                    <hr>
                    <p>{{ item.description }}</p>
                  </template>
                </Popover>
              </div>

              <div class="control">
                <button @click="hideThumbnail = !hideThumbnail" v-if="thumbnails">
                  <span class="icon"><i class="fa-solid"
                      :class="{ 'fa-arrow-down': hideThumbnail, 'fa-arrow-up': !hideThumbnail, }" /></span>
                </button>
              </div>
              <div class="control">
                <label class="checkbox is-block">
                  <input class="completed-checkbox" type="checkbox" v-model="selectedElms" :id="'checkbox-' + item._id"
                    :value="item._id">
                </label>
              </div>
            </div>
          </div>
        </header>
        <div v-if="showThumbnails" class="card-image">
          <figure :class="['image', thumbnail_ratio]">
            <span v-if="item.filename" @click="playVideo(item)" class="play-overlay">
              <div class="play-icon"></div>
              <img @load="pImg" @error="onImgError" :src="getImage(config.app.download_path, item)"
                v-if="getImage(config.app.download_path, item)" />
              <img v-else src="/images/placeholder.png" />
            </span>
            <span v-else-if="isEmbedable(item.url)" @click="embed_url = getEmbedable(item.url) as string"
              class="play-overlay">
              <div class="play-icon embed-icon"></div>
              <img @load="pImg" @error="onImgError" :src="getImage(config.app.download_path, item)"
                v-if="getImage(config.app.download_path, item)" />
              <img v-else src="/images/placeholder.png" />
            </span>
            <template v-else>
              <img @load="pImg" @error="onImgError" v-if="getImage(config.app.download_path, item)"
                :src="getImage(config.app.download_path, item)" />
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
              <span v-tooltip="`Preset: ${item.preset}`" class="has-tooltip">{{ item.preset }}</span>
            </div>
            <div class="column is-half-mobile has-text-centered is-text-overflow is-unselectable"
              v-if="'not_live' === item.status && (item.live_in || item.extras?.release_in)">
              <span :date-datetime="item.live_in || item.extras?.release_in" class="has-tooltip"
                v-tooltip="`Retry at: ${moment(item.live_in || item.extras?.release_in).format('YYYY-M-DD H:mm Z')}`"
                v-rtime="item.live_in || item.extras?.release_in" />
            </div>
            <div class="column is-half-mobile has-text-centered is-text-overflow is-unselectable">
              <span class="has-tooltip" :date-datetime="item.datetime"
                v-tooltip="moment(item.datetime).format('YYYY-M-DD H:mm Z')" v-rtime="item.datetime" />
            </div>
            <div class="column is-half-mobile has-text-centered is-text-overflow is-unselectable" v-if="item.file_size">
              {{ formatBytes(item.file_size) }}
            </div>
          </div>
          <div class="columns is-mobile is-multiline">
            <div class="column is-half-mobile" v-if="!item.filename">
              <a class="button is-warning is-fullwidth" @click="async () => retryItem(item, false)">
                <span class="icon-text is-block">
                  <span class="icon"><i class="fa-solid fa-rotate-right" /></span>
                  <span>Retry</span>
                </span>
              </a>
            </div>

            <div class="column is-half-mobile" v-if="item.filename">
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

            <div class="column">
              <Dropdown icons="fa-solid fa-cogs" label="Actions">
                <template v-if="item.filename">
                  <NuxtLink @click="playVideo(item)" class="dropdown-item">
                    <span class="icon"><i class="fa-solid fa-play" /></span>
                    <span>Play video</span>
                  </NuxtLink>
                  <template v-if="'error' === item.status">
                    <hr class="dropdown-divider" />
                    <NuxtLink class="dropdown-item has-text-warning" @click="async () => await retryItem(item, true)">
                      <span class="icon"><i class="fa-solid fa-rotate-right" /></span>
                      <span>Retry download</span>
                    </NuxtLink>
                  </template>
                  <hr class="dropdown-divider" />
                  <NuxtLink class="dropdown-item has-text-info" @click="generateNfo(item)">
                    <span class="icon"><i class="fa-solid fa-file-code" /></span>
                    <span>Generate NFO</span>
                  </NuxtLink>
                  <hr class="dropdown-divider" />
                </template>

                <template v-else-if="isEmbedable(item.url)">
                  <NuxtLink class="dropdown-item has-text-danger" @click="embed_url = getEmbedable(item.url) as string">
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
                <NuxtLink class="dropdown-item" @click="async () => await retryItem(item, true)">
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

  <div class="columns is-multiline" v-if="!hasItems && !paginationInfo.isLoading">
    <div class="column is-12">
      <Message class="is-warning" title="Filter results" icon="fas fa-search" :useClose="true"
        @close="() => emitter('clear_search')" v-if="query">
        <span class="is-block">No results found for: <code>{{ query }}</code>.</span>
        <hr>
        <p>
          You can search using any value shown in the item’s <code><span class="icon"><i
              class="fa-solid fa-info-circle" /></span> Local Information</code>. You can also do a targeted search
          using <code><u>key</u>:value</code>.
        </p>

        <h5>Examples:</h5>

        <ul>
          <li><code>youtube.com</code> - items containing that text</li>
          <li><code>is_live:true</code> - only live downloads</li>
          <li><code>source_name:task_name</code> - items added by the specified task.</li>
        </ul>
      </Message>
      <Message v-else class="is-primary" title="No items" icon="fas fa-exclamation-triangle" :new-style="true">
        <p>Download history is empty.</p>
      </Message>
    </div>
  </div>

  <div v-if="paginationInfo.isLoaded && paginationInfo.page < paginationInfo.total_pages" ref="loadMoreTrigger"
    class="columns is-centered mt-4">
    <div class="column is-narrow">
      <div v-if="paginationInfo.isLoading" class="has-text-centered">
        <span class="icon is-large has-text-info">
          <i class="fas fa-spinner fa-pulse fa-2x"></i>
        </span>
        <p class="is-size-7 has-text-grey mt-2">Loading more items...</p>
      </div>
    </div>
  </div>

  <div class="modal is-active" v-if="video_item">
    <div class="modal-background" @click="closeVideo"></div>
    <div class="modal-content is-unbounded-model">
      <VideoPlayer type="default" :isMuted="false" autoplay="true" :isControls="true" :item="video_item"
        class="is-fullwidth" @closeModel="closeVideo" @error="async (error: string) => await box.alert(error)" />
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

</template>

<script setup lang="ts">
import moment from 'moment'
import { useStorage, useIntersectionObserver } from '@vueuse/core'
import type { StoreItem } from '~/types/store'
import { useConfirm } from '~/composables/useConfirm'
import { deepIncludes, getPath, getImage } from '~/utils'
import type { item_request } from '~/types/item'

const emitter = defineEmits<{
  (e: 'getInfo', url: string, preset: string, cli: string): void
  (e: 'add_new', item: item_request): void
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
const display_style = useStorage<'grid' | 'list'>('display_style', 'grid')
const bg_enable = useStorage<boolean>('random_bg', true)
const bg_opacity = useStorage<number>('random_bg_opacity', 0.95)
const thumbnail_ratio = useStorage<'is-16by9' | 'is-3by1'>('thumbnail_ratio', 'is-3by1')
const show_popover = useStorage<boolean>('show_popover', true)

const selectedElms = ref<string[]>([])
const masterSelectAll = ref(false)
const embed_url = ref('')
const video_item = ref<StoreItem | null>(null)
const loadMoreTrigger = ref<HTMLElement | null>(null)
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

const paginationInfo = computed(() => stateStore.getPagination())

// Function to load more history items
const loadMoreHistory = async (): Promise<void> => {
  if (paginationInfo.value.isLoading || paginationInfo.value.page >= paginationInfo.value.total_pages) {
    return
  }

  try {
    await stateStore.loadPaginated('history', paginationInfo.value.page + 1, config.app.default_pagination, 'DESC', true)
  } catch (error) {
    console.error('Failed to load more history:', error)
    toast.error('Failed to load more history')
  }
}

// Setup intersection observer for infinite scroll
useIntersectionObserver(loadMoreTrigger, ([entry]) => {
  if (!socket.isConnected) {
    return
  }
  if (entry?.isIntersecting && !paginationInfo.value.isLoading && paginationInfo.value.page < paginationInfo.value.total_pages) {
    loadMoreHistory()
  }
}, { threshold: 0.5, })

watch(showCompleted, async isShown => {
  if (isShown && !paginationInfo.value.isLoaded && socket.isConnected) {
    try {
      await stateStore.loadPaginated('history', 1, config.app.default_pagination, 'DESC', true)
    } catch (error) {
      console.error('Failed to load history:', error)
    }
  }
})

onMounted(async () => {
  if (showCompleted.value && !paginationInfo.value.isLoaded) {
    try {
      await stateStore.loadPaginated('history', 1, config.app.default_pagination, 'DESC', true)
    } catch (error) {
      console.error('Failed to load history on mount:', error)
      toast.error('Failed to load history')
    }
  }
})

watch(() => socket.isConnected, async connected => {
  if (connected && showCompleted.value && !paginationInfo.value.isLoaded) {
    try {
      await stateStore.loadPaginated('history', 1, config.app.default_pagination, 'DESC', true)
    } catch (error) {
      console.error('Failed to load history after socket connection:', error)
    }
  }
})

const showThumbnails = computed(() => (props.thumbnails ?? true) && !hideThumbnail.value)

const playVideo = (item: StoreItem) => { video_item.value = item }
const closeVideo = () => { video_item.value = null }

const filteredItems = (items: StoreItem[]) => !props.query ? items : items.filter(filterItem)

const filterItem = (item: StoreItem) => {
  const q = props.query?.toLowerCase()
  if (!q) {
    return true
  }
  return deepIncludes(item, q, new WeakSet())
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
    if (element.filename) {
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

  if (false === (await box.confirm(msg))) {
    return
  }

  await stateStore.removeItems('history', [...selectedElms.value], config.app.remove_files)
  selectedElms.value = []
}

const clearCompleted = async () => {
  const msg = 'Clear all completed downloads? No files will be removed.'
  if (false === (await box.confirm(msg))) {
    return
  }
  selectedElms.value = []
  Promise.all([
    stateStore.deleteItems('history', { status: 'finished', removeFile: false }),
    stateStore.deleteItems('history', { status: 'skip', removeFile: false })
  ])
}

const clearIncomplete = async () => {
  if (false === (await box.confirm('Clear all in-complete downloads?'))) {
    return
  }
  selectedElms.value = []
  await stateStore.deleteItems('history', { status: '!finished', removeFile: false })
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

  if ('error' === item.status && item.filename) {
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
    if (item.filename) {
      return 'Partial Error'
    }
    return 'Error'
  }
  if ('cancelled' === item.status) {
    return 'Cancelled'
  }
  if ('not_live' === item.status) {
    if (item.extras?.is_premiere) {
      return 'Premiere'
    }
    return display_style.value === 'grid' ? 'Stream' : 'Live'
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
    await retryItem(item)
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
  await stateStore.removeItems('history', [item._id], false)
}

const removeItem = async (item: StoreItem) => {
  let msg = `${config.app.remove_files ? 'Remove' : 'Clear'} '${item.title || item.id || item.url || '??'}'?`
  if (item.status === 'finished' && config.app.remove_files) {
    msg += ' This will remove any associated files if they exists.'
  }
  if (false === (await box.confirm(msg))) {
    return false
  }

  socket.emit('item_delete', {
    id: item._id,
    remove_file: config.app.remove_files
  })

  if (selectedElms.value.includes(item._id || '')) {
    selectedElms.value = selectedElms.value.filter(i => i !== item._id)
  }
}

const retryItem = async (item: StoreItem, re_add: boolean = false, remove_file: boolean = false) => {
  const item_req: item_request = {
    url: item.url,
    preset: item.preset,
    folder: item.folder,
    cookies: item.cookies,
    template: item.template,
    cli: item?.cli,
    extras: toRaw(item?.extras || {}) ?? {},
    auto_start: item.auto_start,
  }

  await stateStore.removeItems('history', [item._id], remove_file)

  if (selectedElms.value.includes(item._id || '')) {
    selectedElms.value = selectedElms.value.filter(i => i !== item._id)
  }

  if (true === re_add) {
    toast.info('Cleared the item from history, and added it to the new download form.')
    emitter('add_new', item_req)
    return
  }
  await stateStore.addDownload(item_req)
}

const pImg = (e: Event) => {
  const target = e.target as HTMLImageElement
  if (target.naturalHeight > target.naturalWidth) {
    target.classList.add('image-portrait')
  }
}

const onImgError = (e: Event) => {
  const target = e.target as HTMLImageElement
  if (target.src.endsWith('/images/placeholder.png')) {
    return
  }
  target.src = '/images/placeholder.png'
}

watch(video_item, (v) => {
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
  const files_list: string[] = []
  for (const key in selectedElms.value) {
    const item_id = selectedElms.value[key]
    if (!item_id) {
      continue
    }
    const item = stateStore.get('history', item_id, {} as StoreItem) as StoreItem
    if (!item.filename) {
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
  const opts = [
    { key: 'remove_history', label: 'Remove from history.' },
    { key: 're_add', label: 'Re-add to download form.' },
  ];
  if (config.app.remove_files) {
    opts.push({ key: 'dont_remove_file', label: "Don't remove associated files." })
  }
  dialog_confirm.value.options = opts
  dialog_confirm.value.confirm = (opts: any) => removeFromArchive(item, opts)
}

const removeFromArchive = async (item: StoreItem, opts?: { re_add?: boolean, remove_history?: boolean, dont_remove_file?: boolean }) => {
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

  let file_delete = config.app.remove_files
  if (opts?.dont_remove_file) {
    file_delete = false
  }

  if (opts?.re_add) {
    await retryItem(item, true, file_delete)
    return
  }

  if (opts?.remove_history) {
    await stateStore.removeItems('history', [item._id], file_delete)
  }
}

const is_queued = (item: StoreItem) => {
  if (!item?.status || 'not_live' !== item.status) {
    return ''
  }
  return item.live_in || item.extras?.live_in || item.extras?.release_in ? 'fa-spin fa-spin-10' : ''
}

const generateNfo = async (item: StoreItem) => {
  try {
    toast.info('Generating please wait...', { timeout: 2000 })
    const response = await request(`/api/history/${item._id}/nfo`, {
      method: 'POST',
      body: JSON.stringify({ type: 'tv', overwrite: true }),
    })
    const data = await response.json()
    if (!response.ok) {
      toast.error(data.error || 'Failed to generate NFO')
      return
    }
    toast.success(data.message || 'NFO file generated')
  } catch (e: any) {
    toast.error(`Error: ${e.message}`)
  }
}
</script>
