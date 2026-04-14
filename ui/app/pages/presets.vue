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
      v-if="!isLoading && filteredPresets.length > 0"
      class="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-default bg-default px-3 py-3"
    >
      <div class="flex flex-wrap items-center gap-2">
        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          :icon="allSelected ? 'i-lucide-square' : 'i-lucide-square-check-big'"
          @click="toggleMasterSelection"
        >
          {{ allSelected ? 'Unselect' : 'Select' }}
        </UButton>

        <UBadge v-if="selectedIds.length > 0" color="error" variant="soft" size="sm">
          {{ selectedIds.length }}
        </UBadge>

        <UDropdownMenu :items="bulkActionGroups" :modal="false">
          <UButton
            color="neutral"
            variant="outline"
            size="sm"
            icon="i-lucide-list"
            trailing-icon="i-lucide-chevron-down"
          >
            Actions
          </UButton>
        </UDropdownMenu>
      </div>

      <div class="text-xs text-toned">{{ filteredPresets.length }} displayed</div>
    </div>

    <div
      v-if="display_style === 'list' && filteredPresets.length > 0"
      class="w-full min-w-0 max-w-full overflow-hidden rounded-lg border border-default bg-default"
    >
      <div class="w-full max-w-full overflow-x-auto overscroll-x-contain">
        <table class="min-w-190 w-full text-sm">
          <thead class="bg-muted/40 text-xs uppercase tracking-wide text-toned">
            <tr class="text-center [&>th]:px-3 [&>th]:py-3 [&>th]:font-semibold">
              <th class="w-12">
                <button type="button" class="cursor-pointer" @click="toggleMasterSelection">
                  <UIcon
                    :name="allSelected ? 'i-lucide-square' : 'i-lucide-square-check-big'"
                    class="size-4"
                  />
                </button>
              </th>
              <th class="w-full text-left">Preset</th>
              <th class="w-44 whitespace-nowrap">Actions</th>
            </tr>
          </thead>

          <tbody class="divide-y divide-default">
            <tr v-for="item in filteredPresets" :key="item.id" class="hover:bg-muted/20">
              <td class="px-3 py-3 text-center align-middle">
                <label class="inline-flex cursor-pointer items-center justify-center">
                  <input
                    v-model="selectedIds"
                    class="completed-checkbox size-4 rounded border-default"
                    type="checkbox"
                    :value="item.id"
                  />
                </label>
              </td>

              <td class="px-3 py-3 align-middle">
                <div class="space-y-1">
                  <div class="font-semibold text-highlighted">
                    {{ prettyName(item.name) }}
                  </div>

                  <div class="flex flex-wrap items-center gap-3 text-xs text-toned">
                    <span
                      class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1"
                    >
                      <UIcon
                        name="i-lucide-cookie"
                        class="size-3.5"
                        :class="item.cookies ? 'text-success' : ''"
                      />
                      <span>{{ item.cookies ? 'Has cookies' : 'No cookies' }}</span>
                    </span>

                    <span
                      v-if="item.priority > 0"
                      class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1"
                    >
                      <UIcon name="i-lucide-list-ordered" class="size-3.5" />
                      <span>Priority: {{ item.priority }}</span>
                    </span>
                  </div>
                </div>
              </td>

              <td class="w-44 px-3 py-3 align-middle whitespace-nowrap">
                <div class="flex items-center justify-end gap-2">
                  <UButton
                    color="neutral"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-file-up"
                    @click="exportItem(item)"
                  >
                    <span v-if="!isMobile">Export</span>
                  </UButton>

                  <UButton
                    color="neutral"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-pencil"
                    @click="editor.openEdit(item)"
                  >
                    <span v-if="!isMobile">Edit</span>
                  </UButton>

                  <UButton
                    color="neutral"
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
      <div v-for="item in filteredPresets" :key="item.id" class="min-w-0 w-full max-w-full">
        <UCard
          class="flex h-full min-w-0 w-full max-w-full flex-col border bg-default"
          :ui="{ header: 'p-4 pb-3', body: 'flex flex-1 flex-col gap-4 p-4 pt-0' }"
        >
          <template #header>
            <div class="flex min-w-0 items-start justify-between gap-3">
              <div class="min-w-0 flex-1">
                <div class="flex items-start gap-2">
                  <button
                    type="button"
                    class="min-w-0 flex-1 text-left text-sm font-semibold text-highlighted"
                    @click="toggleExpand(item.id, 'title')"
                  >
                    <span :class="['block', expandClass(item.id, 'title')]">
                      {{ prettyName(item.name) }}
                    </span>
                  </button>
                </div>
              </div>

              <div class="flex shrink-0 items-center gap-2">
                <UButton
                  color="neutral"
                  variant="ghost"
                  size="xs"
                  icon="i-lucide-file-up"
                  square
                  @click="exportItem(item)"
                >
                  <span class="hidden sm:inline">Export Preset</span>
                </UButton>

                <label class="inline-flex cursor-pointer items-center justify-center">
                  <input
                    v-model="selectedIds"
                    class="completed-checkbox size-4 rounded border-default"
                    type="checkbox"
                    :value="item.id"
                  />
                </label>
              </div>
            </div>
          </template>

          <div class="space-y-2 text-sm text-default">
            <div class="flex flex-wrap gap-2 text-xs text-toned *:min-w-32 *:flex-1">
              <span
                class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1"
              >
                <UIcon
                  name="i-lucide-cookie"
                  class="size-3.5"
                  :class="item.cookies ? 'text-success' : ''"
                />
                <span>Cookies: {{ item.cookies ? 'Configured' : 'Not set' }}</span>
              </span>

              <span
                v-if="item.priority > 0"
                class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1"
              >
                <UIcon name="i-lucide-list-ordered" class="size-3.5" />
                <span>Priority: {{ item.priority }}</span>
              </span>
            </div>

            <button
              v-if="item.folder"
              type="button"
              class="flex min-w-0 w-full items-start gap-2 rounded-md border border-default bg-muted/20 px-3 py-2 text-left"
              @click="toggleExpand(item.id, 'folder')"
            >
              <UIcon name="i-lucide-folder-output" class="mt-0.5 size-4 shrink-0 text-toned" />
              <div class="min-w-0 flex-1">
                <div class="text-xs font-medium text-toned">Download path</div>
                <span :class="['block', expandClass(item.id, 'folder')]">{{
                  calcPath(item.folder)
                }}</span>
              </div>
            </button>

            <div v-if="item.template || item.cli" class="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <button
                v-if="item.template"
                type="button"
                :class="[
                  'flex min-w-0 w-full items-start gap-2 rounded-md border border-default bg-muted/20 px-3 py-2 text-left',
                  !item.cli && 'sm:col-span-2',
                ]"
                @click="toggleExpand(item.id, 'template')"
              >
                <UIcon name="i-lucide-file-code-2" class="mt-0.5 size-4 shrink-0 text-toned" />
                <div class="min-w-0 flex-1">
                  <div class="text-xs font-medium text-toned">Output template</div>
                  <span :class="['block', expandClass(item.id, 'template')]">{{
                    item.template
                  }}</span>
                </div>
              </button>

              <button
                v-if="item.cli"
                type="button"
                :class="[
                  'flex min-w-0 w-full items-start gap-2 rounded-md border border-default bg-muted/20 px-3 py-2 text-left',
                  !item.template && 'sm:col-span-2',
                ]"
                @click="toggleExpand(item.id, 'cli')"
              >
                <UIcon name="i-lucide-terminal" class="mt-0.5 size-4 shrink-0 text-toned" />
                <div class="min-w-0 flex-1">
                  <div class="text-xs font-medium text-toned">CLI options</div>
                  <span :class="['block', expandClass(item.id, 'cli')]">{{ item.cli }}</span>
                </div>
              </button>
            </div>

            <button
              v-if="item.description"
              type="button"
              class="flex min-w-0 w-full items-start gap-2 rounded-md border border-default bg-muted/20 px-3 py-2 text-left"
              @click="toggleExpand(item.id, 'description')"
            >
              <UIcon name="i-lucide-align-left" class="mt-0.5 size-4 shrink-0 text-toned" />
              <div class="min-w-0 flex-1">
                <div class="text-xs font-medium text-toned">Description</div>
                <span :class="['block', expandClass(item.id, 'description')]">{{
                  item.description
                }}</span>
              </div>
            </button>
          </div>

          <div class="mt-auto flex flex-wrap gap-2 pt-2 *:min-w-32 *:flex-1">
            <UButton
              color="neutral"
              variant="outline"
              icon="i-lucide-pencil"
              class="w-full justify-center"
              @click="editor.openEdit(item)"
            >
              Edit
            </UButton>

            <UButton
              color="neutral"
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
            reasons. However, there are some CLI options that could contain sensitive data like
            username or password. Remove them before sharing your preset.
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
      @update:open="(open) => void editor.handleOpenChange(open)"
    >
      <template #body>
        <PresetForm
          :key="editor.modalKey.value"
          :addInProgress="editor.addInProgress.value"
          :reference="editor.reference.value"
          :preset="editor.preset.value"
          :presets="presets"
          @cancel="() => void editor.requestClose()"
          @dirty-change="(dirty) => (editor.dirty.value = dirty)"
          @submit="editor.submit"
        />
      </template>
    </UModal>
  </main>
