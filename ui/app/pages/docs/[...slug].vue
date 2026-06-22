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
    </div>

    <div class="ytp-card p-0 overflow-hidden">
      <div class="min-w-0 max-w-full px-4 py-5 sm:px-6 sm:py-6 lg:px-7">
        <Markdown :file="`/api/docs/${docEntry.file}`" />
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
import Markdown from '~/components/Markdown.vue';
import { getDocsEntryBySlug } from '~/composables/useDocs';
import { formatPageTitle } from '~/utils';
import { requirePageShell } from '~/utils/topLevelNavigation';

const route = useRoute();

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
</script>
