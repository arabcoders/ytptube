<template>
  <main class="w-full min-w-0 max-w-full space-y-6">
    <div class="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
      <div class="flex min-w-0 items-center gap-3">
        <span
          class="inline-flex size-11 shrink-0 items-center justify-center rounded-md border border-default bg-elevated/70 text-primary"
        >
          <UIcon :name="pageShell.icon" class="size-5" />
        </span>

        <div class="min-w-0 space-y-2">
          <div
            class="flex flex-wrap items-center gap-2 text-xs font-medium uppercase tracking-[0.2em] text-toned"
          >
            <span>{{ pageShell.sectionLabel }}</span>
            <span>/</span>
            <span>{{ pageShell.pageLabel }}</span>
          </div>

          <p class="max-w-3xl text-sm text-toned">{{ pageShell.description }}</p>
        </div>
      </div>

      <div class="flex min-w-0 flex-wrap items-center gap-2 xl:justify-end">
        <UButton
          color="neutral"
          :variant="showFilter ? 'soft' : 'outline'"
          size="sm"
          icon="i-lucide-filter"
          @click="showFilter = !showFilter"
        >
          <span>Filter</span>
        </UButton>

        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          :icon="display_style === 'list' ? 'i-lucide-list' : 'i-lucide-grid-2x2'"
          class="hidden sm:inline-flex"
          @click="changeDisplay"
        >
          <span class="hidden sm:inline">{{ display_style === 'list' ? 'List' : 'Grid' }}</span>
        </UButton>

        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-refresh-cw"
          :loading="isLoading"
          :disabled="isLoading"
          @click="void reloadHistory({ order: 'DESC', perPage: config.app.default_pagination })"
        >
          <span>Reload</span>
        </UButton>

        <UInput
          v-if="showFilter"
          id="filter"
          v-model.lazy="query"
          type="search"
          placeholder="Filter displayed content"
          icon="i-lucide-filter"
          size="sm"
          class="order-last w-full sm:order-first sm:w-80"
        />
      </div>
    </div>

    <div v-if="paginationInfo.isLoaded && paginationInfo.total > 0" class="flex justify-end">
      <UPagination
        v-if="paginationInfo.total_pages > 1"
        :page="paginationInfo.page"
        :total="paginationInfo.total"
        :items-per-page="paginationInfo.per_page"
        :disabled="paginationInfo.isLoading"
        show-edges
        :sibling-count="0"
        @update:page="
          (page) => loadHistory(page, { order: 'DESC', perPage: config.app.default_pagination })
        "
      />
    </div>

    <div class="w-full min-w-0 max-w-full space-y-4">
      <div
        v-if="hasItems"
        class="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-default bg-default px-3 py-3"
      >
        <div class="flex flex-wrap items-center gap-2">
          <UButton
            color="neutral"
            variant="outline"
            size="sm"
            :icon="masterSelectAll ? 'i-lucide-square' : 'i-lucide-square-check-big'"
            @click="toggleMasterSelection"
          >
            {{ masterSelectAll ? 'Unselect' : 'Select' }}
          </UButton>

          <UBadge v-if="selectedElms.length > 0" color="error" variant="soft" size="sm">
            {{ selectedElms.length }}
          </UBadge>

          <UDropdownMenu :items="bulkActionGroups" :modal="false">
            <UButton
              color="neutral"
              variant="outline"
              size="sm"
              icon="i-lucide-list"
              trailing-icon="i-lucide-chevron-down"
            >
              Actions
            </UButton>
          </UDropdownMenu>
        </div>
      </div>

      <UAlert
        v-if="paginationInfo.isLoading && !hasItems"
        color="info"
        variant="soft"
        icon="i-lucide-loader-circle"
        title="Loading history..."
      />

      <div
        v-if="'list' === contentStyle && hasItems"
        class="w-full min-w-0 max-w-full overflow-hidden rounded-lg border border-default bg-default"
      >
        <div class="w-full max-w-full overflow-x-auto overscroll-x-contain">
          <table class="min-w-210 table-fixed w-full text-sm">
            <thead class="bg-muted/40 text-xs uppercase tracking-wide text-toned">
              <tr
                class="text-center [&>th]:border-r [&>th]:border-default/60 [&>th]:px-3 [&>th]:py-3 [&>th]:font-semibold [&>th:last-child]:border-r-0"
              >
                <th class="w-12">
                  <button
                    type="button"
                    class="cursor-pointer"
                    :aria-label="masterSelectAll ? 'Unselect all items' : 'Select all items'"
                    @click="toggleMasterSelection"
                  >
                    <UIcon
                      :name="masterSelectAll ? 'i-lucide-square' : 'i-lucide-square-check-big'"
                      class="size-4"
                    />
                  </button>
                </th>
                <th class="text-left">Title</th>
                <th class="w-32 whitespace-nowrap">Status</th>
                <th class="w-36 whitespace-nowrap">Created</th>
                <th class="w-36 whitespace-nowrap">Size/Starts</th>
                <th class="w-80 whitespace-nowrap">Actions</th>
              </tr>
            </thead>

            <tbody class="divide-y divide-default">
              <tr
                v-for="item in displayedItems"
                :key="item._id"
                class="align-top transition-colors hover:bg-elevated/70 [&>td]:border-r [&>td]:border-default/60 [&>td:last-child]:border-r-0"
              >
                <td class="border-r border-default/60 px-3 py-3 text-center align-top">
                  <label class="inline-flex cursor-pointer items-center justify-center">
                    <input
                      :id="`checkbox-${item._id}`"
                      v-model="selectedElms"
                      class="completed-checkbox size-4 rounded border-default"
                      type="checkbox"
                      :value="item._id"
                    />
                  </label>
                </td>

                <td class="w-0 border-r border-default/60 px-3 py-3 align-top">
                  <div class="flex min-w-0 items-start justify-between gap-3">
                    <div class="min-w-0 flex-1">
                      <UTooltip
                        :text="
                          show_popover
                            ? `${item.preset}: ${item.title}`
                            : `[${item.preset}] - ${item.title}`
                        "
                      >
                        <div class="truncate font-medium text-highlighted">
                          <a target="_blank" :href="item.url" class="hover:underline">
                            {{ item.title }}
                          </a>
                        </div>
                      </UTooltip>
                    </div>

                    <div
                      v-if="item.extras?.duration || show_popover"
                      class="flex shrink-0 items-center gap-2"
                    >
                      <UBadge v-if="item.extras?.duration" color="info" variant="soft" size="sm">
                        {{ formatTime(item.extras.duration) }}
                      </UBadge>

                      <UPopover
                        v-if="show_popover"
                        :content="{ side: 'bottom', align: 'end', sideOffset: 8 }"
                      >
                        <UButton
                          color="neutral"
                          variant="ghost"
                          size="xs"
                          icon="i-lucide-info"
                          square
                        />

                        <template #content>
                          <UCard class="max-w-112.5" :ui="{ body: 'space-y-3 p-4' }">
                            <div class="space-y-2">
                              <div class="flex flex-wrap items-center gap-2">
                                <p class="text-sm font-semibold text-highlighted">
                                  {{ item.title }}
                                </p>
                                <UBadge color="info" variant="soft" size="sm">{{
                                  item.preset
                                }}</UBadge>
                              </div>

                              <p v-if="getItemPath(item)" class="text-xs text-toned">
                                <span class="font-semibold text-default">Path:</span>
                                {{ getItemPath(item) }}
                              </p>
                            </div>

                            <img
                              v-if="showThumbnails && getListImage(item)"
                              :src="getListImage(item)"
                              class="max-h-56 w-full rounded-md object-cover"
                            />

                            <div
                              v-if="item.description"
                              class="max-h-40 overflow-y-auto rounded-md border border-default bg-muted/20 px-3 py-2 text-sm text-default"
                            >
                              {{ item.description }}
                            </div>
                          </UCard>
                        </template>
                      </UPopover>
                    </div>
                  </div>

                  <p
                    v-if="item.error"
                    :class="messageClass(item._id, 'error', 'list', 'mt-2')"
                    @click="toggleMessage(item._id, 'error', 'list')"
                  >
                    {{ item.error }}
                  </p>

                  <p
                    v-if="showMessage(item)"
                    :class="messageClass(item._id, 'msg', 'list', 'mt-1')"
                    @click="toggleMessage(item._id, 'msg', 'list')"
                  >
                    {{ item.msg }}
                  </p>
                </td>

                <td class="border-r border-default/60 px-3 py-3 text-center align-top text-sm">
                  <div class="inline-flex items-center gap-2 text-default">
                    <span class="inline-flex items-center">
                      <UIcon
                        :name="setIcon(item)"
                        :class="[setIconColor(item), isQueuedAnimation(item), 'size-4 shrink-0']"
                      />
                    </span>
                    <span>{{ setStatus(item) }}</span>
                  </div>
                </td>

                <td
                  class="border-r border-default/60 px-3 py-3 text-center align-top text-sm text-toned whitespace-nowrap"
                >
                  <UTooltip :text="moment(item.datetime).format('YYYY-M-DD H:mm Z')">
                    <span :date-datetime="item.datetime" v-rtime="item.datetime" />
                  </UTooltip>
                </td>

                <td
                  class="border-r border-default/60 px-3 py-3 text-center align-top text-sm text-toned whitespace-nowrap"
                >
                  <template
                    v-if="'not_live' === item.status && (item.live_in || item.extras?.release_in)"
                  >
                    <UTooltip
                      :text="`Retry at: ${moment(item.live_in || item.extras?.release_in).format('YYYY-M-DD H:mm Z')}`"
                    >
                      <span
                        :date-datetime="item.live_in || item.extras?.release_in"
                        v-rtime="item.live_in || item.extras?.release_in"
                      />
                    </UTooltip>
                  </template>

                  <template v-else>
                    {{ item.file_size ? formatBytes(item.file_size) : 'N/A' }}
                  </template>
                </td>

                <td class="w-80 px-3 py-3 align-top whitespace-nowrap">
                  <div class="flex items-center justify-end gap-1">
                    <UButton
                      v-if="showRetryAction(item)"
                      color="neutral"
                      variant="outline"
                      size="xs"
                      icon="i-lucide-rotate-cw"
                      @click="void retryItem(item, true)"
                    >
                      Retry
                    </UButton>

                    <UButton
                      v-if="item.filename"
                      color="neutral"
                      variant="outline"
                      size="xs"
                      icon="i-lucide-download"
                      external
                      :href="makeDownload(config, item)"
                      :download="item.filename?.split('/').reverse()[0]"
                    >
                      Download
                    </UButton>

                    <UButton
                      color="neutral"
                      variant="outline"
                      size="xs"
                      icon="i-lucide-trash"
                      @click="void removeItem(item)"
                    >
                      Remove
                    </UButton>

                    <UDropdownMenu v-if="item.url" :items="itemActionGroups(item)" :modal="false">
                      <UButton
                        color="neutral"
                        variant="outline"
                        size="xs"
                        icon="i-lucide-settings-2"
                        trailing-icon="i-lucide-chevron-down"
                      >
                        Actions
                      </UButton>
                    </UDropdownMenu>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div v-else-if="hasItems" class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        <LateLoader
          v-for="item in displayedItems"
          :key="item._id"
          :unrender="true"
          :min-height="showThumbnails ? 410 : 210"
          class="min-h-0 min-w-0 w-full max-w-full"
        >
          <UCard
            class="flex h-full min-w-0 w-full max-w-full flex-col overflow-hidden border"
            :ui="{
              body: 'flex flex-1 flex-col gap-4 p-4',
              footer: 'border-t border-default px-4 py-4',
              header: 'p-4 pb-3',
              root: 'bg-default',
            }"
          >
            <template #header>
              <div class="flex min-w-0 flex-wrap items-start justify-between gap-3">
                <div class="min-w-0 flex-1">
                  <UTooltip :text="item.title">
                    <div class="min-w-0 text-sm font-semibold text-highlighted">
                      <a target="_blank" :href="item.url" class="block truncate hover:underline">
                        {{ item.title }}
                      </a>
                    </div>
                  </UTooltip>
                </div>

                <div class="flex max-w-full flex-wrap items-center justify-end gap-1 sm:shrink-0">
                  <UBadge v-if="item.extras?.duration" color="info" variant="soft" size="sm">
                    {{ formatTime(item.extras.duration) }}
                  </UBadge>

                  <UPopover
                    v-if="show_popover && getItemPath(item)"
                    :content="{ side: 'bottom', align: 'end', sideOffset: 8 }"
                  >
                    <UButton
                      color="neutral"
                      variant="ghost"
                      size="xs"
                      icon="i-lucide-info"
                      square
                    />

                    <template #content>
                      <UCard class="max-w-137.5" :ui="{ body: 'space-y-3 p-4' }">
                        <div class="space-y-2">
                          <p class="text-sm font-semibold text-highlighted">{{ item.title }}</p>
                          <p class="text-xs text-toned">
                            <span class="font-semibold text-default">Path:</span>
                            {{ getItemPath(item) }}
                          </p>
                        </div>

                        <div
                          v-if="item.description"
                          class="max-h-40 overflow-y-auto rounded-md border border-default bg-muted/20 px-3 py-2 text-sm text-default"
                        >
                          {{ item.description }}
                        </div>
                      </UCard>
                    </template>
                  </UPopover>

                  <UButton
                    v-if="show_thumbnail"
                    color="neutral"
                    variant="ghost"
                    size="xs"
                    :icon="hideThumbnail ? 'i-lucide-chevron-down' : 'i-lucide-chevron-up'"
                    square
                    @click="hideThumbnail = !hideThumbnail"
                  />

                  <label class="inline-flex cursor-pointer items-center justify-center px-1">
                    <input
                      :id="`checkbox-${item._id}`"
                      v-model="selectedElms"
                      class="completed-checkbox size-4 rounded border-default"
                      type="checkbox"
                      :value="item._id"
                    />
                  </label>
                </div>
              </div>
            </template>

            <div
              v-if="showThumbnails"
              class="-mx-4 -mt-4 overflow-hidden border-b border-default bg-muted/20"
            >
              <figure :class="['relative w-full overflow-hidden', thumbnailRatioClass]">
                <span v-if="item.filename" class="play-overlay" @click="video_item = item">
                  <span class="play-icon" aria-hidden="true">
                    <UIcon name="i-lucide-play" class="size-6 translate-x-px text-white" />
                  </span>
                  <img
                    v-if="getGridImage(item)"
                    :src="getGridImage(item)"
                    @load="pImg"
                    @error="onImgError"
                  />
                  <img v-else src="/images/placeholder.png" />
                </span>

                <span
                  v-else-if="isEmbedable(item.url)"
                  class="play-overlay"
                  @click="embed_url = getEmbedable(item.url) as string"
                >
                  <span class="play-icon embed-icon" aria-hidden="true">
                    <UIcon name="i-lucide-play" class="size-6 translate-x-px text-white" />
                  </span>
                  <img
                    v-if="getGridImage(item)"
                    :src="getGridImage(item)"
                    @load="pImg"
                    @error="onImgError"
                  />
                  <img v-else src="/images/placeholder.png" />
                </span>

                <template v-else>
                  <img
                    v-if="getGridImage(item)"
                    :src="getGridImage(item)"
                    @load="pImg"
                    @error="onImgError"
                  />
                  <img v-else src="/images/placeholder.png" />
                </template>
              </figure>
            </div>

            <div class="flex flex-wrap gap-2 text-sm *:min-w-32 *:flex-1">
              <button
                type="button"
                class="rounded-md border border-default bg-muted/20 px-3 py-2 text-default transition hover:border-primary hover:text-default"
                @click="toggleExpand(item._id, 'status')"
              >
                <span class="inline-flex w-full items-center justify-center gap-2">
                  <UIcon
                    :name="setIcon(item)"
                    :class="[setIconColor(item), isQueuedAnimation(item), 'size-4 shrink-0']"
                  />
                  <span :class="['min-w-0 text-center', expandClass(item._id, 'status')]">
                    {{ setStatus(item) }}
                  </span>
                </span>
              </button>

              <button
                type="button"
                class="rounded-md border border-default bg-muted/20 px-3 py-2 text-default transition hover:border-primary hover:text-default"
                @click="toggleExpand(item._id, 'preset')"
              >
                <span class="inline-flex w-full items-center justify-center gap-2">
                  <UIcon name="i-lucide-sliders-horizontal" class="size-4 shrink-0 text-toned" />
                  <span :class="['min-w-0 text-center', expandClass(item._id, 'preset')]">
                    {{ item.preset }}
                  </span>
                </span>
              </button>

              <button
                v-if="'not_live' === item.status && (item.live_in || item.extras?.release_in)"
                type="button"
                class="rounded-md border border-default bg-muted/20 px-3 py-2 text-toned transition hover:border-primary hover:text-default"
                @click="toggleExpand(item._id, 'retry_at')"
              >
                <UTooltip
                  :text="`Retry at: ${moment(item.live_in || item.extras?.release_in).format('YYYY-M-DD H:mm Z')}`"
                >
                  <span class="inline-flex w-full items-center justify-center gap-2">
                    <UIcon name="i-lucide-calendar" class="size-4 shrink-0 text-toned" />
                    <span
                      :class="['min-w-0 text-center', expandClass(item._id, 'retry_at')]"
                      :date-datetime="item.live_in || item.extras?.release_in"
                      v-rtime="item.live_in || item.extras?.release_in"
                    />
                  </span>
                </UTooltip>
              </button>

              <button
                type="button"
                class="rounded-md border border-default bg-muted/20 px-3 py-2 text-toned transition hover:border-primary hover:text-default"
                @click="toggleExpand(item._id, 'datetime')"
              >
                <UTooltip :text="moment(item.datetime).format('YYYY-M-DD H:mm Z')">
                  <span class="inline-flex w-full items-center justify-center gap-2">
                    <UIcon name="i-lucide-clock-3" class="size-4 shrink-0 text-toned" />
                    <span
                      :class="['min-w-0 text-center', expandClass(item._id, 'datetime')]"
                      :date-datetime="item.datetime"
                      v-rtime="item.datetime"
                    />
                  </span>
                </UTooltip>
              </button>

              <button
                v-if="item.file_size"
                type="button"
                class="rounded-md border border-default bg-muted/20 px-3 py-2 text-toned transition hover:border-primary hover:text-default"
                @click="toggleExpand(item._id, 'size')"
              >
                <span class="inline-flex w-full items-center justify-center gap-2">
                  <UIcon name="i-lucide-hard-drive" class="size-4 shrink-0 text-toned" />
                  <span :class="['min-w-0 text-center', expandClass(item._id, 'size')]">
                    {{ formatBytes(item.file_size) }}
                  </span>
                </span>
              </button>
            </div>

            <div
              v-if="item.error || showMessage(item)"
              class="space-y-2 border-t border-default pt-3"
            >
              <p
                v-if="item.error"
                :class="messageClass(item._id, 'error', 'card')"
                @click="toggleMessage(item._id, 'error', 'card')"
              >
                {{ item.error }}
              </p>

              <p
                v-if="showMessage(item)"
                :class="messageClass(item._id, 'msg', 'card')"
                @click="toggleMessage(item._id, 'msg', 'card')"
              >
                {{ item.msg }}
              </p>
            </div>

            <template #footer>
              <div class="flex flex-wrap gap-2 *:min-w-32 *:flex-1">
                <UButton
                  v-if="showRetryAction(item)"
                  color="neutral"
                  variant="outline"
                  icon="i-lucide-rotate-cw"
                  class="w-full justify-center"
                  @click="void retryItem(item, false)"
                >
                  Retry
                </UButton>

                <UButton
                  v-if="item.filename"
                  color="neutral"
                  variant="outline"
                  icon="i-lucide-download"
                  class="w-full justify-center"
                  external
                  :href="makeDownload(config, item)"
                  :download="item.filename?.split('/').reverse()[0]"
                >
                  Download
                </UButton>

                <UButton
                  color="neutral"
                  variant="outline"
                  icon="i-lucide-trash"
                  class="w-full justify-center"
                  @click="void removeItem(item)"
                >
                  {{ config.app.remove_files ? 'Remove' : 'Clear' }}
                </UButton>

                <UDropdownMenu :items="itemActionGroups(item)" :modal="false" class="w-full">
                  <UButton
                    color="neutral"
                    variant="outline"
                    icon="i-lucide-settings-2"
                    trailing-icon="i-lucide-chevron-down"
                    class="w-full justify-center"
                  >
                    Actions
                  </UButton>
                </UDropdownMenu>
              </div>
            </template>
          </UCard>
        </LateLoader>
      </div>

      <div v-if="!hasItems && !paginationInfo.isLoading" class="space-y-4">
        <UAlert
          v-if="query"
          color="warning"
          variant="soft"
          icon="i-lucide-search"
          title="Filter results"
        >
          <template #description>
            <div class="space-y-3 text-sm text-default">
              <p>
                No results found for: <code>{{ query }}</code
                >.
              </p>

              <p>
                You can search using any value shown in the item's <code>Local Information</code>.
                You can also do a targeted search using <code><u>key</u>:value</code>.
              </p>

              <div>
                <p class="mb-1 font-medium">Examples:</p>
                <ul class="list-disc space-y-1 pl-5">
                  <li><code>youtube.com</code> - items containing that text</li>
                  <li><code>is_live:true</code> - only live downloads</li>
                  <li><code>source_name:task_name</code> - items added by the specified task.</li>
                </ul>
              </div>
            </div>
          </template>
        </UAlert>

        <UEmpty
          v-else
          icon="i-lucide-triangle-alert"
          title="No items"
          description="Download history is empty."
          class="rounded-lg border border-dashed border-default bg-muted/10 py-10"
        />
      </div>

      <div v-if="paginationInfo.total_pages > 1" class="flex justify-end pt-2">
        <UPagination
          :page="paginationInfo.page"
          :total="paginationInfo.total"
          :items-per-page="paginationInfo.per_page"
          :disabled="paginationInfo.isLoading"
          show-edges
          :sibling-count="0"
          @update:page="
            (page) => loadHistory(page, { order: 'DESC', perPage: config.app.default_pagination })
          "
        />
      </div>
    </div>

    <UModal
      v-if="video_item"
      :open="Boolean(video_item)"
      :dismissible="true"
      :title="video_item?.title || 'Player'"
      :ui="{ content: 'sm:max-w-5xl', body: 'p-0' }"
      @update:open="(open) => !open && (video_item = null)"
    >
      <template #body>
        <VideoPlayer
          type="default"
          :isMuted="false"
          autoplay="true"
          :isControls="true"
          :item="video_item"
          class="w-full"
          @closeModel="video_item = null"
          @error="async (error: string) => await box.alert(error)"
        />
      </template>
    </UModal>

    <UModal
      v-if="embed_url"
      :open="Boolean(embed_url)"
      :dismissible="true"
      title="Embedded player"
      :ui="{ content: 'sm:max-w-5xl', body: 'p-0' }"
      @update:open="(open) => !open && (embed_url = '')"
    >
      <template #body>
        <EmbedPlayer :url="embed_url" @closeModel="embed_url = ''" />
      </template>
    </UModal>

    <GetInfo
      v-if="info_view.url"
      :link="info_view.url"
      :preset="info_view.preset"
      :cli="info_view.cli"
      :useUrl="info_view.useUrl"
      @closeModel="close_info"
    />
  </main>