</template>

<script setup lang="ts">
import type { DropdownMenuItem } from '@nuxt/ui';
import { useStorage } from '@vueuse/core';
import type { Preset } from '~/types/presets';
import { useDialog } from '~/composables/useDialog';
import { useExpandableMeta } from '~/composables/useExpandableMeta';
import { useConfirm } from '~/composables/useConfirm';
import { prettyName } from '~/utils';

type PresetWithUI = Preset & { raw?: boolean; toggle_description?: boolean };

const presetsStore = usePresets();
const config = useConfigStore();
const box = useConfirm();
const editor = usePresetEditor();
const { confirmDialog } = useDialog();
const { toggleExpand, expandClass } = useExpandableMeta();

const display_style = useStorage<string>('preset_display_style', 'grid');
const isMobile = useMediaQuery({ maxWidth: 1024 });

const query = ref('');
const showFilter = ref(false);
const filterInput = ref<HTMLInputElement | null>(null);
const selectedIds = ref<number[]>([]);
const massDelete = ref(false);

const presets = computed(() => presetsStore.presets.value as PresetWithUI[]);
const isLoading = presetsStore.isLoading;

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

const selectablePresetIds = computed(() =>
  filteredPresets.value.map((item) => item.id).filter((id): id is number => typeof id === 'number'),
);

