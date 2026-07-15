<template>
  <div class="relative w-full">
    <UInput
      :id="id"
      ref="inputRef"
      v-model="search"
      dir="ltr"
      autocomplete="new-password"
      :disabled="disabled"
      :placeholder="placeholder"
      icon="i-lucide-search"
      size="lg"
      variant="outline"
      color="neutral"
      class="w-full"
      :ui="{ root: 'w-full', base: 'w-full bg-elevated/60' }"
      @focus="onFocus"
      @blur="hideList"
      @keydown="handleKeydown"
    />

    <Teleport to="body">
      <div
        v-if="showList && filteredOptions.length"
        ref="dropdownRef"
        class="fixed z-50 overflow-y-auto rounded-md ytp-floating-surface"
        :style="dropdownStyle"
        dir="ltr"
        role="menu"
      >
        <button
          v-for="(option, idx) in filteredOptions"
          :key="option.value"
          type="button"
          class="flex w-full items-start justify-between gap-4 px-3 py-2 text-start text-sm transition-colors"
          :class="
            idx === highlightedIndex
              ? 'bg-elevated text-highlighted'
              : 'text-default hover:bg-elevated/60'
          "
          @mousedown.prevent="selectOption(option.value)"
          :ref="(el) => setDropdownItemRef(el, idx)"
        >
          <span class="flex min-w-0 shrink-0 items-center gap-2 font-semibold text-highlighted">
            <UIcon :name="option.value" class="size-4 shrink-0 text-toned" />
            <span class="truncate">{{ option.value }}</span>
          </span>
          <abbr
            class="min-w-0 flex-1 truncate text-xs text-toned no-underline"
            :title="option.description"
          >
            {{ option.description }}
          </abbr>
        </button>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import type { ComponentPublicInstance } from 'vue';
import type { AutoCompleteOptions, Option } from '~/types/autocomplete';

const props = withDefaults(
  defineProps<{
    options: AutoCompleteOptions;
    id?: string;
    placeholder?: string;
    disabled?: boolean;
    preferUp?: boolean;
  }>(),
  {
    id: '',
    placeholder: '',
    disabled: false,
    preferUp: false,
  },
);

type ClipRect = {
  top: number;
  right: number;
  bottom: number;
  left: number;
};

const model = defineModel<string>();
const search = ref(model.value ?? '');
const showList = ref(false);
const focused = ref(false);
const placement = ref<'down' | 'up'>('down');
const maxHeight = ref(160);
const dropdownTop = ref(0);
const dropdownLeft = ref(0);
const dropdownWidth = ref(0);
const highlightedIndex = ref(-1);
const dropdownItemRefs = ref<(HTMLElement | null)[]>([]);
const dropdownRef = ref<HTMLElement | null>(null);
const inputRef = ref<{
  inputRef?: { value?: HTMLInputElement | null };
  $el?: Element | null;
} | null>(null);

const normalize = (value: string): string =>
  value
    .trim()
    .toLowerCase()
    .replace(/^i-lucide-/, '')
    .replace(/^lucide:/, '');

const getNativeInput = () => {
  const direct = inputRef.value?.inputRef?.value;
  if (direct) {
    return direct;
  }

  const fallback = inputRef.value?.$el?.querySelector('input');
  return fallback instanceof HTMLInputElement ? fallback : null;
};

const intersect = (left: ClipRect, right: ClipRect): ClipRect => ({
  top: Math.max(left.top, right.top),
  right: Math.min(left.right, right.right),
  bottom: Math.min(left.bottom, right.bottom),
  left: Math.max(left.left, right.left),
});

const getClipRect = (element: HTMLElement): ClipRect => {
  let clip: ClipRect = {
    top: 0,
    right: window.innerWidth,
    bottom: window.innerHeight,
    left: 0,
  };
  let parent = element.parentElement;

  while (parent && parent !== document.documentElement) {
    const style = window.getComputedStyle(parent);
    const overflow = `${style.overflow} ${style.overflowY}`;

    if (/(auto|scroll|hidden|clip)/.test(overflow)) {
      const rect = parent.getBoundingClientRect();
      clip = intersect(clip, {
        top: rect.top,
        right: rect.right,
        bottom: rect.bottom,
        left: rect.left,
      });
    }

    parent = parent.parentElement;
  }

  return clip;
};

const estimatedHeight = (): number => {
  const rowHeight = 37;
  return Math.min(160, Math.max(37, filteredOptions.value.length * rowHeight + 2));
};

const dropdownStyle = computed(() => ({
  top: `${dropdownTop.value}px`,
  left: `${dropdownLeft.value}px`,
  width: `${dropdownWidth.value}px`,
  maxHeight: `${maxHeight.value}px`,
}));