</template>

<script setup lang="ts">
import { toRaw } from 'vue';
import moment from 'moment';
import { useStorage } from '@vueuse/core';
import { useConfirm } from '~/composables/useConfirm';
import { useDialog } from '~/composables/useDialog';
import { useAppSocket } from '~/composables/useAppSocket';
import { useExpandableMeta } from '~/composables/useExpandableMeta';
import { useHistoryState } from '~/composables/useHistoryState';
import { useMediaQuery } from '~/composables/useMediaQuery';
import type { item_request } from '~/types/item';
import type { StoreItem } from '~/types/store';
import {
  deepIncludes,
  formatBytes,
  formatTime,
  getImage,
  getPath,
  isDownloadSkipped,
  makeDownload,
  request,
  uri,
} from '~/utils';
import { getEmbedable, isEmbedable } from '~/utils/embedable';
import { requirePageShell } from '~/utils/topLevelNavigation';

const config = useYtpConfig();
const stateStore = useQueueState();
const socketStore = useAppSocket();
const toast = useNotification();
const box = useConfirm();
const { confirmDialog } = useDialog();
const { toggleExpand, expandClass } = useExpandableMeta();
const pendingDownloadFormItem = useState<item_request | Record<string, never>>(
  'pending-download-form-item',
  () => ({}),
);
const {
  items: historyItems,
  pagination,
  isLoading,
  isLoaded,
  loadHistory,
  reloadHistory,
  deleteHistoryItems,
  historyMoveHandler,
} = useHistoryState();

