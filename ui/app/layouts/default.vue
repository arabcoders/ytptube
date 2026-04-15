<template>
  <UApp :toaster="toasterConfig">
    <Transition name="shell-mode" mode="out-in">
      <div v-if="simpleMode" key="simple" class="shell-stage flex flex-col">
        <UAlert
          v-if="showConnectionBanner"
          color="warning"
          variant="soft"
          orientation="horizontal"
          :title="connectionBannerTitle"
        >
          <template #leading>
            <UIcon
              :name="connectionBannerIcon"
              :class="[
                'size-4 shrink-0 text-warning',
                socket.connectionStatus === 'connecting' ? 'animate-spin' : '',
              ]"
            />
          </template>

          <template v-if="socket.connectionStatus === 'disconnected'" #actions>
            <UButton
              color="neutral"
              variant="link"
              size="sm"
              class="px-0"
              @click="() => socket.reconnect()"
            >
              Reconnect
            </UButton>
          </template>
        </UAlert>

        <Simple @show_settings="() => (show_settings = true)" />
      </div>

      <div v-else key="regular" class="shell-stage flex flex-col">
        <Shutdown v-if="app_shutdown" />

        <div id="main_container" class="shell-root flex flex-col" v-else>
          <UAlert
            v-if="newVersionIsAvailable"
            color="success"
            variant="soft"
            orientation="horizontal"
            title="A new WebUI version is installed."
          >
            <template #leading>
              <UIcon name="i-lucide-info" class="size-4 shrink-0 text-success" />
            </template>

            <template #actions>
              <UButton color="neutral" variant="link" size="sm" class="px-0" @click="reloadPage">
                Reload app
              </UButton>
            </template>
          </UAlert>

          <UDashboardGroup
            storage="local"
            storage-key="ytptube-shell"
            class="shell-dashboard flex-1"
            :ui="{ base: 'relative flex min-h-full overflow-visible' }"
          >
            <UDashboardSidebar
              side="left"
              collapsible
              resizable
              :default-size="15"
              :min-size="10"
              :max-size="20"
              :collapsed-size="4"
              :ui="dashboardSidebarUi"
            >
              <template #header="{ collapsed }">
                <UTooltip :text="connectionStatusLabel">
                  <NuxtLink
                    to="/"
                    class="flex w-full min-w-0 items-center gap-2 rounded-xl transition-colors hover:bg-elevated/60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                    :class="collapsed ? 'justify-center p-1' : 'px-1.5 py-1'"
                    aria-label="Go to home"
                  >
                    <span
                      class="relative inline-flex shrink-0 items-center justify-center transition-all duration-200"
                      :class="
                        collapsed
                          ? 'size-10 rounded-xl bg-elevated/80 ring ring-default shadow-xs'
                          : 'size-9 rounded-lg'
                      "
                    >
                      <img
                        :src="uri('/images/favicon.png')"
                        alt="YTPTube"
                        class="rounded-lg object-contain"
                        :class="collapsed ? 'size-6' : 'size-5'"
                      />
                      <span
                        aria-hidden="true"
                        class="absolute right-0 bottom-0 size-2.5 rounded-full ring-2 ring-default"
                        :class="connectionStatusDotClass"
                      />
                    </span>

                    <div v-if="false === collapsed" class="min-w-0">
                      <p class="truncate text-sm font-semibold" :class="connectionStatusColor">
                        YTPTube
                      </p>
                      <p v-if="config?.app?.instance_title" class="truncate text-xs text-toned">
                        {{ config.app.instance_title }}
                      </p>
                    </div>
                  </NuxtLink>
                </UTooltip>
              </template>

              <template #default="{ collapsed }">
                <div class="flex h-full flex-col gap-6 px-1 py-1">
                  <div v-for="section in sidebarSections" :key="section.id" class="space-y-2">
                    <p
                      v-if="false === collapsed && section.label"
                      class="px-2 text-[11px] font-semibold tracking-[0.22em] text-toned uppercase"
                    >
                      {{ section.label }}
                    </p>

                    <UNavigationMenu
                      orientation="vertical"
                      :collapsed="collapsed"
                      :items="section.items"
                      :tooltip="true"
                      :ui="navigationUi(collapsed)"
                    />
                  </div>
                </div>
              </template>

              <template #footer="{ collapsed }">
                <div v-if="false === collapsed" class="w-full"></div>
              </template>
            </UDashboardSidebar>

            <UDashboardPanel class="min-w-0 bg-transparent" :ui="dashboardPanelUi">
              <template #header>
                <UDashboardNavbar :toggle="false" :title="pageTitle" :ui="dashboardNavbarUi">
                  <template #left>
                    <div class="flex items-center gap-2">
                      <UDashboardSidebarToggle class="lg:hidden" />
                      <UButton
                        to="/"
                        color="neutral"
                        variant="ghost"
                        size="sm"
                        icon="i-lucide-house"
                        class="lg:hidden"
                      >
                        Home
                      </UButton>
                      <UDashboardSidebarCollapse class="hidden lg:inline-flex" />
                    </div>
                  </template>

                  <template #right>
                    <div class="flex items-center gap-1 sm:gap-2">
                      <NotifyDropdown />

                      <UButton
                        color="neutral"
                        variant="ghost"
                        size="sm"
                        icon="i-lucide-refresh-cw"
                        @click="reloadPage"
                      >
                        <span class="hidden xl:inline">Reload</span>
                      </UButton>

                      <UDashboardSearchButton class="shrink-0" />

                      <UColorModeButton
                        color="neutral"
                        variant="ghost"
                        size="sm"
                        aria-label="Toggle color mode"
                      />

                      <UButton
                        color="neutral"
                        variant="ghost"
                        size="sm"
                        icon="i-lucide-settings-2"
                        @click="show_settings = !show_settings"
                      >
                        <span class="hidden xl:inline">WebUI Settings</span>
                      </UButton>

                      <UButton
                        v-if="true === config.app.is_native"
                        color="error"
                        variant="ghost"
                        size="sm"
                        icon="i-lucide-power"
                        @click="shutdownApp"
                      >
                        <span class="hidden xl:inline">Shutdown</span>
                      </UButton>
                    </div>
                  </template>
                </UDashboardNavbar>
              </template>

              <template #body>
                <div class="relative flex min-h-full min-w-0 max-w-full flex-1 flex-col">
                  <NuxtLoadingIndicator />

                  <div
                    class="flex min-h-0 min-w-0 max-w-full flex-1 flex-col px-4 py-4 sm:px-5 sm:py-5 lg:px-6"
                  >
                    <div class="flex min-h-0 min-w-0 max-w-full flex-1 flex-col gap-4">
                      <UAlert
                        v-if="!config.is_loaded"
                        :color="config.is_loading ? 'info' : 'error'"
                        variant="soft"
                        :title="
                          config.is_loading
                            ? 'Loading configuration...'
                            : 'Failed to load configuration'
                        "
                      >
                        <template #leading>
                          <UIcon
                            :name="
                              config.is_loading
                                ? 'i-lucide-loader-circle'
                                : 'i-lucide-triangle-alert'
                            "
                            :class="[
                              'size-4 shrink-0',
                              config.is_loading ? 'animate-spin text-info' : 'text-error',
                            ]"
                          />
                        </template>

                        <template #description>
                          <div class="space-y-3">
                            <p v-if="config.is_loading" class="text-sm text-default">
                              This usually takes less than a few seconds. If this is taking too
                              long,
                              <button
                                type="button"
                                class="font-semibold text-highlighted underline-offset-2 hover:underline"
                                @click="reloadPage"
                              >
                                click here
                              </button>
                              to reload the page.
                            </p>

                            <p v-else class="text-sm text-default">
                              Failed to load the application configuration. This likely indicates a
                              problem with the backend. Try to
                              <button
                                type="button"
                                class="font-semibold text-highlighted underline-offset-2 hover:underline"
                                @click="() => config.loadConfig(true)"
                              >
                                reload configuration
                              </button>
                              or
                              <button
                                type="button"
                                class="font-semibold text-highlighted underline-offset-2 hover:underline"
                                @click="reloadPage"
                              >
                                reload the page
                              </button>
                              .
                            </p>

                            <div
                              v-if="socket.error"
                              class="flex flex-wrap items-center gap-2 border-t border-default pt-3 text-error"
                            >
                              <UIcon name="i-lucide-triangle-alert" class="size-4" />
                              <span
                                class="inline-flex min-w-6 items-center justify-center rounded-full bg-error px-2 py-0.5 text-xs font-semibold text-white"
                              >
                                {{ socket.error_count }}
                              </span>
                              <span>
                                {{ socket.error }}. Check the developer console for more
                                information.
                              </span>
                            </div>
                          </div>
                        </template>
                      </UAlert>

                      <UAlert
                        v-if="showConnectionBanner"
                        color="warning"
                        variant="soft"
                        orientation="horizontal"
                        :title="connectionBannerTitle"
                      >
                        <template #leading>
                          <UIcon
                            :name="connectionBannerIcon"
                            :class="[
                              'size-4 shrink-0 text-warning',
                              socket.connectionStatus === 'connecting' ? 'animate-spin' : '',
                            ]"
                          />
                        </template>

                        <template v-if="socket.connectionStatus === 'disconnected'" #actions>
                          <UButton
                            color="neutral"
                            variant="link"
                            size="sm"
                            class="px-0"
                            @click="() => socket.reconnect()"
                          >
                            Reconnect
                          </UButton>
                        </template>
                      </UAlert>

                      <div
                        v-if="config.is_loaded"
                        class="flex min-h-0 min-w-0 max-w-full flex-1 flex-col"
                      >
                        <NuxtPage :isLoading="loadingImage" @reload_bg="() => loadImage(true)" />
                      </div>
                    </div>

                    <footer
                      v-if="config.is_loaded"
                      class="shell-footer mt-auto border-t border-default pt-6 text-sm text-toned"
                    >
                      <div class="grid gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
                        <div class="space-y-3">
                          <div class="flex flex-wrap items-center gap-x-3 gap-y-2">
                            <NuxtLink
                              href="https://github.com/ArabCoders/ytptube"
                              target="_blank"
                              class="inline-flex items-center gap-2 font-semibold text-highlighted"
                            >
                              <UIcon name="i-lucide-github" class="size-4" />
                              <span>YTPTube</span>
                            </NuxtLink>

                            <UTooltip :text="buildTooltip">
                              <span class="text-xs has-tooltip">
                                {{ config?.app?.app_version || 'unknown' }}
                              </span>
                            </UTooltip>
                          </div>

                          <p
                            v-if="config.app?.new_version"
                            class="flex flex-wrap items-center gap-2 text-xs"
                          >
                            <UIcon name="i-lucide-info" class="size-4 text-warning" />
                            <span>Update available:</span>
                            <NuxtLink
                              :href="`https://github.com/ArabCoders/ytptube/releases/tag/${config.app.new_version}`"
                              target="_blank"
                              class="font-semibold text-highlighted"
                            >
                              {{ config.app.new_version }}
                            </NuxtLink>
                          </p>

                          <button
                            v-else
                            type="button"
                            class="inline-flex items-center gap-2 text-xs text-left transition-colors hover:text-highlighted disabled:opacity-60"
                            :disabled="checkingUpdates"
                            @click="checkForUpdates"
                          >
                            <UIcon
                              :name="
                                checkingUpdates
                                  ? 'i-lucide-loader-circle'
                                  : 'i-lucide-circle-check-big'
                              "
                              :class="['size-4', checkingUpdates ? 'animate-spin' : '']"
                            />
                            <span>{{ updateCheckMessage }}</span>
                          </button>

                          <p v-if="config.app?.started" class="flex items-center gap-2 text-xs">
                            <UIcon name="i-lucide-clock-3" class="size-4" />
                            <UTooltip
                              :text="
                                'Started: ' +
                                moment.unix(config.app?.started).format('YYYY-MM-DD HH:mm Z')
                              "
                            >
                              <span class="has-tooltip">
                                {{ moment.unix(config.app?.started).fromNow() }}
                              </span>
                            </UTooltip>
                          </p>
                        </div>

                        <div
                          class="space-y-3 border-t border-default pt-4 lg:border-t-0 lg:border-l lg:pl-6 lg:pt-0"
                        >
                          <p class="text-xs font-semibold uppercase tracking-[0.2em] text-toned">
                            Powered by
                          </p>

                          <div class="space-y-2">
                            <div class="flex flex-wrap items-center gap-2">
                              <NuxtLink
                                href="https://github.com/yt-dlp/yt-dlp"
                                target="_blank"
                                class="inline-flex items-center gap-2 font-semibold text-highlighted"
                              >
                                <UIcon name="i-lucide-github" class="size-4" />
                                <span>yt-dlp</span>
                              </NuxtLink>

                              <span class="text-xs">{{
                                config?.app?.ytdlp_version || 'unknown'
                              }}</span>
                            </div>

                            <p
                              v-if="config.app?.yt_new_version"
                              class="flex flex-wrap items-center gap-2 text-xs"
                            >
                              <UTooltip text="Restart container to update yt-dlp">
                                <span class="has-tooltip">
                                  <UIcon name="i-lucide-info" class="size-4 text-warning" />
                                </span>
                              </UTooltip>
                              <span>Update available:</span>
                              <NuxtLink
                                :href="`https://github.com/yt-dlp/yt-dlp/releases/tag/${config.app.yt_new_version}`"
                                target="_blank"
                                class="font-semibold text-highlighted"
                              >
                                {{ config.app.yt_new_version }}
                              </NuxtLink>
                            </p>
                          </div>
                        </div>
                      </div>
                    </footer>
                  </div>

                  <ClientOnly>
                    <Dialog />
                  </ClientOnly>
                </div>
              </template>
            </UDashboardPanel>

            <UDashboardSearch
              v-model:open="showRouteSearch"
              :groups="routeSearchGroups"
              shortcut="meta_k"
              placeholder="Search routes and actions"
              :ui="{ modal: 'sm:max-w-3xl h-full sm:h-[28rem]' }"
            />
          </UDashboardGroup>
        </div>
      </div>
    </Transition>

    <SettingsPanel
      :isOpen="show_settings"
      :isLoading="loadingImage"
      @close="closeSettings()"
      @reload_bg="() => loadImage(true)"
      direction="right"
    />
  </UApp>
