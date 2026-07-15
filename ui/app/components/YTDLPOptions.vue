<template>
  <div class="w-full min-w-0 max-w-full space-y-4 p-1 sm:p-2">
    <div class="grid gap-4 rounded-lg border border-default bg-muted/10 p-4 lg:grid-cols-12">
      <UFormField :label="t('common.search')" class="lg:col-span-4" :ui="fieldUi">
        <UInput
          v-model.trim="filters.query"
          type="text"
          :placeholder="t('common.filterFlagDesc')"
          autocomplete="off"
          class="w-full"
          :ui="inputUi"
        >
          <template #leading>
            <UIcon name="i-lucide-search" class="size-4 text-toned" />
          </template>
        </UInput>
      </UFormField>

      <UFormField
        :label="t('common.groupFilter')"
        class="sm:col-span-6 lg:col-span-2"
        :ui="fieldUi"
      >
        <USelectMenu
          v-model="filters.group"
          :items="groupItems"
          value-key="value"
          label-key="label"
          color="neutral"
          class="w-full"
          :ui="{ content: 'min-w-[13rem]' }"
          :search-input="{ placeholder: t('common.searchGroups') }"
        />
      </UFormField>

      <UFormField :label="t('common.display')" class="sm:col-span-6 lg:col-span-2" :ui="fieldUi">
        <USelectMenu
          v-model="displayMode"
          :items="displayItems"
          value-key="value"
          label-key="label"
          color="neutral"
          class="w-full"
          :ui="{ content: 'min-w-[13rem]' }"
          :search-input="false"
        />
      </UFormField>

      <UFormField :label="t('common.sortBy')" class="sm:col-span-6 lg:col-span-2" :ui="fieldUi">
        <USelectMenu
          v-model="sortBy"
          :items="sortItems"
          value-key="value"
          label-key="label"
          color="neutral"
          class="w-full"
          :ui="{ content: 'min-w-[13rem]' }"
          :search-input="false"
        />
      </UFormField>

      <UFormField :label="t('common.order')" class="sm:col-span-6 lg:col-span-2" :ui="fieldUi">
        <USelectMenu
          v-model="sortDir"
          :items="orderItems"
          value-key="value"
          label-key="label"
          color="neutral"
          class="w-full"
          :ui="{ content: 'min-w-[13rem]' }"
          :search-input="false"
        />
      </UFormField>

      <UFormField :label="t('common.flagsColumn')" class="lg:col-span-12" :ui="fieldUi">
        <div class="flex flex-wrap gap-2">
          <UButton
            v-for="item in flagFilterItems"
            :key="item.value"
            type="button"
            size="xs"
            :color="filters.flagKind === item.value ? 'primary' : 'neutral'"
            :variant="filters.flagKind === item.value ? 'solid' : 'outline'"
            @click="
              () => {
                filters.flagKind = item.value;
              }
            "
          >
            {{ item.label }}
          </UButton>

          <UButton
            type="button"
            color="neutral"
            variant="ghost"
            size="xs"
            icon="i-lucide-refresh-cw"
            :loading="isLoading"
            :disabled="isLoading"
            @click="() => void reload()"
          >
            {{ t('common.refresh') }}
          </UButton>
        </div>
      </UFormField>
    </div>

    <UAlert
      v-if="isLoading"
      color="info"
      variant="soft"
      icon="i-lucide-loader-circle"
      :title="t('common.loading')"
      :description="t('common.loadingData')"
    />

    <UAlert
      v-else-if="visible.length === 0"
      color="warning"
      variant="soft"
      icon="i-lucide-search-x"
      :title="t('common.noOptionsMatch')"
    />

    <template v-else-if="displayMode === 'grouped' && grouped.length !== 0">
      <section v-for="group in grouped" :key="group.name" class="space-y-3">
        <div class="flex items-center gap-2 text-sm font-semibold text-highlighted" dir="ltr">
          <UIcon name="i-lucide-folder-open" class="size-4 text-toned" />
          <span>{{ group.name }}</span>
          <UBadge color="neutral" variant="soft" size="sm">{{ group.items.length }}</UBadge>
        </div>

        <div class="w-full min-w-0 max-w-full overflow-hidden ytp-table-surface">
          <div class="w-full max-w-full overflow-x-auto overscroll-x-contain">
            <table class="min-w-180 w-full table-auto text-sm" dir="ltr">
              <thead class="bg-elevated/60 text-xs uppercase tracking-wide text-toned">
                <tr
                  class="text-left [&>th]:border-e [&>th]:border-default/60 [&>th]:px-3 [&>th]:py-3 [&>th]:font-semibold [&>th:last-child]:border-e-0"
                >
                  <th class="w-80 whitespace-nowrap">{{ t('common.flagsColumn') }}</th>
                  <th>{{ t('common.description') }}</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-default">
                <tr
                  v-for="opt in group.items"
                  :key="opt.flags.join('|')"
                  class="align-top transition-colors hover:bg-elevated/70 [&>td]:border-e [&>td]:border-default/60 [&>td:last-child]:border-e-0"
                >
                  <td class="w-80 px-3 py-3 align-top">
                    <div class="flex items-start gap-3" dir="ltr">
                      <div class="flex min-w-0 flex-1 flex-wrap gap-1.5">
                        <UBadge
                          v-for="flag in opt.flags"
                          :key="flag"
                          color="info"
                          variant="soft"
                          size="sm"
                          class="max-w-full whitespace-nowrap font-mono"
                        >
                          {{ flag }}
                        </UBadge>
                      </div>

                      <UTooltip :text="t('common.copyLongFlag')">
                        <UButton
                          type="button"
                          color="neutral"
                          variant="ghost"
                          size="xs"
                          icon="i-lucide-copy"
                          square
                          class="shrink-0"
                          :disabled="!hasLongFlag(opt.flags)"
                          @click="() => void copyFlag(opt.flags)"
                        />
                      </UTooltip>
                    </div>
                  </td>
                  <td class="px-3 py-3 align-top text-default">
                    <div class="min-w-0 wrap-break-word whitespace-normal">
                      <span v-if="opt.description && opt.description.length !== 0">{{
                        opt.description
                      }}</span>
                      <span v-else class="text-toned">-</span>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </template>

    <div v-else class="w-full min-w-0 max-w-full overflow-hidden ytp-table-surface">
      <div class="w-full max-w-full overflow-x-auto overscroll-x-contain">
        <table class="min-w-215 w-full table-auto text-sm" dir="ltr">
          <thead class="bg-muted/40 text-xs uppercase tracking-wide text-toned">
            <tr
              class="text-left [&>th]:border-e [&>th]:border-default/60 [&>th]:px-3 [&>th]:py-3 [&>th]:font-semibold [&>th:last-child]:border-e-0"
            >
              <th class="w-80 whitespace-nowrap">{{ t('common.flagsColumn') }}</th>
              <th class="w-36 whitespace-nowrap">{{ t('common.groupColumn') }}</th>
              <th>{{ t('common.description') }}</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-default">
            <tr
              v-for="opt in visible"
              :key="opt.flags.join('|')"
              class="align-top transition-colors hover:bg-elevated/70 [&>td]:border-e [&>td]:border-default/60 [&>td:last-child]:border-e-0"
            >
              <td class="w-80 px-3 py-3 align-top">
                <div class="flex items-start gap-3" dir="ltr">
                  <div class="flex min-w-0 flex-1 flex-wrap gap-1.5">
                    <UBadge
                      v-for="flag in opt.flags"
                      :key="flag"
                      color="info"
                      variant="soft"
                      size="sm"
                      class="max-w-full whitespace-nowrap font-mono"
                    >
                      {{ flag }}
                    </UBadge>
                  </div>

                  <UTooltip :text="t('common.copyLongFlag')">
                    <UButton
                      type="button"
                      color="neutral"
                      variant="ghost"
                      size="xs"
                      icon="i-lucide-copy"
                      square
                      class="shrink-0"
                      :disabled="!hasLongFlag(opt.flags)"
                      @click="() => void copyFlag(opt.flags)"
                    />
                  </UTooltip>
                </div>
              </td>
              <td class="w-36 px-3 py-3 align-top font-medium text-default whitespace-nowrap">
                {{ opt.group || 'root' }}
              </td>
              <td class="px-3 py-3 align-top text-default">
                <div class="min-w-0 wrap-break-word whitespace-normal">
                  <span v-if="opt.description && opt.description.length !== 0">{{
                    opt.description
                  }}</span>
                  <span v-else class="text-toned">-</span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useStorage } from '@vueuse/core';