const show_thumbnail = useStorage<boolean>('show_thumbnail', true);
const hideThumbnail = useStorage<boolean>('hideThumbnailHistory', false);
const display_style = useStorage<'grid' | 'list'>('history_display_style', 'grid');
const isMobile = useMediaQuery({ maxWidth: 639 });
const bg_enable = useStorage<boolean>('random_bg', true);
const bg_opacity = useStorage<number>('random_bg_opacity', 0.95);
const thumbnail_ratio = useStorage<'is-16by9' | 'is-3by1'>('thumbnail_ratio', 'is-3by1');
const show_popover = useStorage<boolean>('show_popover', true);

const pageShell = requirePageShell('history');
const info_view = ref<{ url: string; preset: string; cli: string; useUrl: boolean }>({
  url: '',
  preset: '',
  cli: '',
  useUrl: false,
});
const query = ref('');
const showFilter = ref(false);
const selectedElms = ref<string[]>([]);
const masterSelectAll = ref(false);
const embed_url = ref('');
const video_item = ref<StoreItem | null>(null);
const expandedMessages = reactive<Record<string, Set<string>>>({});

const contentStyle = computed<'grid' | 'list'>(() =>
  isMobile.value ? 'grid' : display_style.value,
);
const showThumbnails = computed(() => show_thumbnail.value && !hideThumbnail.value);
const paginationInfo = computed(() => ({
  ...pagination.value,
  isLoading: isLoading.value,
  isLoaded: isLoaded.value,
}));

