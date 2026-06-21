<template>
  <main class="w-full min-w-0 max-w-full space-y-6">
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
          v-if="logs.length > 0"
          color="neutral"
          :variant="toggleFilter ? 'soft' : 'outline'"
          size="sm"
          icon="i-lucide-filter"
          @click="toggleFilter = !toggleFilter"
        >
          <span>Filter</span>
        </UButton>

        <USwitch
          v-model="latestOnly"
          color="primary"
          size="sm"
          :label="latestOnly ? 'Latest Only' : 'All Loaded'"
          :ui="{ root: 'items-center gap-2', wrapper: 'ms-0 text-xs text-toned' }"
        />

        <UInput
          v-if="toggleFilter && logs.length > 0"
          id="filter"
          v-model.lazy="query"
          type="search"
          placeholder="Filter changelog entries"
          icon="i-lucide-filter"
          size="sm"
          class="order-last w-full sm:order-first sm:w-80"
        />
      </div>
    </div>

    <UAlert
      v-if="isLoading"
      color="info"
      variant="soft"
      icon="i-lucide-loader-circle"
      title="Loading"
      description="Loading data. Please wait..."
    />

    <template v-else>
      <div v-if="filteredLogs.length > 0" class="space-y-5">
        <section v-for="log in filteredLogs" :key="log.tag" class="space-y-3">
          <section class="space-y-3">
            <button
              type="button"
              class="flex w-full flex-wrap items-center justify-between gap-3 text-left"
              @click="toggleRelease(log.tag)"
            >
              <div class="flex min-w-0 items-center gap-3">
                <span class="ytp-section-icon">
                  <UIcon
                    :name="isInstalled(log) ? 'i-lucide-badge-check' : 'i-lucide-git-branch'"
                    class="size-5"
                  />
                </span>

                <div class="min-w-0 space-y-1">
                  <h2 class="truncate text-base font-semibold text-highlighted">
                    {{ log.tag }}
                  </h2>

                  <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-toned">
                    <UTooltip v-if="log.date" :text="`Release Date: ${log.date}`">
                      <span class="inline-flex cursor-help items-center gap-1.5">
                        <UIcon name="i-lucide-calendar-days" class="size-3.5 text-muted" />
                        <span>{{ moment(log.date).fromNow() }}</span>
                      </span>
                    </UTooltip>
                  </div>
                </div>
              </div>

              <div class="flex shrink-0 items-center gap-2">
                <UBadge
                  v-if="isInstalled(log)"
                  color="success"
                  variant="soft"
                  size="sm"
                  icon="i-lucide-check"
                >
                  Installed
                </UBadge>

                <UBadge color="neutral" variant="outline" size="sm" icon="i-lucide-list">
                  {{ log.commits?.length || 0 }} commits
                </UBadge>

                <UIcon
                  name="i-lucide-chevron-right"
                  :class="[
                    'size-4 text-toned transition-transform',
                    isReleaseOpen(log.tag) ? 'rotate-90' : '',
                  ]"
                />
              </div>
            </button>

            <div v-if="isReleaseOpen(log.tag)" class="space-y-2">
              <article
                v-for="commit in log.commits"
                :key="commit.sha"
                class="rounded-md border border-default bg-elevated/20 px-3 py-3 transition-colors hover:bg-elevated/35"
              >
                <NuxtLink
                  :to="`${REPO}/commit/${commit.full_sha}`"
                  target="_blank"
                  class="block min-w-0 text-sm font-medium leading-5 text-highlighted transition hover:text-primary"
                >
                  {{ formatCommitMessage(commit.message) }}
                </NuxtLink>

                <div class="mt-2 flex flex-wrap items-center gap-2 text-xs text-toned">
                  <span
                    class="inline-flex items-center gap-1 rounded-sm border border-default px-2 py-1"
                  >
                    <UIcon name="i-lucide-user" class="size-3.5 text-muted" />
                    <span>{{ commit.author }}</span>
                  </span>

                  <UTooltip :text="`Date: ${commit.date}`">
                    <time
                      class="inline-flex cursor-help items-center gap-1 rounded-sm border border-default px-2 py-1"
                    >
                      <UIcon name="i-lucide-clock-3" class="size-3.5 text-muted" />
                      <span>{{ moment(commit.date).fromNow() }}</span>
                    </time>
                  </UTooltip>

                  <UTooltip :text="`SHA: ${commit.full_sha}`">
                    <NuxtLink
                      :to="`${REPO}/commit/${commit.full_sha}`"
                      target="_blank"
                      class="inline-flex items-center gap-1 rounded-sm border border-default px-2 py-1 font-mono transition hover:border-primary hover:text-primary"
                    >
                      <UIcon name="i-lucide-git-commit-horizontal" class="size-3.5 text-muted" />
                      <span>{{ commit.sha }}</span>
                    </NuxtLink>
                  </UTooltip>

                  <span
                    v-if="commit.full_sha === app_sha"
                    class="inline-flex items-center gap-1 rounded-sm border border-default px-2 py-1 font-medium"
                  >
                    <UIcon name="i-lucide-check" class="size-3.5 text-success" />
                    <span>Installed</span>
                  </span>
                </div>
              </article>
            </div>
          </section>
        </section>
      </div>

      <div v-else class="space-y-3">
        <UAlert
          v-if="query"
          color="warning"
          variant="soft"
          icon="i-lucide-search"
          title="No Results"
          :description="`No changelog entries found for the query: ${query}.`"
        />

        <UAlert
          v-else
          color="warning"
          variant="soft"
          icon="i-lucide-circle-alert"
          title="No changelog entries"
          description="No changelog data is available right now."
        />
      </div>
    </template>
  </main>
