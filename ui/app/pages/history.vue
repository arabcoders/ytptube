<template>
  <main class="w-full min-w-0 max-w-full space-y-6">
    <div
      class="pointer-events-none fixed inset-0 z-20 bg-black/45 backdrop-blur-[1px] transition-all duration-500 ease-out"
      :class="lightsOut ? 'opacity-100' : 'opacity-0'"
      aria-hidden="true"
    />

    <div class="ytp-page-header">
      <div class="ytp-page-heading">
        <span class="ytp-page-icon">
          <UIcon :name="pageShell.icon" class="size-5" />
        </span>

        <div class="min-w-0 space-y-2">
          <div class="ytp-page-kicker">
            <span>{{ pageShell.sectionLabel }}</span>
            <span>/</span>
            <span>{{ pageShell.pageLabel }}</span>
          </div>

          <p class="max-w-3xl text-sm text-toned">{{ pageShell.description }}</p>
        </div>
      </div>

      <div class="flex w-full flex-wrap items-center gap-2 xl:w-auto xl:justify-end">
        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-plus"
          @click="addNewDownload"
        >
          <span>{{ t('common.add') }}</span>
        </UButton>

        <UButton
          color="neutral"
          :variant="showFilter ? 'soft' : 'outline'"
          size="sm"
          icon="i-lucide-filter"
          @click="
            () => {
              showFilter = !showFilter;
            }
          "
        >
          <span>{{ t('common.filter') }}</span>
        </UButton>

        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          :icon="display_style === 'list' ? 'i-lucide-list' : 'i-lucide-grid-2x2'"
          class="hidden sm:inline-flex"
          @click="changeDisplay"
        >
          <span class="hidden sm:inline">{{
            display_style === 'list' ? t('common.list') : t('common.grid')
          }}</span>
        </UButton>

        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-refresh-cw"
          :loading="isLoading"
          :disabled="isLoading"
          @click="() => reload({ order: 'DESC', perPage: config.app.default_pagination })"
        >
          <span>{{ t('common.refresh') }}</span>
        </UButton>

        <UInput
          v-if="showFilter"
          id="filter"
          v-model.lazy="query"
          type="search"
          :placeholder="t('common.filterDisplayedContent')"
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
          (page) => load(page, { order: 'DESC', perPage: config.app.default_pagination })
        "
      />
    </div>

    <div class="w-full min-w-0 max-w-full space-y-4">
      <div
        v-if="hasItems"
        class="flex flex-wrap items-center justify-between gap-3 ytp-card px-3 py-3"
      >
        <div class="flex flex-wrap items-center gap-2">
          <UButton
            color="neutral"
            variant="outline"
            size="sm"
            :icon="masterSelectAll ? 'i-lucide-square' : 'i-lucide-square-check-big'"
            @click="toggleMasterSelection"
          >
            {{ masterSelectAll ? t('common.unselect') : t('common.select') }}
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
              {{ t('common.actions') }}
            </UButton>
          </UDropdownMenu>
        </div>
      </div>

      <UAlert
        v-if="paginationInfo.isLoading && !hasItems"
        color="info"
        variant="soft"
        icon="i-lucide-loader-circle"
        :title="t('history.loading')"
      />

      <div
        v-if="'list' === contentStyle && hasItems"
        class="w-full min-w-0 max-w-full overflow-hidden ytp-table-surface"
      >
        <div class="w-full max-w-full overflow-x-auto overscroll-x-contain">
          <table class="min-w-210 table-fixed w-full text-sm">
            <thead class="bg-elevated/60 text-xs uppercase tracking-wide text-toned">
              <tr
                class="text-center [&>th]:border-e [&>th]:border-default/60 [&>th]:px-3 [&>th]:py-3 [&>th]:font-semibold [&>th:last-child]:border-e-0"
              >
                <th class="w-12">
                  <button
                    type="button"
                    class="cursor-pointer"
                    :aria-label="masterSelectAll ? t('common.unselectAll') : t('common.selectAll')"
                    @click="toggleMasterSelection"
                  >
                    <UIcon
                      :name="masterSelectAll ? 'i-lucide-square' : 'i-lucide-square-check-big'"
                      class="size-4"
                    />
                  </button>
                </th>
                <th class="text-start">{{ t('common.history') }}</th>
                <th class="w-32 whitespace-nowrap">{{ t('common.status') }}</th>
                <th class="w-36 whitespace-nowrap">{{ t('common.created') }}</th>
                <th class="w-36 whitespace-nowrap">{{ t('history.sizeStarts') }}</th>
                <th class="w-80 whitespace-nowrap">{{ t('common.actions') }}</th>
              </tr>
            </thead>

            <tbody class="divide-y divide-default">
              <tr
                v-for="item in displayedItems"
                :key="item._id"
                class="align-top transition-colors hover:bg-elevated/70 [&>td]:border-e [&>td]:border-default/60 [&>td:last-child]:border-e-0"
              >
                <td class="border-e border-default/60 px-3 py-3 text-center align-top">
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

                <td class="w-0 border-e border-default/60 px-3 py-3 align-top">
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
                      v-if="item.extras?.duration || mediaProfileLabel(item) || show_popover"
                      class="flex shrink-0 items-center gap-2"
                    >
                      <UBadge v-if="item.extras?.duration" color="info" variant="soft" size="sm">
                        {{ formatTime(item.extras.duration) }}
                      </UBadge>

                      <UBadge
                        v-if="mediaProfileLabel(item)"
                        color="neutral"
                        variant="soft"
                        size="sm"
                      >
                        {{ mediaProfileLabel(item) }}
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

                              <p v-if="getItemPath(item)" class="text-xs text-toned" dir="ltr">
                                <span class="font-semibold text-default">{{
                                  t('queue.path')
                                }}</span>
                                {{ getItemPath(item) }}
                              </p>
                            </div>

                            <img
                              v-if="showThumbnails && getListImage(item)"
                              :src="getListImage(item)"
                              class="max-h-56 w-full rounded-md object-cover"
                              @error="onImgError($event, item)"
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

                <td class="border-e border-default/60 px-3 py-3 text-center align-top text-sm">
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
                  class="border-e border-default/60 px-3 py-3 text-center align-top text-sm text-toned whitespace-nowrap"
                >
                  <UTooltip :text="moment(item.datetime).format('YYYY-M-DD H:mm Z')">
                    <span :date-datetime="item.datetime" v-rtime="item.datetime" />
                  </UTooltip>
                </td>

                <td
                  class="border-e border-default/60 px-3 py-3 text-center align-top text-sm text-toned whitespace-nowrap"
                >
                  <template
                    v-if="'not_live' === item.status && (item.live_in || item.extras?.release_in)"
                  >
                    <UTooltip
                      :text="
                        t('history.retryAt', {
                          date: moment(item.live_in || item.extras?.release_in).format(
                            'YYYY-M-DD H:mm Z',
                          ),
                        })
                      "
                    >
                      >
                      <span
                        :date-datetime="item.live_in || item.extras?.release_in"
                        v-rtime="item.live_in || item.extras?.release_in"
                      />
                    </UTooltip>
                  </template>

                  <template v-else>
                    {{
                      item.file_size ? formatBytes(item.file_size, 2, t) : t('common.notAvailable')
                    }}
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
                      @click="() => retryItem(item, true)"
                    >
                      {{ t('common.retry') }}
                    </UButton>

                    <UButton
                      v-if="item.filename && canShareUrl"
                      color="neutral"
                      variant="outline"
                      size="xs"
                      icon="i-lucide-share"
                      @click="() => shareUrl(item)"
                    />

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
                      {{ t('common.download') }}
                    </UButton>

                    <UButton
                      color="neutral"
                      variant="outline"
                      size="xs"
                      icon="i-lucide-trash"
                      @click="() => removeItem(item)"
                    >
                      {{ t('common.remove') }}
                    </UButton>

                    <UDropdownMenu v-if="item.url" :items="itemActionGroups(item)" :modal="false">
                      <UButton
                        color="neutral"
                        variant="outline"
                        size="xs"
                        icon="i-lucide-settings-2"
                        trailing-icon="i-lucide-chevron-down"
                      >
                        {{ t('common.actions') }}
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
          <div class="ytp-card flex h-full min-w-0 w-full max-w-full flex-col overflow-hidden">
            <div class="ytp-border-bottom-soft p-4 pb-3">
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
                          <p class="text-xs text-toned" dir="ltr">
                            <span class="font-semibold text-default">{{ t('queue.path') }}</span>
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
                    @click="
                      () => {
                        hideThumbnail = !hideThumbnail;
                      }
                    "
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
            </div>

            <div class="flex flex-1 flex-col gap-4 p-4">
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
                      @error="onImgError($event, item)"
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
                      @error="onImgError($event, item)"
                    />
                    <img v-else src="/images/placeholder.png" />
                  </span>

                  <template v-else>
                    <img
                      v-if="getGridImage(item)"
                      :src="getGridImage(item)"
                      @load="pImg"
                      @error="onImgError($event, item)"
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
                    :text="
                      t('history.retryAt', {
                        date: moment(item.live_in || item.extras?.release_in).format(
                          'YYYY-M-DD H:mm Z',
                        ),
                      })
                    "
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
                  v-if="item.extras?.duration"
                  type="button"
                  class="rounded-md border border-default bg-muted/20 px-3 py-2 text-toned transition hover:border-primary hover:text-default"
                  @click="toggleExpand(item._id, 'duration')"
                >
                  <span class="inline-flex w-full items-center justify-center gap-2">
                    <UIcon name="i-lucide-timer" class="size-4 shrink-0 text-toned" />
                    <span :class="['min-w-0 text-center', expandClass(item._id, 'duration')]">
                      {{ formatTime(item.extras.duration) }}
                    </span>
                  </span>
                </button>

                <button
                  v-if="mediaProfileLabel(item)"
                  type="button"
                  class="rounded-md border border-default bg-muted/20 px-3 py-2 text-toned transition hover:border-primary hover:text-default"
                  @click="toggleExpand(item._id, 'profile')"
                >
                  <span class="inline-flex w-full items-center justify-center gap-2">
                    <UIcon name="i-lucide-badge-info" class="size-4 shrink-0 text-toned" />
                    <span :class="['min-w-0 text-center', expandClass(item._id, 'profile')]">
                      {{ mediaProfileLabel(item) }}
                    </span>
                  </span>
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
                      {{ formatBytes(item.file_size, 2, t) }}
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

              <div class="ytp-border-top-soft px-4 py-4">
                <div class="flex flex-wrap gap-2 *:min-w-32 *:flex-1">
                  <UButton
                    v-if="showRetryAction(item)"
                    color="neutral"
                    variant="outline"
                    icon="i-lucide-rotate-cw"
                    class="w-full justify-center"
                    @click="() => retryItem(item, false)"
                  >
                    {{ t('common.retry') }}
                  </UButton>

                  <UButton
                    v-if="item.filename && canShareUrl"
                    color="neutral"
                    variant="outline"
                    icon="i-lucide-share"
                    class="w-full justify-center"
                    @click="() => shareUrl(item)"
                  >
                    {{ t('common.share') }}
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
                    {{ t('common.download') }}
                  </UButton>

                  <UButton
                    color="neutral"
                    variant="outline"
                    icon="i-lucide-trash"
                    class="w-full justify-center"
                    @click="() => removeItem(item)"
                  >
                    {{ config.app.remove_files ? t('common.remove') : t('common.clear') }}
                  </UButton>

                  <UDropdownMenu :items="itemActionGroups(item)" :modal="false" class="w-full">
                    <UButton
                      color="neutral"
                      variant="outline"
                      icon="i-lucide-settings-2"
                      trailing-icon="i-lucide-chevron-down"
                      class="w-full justify-center"
                    >
                      {{ t('common.actions') }}
                    </UButton>
                  </UDropdownMenu>
                </div>
              </div>
            </div>
          </div>
        </LateLoader>
      </div>

      <div v-if="!hasItems && !paginationInfo.isLoading" class="space-y-4">
        <UAlert
          v-if="query"
          color="warning"
          variant="soft"
          icon="i-lucide-search"
          :title="t('queue.filterTitle')"
        >
          <template #description>
            <div class="space-y-3 text-sm text-default">
              <p>
                {{ t('queue.noResultsFor') }} <code>{{ query }}</code
                >.
              </p>

              <p>
                {{ t('queue.filterHelp') }}
                {{ t('queue.filterKeyValue') }}
              </p>

              <div>
                <p class="mb-1 font-medium">{{ t('queue.filterExamples') }}</p>
                <ul class="list-disc space-y-1 ps-5">
                  <li><code>youtube.com</code> - {{ t('queue.filterExample1') }}</li>
                  <li><code>is_live:true</code> - {{ t('queue.filterExample2') }}</li>
                  <li><code>source_name:task_name</code> - {{ t('queue.filterExample3') }}</li>
                </ul>
              </div>
            </div>
          </template>
        </UAlert>

        <UEmpty
          v-else
          icon="i-lucide-triangle-alert"
          :title="t('common.noItems')"
          :description="t('history.empty')"
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
            (page) => load(page, { order: 'DESC', perPage: config.app.default_pagination })
          "
        />
      </div>
    </div>

    <UModal
      v-if="video_item"
      :open="videoOpen"
      :dismissible="true"
      :title="video_item?.title || t('history.player')"
      :ui="{ content: lightsOut ? 'sm:max-w-5xl shadow-2xl' : 'sm:max-w-5xl', body: 'p-0' }"
      @update:open="handleVideoOpenChange"
    >
      <template #body>
        <VideoPlayer
          type="default"
          :isMuted="false"
          autoplay="true"
          :isControls="true"
          :item="video_item"
          class="w-full"
          @closeModel="() => void requestCloseVideo()"
          @error="async (error: string) => await box.alert(error)"
          @playback-state-change="(playing: boolean) => (playingNow = playing)"
        />
      </template>
    </UModal>

    <UModal
      v-if="embed_url"
      :open="Boolean(embed_url)"
      :dismissible="true"
      :title="t('common.embeddedPlayer')"
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
import { useDirtyCloseGuard } from '~/composables/useDirtyCloseGuard';
import { useDialog } from '~/composables/useDialog';
import { useAppSocket } from '~/composables/useAppSocket';
import { useExpandableMeta } from '~/composables/useExpandableMeta';
import { useHistoryState } from '~/composables/useHistoryState';
import { useMediaQuery } from '~/composables/useMediaQuery';
import { useWebShare } from '~/composables/useWebShare';
import type { item_request } from '~/types/item';
import type { StoreItem } from '~/types/store';
import {
  deepIncludes,
  formatBytes,
  formatTime,
  getHistoryImage,
  getRemoteImage,
  getPath,
  isDownloadSkipped,
  makeDownload,
  request,
  uri,
} from '~/utils';
import { getEmbedable, isEmbedable } from '~/utils/embedable';
import { mediaProfileLabel } from '~/utils/mediaProfile';
import { usePageShell } from '~/composables/usePageShell';
const { t } = useI18n();