const handleHistoryItemMoved = historyMoveHandler();

onMounted(async () => {
  socketStore.on('item_moved', handleHistoryItemMoved);
  await loadHistory(1, { order: 'DESC', perPage: config.app.default_pagination });
});

onBeforeUnmount(() => {
  socketStore.off('item_moved', handleHistoryItemMoved);
});

watch(showFilter, () => {
  if (!showFilter.value) {
    query.value = '';
  }
});

watch(video_item, (value) => {
  if (!bg_enable.value) {
    return;
  }

  document.querySelector('body')?.setAttribute('style', `opacity: ${value ? 1 : bg_opacity.value}`);
});

watch(embed_url, (value) => {
  if (!bg_enable.value) {
    return;
  }

  document.querySelector('body')?.setAttribute('style', `opacity: ${value ? 1 : bg_opacity.value}`);
});

const close_info = (): void => {
  info_view.value.url = '';
  info_view.value.preset = '';
  info_view.value.cli = '';
  info_view.value.useUrl = false;
};

const view_info = (
  url: string,
  useUrl: boolean = false,
  preset: string = '',
  cli: string = '',
): void => {
  info_view.value.url = url;
  info_view.value.useUrl = useUrl;
  info_view.value.preset = preset;
  info_view.value.cli = cli;
};

