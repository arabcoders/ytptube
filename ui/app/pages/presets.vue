<template>
  <main class="w-full min-w-0 max-w-full space-y-4">
    <div class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
      <div class="min-w-0 space-y-1">
        <div class="flex items-center gap-2 text-lg font-semibold text-highlighted">
          <UIcon name="i-lucide-sliders-horizontal" class="size-5 text-toned" />
          <span>Presets</span>
        </div>

        <p class="text-sm text-toned">
          Presets are pre-defined command options for yt-dlp that you want to apply to given
          download.
        </p>
      </div>

      <div class="flex flex-wrap items-center justify-end gap-2">
        <div v-if="showFilter && presetsNoDefault.length > 0" class="relative w-full sm:w-80">
          <span
            class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-toned"
          >
            <UIcon name="i-lucide-filter" class="size-4" />
          </span>
          <input
            id="filter"
            ref="filterInput"
            v-model="query"
            type="search"
            placeholder="Filter displayed content"
            class="w-full rounded-md border border-default bg-elevated py-2 pr-3 pl-9 text-sm text-default outline-none transition focus:border-primary"
          />
        </div>

        <UButton
          v-if="presetsNoDefault.length > 0"
          color="neutral"
          :variant="showFilter ? 'soft' : 'outline'"
          size="sm"
          icon="i-lucide-filter"
          @click="toggleFilterPanel"
        >
          <span v-if="!isMobile">Filter</span>
        </UButton>

        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-plus"
          @click="editor.openCreate()"
        >
          <span v-if="!isMobile">New Preset</span>
        </UButton>

        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          :icon="display_style === 'list' ? 'i-lucide-list' : 'i-lucide-grid-2x2'"
          @click="toggleDisplayStyle"
        >
          <span v-if="!isMobile">{{ display_style === 'list' ? 'List' : 'Grid' }}</span>
        </UButton>

        <UButton
          v-if="presets.length > 0"
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-refresh-cw"
          :loading="isLoading"
          :disabled="isLoading"
          @click="() => void reloadContent()"
        >
          <span v-if="!isMobile">Reload</span>
        </UButton>
      </div>
    </div>

    <div
      v-if="display_style === 'list' && filteredPresets.length > 0"
      class="w-full min-w-0 max-w-full overflow-hidden rounded-lg border border-default bg-default"
    >
      <div class="w-full max-w-full overflow-x-auto overscroll-x-contain">
        <table class="min-w-190 w-full text-sm">
          <thead class="bg-muted/40 text-xs uppercase tracking-wide text-toned">
            <tr class="text-center [&>th]:px-3 [&>th]:py-3 [&>th]:font-semibold">
              <th class="w-full text-left">Preset</th>
              <th class="w-44 whitespace-nowrap">Actions</th>
            </tr>
          </thead>

          <tbody class="divide-y divide-default">
            <tr v-for="item in filteredPresets" :key="item.id" class="hover:bg-muted/20">
              <td class="px-3 py-3 align-middle">
                <div class="space-y-1">
                  <div class="font-semibold text-highlighted">
                    {{ prettyName(item.name) }}
                  </div>

                  <div class="flex flex-wrap items-center gap-3 text-xs text-toned">
                    <span
                      class="inline-flex items-center gap-1"
                      :class="item.cookies ? 'text-info' : ''"
                    >
                      <UIcon name="i-lucide-cookie" class="size-3.5" />
                      <span>{{ item.cookies ? 'Has cookies' : 'No cookies' }}</span>
                    </span>

                    <span v-if="item.priority > 0" class="inline-flex items-center gap-1">
                      <UIcon name="i-lucide-list-ordered" class="size-3.5" />
                      <span>Priority: {{ item.priority }}</span>
                    </span>
                  </div>
                </div>
              </td>

              <td class="w-44 px-3 py-3 align-middle whitespace-nowrap">
                <div class="flex items-center justify-end gap-2">
                  <UButton
                    color="info"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-file-up"
                    @click="exportItem(item)"
                  >
                    <span v-if="!isMobile">Export</span>
                  </UButton>

                  <UButton
                    color="warning"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-pencil"
                    @click="editor.openEdit(item)"
                  >
                    <span v-if="!isMobile">Edit</span>
                  </UButton>

                  <UButton
                    color="error"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-trash"
                    @click="() => void deleteItem(item)"
                  >
                    <span v-if="!isMobile">Delete</span>
                  </UButton>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-else-if="filteredPresets.length > 0" class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      <UCard
        v-for="item in filteredPresets"
        :key="item.id"
        class="flex h-full flex-col border bg-default"
        :ui="{ header: 'p-4 pb-3', body: 'flex flex-1 flex-col gap-4 p-4 pt-0' }"
      >
        <template #header>
          <div class="flex items-start justify-between gap-3">
            <button
              type="button"
              class="min-w-0 flex-1 text-left text-sm font-semibold text-highlighted"
              @click="toggleExpand(item.id, 'title')"
            >
              <span
                :class="
                  !isExpanded(item.id, 'title') ? 'block truncate' : 'block whitespace-pre-wrap'
                "
              >
                {{ prettyName(item.name) }}
              </span>
            </button>

            <UButton
              color="info"
              variant="ghost"
              size="xs"
              icon="i-lucide-file-up"
              square
              @click="exportItem(item)"
            />
          </div>

          <div class="flex flex-wrap gap-2 text-xs text-toned *:min-w-32 *:flex-1">
            <span
              class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1"
              :class="item.cookies ? 'border-info/40 text-info' : ''"
            >
              <UIcon name="i-lucide-cookie" class="size-3.5" />
              <span>{{ item.cookies ? 'Has cookies' : 'No cookies' }}</span>
            </span>

            <span
              v-if="item.priority > 0"
              class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1"
            >
              <UIcon name="i-lucide-list-ordered" class="size-3.5" />
              <span>Priority {{ item.priority }}</span>
            </span>
          </div>
        </template>

        <div class="space-y-2 text-sm text-default">
          <button
            v-if="item.folder"
            type="button"
            class="flex w-full items-start gap-2 rounded-md border border-default bg-muted/20 px-3 py-2 text-left"
            @click="toggleExpand(item.id, 'folder')"
          >
            <UIcon name="i-lucide-folder-output" class="mt-0.5 size-4 shrink-0 text-toned" />
            <span :class="expandClass(item.id, 'folder')">{{ calcPath(item.folder) }}</span>
          </button>

          <button
            v-if="item.template"
            type="button"
            class="flex w-full items-start gap-2 rounded-md border border-default bg-muted/20 px-3 py-2 text-left"
            @click="toggleExpand(item.id, 'template')"
          >
            <UIcon name="i-lucide-file-code-2" class="mt-0.5 size-4 shrink-0 text-toned" />
            <span :class="expandClass(item.id, 'template')">{{ item.template }}</span>
          </button>

          <button
            v-if="item.cli"
            type="button"
            class="flex w-full items-start gap-2 rounded-md border border-default bg-muted/20 px-3 py-2 text-left"
            @click="toggleExpand(item.id, 'cli')"
          >
            <UIcon name="i-lucide-terminal" class="mt-0.5 size-4 shrink-0 text-toned" />
            <span :class="expandClass(item.id, 'cli')">{{ item.cli }}</span>
          </button>

          <button
            v-if="item.description"
            type="button"
            class="flex w-full items-start gap-2 rounded-md border border-default bg-muted/20 px-3 py-2 text-left"
            @click="toggleExpand(item.id, 'description')"
          >
            <UIcon name="i-lucide-align-left" class="mt-0.5 size-4 shrink-0 text-toned" />
            <span :class="expandClass(item.id, 'description')">{{ item.description }}</span>
          </button>
        </div>

        <div class="mt-auto flex flex-wrap gap-2 pt-2 *:min-w-32 *:flex-1">
          <UButton
            color="warning"
            variant="outline"
            icon="i-lucide-pencil"
            class="w-full justify-center"
            @click="editor.openEdit(item)"
          >
            Edit
          </UButton>

          <UButton
            color="error"
            variant="outline"
            icon="i-lucide-trash"
            class="w-full justify-center"
            @click="() => void deleteItem(item)"
          >
            Delete
          </UButton>
        </div>
      </UCard>
    </div>

    <UAlert
      v-if="isLoading"
      color="info"
      variant="soft"
      icon="i-lucide-loader-circle"
      title="Loading"
      description="Loading data. Please wait..."
    />

    <div v-else-if="query && filteredPresets.length < 1" class="space-y-3">
      <UAlert
        color="warning"
        variant="soft"
        icon="i-lucide-search"
        title="No Results"
        :description="`No results found for the query: ${query}. Please try a different search term.`"
      />

      <UButton color="neutral" variant="outline" size="sm" @click="query = ''"
        >Clear filter</UButton
      >
    </div>

    <UAlert
      v-else-if="!filteredPresets.length"
      color="warning"
      variant="soft"
      icon="i-lucide-circle-alert"
      title="No presets"
      description="There are no custom defined presets."
    />

    <UAlert v-if="!query && presets.length > 0" color="info" variant="soft">
      <template #description>
        <ul class="list-disc space-y-2 pl-5 text-sm text-default">
          <li>
            When you export preset, it doesn't include the cookies field contents for security
            reasons.
          </li>
        </ul>
      </template>
    </UAlert>

    <UModal
      v-if="editor.isOpen.value"
      :open="editor.isOpen.value"
      :title="editor.modalTitle.value"
      :description="editor.modalDescription.value"
      :dismissible="!editor.addInProgress.value"
      :ui="{ content: 'w-full sm:max-w-6xl', body: 'max-h-[85vh] overflow-y-auto p-4 sm:p-6' }"
      @update:open="(open) => !open && void editor.requestClose()"
    >
      <template #body>
        <PresetForm
          :key="editor.modalKey.value"
          :addInProgress="editor.addInProgress.value"
          :reference="editor.reference.value"
          :preset="editor.preset.value"
          :presets="presets"
          @cancel="() => void editor.requestClose()"
          @submit="editor.submit"
        />
      </template>
    </UModal>
  </main>
