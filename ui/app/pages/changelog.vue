<template>
  <main class="w-full min-w-0 max-w-full space-y-6">
    <PageHeader v-bind="pageShell" />

    <section :aria-label="pageShell.pageLabel" :aria-busy="isLoading" class="space-y-4">
      <div class="flex flex-wrap items-end justify-between gap-4">
        <div class="w-full space-y-1.5 sm:max-w-md">
          <label for="changelog-filter" class="block text-xs font-medium text-toned">
            {{ t('changelog.search') }}
          </label>
          <UInput
            id="changelog-filter"
            v-model.lazy="query"
            type="search"
            :placeholder="t('changelog.filterPlaceholder')"
            icon="i-lucide-search"
            size="sm"
            class="w-full"
          />
        </div>
        <USwitch
          v-model="latestOnly"
          size="sm"
          :label="t('changelog.latestOnly')"
          :description="t('changelog.latestCount', { count: DEFAULT_LIMIT })"
          :ui="{ root: 'items-center gap-2', wrapper: 'ms-0 text-xs text-toned' }"
        />
      </div>

      <UAlert
        v-if="isLoading"
        color="info"
        variant="soft"
        icon="i-lucide-loader-circle"
        :title="t('common.loading')"
        :description="t('common.loadingData')"
        :ui="{ icon: 'animate-spin' }"
      />

      <template v-else>
        <UAlert
          v-if="loadError"
          color="error"
          variant="soft"
          icon="i-lucide-triangle-alert"
          :title="t('common.error')"
          :description="loadError"
        />
        <div v-if="filteredLogs.length > 0" class="divide-y divide-default border-y border-default">
          <section
            v-for="(log, index) in filteredLogs"
            :key="log.tag"
            :aria-labelledby="`changelog-release-${index}`"
            class="py-5"
          >
            <h2>
              <button
                :id="`changelog-release-${index}`"
                type="button"
                :aria-expanded="isReleaseOpen(log.tag)"
                :aria-controls="`changelog-commits-${index}`"
                class="group flex w-full items-start gap-3 rounded-sm text-start focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                @click="toggleRelease(log.tag)"
              >
                <UIcon
                  :name="isRtl ? 'i-lucide-chevron-left' : 'i-lucide-chevron-right'"
                  :class="[
                    'mt-0.5 size-5 shrink-0 text-muted transition-transform',
                    isReleaseOpen(log.tag) ? (isRtl ? '-rotate-90' : 'rotate-90') : '',
                  ]"
                  aria-hidden="true"
                />
                <span
                  class="flex min-w-0 flex-1 flex-wrap items-center justify-between gap-x-6 gap-y-2"
                >
                  <span class="flex min-w-0 flex-wrap items-center gap-2">
                    <span
                      class="wrap-anywhere font-mono text-base font-semibold text-highlighted transition-colors group-hover:text-primary"
                    >
                      {{ log.tag }}
                    </span>
                    <UBadge
                      v-if="isInstalled(log)"
                      color="success"
                      variant="soft"
                      size="sm"
                      icon="i-lucide-check"
                    >
                      {{ t('changelog.installed') }}
                    </UBadge>
                  </span>
                  <span class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-toned">
                    <time v-if="log.date" :datetime="log.date" :title="log.date">
                      {{ formatDateOnly(log.date, locale) }}
                    </time>
                    <span class="tabular-nums">
                      {{ t('changelog.commits', { count: log.commits?.length || 0 }) }}
                    </span>
                  </span>
                </span>
              </button>
            </h2>

            <div
              :id="`changelog-commits-${index}`"
              :hidden="!isReleaseOpen(log.tag)"
              class="mt-4 sm:ms-8"
            >
              <ul v-if="isReleaseOpen(log.tag)" class="divide-y divide-default">
                <li v-for="commit in log.commits" :key="commit.sha">
                  <article class="min-w-0 max-w-full space-y-2 py-3" dir="ltr">
                    <NuxtLink
                      :to="`${REPO}/commit/${commit.full_sha}`"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="block wrap-anywhere text-sm font-medium leading-6 text-highlighted transition-colors hover:text-primary focus-visible:outline-none focus-visible:underline"
                    >
                      {{ formatCommitMessage(commit.message).title }}
                    </NuxtLink>

                    <div
                      v-if="formatCommitMessage(commit.message).description.length > 0"
                      class="mt-2 min-w-0 max-w-full"
                    >
                      <button
                        type="button"
                        class="inline-flex max-w-full items-center gap-1 text-xs text-toned hover:text-primary"
                        :aria-expanded="isCommitDescriptionOpen(commit.sha)"
                        :aria-label="t('common.showMore')"
                        @click="toggleCommitDescription(commit.sha)"
                      >
                        <UIcon
                          name="i-lucide-chevron-right"
                          :class="[
                            'size-3.5 transition-transform',
                            isCommitDescriptionOpen(commit.sha) ? 'rotate-90' : '',
                          ]"
                        />
                        <span>{{ t('common.showMore') }}</span>
                      </button>

                      <Markdown
                        v-if="isCommitDescriptionOpen(commit.sha)"
                        :markdown="formatCommitMessage(commit.message).description.join('\n\n')"
                        class="changelog-commit-markdown mt-1 text-sm text-toned"
                      />
                    </div>

                    <div
                      class="flex min-w-0 max-w-full flex-wrap items-center gap-x-4 gap-y-1 text-xs text-toned"
                    >
                      <span class="inline-flex min-w-0 max-w-full items-center gap-1.5">
                        <UIcon name="i-lucide-user" class="size-3.5 text-muted" />
                        <span class="wrap-anywhere">{{ commit.author }}</span>
                      </span>

                      <UTooltip :text="t('changelog.date', { date: commit.date })">
                        <time :datetime="commit.date" class="cursor-help">
                          {{ relativeTime(commit.date) }}
                        </time>
                      </UTooltip>

                      <UTooltip :text="`SHA: ${commit.full_sha}`">
                        <NuxtLink
                          :to="`${REPO}/commit/${commit.full_sha}`"
                          target="_blank"
                          rel="noopener noreferrer"
                          :aria-label="`SHA: ${commit.full_sha}`"
                          class="inline-flex items-center gap-1.5 font-mono transition-colors hover:text-primary focus-visible:outline-none focus-visible:underline"
                        >
                          <UIcon
                            name="i-lucide-git-commit-horizontal"
                            class="size-3.5 text-muted"
                          />
                          <span>{{ commit.sha }}</span>
                        </NuxtLink>
                      </UTooltip>

                      <span
                        v-if="matchesSha(commit.full_sha, app_sha)"
                        class="inline-flex items-center gap-1.5 font-medium text-success"
                      >
                        <UIcon name="i-lucide-check" class="size-3.5 text-success" />
                        <span>{{ t('changelog.installed') }}</span>
                      </span>
                    </div>
                  </article>
                </li>
              </ul>
              <UEmpty
                v-if="isReleaseOpen(log.tag) && log.commits.length === 0"
                size="sm"
                variant="naked"
                icon="i-lucide-git-commit-horizontal"
                :title="t('changelog.noCommits')"
              />
            </div>
          </section>
        </div>

        <UEmpty
          v-else-if="!loadError"
          variant="naked"
          size="sm"
          :icon="query ? 'i-lucide-search' : 'i-lucide-scroll-text'"
          :title="query ? t('common.noResults') : t('changelog.noItems')"
          :description="query ? t('changelog.noResultsFor', { query }) : t('changelog.empty')"
        />
      </template>
    </section>
  </main>