const changeDisplay = (): void => {
  display_style.value = display_style.value === 'grid' ? 'list' : 'grid';
};

const toNewDownload = async (item: item_request | Partial<StoreItem>): Promise<void> => {
  if (!item) {
    return;
  }

  pendingDownloadFormItem.value = item as item_request;
  await navigateTo('/');
};

const filterItem = (item: StoreItem): boolean => {
  const normalizedQuery = query.value.trim().toLowerCase();

  if (!normalizedQuery) {
    return true;
  }

  return deepIncludes(item, normalizedQuery, new WeakSet());
};

const displayedItems = computed(() => historyItems.value.filter(filterItem));
const hasSelected = computed(() => selectedElms.value.length > 0);
const hasItems = computed(() => displayedItems.value.length > 0);
const displayedItemIds = computed(() => displayedItems.value.map((item) => item._id));

watch(
  displayedItemIds,
  (ids) => {
    const idSet = new Set(ids);
    selectedElms.value = selectedElms.value.filter((id) => idSet.has(id));

    if (masterSelectAll.value) {
      selectedElms.value = [...ids];
    }
  },
  { immediate: true },
);

watch(selectedElms, (value) => {
  const ids = displayedItemIds.value;
  masterSelectAll.value = ids.length > 0 && ids.every((id) => value.includes(id));
});