</template>

<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui';
import { ref, onMounted, readonly } from 'vue';
import { useStorage } from '@vueuse/core';
import moment from 'moment';
import type { toastPosition } from '~/composables/useNotification';
import type { YTDLPOption } from '~/types/ytdlp';
import { useDialog } from '~/composables/useDialog';
import Dialog from '~/components/Dialog.vue';
import Simple from '~/components/Simple.vue';
import Shutdown from '~/components/shutdown.vue';
import type { version_check } from '~/types';
import {
  getActiveNavItem,
  getNavItems,
  getNavSections,
  isNavItemActive,
  type NavItem,
} from '~/utils/topLevelNavigation';

type SidebarSection = {
  id: string;
  label?: string;
  items: Array<Array<NavigationMenuItem>>;
};

const socket = useSocketStore();
const config = useConfigStore();
const route = useRoute();
const loadedImage = ref();
const loadingImage = ref(false);
const bg_enable = useStorage('random_bg', true);
const bg_opacity = useStorage('random_bg_opacity', 0.95);
const app_shutdown = ref<boolean>(false);
const simpleMode = useStorage<boolean>('simple_mode', config.app.simple_mode || false);
const show_settings = ref(false);
const checkingUpdates = ref(false);
const updateCheckMessage = ref('Up to date - Click to check');
const showRouteSearch = ref(false);
const { alertDialog, confirmDialog } = useDialog();

