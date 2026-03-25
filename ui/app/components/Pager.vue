<template>
  <div class="flex flex-wrap items-center gap-2">
    <UButton
      v-if="page !== 1"
      rel="first"
      aria-label="Go to first page"
      color="neutral"
      variant="outline"
      size="sm"
      icon="i-lucide-chevrons-left"
      :disabled="isLoading"
      :loading="isLoading"
      square
      @click="changePage(1)"
    />

    <UButton
      v-if="page > 1 && page - 1 !== 1"
      rel="prev"
      aria-label="Go to previous page"
      color="neutral"
      variant="outline"
      size="sm"
      icon="i-lucide-chevron-left"
      :disabled="isLoading"
      :loading="isLoading"
      square
      @click="changePage(page - 1)"
    />

    <USelect
      id="pager_list"
      v-model="currentPage"
      :items="paginationItems"
      value-key="page"
      label-key="text"
      color="neutral"
      variant="outline"
      size="sm"
      class="min-w-52"
      :disabled="isLoading"
      :ui="{ base: 'w-full' }"
      @update:model-value="changePage"
    />

    <UButton
      v-if="page !== last_page && page + 1 !== last_page"
      rel="next"
      aria-label="Go to next page"
      color="neutral"
      variant="outline"
      size="sm"
      icon="i-lucide-chevron-right"
      :disabled="isLoading"
      :loading="isLoading"
      square
      @click="changePage(page + 1)"
    />

    <UButton
      v-if="page !== last_page"
      rel="last"
      aria-label="Go to last page"
      color="neutral"
      variant="outline"
      size="sm"
      icon="i-lucide-chevrons-right"
      :disabled="isLoading"
      :loading="isLoading"
      square
      @click="changePage(last_page)"
    />
  </div>
</template>

<script setup lang="ts">
import { makePagination } from '~/utils/index';

const emitter = defineEmits<{
  (e: 'navigate', page: number): void;
}>();

const props = defineProps<{
  page: number;
  last_page: number;
  isLoading?: boolean;
}>();

const currentPage = ref(props.page);

const paginationItems = computed(() =>
  makePagination(props.page, props.last_page).map((item) => ({
    ...item,
    disabled: item.page === 0,
  })),
);

watch(
  () => props.page,
  (value) => {
    currentPage.value = value;
  },
);

const changePage = (page: number | string): void => {
  const nextPage = Number(page);
  if (Number.isNaN(nextPage) || nextPage < 1 || nextPage > props.last_page) {
    currentPage.value = props.page;
    return;
  }

  emitter('navigate', nextPage);
  currentPage.value = nextPage;
};
</script>
