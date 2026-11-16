<template>
  <main class="w-full min-w-0 max-w-full space-y-6">
    <NuxtLink
      v-if="docEntry.id !== 'docs-index'"
      to="/docs"
      class="inline-flex items-center gap-2 text-sm text-toned hover:text-primary"
    >
      <UIcon
        :name="isRtl ? 'i-lucide-arrow-right' : 'i-lucide-arrow-left'"
        class="size-4"
        aria-hidden="true"
      />
      {{ t('docs.entries.index.navLabel') }}
    </NuxtLink>

    <PageHeader v-else v-bind="pageShell" />

    <template v-if="docEntry.id === 'docs-index'">
      <section
        v-for="group in groups"
        :key="group.id"
        :aria-labelledby="`docs-${group.id}`"
        class="space-y-3"
      >
        <h2 :id="`docs-${group.id}`" class="text-sm font-semibold text-highlighted">
          {{ t(group.title) }}
        </h2>
        <ul class="ytp-card divide-y divide-default overflow-hidden">
          <li v-for="entry in group.entries" :key="entry.id">
            <NuxtLink
              :to="entry.route"
              class="group flex items-center gap-3 p-4 transition-colors hover:bg-elevated/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary"
            >
              <UIcon :name="entry.icon" class="size-5 shrink-0 text-toned" aria-hidden="true" />
              <div class="min-w-0 flex-1 space-y-1">
                <h3
                  class="wrap-anywhere text-sm font-semibold text-highlighted group-hover:text-primary"
                >
                  {{ t(entry.title) }}
                </h3>
                <p class="wrap-anywhere text-sm text-toned">{{ t(entry.description) }}</p>
              </div>
              <UIcon
                :name="isRtl ? 'i-lucide-chevron-left' : 'i-lucide-chevron-right'"
                class="size-4 shrink-0 text-muted"
                aria-hidden="true"
              />
            </NuxtLink>
          </li>
        </ul>
      </section>
    </template>
    <Markdown v-else :file="`/api/docs/${docEntry.file}`" />
  </main>
</template>

<script setup lang="ts">
import Markdown from '~/components/Markdown.vue';
import { getDocsEntryBySlug, getDocsGroups } from '~/composables/useDocs';
import { formatPageTitle } from '~/utils';
import { usePageShell } from '~/composables/usePageShell';

const route = useRoute();
const { t } = useI18n();
const { isRtl } = useAppLocale();
const groups = getDocsGroups();

const docEntry = computed(() => {
  const entry = getDocsEntryBySlug(route.params.slug as string | string[] | undefined);

  if (!entry) {
    throw createError({
      statusCode: 404,
      statusMessage: t('docs.notFound'),
    });
  }

  return entry;
});

const pageShell = computed(() => usePageShell(docEntry.value.id));

useHead(() => ({
  title: formatPageTitle(pageShell.value.pageLabel),
}));
</script>