const dashboardSidebarUi = {
  root: 'border-r border-default bg-default/95 backdrop-blur-sm',
  header: 'border-b border-default px-2.5 py-3',
  body: 'gap-3 px-2.5 py-3',
  footer: 'border-t border-default px-2.5 py-3',
};

const dashboardNavbarUi = {
  root: 'border-b border-default bg-transparent px-4 py-3 sm:px-5 lg:px-6',
  title: 'text-sm font-semibold text-highlighted',
  right: 'flex items-center shrink-0 gap-1.5',
};

const dashboardPanelUi = {
  root: 'min-w-0 min-h-screen max-w-full flex flex-1 flex-col bg-transparent',
  body: 'flex min-h-0 min-w-0 max-w-full flex-1 flex-col overflow-y-visible p-0',
};

const navigationUi = (collapsed: boolean) => ({
  root: 'w-full',
  list: 'gap-1.5',
  link: collapsed
    ? 'justify-center rounded-lg px-2 py-2'
    : 'rounded-lg px-2.5 py-2 text-sm font-medium text-default transition-colors',
  linkLeadingIcon: collapsed ? 'size-5' : 'size-4',
  linkLabel: collapsed ? 'hidden' : 'truncate',
});

const makeNavigationItem = (item: NavItem): NavigationMenuItem => ({
  label: item.label,
  icon: item.icon,
  to: item.to,
  value: item.id,
  active: isNavItemActive(item, route),
});