</template>

<script setup lang="ts">
import { useStorage } from '@vueuse/core';
import type { Preset } from '~/types/presets';
import { useConfirm } from '~/composables/useConfirm';
import { prettyName } from '~/utils';

type PresetWithUI = Preset & { raw?: boolean; toggle_description?: boolean };

const presetsStore = usePresets();
const config = useConfigStore();
const box = useConfirm();
const editor = usePresetEditor();

const display_style = useStorage<string>('preset_display_style', 'grid');
const isMobile = useMediaQuery({ maxWidth: 1024 });

const query = ref('');
const showFilter = ref(false);
const filterInput = ref<HTMLInputElement | null>(null);

const presets = computed(() => presetsStore.presets.value as PresetWithUI[]);
const isLoading = presetsStore.isLoading;
const expandedItems = ref<Record<string, Set<string>>>({});

const presetsNoDefault = computed(() => presets.value.filter((item) => !item.default));

const filteredPresets = computed<PresetWithUI[]>(() => {
  const normalizedQuery = query.value?.toLowerCase();
  if (!normalizedQuery) {
    return presetsNoDefault.value;
  }

  return presetsNoDefault.value.filter((item) =>
    deepIncludes(item, normalizedQuery, new WeakSet()),
  );
});

watch(showFilter, (value) => {
  if (!value) {
    query.value = '';
  }
});

