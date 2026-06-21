<template>
  <div class="relative w-full">
    <UInput
      :id="id"
      ref="inputRef"
      v-model="model"
      type="text"
      :placeholder="placeholder"
      :disabled="disabled"
      :size="size"
      autocomplete="off"
      class="w-full"
      :ui="ui"
      @focus="onFocus"
      @blur="onBlur"
      @input="onInput"
      @keydown="onKeydown"
    />

    <div
      v-if="open && suggestions.length"
      ref="dropdownRef"
      class="absolute inset-x-0 top-full z-20 mt-1 max-h-40 overflow-y-auto rounded-md ytp-floating-surface"
      role="listbox"
    >
      <button
        v-for="(item, idx) in suggestions"
        :key="item"
        type="button"
        class="flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors"
        :class="
          idx === highlighted ? 'bg-elevated text-highlighted' : 'text-default hover:bg-elevated/60'
        "
        role="option"
        :aria-selected="idx === highlighted"
        @mousedown.prevent="select(item)"
      >
        <UIcon name="i-lucide-folder" class="size-3.5 shrink-0 text-toned" />
        <span>{{ item }}</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick } from 'vue';
import { useFolderSuggestions } from '~/composables/useFolderSuggestions';

withDefaults(
  defineProps<{
    id?: string;
    placeholder?: string;
    disabled?: boolean;
    size?: 'sm' | 'md' | 'lg' | 'xl';
    ui?: Record<string, any>;
  }>(),
  {
    id: undefined,
    placeholder: '/',
    disabled: false,
    size: 'lg',
    ui: undefined,
  },
);

const model = defineModel<string>({ default: '' });
const { fetchFolders } = useFolderSuggestions();

const open = ref(false);
const highlighted = ref(-1);
const children = ref<string[]>([]);
const dropdownRef = ref<HTMLElement | null>(null);
const inputRef = ref<any>(null);
let debounceTimer: ReturnType<typeof setTimeout> | null = null;
let selecting = false;

const parentPath = computed(() => {
  const val = model.value || '';
  const lastSlash = val.lastIndexOf('/');
  return lastSlash === -1 ? '' : val.slice(0, lastSlash);
});

const suffix = computed(() => {
  const val = model.value || '';
  const lastSlash = val.lastIndexOf('/');
  return lastSlash === -1 ? val : val.slice(lastSlash + 1);
});

const suggestions = computed(() => {
  const s = suffix.value.toLowerCase();
  if (!s) return children.value;
  return children.value.filter((c) => c.toLowerCase().startsWith(s));
});

const loadChildren = async (path: string) => {
  children.value = await fetchFolders(path);
  highlighted.value = children.value.length ? 0 : -1;
};

const scheduleLoad = () => {
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => loadChildren(parentPath.value), 200);
};

const onFocus = () => {
  open.value = true;
  loadChildren(parentPath.value);
};

const onBlur = () => {
  setTimeout(() => {
    if (selecting) return;
    open.value = false;
    highlighted.value = -1;
  }, 120);
};

const onInput = () => {
  open.value = true;
  scheduleLoad();
};

const select = async (name: string) => {
  selecting = true;
  const parent = parentPath.value;
  const newPath = parent ? `${parent}/${name}` : name;
  model.value = newPath + '/';
  highlighted.value = -1;
  await loadChildren(newPath);
  open.value = true;
  selecting = false;
  nextTick(() => {
    const el = inputRef.value?.$el?.querySelector('input') ?? inputRef.value?.inputRef?.value;
    el?.focus();
  });
};

const onKeydown = (e: KeyboardEvent) => {
  if (!open.value || !suggestions.value.length) {
    return;
  }

  if (e.key === 'ArrowDown') {
    e.preventDefault();
    highlighted.value = Math.min(highlighted.value + 1, suggestions.value.length - 1);
    scrollIntoView();
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    highlighted.value = Math.max(highlighted.value - 1, 0);
    scrollIntoView();
  } else if (e.key === 'Enter' || e.key === 'Tab') {
    const item = suggestions.value[highlighted.value];
    if (highlighted.value >= 0 && item) {
      e.preventDefault();
      select(item);
    }
  } else if (e.key === 'Escape') {
    open.value = false;
    highlighted.value = -1;
  }
};

const scrollIntoView = () => {
  nextTick(() => {
    const el = dropdownRef.value?.children[highlighted.value] as HTMLElement | undefined;
    el?.scrollIntoView({ block: 'nearest' });
  });
};
</script>