const navigationAvailability = computed(() => ({
  fileLogging: Boolean(config.app?.file_logging),
  consoleEnabled: Boolean(config.app?.console_enabled),
}));

const navItems = computed(() => getNavItems(navigationAvailability.value));

const groupSectionEntries = (entries: Array<NavItem>): Array<Array<NavItem>> => {
  const order = [...new Set(entries.map((entry) => entry.group))];
  return order.map((group) => entries.filter((entry) => entry.group === group));
};

const sidebarItems = computed<
  Array<{
    id: string;
    label: string;
    items: Array<Array<NavItem>>;
  }>
>(() => {
  return getNavSections()
    .map((section) => {
      const sectionEntries = navItems.value.filter(
        (entry) => entry.section === section.id && entry.sidebarVisible !== false,
      );

      return {
        id: section.id,
        label: section.label,
        items: groupSectionEntries(sectionEntries),
      };
    })
    .filter((section) => section.items.some((group) => group.length > 0));
});

const pageTitle = computed(() => {
  const match = getActiveNavItem(route, navigationAvailability.value);
  return match?.navbarTitle || match?.label || 'YTPTube';
});

const buildTooltip = computed(
  () =>
    `Build: ${config.app?.app_build_date}, Branch: ${config.app?.app_branch}, SHA: ${config.app?.app_commit_sha}`,
);