import type { YTDLPOption } from '~/types/ytdlp';
import {
  buildYtdlpGroupItems,
  normalizeYtdlpGroupFilter,
  YTDLP_ALL_GROUPS,
} from '~/utils/ytdlpOptions';

const { t } = useI18n();

const isLoading = ref(false);
const options = ref<YTDLPOption[]>([]);
const displayMode = useStorage<'grouped' | 'list'>('opts_display', 'grouped');
const sortBy = useStorage<'flag' | 'group'>('opts_sort_by', 'flag');
const sortDir = useStorage<'asc' | 'desc'>('opts_sort_dir', 'asc');

const filters = reactive({
  query: '',
  group: YTDLP_ALL_GROUPS,
  flagKind: 'any' as 'any' | 'short' | 'long',
});

const fieldUi = {
  label: 'font-semibold text-default',
  container: 'space-y-2',
  description: 'text-sm text-toned',
};

const inputUi = {
  root: 'w-full',
  base: 'w-full bg-elevated/60 ring-default focus-visible:ring-primary',
};

const displayItems = computed(() => [
  { label: t('common.grouped'), value: 'grouped' },
  { label: t('common.list'), value: 'list' },
]);

const sortItems = computed(() => [
  { label: t('common.sortByFlag'), value: 'flag' },
  { label: t('common.groupColumn'), value: 'group' },
]);