const config = useYtpConfig();
const stateStore = useQueueState();
const socketStore = useAppSocket();
const toast = useNotification();
const box = useConfirm();
const { confirmDialog, promptDialog } = useDialog();
const { toggleExpand, expandClass } = useExpandableMeta();
const { canShare, shareUrl } = useWebShare();
const pendingDownloadFormItem = useState<item_request | Record<string, never>>(
  'pending-download-form-item',
  () => ({}),
);
const {
  items: historyItems,
  pagination,
  isLoading,
  isLoaded,
  load,
  reload,
  remove,
  rename,
  moveHandler,
} = useHistoryState();

const show_thumbnail = useStorage<boolean>('show_thumbnail', true);
const hideThumbnail = useStorage<boolean>('hideThumbnailHistory', false);
const display_style = useStorage<'grid' | 'list'>('history_display_style', 'grid');
const isMobile = useMediaQuery({ maxWidth: 639 });
const bg_enable = useStorage<boolean>('random_bg', true);
const bg_opacity = useStorage<number>('random_bg_opacity', 0.95);
const thumbnail_ratio = useStorage<'is-16by9' | 'is-3by1'>('thumbnail_ratio', 'is-3by1');
const show_popover = useStorage<boolean>('show_popover', true);

const pageShell = usePageShell('history');
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
const playingNow = ref(false);
const expandedMessages = reactive<Record<string, Set<string>>>({});