const findHistoryItem = (itemId: string): StoreItem | null => {
  return historyItems.value.find((item) => item._id === itemId) ?? null;
};

const selectedDownloadableCount = computed(() =>
  selectedElms.value.reduce((count, itemId) => {
    const item = findHistoryItem(itemId);
    return item?.filename ? count + 1 : count;
  }, 0),
);

const thumbnailRatioClass = computed(() =>
  thumbnail_ratio.value === 'is-16by9' ? 'aspect-video' : 'aspect-[3/1]',
);

const toggleMasterSelection = (): void => {
  if (masterSelectAll.value) {
    selectedElms.value = [];
    masterSelectAll.value = false;
    return;
  }

  selectedElms.value = [...displayedItemIds.value];
  masterSelectAll.value = true;
};

const getItemPath = (item: StoreItem): string => getPath(config.app.download_path, item) || '';
const getListImage = (item: StoreItem): string =>
  getImage(config.app.download_path, item, false) || '';
const getGridImage = (item: StoreItem): string => getImage(config.app.download_path, item) || '';
const showRetryAction = (item: StoreItem): boolean => !item.filename && !isDownloadSkipped(item);

const hasIncomplete = computed(() => historyItems.value.some((item) => item.status !== 'finished'));
const hasCompleted = computed(() =>
  historyItems.value.some((item) => item.status === 'finished' || item.status === 'skip'),
);

const bulkActionGroups = computed(() => {
  const groups: Array<Array<Record<string, unknown>>> = [
    [
      {
        label: 'Download',
        icon: 'i-lucide-download',
        disabled: !hasSelected.value || selectedDownloadableCount.value < 1,
        onSelect: () => void downloadSelected(),
      },
      {
        label: config.app.remove_files ? 'Remove' : 'Clear',
        icon: 'i-lucide-trash',
        disabled: !hasSelected.value,
        onSelect: deleteSelectedItems,
      },
    ],
  ];

  const cleanupActions: Array<Record<string, unknown>> = [];

  if (hasCompleted.value) {
    cleanupActions.push({
      label: 'Clear Completed',
      icon: 'i-lucide-circle-check-big',
      onSelect: clearCompleted,
    });
  }

  if (hasIncomplete.value) {
    cleanupActions.push(
      {
        label: 'Clear Incomplete',
        icon: 'i-lucide-circle-x',
        onSelect: clearIncomplete,
      },
      {
        label: 'Retry Incomplete',
        icon: 'i-lucide-rotate-cw',
        onSelect: retryIncomplete,
      },
    );
  }

  if (cleanupActions.length > 0) {
    groups.push(cleanupActions);
  }

  return groups;
});

const itemActionGroups = (item: StoreItem): Array<Array<Record<string, unknown>>> => {
  const groups: Array<Array<Record<string, unknown>>> = [];
  const mediaActions: Array<Record<string, unknown>> = [];

  if (item.filename) {
    mediaActions.push({
      label: 'Play video',
      icon: 'i-lucide-play',
      onSelect: () => {
        video_item.value = item;
      },
    });

    if ('error' === item.status) {
      mediaActions.push({
        label: 'Retry download',
        icon: 'i-lucide-rotate-cw',
        onSelect: () => void retryItem(item, true),
      });
    }

    mediaActions.push({
      label: 'Generate NFO',
      icon: 'i-lucide-file-code-2',
      onSelect: () => void generateNfo(item),
    });
  } else if (isEmbedable(item.url)) {
    mediaActions.push({
      label: 'Play video',
      icon: 'i-lucide-play',
      onSelect: () => {
        embed_url.value = getEmbedable(item.url) as string;
      },
    });
  }

  if (mediaActions.length > 0) {
    groups.push(mediaActions);
  }

  groups.push([
    {
      label: 'yt-dlp Information',
      icon: 'i-lucide-info',
      onSelect: () => view_info(item.url, false, item.preset, item.cli),
    },
    {
      label: 'Local Information',
      icon: 'i-lucide-info',
      onSelect: () => view_info(`/api/history/${item._id}`, true),
    },
    {
      label: 'Add to download form',
      icon: 'i-lucide-copy',
      onSelect: () => void retryItem(item, true),
    },
  ]);

  if (item.is_archivable && !item.is_archived) {
    groups.push([
      {
        label: 'Add to archive',
        icon: 'i-lucide-archive',
        onSelect: () => void addArchiveDialog(item),
      },
    ]);
  }

  if (item.is_archivable && item.is_archived) {
    groups.push([
      {
        label: 'Remove from archive',
        icon: 'i-lucide-archive-x',
        onSelect: () => void removeFromArchiveDialog(item),
      },
    ]);
  }

  return groups;
};

const showMessage = (item: StoreItem): boolean => {
  if (!item?.msg || item.msg === item?.error) {
    return false;
  }

  return (item.msg?.length || 0) > 0;
};