const orderItems = computed(() => [
  { label: t('common.asc'), value: 'asc' },
  { label: t('common.desc'), value: 'desc' },
]);

const flagFilterItems = computed(() => [
  { label: t('common.anyFilter'), value: 'any' as const },
  { label: t('common.shortFilter'), value: 'short' as const },
  { label: t('common.longFilter'), value: 'long' as const },
]);

const reload = async (): Promise<void> => {
  try {
    isLoading.value = true;
    const resp = await request('/api/yt-dlp/options');
    if (!resp.ok) {
      return;
    }
    const data = await resp.json();
    if (Array.isArray(data)) {
      options.value = data as YTDLPOption[];
    }
  } finally {
    isLoading.value = false;
  }
};

const hasLongFlag = (flags: string[]): boolean => {
  return flags.some((flag) => flag.startsWith('--'));
};

const copyFlag = async (flags: string[]): Promise<void> => {
  const longFlag = flags.find((flag) => flag.startsWith('--'));
  if (!longFlag) {
    return;
  }
  copyText(longFlag);
};

onMounted(async () => await reload());

const groupNames = computed<string[]>(() => {
  const names = new Set<string>();
  for (const option of options.value) {
    names.add(option.group || 'root');
  }
  return Array.from(names).sort((a, b) => a.localeCompare(b));
});

const groupItems = computed(() => {
  return buildYtdlpGroupItems(groupNames.value);
});

const filtered = computed<YTDLPOption[]>(() => {
  const q = filters.query.toLowerCase();
  const g = normalizeYtdlpGroupFilter(filters.group);

  return options.value.filter((option) => {
    if (option.ignored) {
      return false;
    }

    if (g && (option.group || 'root') !== g) {
      return false;
    }

    if (
      filters.flagKind === 'short' &&
      !option.flags.some((flag) => /^-\w(,|$)|^-\w$/.test(flag))
    ) {
      return false;
    }

    if (
      filters.flagKind === 'long' &&
      !option.flags.some((flag) => /^--[a-zA-Z0-9][\w-]*/.test(flag))
    ) {
      return false;
    }

    if (q.length !== 0) {
      const haystack = [option.flags.join(' '), option.description || '', option.group || 'root']
        .join(' ')
        .toLowerCase();
      if (!haystack.includes(q)) {
        return false;
      }
    }

    return true;
  });
});

const sorted = computed<YTDLPOption[]>(() => {
  const dir = sortDir.value === 'asc' ? 1 : -1;
  const list = [...filtered.value];

  list.sort((a, b) => {
    if (sortBy.value === 'group') {
      const groupCompare = (a.group || 'root').localeCompare(b.group || 'root');
      if (groupCompare !== 0) {
        return groupCompare * dir;
      }
    }

    return (a.flags[0] || '').localeCompare(b.flags[0] || '') * dir;
  });

  return list;
});

const visible = computed(() => sorted.value);

const grouped = computed<{ name: string; items: YTDLPOption[] }[]>(() => {
  const map = new Map<string, YTDLPOption[]>();

  for (const option of visible.value) {
    const key = option.group || 'root';
    if (!map.has(key)) {
      map.set(key, []);
    }
    map.get(key)?.push(option);
  }

  const dir = sortDir.value === 'asc' ? 1 : -1;
  const list = Array.from(map.entries()).map(([name, items]) => ({ name, items }));

  if (sortBy.value === 'group') {
    list.sort((a, b) => a.name.localeCompare(b.name) * dir);
  } else {
    list.sort((a, b) => a.name.localeCompare(b.name));
  }

  return list;
});
</script>
