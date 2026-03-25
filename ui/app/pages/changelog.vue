<template>
  <main class="w-full min-w-0 max-w-full space-y-4">
    <div class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
      <div class="min-w-0 space-y-1">
        <div class="flex items-center gap-2 text-lg font-semibold text-highlighted">
          <UIcon name="i-lucide-git-commit-horizontal" class="size-5 text-toned" />
          <span>CHANGELOG</span>
        </div>

        <p class="text-sm text-toned">
          Latest project changes, loaded remotely when available and falling back to the bundled
          changelog file.
        </p>
      </div>

      <div class="flex flex-wrap items-center justify-end gap-2">
        <div v-if="toggleFilter && logs.length > 0" class="relative w-full sm:w-80">
          <span
            class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-toned"
          >
            <UIcon name="i-lucide-filter" class="size-4" />
          </span>

          <input
            id="filter"
            v-model.lazy="query"
            type="search"
            placeholder="Filter changelog entries"
            class="w-full rounded-md border border-default bg-elevated py-2 pr-3 pl-9 text-sm text-default outline-none transition focus:border-primary"
          />
        </div>

        <UButton
          v-if="logs.length > 0"
          color="neutral"
          :variant="toggleFilter ? 'soft' : 'outline'"
          size="sm"
          icon="i-lucide-filter"
          @click="toggleFilter = !toggleFilter"
        >
          <span v-if="!isMobile">Filter</span>
        </UButton>

        <USwitch
          v-model="latestOnly"
          color="primary"
          size="sm"
          :label="latestOnly ? 'Latest Only' : 'All Loaded'"
          :ui="{ root: 'items-center gap-2', wrapper: 'ms-0 text-xs text-toned' }"
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

                  <p v-if="log.date" class="text-xs text-toned">
                    <UTooltip :text="`Release Date: ${log.date}`">
                      <span>{{ moment(log.date).fromNow() }}</span>
                    </UTooltip>
                  </p>
                </div>

                <UBadge color="neutral" variant="soft" size="sm">
                  {{ log.commits?.length || 0 }} commits
                </UBadge>
              </div>

              <div class="space-y-3 border-t border-default pt-4">
                <article
                  v-for="commit in log.commits"
                  :key="commit.sha"
                  class="flex flex-col gap-2 rounded-md border border-default bg-muted/20 px-3 py-3"
                >
                  <div class="flex flex-wrap items-start justify-between gap-3">
                    <p class="min-w-0 flex-1 text-sm text-default">
                      <span class="font-semibold text-highlighted">
                        {{ ucFirst(commit.message).replace(/\.$/, '') }}.
                      </span>
                    </p>

                    <div class="flex shrink-0 items-center gap-2">
                      <NuxtLink
                        :to="`${REPO}/commit/${commit.full_sha}`"
                        target="_blank"
                        class="text-xs font-medium text-primary hover:underline"
                      >
                        {{ commit.sha }}
                      </NuxtLink>

                      <UIcon
                        v-if="commit.full_sha === app_sha"
                        name="i-lucide-check"
                        class="size-4 text-success"
                      />
                    </div>
                  </div>

                  <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-toned">
                    <span>{{ commit.author }}</span>
                    <UTooltip :text="`SHA: ${commit.full_sha} - Date: ${commit.date}`">
                      <span>{{ moment(commit.date).fromNow() }}</span>
                    </UTooltip>
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

        <UButton v-if="query" color="neutral" variant="outline" size="sm" @click="query = ''">
          Clear filter
        </UButton>

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

const toast = useNotification();
const config = useConfigStore();
const isMobile = useMediaQuery({ maxWidth: 1024 });

useHead({ title: 'CHANGELOG' });

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
