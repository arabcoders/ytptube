<template>
  <main class="space-y-6">
    <UPageHeader :title="docEntry.title" :description="docEntry.description" :ui="pageHeaderUi">
      <template #links>
        <div class="flex flex-wrap items-center gap-2">
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
      </template>
    </UPageHeader>

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

useHead(() => ({
  title: docEntry.value.title,
}));

const pageHeaderUi = {
  root: 'border-b border-default py-4',
  headline: 'hidden',
  title: 'text-2xl font-semibold text-highlighted',
  description: 'text-sm text-toned',
  wrapper: 'flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between',
  links: 'flex flex-wrap items-center gap-2',
};

const pageCardUi = {
  root: 'w-full bg-default',
  container: 'w-full p-0',
  wrapper: 'w-full items-stretch',
  body: 'w-full p-0',
};
</script>