const deleteSelectedItems = async (): Promise<void> => {
  if (selectedElms.value.length < 1) {
    toast.error('No items selected.');
    return;
  }

  let message = `${config.app.remove_files ? 'Remove' : 'Clear'} '${selectedElms.value.length}' items?`;

  if (true === config.app.remove_files) {
    message += ' This will remove any associated files if they exists.';
  }

  if (false === (await box.confirm(message))) {
    return;
  }

  await deleteHistoryItems({ ids: [...selectedElms.value], removeFile: config.app.remove_files });
  selectedElms.value = [];
  await reloadHistory({ order: 'DESC', perPage: config.app.default_pagination });
};

const clearCompleted = async (): Promise<void> => {
  const message = 'Clear all completed downloads? No files will be removed.';

  if (false === (await box.confirm(message))) {
    return;
  }

  selectedElms.value = [];

  await deleteHistoryItems({ status: 'finished,skip', removeFile: false });

  await reloadHistory({ order: 'DESC', perPage: config.app.default_pagination });
};

const clearIncomplete = async (): Promise<void> => {
  if (false === (await box.confirm('Clear all incomplete downloads?'))) {
    return;
  }

  selectedElms.value = [];
  await deleteHistoryItems({ status: '!finished', removeFile: false });
  await reloadHistory({ order: 'DESC', perPage: config.app.default_pagination });
};

const setIcon = (item: StoreItem): string => {
  if ('finished' === item.status) {
    if (isDownloadSkipped(item)) {
      return 'i-lucide-ban';
    }

    if (!item.filename) {
      return 'i-lucide-triangle-alert';
    }

    if (item.extras?.is_premiere) {
      return 'i-lucide-star';
    }

    return item.is_live ? 'i-lucide-globe' : 'i-lucide-circle-check-big';
  }

  if ('error' === item.status) {
    return 'i-lucide-circle-x';
  }

  if ('cancelled' === item.status) {
    return 'i-lucide-circle-off';
  }

  if ('not_live' === item.status) {
    return item.extras?.is_premiere ? 'i-lucide-star' : 'i-lucide-headphones';
  }

  if ('skip' === item.status) {
    return 'i-lucide-ban';
  }

  return 'i-lucide-circle';
};

const setIconColor = (item: StoreItem): string => {
  if ('finished' === item.status) {
    if (isDownloadSkipped(item)) {
      return 'text-info';
    }

    if (!item.filename) {
      return 'text-warning';
    }

    return 'text-success';
  }

  if ('not_live' === item.status) {
    return 'text-info';
  }

  if ('cancelled' === item.status || 'skip' === item.status) {
    return 'text-warning';
  }

  if ('error' === item.status && item.filename) {
    return 'text-warning';
  }

  return 'text-error';
};

const setStatus = (item: StoreItem): string => {
  if ('finished' === item.status) {
    if (isDownloadSkipped(item)) {
      return 'Download skipped';
    }

    if (item.extras?.is_premiere) {
      return 'Premiered';
    }

    return item.is_live ? 'Streamed' : 'Completed';
  }

  if ('error' === item.status) {
    if (item.filename) {
      return 'Partial Error';
    }

    return 'Error';
  }

  if ('cancelled' === item.status) {
    return 'Cancelled';
  }

  if ('not_live' === item.status) {
    if (item.extras?.is_premiere) {
      return 'Premiere';
    }

    return 'Live';
  }

  if ('skip' === item.status) {
    return 'Skipped';
  }

  return item.status || 'Unknown';
};

const retryIncomplete = async (): Promise<void> => {
  if (false === (await box.confirm('Retry all incomplete downloads?'))) {
    return;
  }

  for (const item of historyItems.value) {
    if ('finished' === item.status) {
      continue;
    }

    await retryItem(item);
  }
};

const addArchiveDialog = async (item: StoreItem): Promise<void> => {
  const { status, value } = await confirmDialog({
    title: 'Archive Item',
    message: `Archive '${item.title || item.id || item.url || '??'}'?`,
    confirmText: 'Archive',
    confirmColor: 'warning',
    options: [{ key: 'remove_history', label: 'Also, Remove from history.' }],
  });

  if (!status) {
    return;
  }

  await archiveItem(item, value ?? undefined);
};

const archiveItem = async (item: StoreItem, opts = {}): Promise<void> => {
  try {
    const response = await request(`/api/history/${item._id}/archive`, { method: 'POST' });
    const data = await response.json();

    if (!response.ok) {
      toast.error(data.error);
      return;
    }

    toast.success(data.message ?? `Archived '${item.title || item.id || item.url || '??'}'.`);
  } catch (error: any) {
    console.error(error);
    return;
  }

  if ((opts as { remove_history?: boolean })?.remove_history) {
    await deleteHistoryItems({ ids: [item._id], removeFile: false });
  }

  await reloadHistory({ order: 'DESC', perPage: config.app.default_pagination });
};

const removeItem = async (item: StoreItem): Promise<void> => {
  let message = `${config.app.remove_files ? 'Remove' : 'Clear'} '${item.title || item.id || item.url || '??'}'?`;

  if (item.status === 'finished' && config.app.remove_files) {
    message += ' This will remove any associated files if they exists.';
  }

  if (false === (await box.confirm(message))) {
    return;
  }

  await deleteHistoryItems({ ids: [item._id], removeFile: config.app.remove_files });

  if (selectedElms.value.includes(item._id || '')) {
    selectedElms.value = selectedElms.value.filter((entry) => entry !== item._id);
  }

  await reloadHistory({ order: 'DESC', perPage: config.app.default_pagination });
};

