<template>
  <div class="space-y-6">
    <UPageHeader
      title="Downloads"
      description="Queued and completed downloads are displayed here."
      :ui="{
        root: 'border-b border-default py-4',
        headline: 'hidden',
        title: 'text-2xl font-semibold text-highlighted',
        description: 'text-sm text-toned',
        wrapper: 'flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between',
        links: 'flex flex-wrap items-center gap-2',
      }"
    >
      <template #links>
        <UDashboardToolbar
          :ui="{
            root: 'w-full border-0 p-0',
            left: 'flex flex-wrap items-center gap-2',
            right: 'flex flex-wrap items-center gap-2',
          }"
        >
          <template #left>
            <UInput
              v-if="toggleFilter"
              id="filter"
              v-model.lazy="query"
              type="search"
              placeholder="Filter displayed content"
              icon="i-lucide-filter"
              size="sm"
              class="w-full sm:w-72"
            />

            <UButton
              color="neutral"
              variant="outline"
              size="sm"
              icon="i-lucide-filter"
              @click="toggleFilter = !toggleFilter"
            >
              <span v-if="!isMobile">Filter</span>
            </UButton>

            <UButton
              v-if="false === config.paused"
              color="neutral"
              variant="outline"
              size="sm"
              icon="i-lucide-pause"
              @click="() => void pauseDownload()"
            >
              <span v-if="!isMobile">Pause</span>
            </UButton>

            <UButton
              v-else
              color="neutral"
              variant="outline"
              size="sm"
              icon="i-lucide-play"
              @click="() => void resumeDownload()"
            >
              <span v-if="!isMobile">Resume</span>
            </UButton>

            <UButton
              color="neutral"
              variant="outline"
              size="sm"
              icon="i-lucide-plus"
              @click="config.showForm = !config.showForm"
            >
              <span v-if="!isMobile">Add</span>
            </UButton>
          </template>

          <template #right>
            <UButton
              color="neutral"
              variant="outline"
              size="sm"
              :icon="display_style === 'list' ? 'i-lucide-list' : 'i-lucide-grid-2x2'"
              @click="changeDisplay"
            >
              <span v-if="!isMobile">{{ display_style === 'list' ? 'List' : 'Grid' }}</span>
            </UButton>
          </template>
        </UDashboardToolbar>
      </template>
    </UPageHeader>

    <div v-if="config.showForm" class="page-form-wrap">
      <NewDownload
        :item="item_form"
        @clear_form="item_form = {}"
        @getInfo="
          (url: string, preset: string = '', cli: string = '') => view_info(url, false, preset, cli)
        "
      />
    </div>

    <UPageCard
      variant="outline"
      :ui="{
        root: 'w-full min-w-0 max-w-full bg-default',
        container: 'w-full min-w-0 max-w-full p-0 sm:p-0',
        wrapper: 'w-full min-w-0 items-stretch',
        body: 'w-full min-w-0 max-w-full p-0',
      }"
    >
      <template #body>
        <UTabs
          v-model="activeTab"
          :items="tabItems"
          value-key="value"
          color="neutral"
          variant="link"
          size="md"
          :content="false"
          :ui="{
            root: 'flex-col gap-4',
            list: 'border-b border-default px-2 sm:px-4',
            trigger: 'justify-start rounded-none px-3 py-3 text-sm font-medium',
            trailingBadge: 'ml-1',
          }"
          @update:model-value="(value) => void setActiveTab(value as TabType)"
        />

        <div class="w-full min-w-0 max-w-full px-0 pt-2">
          <div v-show="'queue' === activeTab" class="w-full min-w-0 max-w-full">
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
          </div>

          <div v-show="'history' === activeTab" class="w-full min-w-0 max-w-full">
            <History
              :query="query"
              :thumbnails="show_thumbnail"
              @getInfo="
                (url: string, preset: string = '', cli: string = '') =>
                  view_info(url, false, preset, cli)
              "
              @add_new="(item: item_request) => toNewDownload(item)"
              @getItemInfo="(id: string) => view_info(`/api/history/${id}`, true)"
              @clear_search="query = ''"
            />
          </div>
        </div>
      </template>
    </UPageCard>

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

const config = useConfigStore();
const stateStore = useStateStore();
const route = useRoute();
const router = useRouter();
const { confirmDialog } = useDialog();

const bg_enable = useStorage<boolean>('random_bg', true);
const bg_opacity = useStorage<number>('random_bg_opacity', 0.95);
const display_style = useStorage<string>('display_style', 'grid');
const show_thumbnail = useStorage<boolean>('show_thumbnail', true);
const isMobile = useMediaQuery({ maxWidth: 1024 });

const info_view = ref({
  url: '',
  preset: '',
  cli: '',
  useUrl: false,
}) as Ref<{ url: string; preset: string; cli: string; useUrl: boolean }>;
const item_form = ref<item_request | object>({});
const query = ref('');
const toggleFilter = ref(false);

type TabType = 'queue' | 'history';

const activeTab = ref<TabType>('queue');

const getInitialTab = (): TabType => {
  const tabParam = route.query.tab as string;
  return tabParam === 'queue' || tabParam === 'history' ? tabParam : 'queue';
};

const setActiveTab = async (tab: TabType): Promise<void> => {
  activeTab.value = tab;
  await router.push({ query: { ...route.query, tab }, replace: true });
};

watch(
  () => route.query.tab,
  (newTab) => {
    if (!['queue', 'history'].includes(newTab as string)) {
      return;
    }
    activeTab.value = newTab as TabType;
  },
);

onMounted(async () => {
  const route = useRoute();

  if (route.query?.simple !== undefined) {
    const simpleMode = useStorage<boolean>('simple_mode', config.app.simple_mode || false);
    simpleMode.value = ['true', '1', 'yes', 'on'].includes(route.query.simple as string);
    await nextTick();
    const url = new URL(window.location.href);
    url.searchParams.delete('simple');
    window.history.replaceState({}, '', url.toString());
  }

  activeTab.value = getInitialTab();
  useHead({ title: getTitle() });
});

const queueCount = computed(() => stateStore.count('queue'));
const historyCount = computed(() => stateStore.count('history'));

const tabItems = computed(() => [
  {
    label: 'Downloads',
    icon: 'i-lucide-download',
    value: 'queue',
    badge: { label: String(queueCount.value), color: 'info' as const, variant: 'soft' as const },
  },
  {
    label: 'History',
    icon: 'i-lucide-history',
    value: 'history',
    badge: {
      label: String(historyCount.value),
      color: 'primary' as const,
      variant: 'soft' as const,
    },
  },
]);

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
};
</script>

<style scoped>
.page-form-wrap {
  max-width: 100%;
}
</style>