const contentStyle = computed<'grid' | 'list'>(() =>
  isMobile.value ? 'grid' : display_style.value,
);
const showThumbnails = computed(() => show_thumbnail.value && !hideThumbnail.value);
const lightsOut = computed(() => Boolean(video_item.value && playingNow.value));
const videoOpen = computed<boolean>({
  get: () => Boolean(video_item.value),
  set: (value: boolean) => {
    if (value) {
      return;
    }

    closeVideo();
  },
});
const paginationInfo = computed(() => ({
  ...pagination.value,
  isLoading: isLoading.value,
  isLoaded: isLoaded.value,
}));

const handleHistoryItemMoved = moveHandler();

onMounted(async () => {
  socketStore.on('item_moved', handleHistoryItemMoved);
  await load(1, { order: 'DESC', perPage: config.app.default_pagination });
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

const canShareUrl = computed(() => canShare());

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

const closeVideo = (): void => {
  playingNow.value = false;
  video_item.value = null;
};

const { handleOpenChange: handleVideoOpenChange, requestClose: requestCloseVideo } =
  useDirtyCloseGuard(videoOpen, {
    dirty: playingNow,
    title: t('common.closePlayer'),
    message: t('common.closePlayerDesc'),
    confirmText: t('common.closePlayer'),
    cancelText: t('common.keepPlaying'),
    onDiscard: async () => {
      closeVideo();
    },
  });

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

const addNewDownload = async (): Promise<void> => {
  config.showForm = true;
  await nextTick();
  await navigateTo('/');
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
const getListImage = (item: StoreItem): string => getHistoryImage(item, false) || '';
const getGridImage = (item: StoreItem): string => getHistoryImage(item) || '';
const showRetryAction = (item: StoreItem): boolean => !item.filename && !isDownloadSkipped(item);

const hasIncomplete = computed(() => historyItems.value.some((item) => item.status !== 'finished'));
const hasCompleted = computed(() =>
  historyItems.value.some((item) => item.status === 'finished' || item.status === 'skip'),
);

const bulkActionGroups = computed(() => {
  const groups: Array<Array<Record<string, unknown>>> = [
    [
      {
        label: t('common.download'),
        icon: 'i-lucide-download',
        disabled: !hasSelected.value || selectedDownloadableCount.value < 1,
        onSelect: () => void downloadSelected(),
      },
      {
        label: config.app.remove_files ? t('common.remove') : t('common.clear'),
        icon: 'i-lucide-trash',
        disabled: !hasSelected.value,
        onSelect: deleteSelectedItems,
      },
    ],
  ];

  const cleanupActions: Array<Record<string, unknown>> = [];

  if (hasCompleted.value) {
    cleanupActions.push({
      label: t('common.clearCompleted'),
      icon: 'i-lucide-circle-check-big',
      onSelect: clearCompleted,
    });
  }

  if (hasIncomplete.value) {
    cleanupActions.push(
      {
        label: t('common.clearIncomplete'),
        icon: 'i-lucide-circle-x',
        onSelect: clearIncomplete,
      },
      {
        label: t('common.retryIncomplete'),
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
      label: t('common.playVideo'),
      icon: 'i-lucide-play',
      onSelect: () => {
        video_item.value = item;
      },
    });

    if ('error' === item.status) {
      mediaActions.push({
        label: t('common.retryDownload'),
        icon: 'i-lucide-rotate-cw',
        onSelect: () => void retryItem(item, true),
      });
    }

    mediaActions.push({
      label: t('common.generateNfo'),
      icon: 'i-lucide-file-code-2',
      onSelect: () => void generateNfo(item),
    });

    mediaActions.push({
      label: t('common.renameFile'),
      icon: 'i-lucide-pencil',
      onSelect: () => void renameFile(item),
    });
  } else if (isEmbedable(item.url)) {
    mediaActions.push({
      label: t('common.playVideo'),
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
      label: t('common.ytdlpInformation'),
      icon: 'i-lucide-info',
      onSelect: () => view_info(item.url, false, item.preset, item.cli),
    },
    {
      label: t('common.localInformation'),
      icon: 'i-lucide-info',
      onSelect: () => view_info(`/api/history/${item._id}`, true),
    },
    {
      label: t('common.addToDownloadForm'),
      icon: 'i-lucide-copy',
      onSelect: () => void retryItem(item, true),
    },
  ]);

  if (item.is_archivable && !item.is_archived) {
    groups.push([
      {
        label: t('common.addToArchive'),
        icon: 'i-lucide-archive',
        onSelect: () => void addArchiveDialog(item),
      },
    ]);
  }

  if (item.is_archivable && item.is_archived) {
    groups.push([
      {
        label: t('common.removeFromArchive'),
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
    toast.error(t('common.noItemsSelected'));
    return;
  }

  let message = t('history.confirmActionCount', {
    action: config.app.remove_files ? t('common.remove') : t('common.clear'),
    count: selectedElms.value.length,
  });

  if (true === config.app.remove_files) {
    message += t('history.removeFilesWarning');
  }

  if (false === (await box.confirm(message))) {
    return;
  }

  await remove({ ids: [...selectedElms.value], removeFile: config.app.remove_files });
  selectedElms.value = [];
  await reload({ order: 'DESC', perPage: config.app.default_pagination });
};

const clearCompleted = async (): Promise<void> => {
  const message = t('history.clearCompletedConfirm');

  if (false === (await box.confirm(message))) {
    return;
  }

  selectedElms.value = [];

  await remove({ status: 'finished,skip', removeFile: false });

  await reload({ order: 'DESC', perPage: config.app.default_pagination });
};

const clearIncomplete = async (): Promise<void> => {
  if (false === (await box.confirm(t('history.clearIncompleteConfirm')))) {
    return;
  }

  selectedElms.value = [];
  await remove({ status: '!finished', removeFile: false });
  await reload({ order: 'DESC', perPage: config.app.default_pagination });
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
      return t('history.downloadSkipped');
    }

    if (item.extras?.is_premiere) {
      return t('history.premiered');
    }

    return item.is_live ? t('history.streamed') : t('common.completed');
  }

  if ('error' === item.status) {
    if (item.filename) {
      return t('history.partialError');
    }

    return t('common.error');
  }

  if ('cancelled' === item.status) {
    return t('common.cancelled');
  }

  if ('not_live' === item.status) {
    if (item.extras?.is_premiere) {
      return t('history.premiere');
    }

    return t('common.live');
  }

  if ('skip' === item.status) {
    return t('common.skipped');
  }

  return item.status || t('history.unknown');
};

const retryIncomplete = async (): Promise<void> => {
  if (false === (await box.confirm(t('history.retryIncompleteConfirm')))) {
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
    title: t('history.archiveTitle'),
    message: t('history.archiveConfirm', { title: item.title || item.id || item.url || '??' }),
    confirmText: t('history.archiveLabel'),
    confirmColor: 'warning',
    options: [{ key: 'remove_history', label: t('history.removeFromHistory') }],
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

    toast.success(
      data.message ?? t('history.archived', { title: item.title || item.id || item.url || '??' }),
    );
  } catch (error: any) {
    console.error(error);
    return;
  }

  if ((opts as { remove_history?: boolean })?.remove_history) {
    await remove({ ids: [item._id], removeFile: false });
  }

  await reload({ order: 'DESC', perPage: config.app.default_pagination });
};

const removeItem = async (item: StoreItem): Promise<void> => {
  const action = config.app.remove_files ? t('common.remove') : t('common.clear');
  const title = item.title || item.id || item.url || '??';
  const message =
    item.status === 'finished' && config.app.remove_files
      ? t('history.itemActionConfirmWithFiles', { action, title })
      : t('history.itemActionConfirm', { action, title });

  if (false === (await box.confirm(message))) {
    return;
  }

  await remove({ ids: [item._id], removeFile: config.app.remove_files });

  if (selectedElms.value.includes(item._id || '')) {
    selectedElms.value = selectedElms.value.filter((entry) => entry !== item._id);
  }

  await reload({ order: 'DESC', perPage: config.app.default_pagination });
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

  await remove({ ids: [item._id], removeFile: remove_file });

  if (selectedElms.value.includes(item._id || '')) {
    selectedElms.value = selectedElms.value.filter((entry) => entry !== item._id);
  }

  await reload({ order: 'DESC', perPage: config.app.default_pagination });

  if (true === re_add) {
    toast.info(t('common.itemAddedToForm'));
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

const onImgError = (event: Event, item: StoreItem): void => {
  const target = event.target as HTMLImageElement;
  const fallback = item ? getRemoteImage(item, false) || '' : '';
  const currentSrc = target.getAttribute('src') || '';

  if (target.src.endsWith('/images/placeholder.png')) {
    return;
  }

  if (fallback && currentSrc !== uri(fallback)) {
    target.src = uri(fallback);
    return;
  }

  target.src = '/images/placeholder.png';
};

const downloadSelected = async (): Promise<void> => {
  if (selectedElms.value.length < 1) {
    toast.error(t('common.noItemsSelected'));
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
      toast.error(json.error || t('common.failedStartDownload'));
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
    toast.error(t('common.errorPrefix', { msg: error.message }));
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
    { key: 'remove_history', label: t('history.removeFromHistory') },
    { key: 're_add', label: t('common.readdToForm') },
  ];

  if (config.app.remove_files) {
    options.push({ key: 'dont_remove_file', label: t('history.dontRemoveFiles') });
  }

  const { status, value } = await confirmDialog({
    title: t('history.removeFromArchiveTitle'),
    message: t('history.removedFromArchive', { title: item.title || item.id || item.url || '??' }),
    confirmText: t('common.remove'),
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
      data.message ||
        t('history.removedFromArchive', { title: item.title || item.id || item.url || '??' }),
    );
  } catch (error: any) {
    console.error(error);
    toast.error(t('common.errorPrefix', { msg: error.message }));
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
    await remove({ ids: [item._id], removeFile: file_delete });
  }

  await reload({ order: 'DESC', perPage: config.app.default_pagination });
};

const isQueuedAnimation = (item: StoreItem): string => {
  if (!item?.status || 'not_live' !== item.status) {
    return '';
  }

  return item.live_in || item.extras?.live_in || item.extras?.release_in ? 'animate-spin' : '';
};

const generateNfo = async (item: StoreItem): Promise<void> => {
  try {
    toast.info(t('common.generating'), { timeout: 2000 });
    const response = await request(`/api/history/${item._id}/nfo`, {
      method: 'POST',
      body: JSON.stringify({ type: 'tv', overwrite: true }),
    });
    const data = await response.json();

    if (!response.ok) {
      toast.error(data.error || t('common.failedGenerateNfo'));
      return;
    }

    toast.success(data.message || t('common.nfoGenerated'));
  } catch (error: any) {
    toast.error(t('common.errorPrefix', { msg: error.message }));
  }
};

const renameFile = async (item: StoreItem): Promise<void> => {
  if (!item.filename) {
    return;
  }

  const currentName = item.filename.split('/').pop() || item.filename;
  const { status, value: newName } = await promptDialog({
    title: t('history.renameFileTitle'),
    message: t('files.renameItemDesc', { name: currentName }),
    initial: currentName,
    confirmText: t('common.rename'),
    cancelText: t('common.cancel'),
  });

  if (!status) {
    return;
  }

  const trimmedName = (newName || '').trim();
  if (!trimmedName || trimmedName === currentName) {
    return;
  }

  const success = await rename(item, trimmedName);
  if (success) {
    toast.success(t('common.renamed', { name: currentName }));
  }
};
</script>