const showConnectionBanner = computed(() => socket.connectionStatus !== 'connected');

const connectionBannerTitle = computed(() => {
  switch (socket.connectionStatus) {
    case 'connecting':
      return 'Connecting to websocket server...';
    case 'disconnected':
    default:
      return 'Websocket connection lost.';
  }
});

const connectionBannerIcon = computed(() =>
  socket.connectionStatus === 'connecting' ? 'i-lucide-loader-circle' : 'i-lucide-info',
);

const sidebarSections = computed<Array<SidebarSection>>(() =>
  sidebarItems.value.map((section) => ({
    ...section,
    items: section.items.map((group) => group.map((entry) => makeNavigationItem(entry))),
  })),
);

const routeSearchGroups = computed(() => [
  ...sidebarItems.value
    .map((section) => ({
      id: section.id,
      label: section.label,
      items: section.items
        .flat()
        .filter((entry) => entry.searchable !== false)
        .map((entry) => ({
          label: entry.label,
          description: entry.description,
          icon: entry.icon,
          suffix: entry.to,
          onSelect: () => handleRouteSelect(entry),
        })),
    }))
    .filter((section) => section.items.length > 0),
  {
    id: 'downloads',
    label: 'Downloads',
    items: [
      config.paused
        ? {
            label: 'Resume Downloads',
            description: 'Resume globally paused downloads.',
            icon: 'i-lucide-play',
            onSelect: () => void resumeDownloads(),
          }
        : {
            label: 'Pause Downloads',
            description: 'Globally pause all non-active downloads.',
            icon: 'i-lucide-pause',
            onSelect: () => void pauseDownloads(),
          },
    ],
  },
  {
    id: 'preferences',
    label: 'Preferences',
    items: [
      {
        label: 'WebUI Settings',
        description: 'Adjust interface behavior and download defaults.',
        icon: 'i-lucide-settings-2',
        onSelect: () => void openSettings(),
      },
    ],
  },
]);