</template>

<script setup lang="ts">
import { useStorage } from '@vueuse/core';
import Markdown from '~/components/Markdown.vue';
import type { changelogs, changeset } from '~/types/changelogs';
import { request, ucFirst, uri } from '~/utils';
import { formatRelativeTime, type RelativeTimeInput } from '~/utils/relativeTime';
import { formatDateOnly } from '~/utils/date';
import {
  filterChangelog,
  getOpenReleases,
  isInstalledRelease,
  matchesSha,
} from '~/utils/changelog';
import { usePageShell } from '~/composables/usePageShell';
const { locale, t } = useI18n();
const { isRtl } = useAppLocale();

const toast = useNotification();
const config = useYtpConfig();
const pageShell = usePageShell('changelog');
const relativeTime = (value: RelativeTimeInput): string => formatRelativeTime(value, locale.value);

const PROJECT = 'ytptube';
const REPO = `https://github.com/arabcoders/${PROJECT}`;
const REPO_URL = `https://arabcoders.github.io/${PROJECT}/CHANGELOG.json?version={version}`;
const DEFAULT_LIMIT = 10;

const logs = ref<changelogs>([]);
const app_version = ref('');
const app_branch = ref('');
const app_sha = ref('');
const isLoading = ref(true);
const loadError = ref('');
const query = ref('');
const latestOnly = useStorage<boolean>('changelog_latest_only', true);
const openReleases = ref<string[]>([]);
const openCommitDescriptions = ref<string[]>([]);