const toggleFilterPanel = async (): Promise<void> => {
  showFilter.value = !showFilter.value;
  if (!showFilter.value) {
    query.value = '';
    return;
  }

  await nextTick();
  filterInput.value?.focus();
};

const reloadContent = async (): Promise<void> => {
  await presetsStore.loadPresets(1, 1000);
};

const deleteItem = async (item: Preset): Promise<void> => {
  if (true !== (await box.confirm(`Delete preset '${item.name}'?`))) {
    return;
  }

  if (item.id) {
    await presetsStore.deletePreset(item.id);
  }
};

const toggleDisplayStyle = (): void => {
  display_style.value = display_style.value === 'list' ? 'grid' : 'list';
};

const toggleExpand = (itemId: number | string | undefined, field: string): void => {
  if (itemId === undefined || itemId === null) {
    return;
  }

  const key = String(itemId);
  if (!expandedItems.value[key]) {
    expandedItems.value[key] = new Set();
  }

  if (expandedItems.value[key]?.has(field)) {
    expandedItems.value[key]?.delete(field);
  } else {
    expandedItems.value[key]?.add(field);
  }
};

const isExpanded = (itemId: number | string | undefined, field: string): boolean => {
  if (itemId === undefined || itemId === null) {
    return false;
  }

  return expandedItems.value[String(itemId)]?.has(field) ?? false;
};

const expandClass = (itemId: number | string | undefined, field: string): string => {
  return isExpanded(itemId, field) ? 'whitespace-pre-wrap break-words' : 'truncate';
};

const exportItem = (item: Preset): void => {
  const excludedKeys = ['id', 'default', 'raw', 'cookies', 'toggle_description'];
  const userData = Object.fromEntries(
    Object.entries(JSON.parse(JSON.stringify(item))).filter(
      ([key, value]) => !excludedKeys.includes(key) && value,
    ),
  );

  userData['_type'] = 'preset';
  userData['_version'] = '2.6';

  copyText(encode(userData));
};

const calcPath = (path?: string): string => {
  const location = config.app.download_path || '/downloads';
  return path ? location + '/' + sTrim(path, '/') : location;
};

onMounted(async () => await reloadContent());
</script>