const closeRouteSearch = async (): Promise<void> => {
  if (!showRouteSearch.value) {
    return;
  }

  showRouteSearch.value = false;
  await nextTick();
};

const pauseDownloads = async (): Promise<void> => {
  await closeRouteSearch();
  await request('/api/system/pause', { method: 'POST' });
};

const resumeDownloads = async (): Promise<void> => {
  await closeRouteSearch();
  await request('/api/system/resume', { method: 'POST' });
};

const openSettings = async (): Promise<void> => {
  await closeRouteSearch();
  show_settings.value = true;
};

const syncShellModeClass = () => {
  const html = document.documentElement;
  html.classList.toggle('simple-mode', simpleMode.value);
};

const handleRouteSelect = async (item: NavItem) => {
  await closeRouteSearch();

  if (item.to) {
    await navigateTo(item.to);
  }
};

const checkForUpdates = async () => {
  if (checkingUpdates.value) {
    return;
  }

  const msg = 'Up to date - Click to check';

  try {
    checkingUpdates.value = true;
    updateCheckMessage.value = 'Checking...';

    const response = await fetch('/api/system/check-updates', { method: 'POST' });

    if (!response.ok) {
      await response.json();
      updateCheckMessage.value = 'Check failed';
      setTimeout(() => (updateCheckMessage.value = msg), 3000);
      return;
    }

    const data = await parse_api_response<version_check>(await response.json());

    if ('update_available' === data.app.status) {
      config.app.new_version = data.app.new_version;
    }
    if (data.ytdlp && 'update_available' === data.ytdlp.status) {
      config.app.yt_new_version = data.ytdlp.new_version;
    }

    if ('update_available' === data.app.status) {
      updateCheckMessage.value = 'Update found!';
    } else if ('up_to_date' === data.app.status && 'up_to_date' === data.ytdlp?.status) {
      updateCheckMessage.value = 'Up to date ✓';
      setTimeout(() => (updateCheckMessage.value = msg), 3000);
    } else if ('up_to_date' === data.app.status && 'update_available' === data.ytdlp?.status) {
      updateCheckMessage.value = 'Up to date ✓';
      setTimeout(() => (updateCheckMessage.value = msg), 3000);
    } else {
      updateCheckMessage.value = 'Check failed';
      setTimeout(() => (updateCheckMessage.value = msg), 3000);
    }
  } catch (e) {
    console.error('Update check failed:', e);
    updateCheckMessage.value = 'Check failed';
    setTimeout(() => (updateCheckMessage.value = msg), 3000);
  } finally {
    checkingUpdates.value = false;
  }
};

onMounted(async () => {
  syncShellModeClass();

  try {
    await config.loadConfig();
  } catch {}

  try {
    const opts = await request('/api/yt-dlp/options');
    if (opts.ok) {
      config.ytdlp_options = (await opts.json()) as Array<YTDLPOption>;
    }
  } catch {}

  try {
    socket.connect();
  } catch {}

  try {
    await handleImage(bg_enable.value);
  } catch {}
});

watch(bg_enable, async (v) => await handleImage(v));
watch(simpleMode, () => syncShellModeClass());
watch(bg_opacity, () => {
  if (false === bg_enable.value) {
    return;
  }

  syncOpacity();
});

watch(loadedImage, () => {
  if (false === bg_enable.value) {
    return;
  }

  const html = document.documentElement;

  const style = {
    'background-color': 'unset',
    display: 'block',
    'min-height': '100%',
    'min-width': '100%',
    'background-image': `url(${loadedImage.value})`,
  } as any;

  html.setAttribute(
    'style',
    Object.keys(style)
      .map((k) => `${k}: ${style[k]}`)
      .join('; ')
      .trim(),
  );
  html.classList.add('bg-fanart');
  syncOpacity();
});

