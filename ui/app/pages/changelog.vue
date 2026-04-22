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
      <div v-if="filteredLogs.length > 0" class="space-y-4">
        <UPageCard v-for="log in filteredLogs" :key="log.tag" variant="outline" :ui="pageCardUi">
          <template #body>
            <div class="space-y-4">
              <div class="flex flex-wrap items-start justify-between gap-3">
                <div class="min-w-0 space-y-2">
                  <div class="flex flex-wrap items-center gap-2">
                    <div
                      class="inline-flex items-center gap-2 text-base font-semibold text-highlighted"
                    >
                      <UIcon name="i-lucide-git-branch" class="size-4 text-toned" />
                      <span>{{ log.tag }}</span>
                    </div>

                    <UBadge v-if="isInstalled(log)" color="success" variant="soft" size="sm">
                      Installed
                    </UBadge>
                  </div>
                </div>

                <div class="flex flex-wrap items-center justify-end gap-2 text-xs text-toned">
                  <span
                    class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1"
                  >
                    <UIcon name="i-lucide-list" class="size-3.5" />
                    <span>{{ log.commits?.length || 0 }} commits</span>
                  </span>

                  <UTooltip v-if="log.date" :text="`Release Date: ${log.date}`">
                    <span
                      class="inline-flex cursor-help items-center gap-1 rounded-md border border-default px-2 py-1"
                    >
                      <UIcon name="i-lucide-calendar-days" class="size-3.5" />
                      <span>{{ moment(log.date).fromNow() }}</span>
                    </span>
                  </UTooltip>
                </div>
              </div>

              <div class="space-y-3 border-t border-default pt-4">
                <article
                  v-for="commit in log.commits"
                  :key="commit.sha"
                  class="flex flex-col gap-2 rounded-md border border-default bg-muted/20 px-3 py-3"
                >
                  <div class="min-w-0">
                    <NuxtLink
                      :to="`${REPO}/commit/${commit.full_sha}`"
                      target="_blank"
                      class="block min-w-0 text-sm text-default hover:underline"
                    >
                      <span class="font-semibold text-highlighted">
                        {{ ucFirst(commit.message).replace(/\.$/, '') }}.
                      </span>
                    </NuxtLink>
                  </div>

                  <div class="flex flex-wrap items-center gap-2 text-xs text-toned">
                    <span
                      class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1"
                    >
                      <UIcon name="i-lucide-user" class="size-3.5" />
                      {{ commit.author }}
                    </span>
                    <UTooltip :text="`Date: ${commit.date}`">
                      <span
                        class="inline-flex cursor-help items-center gap-1 rounded-md border border-default px-2 py-1"
                      >
                        <UIcon name="i-lucide-clock-3" class="size-3.5" />
                        {{ moment(commit.date).fromNow() }}
                      </span>
                    </UTooltip>
                    <UTooltip :text="`SHA: ${commit.full_sha}`">
                      <span
                        class="inline-flex cursor-help items-center gap-1 rounded-md border border-default px-2 py-1 font-medium"
                      >
                        <UIcon name="i-lucide-git-commit-horizontal" class="size-3.5" />
                        {{ commit.sha }}
                      </span>
                    </UTooltip>
                    <span
                      v-if="commit.full_sha === app_sha"
                      class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1 font-medium"
                    >
                      <UIcon name="i-lucide-check" class="size-3.5 text-success" />
                      <span>Installed</span>
                    </span>
                  </div>
                </article>
              </div>
            </div>
          </template>
        </UPageCard>
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

const pageCardUi = {
  root: 'w-full bg-default',
  container: 'w-full p-4 sm:p-5',
  wrapper: 'w-full items-stretch',
  body: 'w-full',
};

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