const updatePlacement = () => {
  const input = getNativeInput();

  if (!input || typeof window === 'undefined') {
    placement.value = 'down';
    maxHeight.value = 160;
    return;
  }

  const rect = input.getBoundingClientRect();
  const clip = getClipRect(input);
  const gap = 8;
  const wanted = estimatedHeight();
  const below = Math.max(0, clip.bottom - rect.bottom - gap);
  const above = Math.max(0, rect.top - clip.top - gap);
  const openUp = props.preferUp || (below < 160 && above > below);
  const available = openUp ? above : below;
  const height = Math.max(37, Math.min(wanted, available || wanted));

  placement.value = openUp ? 'up' : 'down';
  maxHeight.value = height;
  dropdownLeft.value = rect.left;
  dropdownWidth.value = rect.width;
  dropdownTop.value = openUp
    ? Math.max(clip.top + gap, rect.top - gap - height)
    : rect.bottom + gap;
};

const filteredOptions = computed<Option[]>(() => {
  const token = normalize(search.value);

  if (!token) {
    return props.options;
  }

  const exact = props.options.find((option) => option.value === search.value);
  if (exact) {
    return [exact];
  }

  const startsWith: Option[] = [];
  const includes: Option[] = [];
  const desc: Option[] = [];

  for (const option of props.options) {
    const value = normalize(option.value);
    const description = option.description.toLowerCase();

    if (value.startsWith(token)) {
      startsWith.push(option);
    } else if (value.includes(token)) {
      includes.push(option);
    } else if (description.includes(token)) {
      desc.push(option);
    }
  }

  return [...startsWith, ...includes, ...desc];
});

const updateList = () => {
  showList.value = focused.value && filteredOptions.value.length > 0;
  highlightedIndex.value = showList.value ? 0 : -1;

  if (showList.value) {
    updatePlacement();
  }
};

const updateWhileOpen = () => {
  if (showList.value) {
    updatePlacement();
  }
};

const onFocus = () => {
  focused.value = true;
  updateList();
  window.addEventListener('scroll', updateWhileOpen, true);
  window.addEventListener('resize', updateWhileOpen);
};

const hideList = () => {
  setTimeout(() => {
    focused.value = false;
    showList.value = false;
    highlightedIndex.value = -1;
    dropdownItemRefs.value = [];
    window.removeEventListener('scroll', updateWhileOpen, true);
    window.removeEventListener('resize', updateWhileOpen);
  }, 100);
};

onBeforeUnmount(() => {
  window.removeEventListener('scroll', updateWhileOpen, true);
  window.removeEventListener('resize', updateWhileOpen);
});

const selectOption = (value: string) => {
  search.value = value;
  model.value = value;
  showList.value = false;
  highlightedIndex.value = -1;

  nextTick(() => getNativeInput()?.focus());
};

const setDropdownItemRef = (el: Element | ComponentPublicInstance | null, idx: number) => {
  dropdownItemRefs.value[idx] = el instanceof HTMLElement ? el : null;
};

const scrollHighlightedIntoView = () => {
  const el = dropdownItemRefs.value[highlightedIndex.value];
  if (!el) {
    return;
  }

  el.scrollIntoView({ block: 'nearest' });
};

const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape') {
    showList.value = false;
    highlightedIndex.value = -1;
    return;
  }

  if (!showList.value || filteredOptions.value.length < 1) {
    return;
  }

  if (event.key === 'ArrowDown') {
    event.preventDefault();
    highlightedIndex.value = Math.min(highlightedIndex.value + 1, filteredOptions.value.length - 1);
    nextTick(scrollHighlightedIntoView);
  } else if (event.key === 'ArrowUp') {
    event.preventDefault();
    highlightedIndex.value = Math.max(highlightedIndex.value - 1, 0);
    nextTick(scrollHighlightedIntoView);
  } else if (event.key === 'Enter' || event.key === 'Tab') {
    const option = filteredOptions.value[highlightedIndex.value];

    if (option) {
      event.preventDefault();
      selectOption(option.value);
    }
  }
};

watch(model, (value) => {
  if ((value ?? '') !== search.value) {
    search.value = value ?? '';
  }
});

watch(search, (value) => {
  if ((model.value ?? '') !== value) {
    model.value = value;
  }

  nextTick(updateList);
});

watch(filteredOptions, () => {
  highlightedIndex.value = filteredOptions.value.length ? 0 : -1;
  dropdownItemRefs.value = Array(filteredOptions.value.length).fill(null);

  nextTick(() => {
    if (showList.value) {
      updatePlacement();
    }

    if (dropdownRef.value) {
      dropdownRef.value.scrollTop = 0;
    }
  });
});
</script>