const retryItem = async (
  item: StoreItem,
  re_add: boolean = false,
  remove_file: boolean = false,
): Promise<void> => {
  const item_req: item_request = {
    url: item.url,
    preset: item.preset,
    folder: item.folder,
    cookies: item.cookies,
    template: item.template,
    cli: item?.cli,
    extras: toRaw(item?.extras || {}) ?? {},
    auto_start: item.auto_start,
  };

  await deleteHistoryItems({ ids: [item._id], removeFile: remove_file });

  if (selectedElms.value.includes(item._id || '')) {
    selectedElms.value = selectedElms.value.filter((entry) => entry !== item._id);
  }

  await reloadHistory({ order: 'DESC', perPage: config.app.default_pagination });

  if (true === re_add) {
    toast.info('Cleared the item from history, and added it to the new download form.');
    await toNewDownload(item_req);
    return;
  }

  await stateStore.addDownload(item_req);
};

const pImg = (event: Event): void => {
  const target = event.target as HTMLImageElement;

  if (target.naturalHeight > target.naturalWidth) {
    target.classList.add('image-portrait');
  }
};

const onImgError = (event: Event): void => {
  const target = event.target as HTMLImageElement;

  if (target.src.endsWith('/images/placeholder.png')) {
    return;
  }

  target.src = '/images/placeholder.png';
};

const downloadSelected = async (): Promise<void> => {
  if (selectedElms.value.length < 1) {
    toast.error('No items selected.');
    return;
  }

  const files_list: string[] = [];

  for (const itemId of selectedElms.value) {
    const item = findHistoryItem(itemId);

    if (!item?.filename) {
      continue;
    }

    files_list.push(item.folder ? item.folder + '/' + item.filename : item.filename);
  }

  selectedElms.value = [];

  try {
    const response = await request('/api/file/download', {
      method: 'POST',
      body: JSON.stringify(files_list),
    });
    const json = await response.json();

    if (!response.ok) {
      toast.error(json.error || 'Failed to start download.');
      return;
    }

    const token = json.token;
    const body = document.querySelector('body');
    const link = document.createElement('a');
    link.href = uri(`/api/file/download/${token}`);
    link.setAttribute('target', '_blank');
    body?.appendChild(link);
    link.click();
    body?.removeChild(link);
  } catch (error: any) {
    console.error(error);
    toast.error(`Error: ${error.message}`);
  }
};

const toggleMessage = (itemId: string, field: 'error' | 'msg', view: 'list' | 'card'): void => {
  const key = `${itemId}:${view}`;

  if (!expandedMessages[key]) {
    expandedMessages[key] = new Set();
  }

  if (expandedMessages[key].has(field)) {
    expandedMessages[key].delete(field);
    return;
  }

  expandedMessages[key].add(field);
};

const isMessageExpanded = (
  itemId: string,
  field: 'error' | 'msg',
  view: 'list' | 'card',
): boolean => expandedMessages[`${itemId}:${view}`]?.has(field) ?? false;

const messageClass = (
  itemId: string,
  field: 'error' | 'msg',
  view: 'list' | 'card',
  spacingClass = '',
): string[] => {
  const expanded = isMessageExpanded(itemId, field, view);
  const classes = ['cursor-pointer', 'text-sm', 'text-error'];

  if (spacingClass) {
    classes.push(spacingClass);
  }

  if ('card' === view) {
    classes.push(expanded ? 'whitespace-pre-wrap break-words' : 'line-clamp-2 break-words');
    return classes;
  }

  classes.push(expanded ? 'whitespace-pre-wrap break-words' : 'block max-w-full truncate');
  return classes;
};

const removeFromArchiveDialog = async (item: StoreItem): Promise<void> => {
  const options = [
    { key: 'remove_history', label: 'Remove from history.' },
    { key: 're_add', label: 'Re-add to download form.' },
  ];

  if (config.app.remove_files) {
    options.push({ key: 'dont_remove_file', label: "Don't remove associated files." });
  }

  const { status, value } = await confirmDialog({
    title: 'Remove from Archive',
    message: `Remove '${item.title || item.id || item.url || '??'}' from archive?`,
    confirmText: 'Remove',
    confirmColor: 'error',
    options,
  });

  if (!status) {
    return;
  }

  await removeFromArchive(item, value ?? undefined);
};

const removeFromArchive = async (
  item: StoreItem,
  opts?: { re_add?: boolean; remove_history?: boolean; dont_remove_file?: boolean },
): Promise<void> => {
  try {
    const response = await request(`/api/history/${item._id}/archive`, { method: 'DELETE' });
    const data = await response.json();

    if (!response.ok) {
      toast.error(data.error);
      return;
    }

    toast.success(
      data.message || `Removed '${item.title || item.id || item.url || '??'}' from archive.`,
    );
  } catch (error: any) {
    console.error(error);
    toast.error(`Error: ${error.message}`);
    return;
  }

  let file_delete = config.app.remove_files;

  if (opts?.dont_remove_file) {
    file_delete = false;
  }

  if (opts?.re_add) {
    await retryItem(item, true, file_delete);
    return;
  }

  if (opts?.remove_history) {
    await deleteHistoryItems({ ids: [item._id], removeFile: file_delete });
  }

  await reloadHistory({ order: 'DESC', perPage: config.app.default_pagination });
};

const isQueuedAnimation = (item: StoreItem): string => {
  if (!item?.status || 'not_live' !== item.status) {
    return '';
  }

  return item.live_in || item.extras?.live_in || item.extras?.release_in ? 'animate-spin' : '';
};

const generateNfo = async (item: StoreItem): Promise<void> => {
  try {
    toast.info('Generating please wait...', { timeout: 2000 });
    const response = await request(`/api/history/${item._id}/nfo`, {
      method: 'POST',
      body: JSON.stringify({ type: 'tv', overwrite: true }),
    });
    const data = await response.json();

    if (!response.ok) {
      toast.error(data.error || 'Failed to generate NFO');
      return;
    }

    toast.success(data.message || 'NFO file generated');
  } catch (error: any) {
    toast.error(`Error: ${error.message}`);
  }
};
</script>