const handleImage = async (enabled: boolean) => {
  if (false === enabled) {
    const html = document.documentElement;
    const body = document.querySelector('body');

    html.classList.remove('bg-fanart');

    if (html.getAttribute('style')) {
      html.removeAttribute('style');
    }

    if (body?.getAttribute('style')) {
      body.removeAttribute('style');
    }

    loadedImage.value = '';
    return;
  }

  if (loadedImage.value) {
    return;
  }

  await loadImage();
};

const loadImage = async (force = false) => {
  if (loadingImage.value) {
    return;
  }

  try {
    loadingImage.value = true;

    let url = '/api/random/background';
    if (force) {
      url += '?force=true';
    }

    const imgRequest = await request(url);
    if (200 !== imgRequest.status) {
      return;
    }

    loadedImage.value = URL.createObjectURL(await imgRequest.blob());
  } catch (e) {
    console.error(e);
  } finally {
    loadingImage.value = false;
  }
};

const useVersionUpdate = () => {
  const newVersionIsAvailable = ref(false);
  const nuxtApp = useNuxtApp();
  nuxtApp.hooks.addHooks({
    'app:manifest:update': () => {
      newVersionIsAvailable.value = true;
    },
  });

  return {
    newVersionIsAvailable: readonly(newVersionIsAvailable),
  };
};

const { newVersionIsAvailable } = useVersionUpdate();

const closeSettings = () => (show_settings.value = false);

const shutdownApp = async () => {
  if (false === config.app.is_native) {
    await alertDialog({
      title: 'Shutdown Unavailable',
      message: 'The shutdown feature is only available when running as native application.',
    });
    return;
  }

  const { status } = await confirmDialog({
    title: 'Shutdown Application',
    message: 'Are you sure you want to shutdown the application?',
  });

  if (false === status) {
    return;
  }

  try {
    const resp = await fetch('/api/system/shutdown', { method: 'POST' });
    if (!resp.ok) {
      const body = await resp.json();
      await alertDialog({
        title: 'Shutdown Failed',
        message: `Failed to shutdown the application: ${body.error || resp.statusText || resp.status}`,
      });
      return;
    }
    app_shutdown.value = true;
    await nextTick();
  } catch (e: any) {
    await alertDialog({
      title: 'Shutdown Failed',
      message: `Failed to shutdown the application: ${e.message || e}`,
    });
  }
};

const reloadPage = () => window.location.reload();

const connectionStatusColor = computed(() => {
  switch (socket.connectionStatus) {
    case 'connected':
      return 'text-success';
    case 'connecting':
      return 'text-warning';
    case 'disconnected':
    default:
      return 'text-error';
  }
});

const connectionStatusDotClass = computed(() => {
  switch (socket.connectionStatus) {
    case 'connected':
      return 'bg-success';
    case 'connecting':
      return 'bg-warning';
    case 'disconnected':
    default:
      return 'bg-error';
  }
});

const connectionStatusLabel = computed(() => {
  switch (socket.connectionStatus) {
    case 'connected':
      return 'Connected';
    case 'connecting':
      return 'Connecting...';
    case 'disconnected':
    default:
      return 'Disconnected';
  }
});

const toastPosition = useStorage<toastPosition>('toast_position', 'top-right');

const toasterConfig = computed(() => ({
  position: toastPosition.value,
  max: 5,
  expand: true,
  progress: true,
}));
</script>

<style>
.shell-stage {
  min-height: 100vh;
  min-height: 100dvh;
}

.shell-mode-enter-active,
.shell-mode-leave-active {
  transition:
    opacity 0.28s ease,
    transform 0.34s cubic-bezier(0.22, 1, 0.36, 1);
  will-change: opacity, transform;
}

.shell-mode-enter-from,
.shell-mode-leave-to {
  opacity: 0;
  transform: translateY(18px) scale(0.985);
}

.shell-root {
  min-height: 100vh;
  min-height: 100dvh;
}

.shell-dashboard {
  min-height: 100vh;
  min-height: 100dvh;
}

.shell-footer {
  padding-top: 1.5rem;
  padding-bottom: 1.5rem;
}
</style>
