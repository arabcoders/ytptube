<template>
  <div class="w-full min-w-0 max-w-full space-y-4 p-1 sm:p-2">
    <div class="grid gap-4 rounded-lg border border-default bg-muted/10 p-4 lg:grid-cols-12">
      <UFormField label="Search" class="lg:col-span-4" :ui="fieldUi">
        <UInput
          v-model.trim="filters.query"
          type="text"
          placeholder="Filter by flag or description..."
          autocomplete="off"
          class="w-full"
          :ui="inputUi"
        >
          <template #leading>
            <UIcon name="i-lucide-search" class="size-4 text-toned" />
          </template>
        </UInput>
      </UFormField>

      <UFormField label="Group Filter" class="sm:col-span-6 lg:col-span-2" :ui="fieldUi">
        <USelect
          v-model="filters.group"
          :items="groupItems"
          value-key="value"
          label-key="label"
          class="w-full"
          :ui="inputUi"
        />
      </UFormField>

      <UFormField label="Display" class="sm:col-span-6 lg:col-span-2" :ui="fieldUi">
        <USelect
          v-model="displayMode"
          :items="displayItems"
          value-key="value"
          label-key="label"
          class="w-full"
          :ui="inputUi"
        />
      </UFormField>

      <UFormField label="Sort By" class="sm:col-span-6 lg:col-span-2" :ui="fieldUi">
        <USelect
          v-model="sortBy"
          :items="sortItems"
          value-key="value"
          label-key="label"
          class="w-full"
          :ui="inputUi"
        />
      </UFormField>

      <UFormField label="Order" class="sm:col-span-6 lg:col-span-2" :ui="fieldUi">
        <USelect
          v-model="sortDir"
          :items="orderItems"
          value-key="value"
          label-key="label"
          class="w-full"
          :ui="inputUi"
        />
      </UFormField>

      <UFormField label="Flags" class="lg:col-span-12" :ui="fieldUi">
        <div class="flex flex-wrap gap-2">
          <UButton
            v-for="item in flagFilterItems"
            :key="item.value"
            type="button"
            size="xs"
            :color="filters.flagKind === item.value ? 'primary' : 'neutral'"
            :variant="filters.flagKind === item.value ? 'solid' : 'outline'"
            @click="filters.flagKind = item.value"
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
            Reload
          </UButton>
        </div>
      </UFormField>
    </div>

    <UAlert
      v-if="isLoading"
      color="info"
      variant="soft"
      icon="i-lucide-loader-circle"
      title="Loading"
      description="Loading yt-dlp options. Please wait..."
    />

    <UAlert
      v-else-if="visible.length === 0"
      color="warning"
      variant="soft"
      icon="i-lucide-search-x"
      title="No options match your criteria."
    />

    <template v-else-if="displayMode === 'grouped' && grouped.length !== 0">
      <section v-for="group in grouped" :key="group.name" class="space-y-3">
        <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
          <UIcon name="i-lucide-folder-open" class="size-4 text-toned" />
          <span>{{ group.name }}</span>
          <UBadge color="neutral" variant="soft" size="sm">{{ group.items.length }}</UBadge>
        </div>

        <div
          class="w-full min-w-0 max-w-full overflow-hidden rounded-lg border border-default bg-default"
        >
          <div class="w-full max-w-full overflow-x-auto overscroll-x-contain">
            <table class="min-w-180 w-full table-auto text-sm">
              <thead class="bg-muted/40 text-xs uppercase tracking-wide text-toned">
                <tr
                  class="text-left [&>th]:border-r [&>th]:border-default/60 [&>th]:px-3 [&>th]:py-3 [&>th]:font-semibold [&>th:last-child]:border-r-0"
                >
                  <th class="w-80 whitespace-nowrap">Flags</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-default">
                <tr
                  v-for="opt in group.items"
                  :key="opt.flags.join('|')"
                  class="align-top transition-colors hover:bg-elevated/70 [&>td]:border-r [&>td]:border-default/60 [&>td:last-child]:border-r-0"
                >
                  <td class="w-80 px-3 py-3 align-top">
                    <div class="flex items-start gap-2">
                      <div class="flex flex-wrap gap-1.5">
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

                      <UTooltip text="Copy long flag">
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

    <div
      v-else
      class="w-full min-w-0 max-w-full overflow-hidden rounded-lg border border-default bg-default"
    >
      <div class="w-full max-w-full overflow-x-auto overscroll-x-contain">
        <table class="min-w-215 w-full table-auto text-sm">
          <thead class="bg-muted/40 text-xs uppercase tracking-wide text-toned">
            <tr
              class="text-left [&>th]:border-r [&>th]:border-default/60 [&>th]:px-3 [&>th]:py-3 [&>th]:font-semibold [&>th:last-child]:border-r-0"
            >
              <th class="w-80 whitespace-nowrap">Flags</th>
              <th class="w-36 whitespace-nowrap">Group</th>
              <th>Description</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-default">
            <tr
              v-for="opt in visible"
              :key="opt.flags.join('|')"
              class="align-top transition-colors hover:bg-elevated/70 [&>td]:border-r [&>td]:border-default/60 [&>td:last-child]:border-r-0"
            >
              <td class="w-80 px-3 py-3 align-top">
                <div class="flex items-start gap-2">
                  <div class="flex flex-wrap gap-1.5">
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

                  <UTooltip text="Copy long flag">
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

const displayItems = [
  { label: 'Grouped', value: 'grouped' },
  { label: 'List', value: 'list' },
];

const sortItems = [
  { label: 'Flag', value: 'flag' },
  { label: 'Group', value: 'group' },
];

const orderItems = [
  { label: 'Asc', value: 'asc' },
  { label: 'Desc', value: 'desc' },
];

const flagFilterItems = [
  { label: 'Any', value: 'any' as const },
  { label: 'Short Only (-x)', value: 'short' as const },
  { label: 'Long Only (--xyz)', value: 'long' as const },
];

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