const visibleLogs = computed<changelogs>(() =>
  latestOnly.value ? logs.value.slice(0, DEFAULT_LIMIT) : logs.value,
);

const filteredLogs = computed(() => filterChangelog(visibleLogs.value, query.value));

const isReleaseOpen = (tag: string): boolean => openReleases.value.includes(tag);

const toggleRelease = (tag: string): void => {
  if (isReleaseOpen(tag)) {
    openReleases.value = openReleases.value.filter((entry) => entry !== tag);
    return;
  }

  openReleases.value = [...openReleases.value, tag];
};

const isCommitDescriptionOpen = (sha: string): boolean =>
  openCommitDescriptions.value.includes(sha);

const toggleCommitDescription = (sha: string): void => {
  if (isCommitDescriptionOpen(sha)) {
    openCommitDescriptions.value = openCommitDescriptions.value.filter((entry) => entry !== sha);
    return;
  }

  openCommitDescriptions.value = [...openCommitDescriptions.value, sha];
};

const formatCommitMessage = (message: string): { title: string; description: string[] } => {
  const lines = message
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const title = lines.shift() || '';

  return {
    title: `${ucFirst(title).replace(/\.$/, '')}.`,
    description: lines,
  };
};

const loadContent = async (): Promise<void> => {
  if (app_version.value === '' || logs.value.length > 0) {
    return;
  }

  loadError.value = '';
  try {
    try {
      const changes = await fetch(
        REPO_URL.replace('{branch}', app_branch.value).replace('{version}', app_version.value),
      );
      if (!changes.ok) {
        throw new Error(t('common.failedFetch'));
      }
      logs.value = await changes.json();
    } catch (error) {
      console.error(error);
      const response = await request(uri('/CHANGELOG.json'), { method: 'GET' });
      if (!response.ok) {
        throw new Error(t('common.failedFetch'), { cause: error });
      }
      logs.value = await response.json();
    }
    openReleases.value = getOpenReleases(logs.value, app_sha.value);
  } catch (error: unknown) {
    console.error(error);
    loadError.value = t('changelog.failedFetch', {
      error: error instanceof Error ? error.message : String(error),
    });
    toast.error(loadError.value);
  } finally {
    isLoading.value = false;
  }
};

const isInstalled = (log: changeset): boolean => isInstalledRelease(log, app_sha.value);

onMounted(async () => {
  await awaiter(config.isLoaded);
  app_branch.value = config.app.app_branch;
  app_version.value = config.app.app_version;
  app_sha.value = config.app.app_commit_sha;
  await loadContent();
});
</script>