</template>

<script setup lang="ts">
import moment from 'moment';
import { useStorage } from '@vueuse/core';
import type { changelogs, changeset } from '~/types/changelogs';
import { request, ucFirst, uri } from '~/utils';
import { requirePageShell } from '~/utils/topLevelNavigation';

const toast = useNotification();
const config = useYtpConfig();
const pageShell = requirePageShell('changelog');

const PROJECT = 'ytptube';
const REPO = `https://github.com/arabcoders/${PROJECT}`;
const REPO_URL = `https://arabcoders.github.io/${PROJECT}/CHANGELOG.json?version={version}`;
const DEFAULT_LIMIT = 10;

const logs = ref<changelogs>([]);
const app_version = ref('');
const app_branch = ref('');
const app_sha = ref('');
const isLoading = ref(true);
const query = ref('');
const toggleFilter = ref(false);
const latestOnly = useStorage<boolean>('changelog_latest_only', true);
const openReleases = useStorage<string[]>('changelog_open_releases', []);

watch(toggleFilter, () => {
  if (!toggleFilter.value) {
    query.value = '';
  }
});

const visibleLogs = computed<changelogs>(() =>
  latestOnly.value ? logs.value.slice(0, DEFAULT_LIMIT) : logs.value,
);

const filteredLogs = computed<changelogs>(() => {
  const q = query.value?.toLowerCase();
  if (!q) {
    return visibleLogs.value;
  }

  return visibleLogs.value
    .map((log) => {
      const tagMatches = log.tag.toLowerCase().includes(q);
      const filteredCommits =
        log.commits?.filter(
          (commit) =>
            commit.message.toLowerCase().includes(q) ||
            commit.author.toLowerCase().includes(q) ||
            commit.full_sha.toLowerCase().includes(q),
        ) ?? [];

      if (tagMatches || filteredCommits.length > 0) {
        return { ...log, commits: tagMatches ? log.commits : filteredCommits };
      }

      return null;
    })
    .filter((log): log is changeset => log !== null);
});

watch(filteredLogs, (items) => {
  if (openReleases.value.length > 0 || items.length < 1) {
    return;
  }

  openReleases.value = items.slice(0, 3).map((log) => log.tag);
});

const isReleaseOpen = (tag: string): boolean => openReleases.value.includes(tag);

const toggleRelease = (tag: string): void => {
  if (isReleaseOpen(tag)) {
    openReleases.value = openReleases.value.filter((entry) => entry !== tag);
    return;
  }

  openReleases.value = [...openReleases.value, tag];
};

const formatCommitMessage = (message: string): string => `${ucFirst(message).replace(/\.$/, '')}.`;

const loadContent = async (): Promise<void> => {
  if (app_version.value === '' || logs.value.length > 0) {
    return;
  }

  try {
    try {
      const changes = await fetch(
        REPO_URL.replace('{branch}', app_branch.value).replace('{version}', app_version.value),
      );
      logs.value = await changes.json();
    } catch (error) {
      console.error(error);
      logs.value = await (await request(uri('/CHANGELOG.json'), { method: 'GET' })).json();
    }
  } catch (error: any) {
    console.error(error);
    toast.error(`Failed to fetch changelog. ${error.message}`);
  } finally {
    isLoading.value = false;
  }
};

const isInstalled = (log: changeset): boolean => {
  const installed = String(app_sha.value);

  if (log.full_sha.startsWith(installed)) {
    return true;
  }

  for (const commit of log?.commits ?? []) {
    if (commit.full_sha.startsWith(installed)) {
      return true;
    }
  }

  return false;
};

onMounted(async () => {
  await awaiter(config.isLoaded);
  app_branch.value = config.app.app_branch;
  app_version.value = config.app.app_version;
  app_sha.value = config.app.app_commit_sha;
  await loadContent();
});
</script>