const allSelected = computed(
  () =>
    selectablePresetIds.value.length > 0 &&
    selectablePresetIds.value.every((id) => selectedIds.value.includes(id)),
);

const hasSelected = computed(() => selectedIds.value.length > 0);

const bulkActionGroups = computed<DropdownMenuItem[][]>(() => [
  [
    {
      label: 'Remove Selected',
      icon: 'i-lucide-trash',
      color: 'error',
      disabled: !hasSelected.value || massDelete.value,
      onSelect: () => void deleteSelected(),
    },
  ],
]);

watch(showFilter, (value) => {
  if (!value) {
    query.value = '';
  }
});

watch(
  filteredPresets,
  (items) => {
    const validIds = new Set(
      items.map((item) => item.id).filter((id): id is number => typeof id === 'number'),
    );
    selectedIds.value = selectedIds.value.filter((id) => validIds.has(id));
  },
  { deep: true },
);

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

const toggleMasterSelection = (): void => {
  if (allSelected.value) {
    selectedIds.value = [];
    return;
  }

  selectedIds.value = [...selectablePresetIds.value];
};

const deleteSelected = async (): Promise<void> => {
  if (selectedIds.value.length < 1) {
    return;
  }

  const { status } = await confirmDialog({
    title: 'Delete Selected Presets',
    rawHTML:
      `Delete <strong class="text-red-500">${selectedIds.value.length}</strong> preset/s?<ul>` +
      selectedIds.value
        .map((id) => {
          const item = filteredPresets.value.find((preset) => preset.id === id);
          return item ? `<li>${item.id}: ${prettyName(item.name)}</li>` : '';
        })
        .join('') +
      '</ul>',
    confirmText: 'Delete',
    confirmColor: 'error',
  });

  if (true !== status) {
    return;
  }

  const itemsToDelete = filteredPresets.value.filter(
    (item) => item.id && selectedIds.value.includes(item.id),
  );
  if (itemsToDelete.length < 1) {
    return;
  }

  massDelete.value = true;

  for (const item of itemsToDelete) {
    if (!item.id) {
      continue;
    }
    await presetsStore.deletePreset(item.id);
  }

  selectedIds.value = [];
  massDelete.value = false;
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
