<template>
  <main class="space-y-6">
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

      <div class="flex flex-wrap gap-2 xl:justify-end">
        <UButton
          v-for="entry in docsEntries"
          :key="entry.id"
          :to="entry.route"
          :color="entry.file === docEntry.file ? 'primary' : 'neutral'"
          :variant="entry.file === docEntry.file ? 'solid' : 'outline'"
          size="sm"
          :icon="entry.icon"
        >
          {{ entry.navLabel }}
        </UButton>
      </div>
    </div>

    <UPageCard variant="outline" :ui="pageCardUi">
      <template #body>
        <div class="px-4 py-5 sm:px-6 sm:py-6 lg:px-7">
          <Markdown :file="`/api/docs/${docEntry.file}`" />
        </div>
      </template>
    </UPageCard>
  </main>
</template>

<script setup lang="ts">
import Markdown from '~/components/Markdown.vue';
import { DOCS_ENTRIES, getDocsEntryBySlug } from '~/composables/useDocs';
import { formatPageTitle } from '~/utils';
import { requirePageShell } from '~/utils/topLevelNavigation';

const route = useRoute();

const docsEntries = DOCS_ENTRIES;

const docEntry = computed(() => {
  const entry = getDocsEntryBySlug(route.params.slug as string | string[] | undefined);

  if (!entry) {
    throw createError({
      statusCode: 404,
      statusMessage: 'Documentation not found',
    });
  }

  return entry;
});

const pageShell = computed(() => requirePageShell(docEntry.value.id));

useHead(() => ({
  title: formatPageTitle(docEntry.value.title),
}));

const pageCardUi = {
  root: 'w-full bg-default',
  container: 'w-full p-0',
  wrapper: 'w-full items-stretch',
  body: 'w-full p-0',
};
</script>
