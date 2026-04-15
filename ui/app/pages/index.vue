<template>
  <div class="space-y-6">
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

      <div class="flex flex-col gap-3 xl:items-end">
        <div class="flex flex-wrap gap-2 xl:justify-end">
          <UButton
            color="neutral"
            :variant="toggleFilter ? 'soft' : 'outline'"
            size="sm"
            icon="i-lucide-filter"
            @click="toggleFilter = !toggleFilter"
          >
            <span>Filter</span>
          </UButton>

          <UButton
            v-if="false === config.paused"
            color="neutral"
            variant="outline"
            size="sm"
            icon="i-lucide-pause"
            @click="() => void pauseDownload()"
          >
            <span>Pause</span>
          </UButton>

          <UButton
            v-else
            color="neutral"
            variant="outline"
            size="sm"
            icon="i-lucide-play"
            @click="() => void resumeDownload()"
          >
            <span>Resume</span>
          </UButton>

          <UButton
            color="neutral"
            variant="outline"
            size="sm"
            icon="i-lucide-plus"
            @click="config.showForm = !config.showForm"
          >
            <span>Add</span>
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
        </div>

        <UInput
          v-if="toggleFilter"
          id="filter"
          v-model.lazy="query"
          type="search"
          placeholder="Filter displayed content"
          icon="i-lucide-filter"
          size="sm"
          class="w-full xl:w-80"
        />
      </div>
    </div>

    <div v-if="config.showForm" ref="formSection" class="page-form-wrap scroll-mt-24">
      <NewDownload
        :item="item_form"
        @clear_form="item_form = {}"
        @getInfo="
          (url: string, preset: string = '', cli: string = '') => view_info(url, false, preset, cli)
        "
      />
    </div>

    <UEmpty
      v-if="!hasDownloadsContent"
      icon="i-lucide-inbox"
      title="No downloads yet"
      description="Add a URL to get started."
      class="rounded-lg border border-dashed border-default bg-muted/10 py-10"
    />

    <div v-else class="space-y-8">
      <section id="queue" class="scroll-mt-24 space-y-4">
        <Queue
          :thumbnails="show_thumbnail"
          :query="query"
          @getInfo="
            (url: string, preset: string = '', cli: string = '') =>
              view_info(url, false, preset, cli)
          "
          @getItemInfo="(id: string) => view_info(`/api/history/${id}`, true)"
          @clear_search="query = ''"
        />
      </section>

      <section id="history" class="scroll-mt-24 space-y-4">
        <div class="flex flex-wrap items-start justify-between gap-3 border-b border-default pb-3">
          <div class="space-y-1.5">
            <div class="flex items-center gap-2 text-base font-semibold text-highlighted">
              <UIcon :name="historyShell.icon" class="size-4 text-toned" />
              <h2>{{ historyShell.pageLabel }}</h2>
            </div>

            <p class="text-sm text-toned">{{ historyShell.description }}</p>
          </div>

          <UBadge color="neutral" variant="soft" size="sm">{{ historyCount }}</UBadge>
        </div>

        <History
          :query="query"
          :thumbnails="show_thumbnail"
          @getInfo="
            (url: string, preset: string = '', cli: string = '') =>
              view_info(url, false, preset, cli)
          "
          @add_new="(item: item_request) => void toNewDownload(item)"
          @getItemInfo="(id: string) => view_info(`/api/history/${id}`, true)"
          @clear_search="query = ''"
        />
      </section>
    </div>

    <GetInfo
      v-if="info_view.url"
      :link="info_view.url"
      :preset="info_view.preset"
      :cli="info_view.cli"
      :useUrl="info_view.useUrl"
      @closeModel="close_info()"
    />
  </div>
</template>

<script setup lang="ts">
import { useStorage } from '@vueuse/core';
import { useDialog } from '~/composables/useDialog';
import type { item_request } from '~/types/item';
import type { StoreItem } from '~/types/store';
import { requirePageShell } from '~/utils/topLevelNavigation';

const config = useConfigStore();
const stateStore = useStateStore();
const route = useRoute();
const { confirmDialog } = useDialog();

const bg_enable = useStorage<boolean>('random_bg', true);
const bg_opacity = useStorage<number>('random_bg_opacity', 0.95);
const display_style = useStorage<string>('display_style', 'grid');
const show_thumbnail = useStorage<boolean>('show_thumbnail', true);
const pageShell = requirePageShell('downloads');
const historyShell = requirePageShell('history');

const formSection = ref<HTMLElement | null>(null);
const info_view = ref({
  url: '',
  preset: '',
  cli: '',
  useUrl: false,
}) as Ref<{ url: string; preset: string; cli: string; useUrl: boolean }>;
const item_form = ref<item_request | object>({});
const query = ref('');
const toggleFilter = ref(false);

onMounted(async () => {
  if (route.query?.simple !== undefined) {
    const simpleMode = useStorage<boolean>('simple_mode', config.app.simple_mode || false);
    simpleMode.value = ['true', '1', 'yes', 'on'].includes(route.query.simple as string);
    await nextTick();
    const url = new URL(window.location.href);
    url.searchParams.delete('simple');
    window.history.replaceState({}, '', url.toString());
  }

  useHead({ title: getTitle() });
});

const queueCount = computed(() => stateStore.count('queue'));
const historyCount = computed(() => stateStore.count('history'));
const hasDownloadsContent = computed(
  () => queueCount.value > 0 || historyCount.value > 0 || query.value.trim().length > 0,
);

watch(toggleFilter, () => {
  if (!toggleFilter.value) {
    query.value = '';
  }
});

const getTitle = (): string => {
  if (!config.app.ui_update_title) {
    return 'YTPTube';
  }
  return `YTPTube: ( ${Object.keys(stateStore.queue).length || 0}/${config.app.max_workers}:${config.app.max_workers_per_extractor} | ${Object.keys(stateStore.history).length || 0} )`;
};

watch(
  () => stateStore.history,
  () => {
    if (!config.app.ui_update_title) {
      return;
    }
    useHead({ title: getTitle() });
  },
  { deep: true },
);

watch(
  () => stateStore.queue,
  () => {
    if (!config.app.ui_update_title) {
      return;
    }
    useHead({ title: getTitle() });
  },
  { deep: true },
);

const resumeDownload = async (): Promise<void> => {
  await request('/api/system/resume', { method: 'POST' });
};

const pauseDownload = async (): Promise<void> => {
  const { status } = await confirmDialog({
    title: 'Pause Downloads',
    confirmText: 'Pause',
    cancelText: 'Cancel',
    confirmColor: 'warning',
    message: 'Are you sure you want to pause all non-active downloads?',
  });

  if (!status) {
    return;
  }

  await request('/api/system/pause', { method: 'POST' });
};

const close_info = () => {
  info_view.value.url = '';
  info_view.value.preset = '';
  info_view.value.useUrl = false;
};

const view_info = (url: string, useUrl: boolean = false, preset: string = '', cli: string = '') => {
  info_view.value.url = url;
  info_view.value.useUrl = useUrl;
  info_view.value.preset = preset;
  info_view.value.cli = cli;
};

watch(
  () => info_view.value.url,
  (v) => {
    if (!bg_enable.value) {
      return;
    }

    document.querySelector('body')?.setAttribute('style', `opacity: ${v ? 1 : bg_opacity.value}`);
  },
);

const changeDisplay = (): void => {
  display_style.value = display_style.value === 'grid' ? 'list' : 'grid';
};

const toNewDownload = async (item: item_request | Partial<StoreItem>) => {
  if (!item) {
    return;
  }

  if (config.showForm) {
    config.showForm = false;
    await nextTick();
  }

  item_form.value = item;

  await nextTick();
  config.showForm = true;
  await nextTick();
  formSection.value?.scrollIntoView({ behavior: 'smooth', block: 'start' });
};
</script>

<style scoped>
.page-form-wrap {
  max-width: 100%;
}
</style>
