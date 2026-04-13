<template>
  <div class="relative w-full">
    <UInput
      :id="id"
      ref="inputRef"
      v-model="model"
      :placeholder="placeholder"
      autocomplete="new-password"
      :disabled="disabled"
      :icon="icon"
      size="lg"
      variant="outline"
      color="neutral"
      class="w-full"
      :ui="{ root: 'w-full', base: 'w-full bg-default/90', leadingIcon: iconClass }"
      @focus="onFocus"
      @blur="hideList"
      @input="onInput"
      @keydown="handleKeydown"
      @keyup="updateCaretFromInput"
      @click="updateCaretFromInput"
      @mouseup="updateCaretFromInput"
    />

    <div
      v-if="showList && filteredOptions.length"
      ref="dropdownRef"
      class="absolute inset-x-0 top-full z-20 mt-1 max-h-40 overflow-y-auto rounded-md border border-default bg-default shadow-lg"
      role="menu"
    >
      <button
        v-for="(option, idx) in filteredOptions"
        :key="option.value"
        type="button"
        class="flex w-full items-start justify-between gap-4 px-3 py-2 text-left text-sm transition-colors"
        :class="
          idx === highlightedIndex
            ? 'bg-elevated text-highlighted'
            : 'text-default hover:bg-elevated/60'
        "
        @mousedown.prevent="selectOption(option.value)"
        :ref="(el) => setDropdownItemRef(el, idx)"
      >
        <span class="shrink-0 font-semibold text-highlighted">{{ option.value }}</span>
        <abbr
          class="min-w-0 flex-1 truncate text-xs text-toned no-underline"
          :title="option.description"
        >
          {{ option.description }}
        </abbr>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed, nextTick, toRefs } from 'vue';
import type { ComponentPublicInstance } from 'vue';
import type { AutoCompleteOptions } from '~/types/autocomplete';

const props = withDefaults(
  defineProps<{
    options: AutoCompleteOptions;
    placeholder?: string;
    disabled?: boolean;
    id?: string;
    icon?: string;
    iconClass?: string;
    multiple?: boolean;
    openOnFocus?: boolean;
    allowShortFlags?: boolean;
  }>(),
  {
    placeholder: '',
    disabled: false,
    id: '',
    icon: undefined,
    iconClass: '',
    multiple: true,
    openOnFocus: false,
    allowShortFlags: false,
  },
);

const { placeholder, disabled, id, icon, iconClass, multiple, openOnFocus, allowShortFlags } =
  toRefs(props);

const model = defineModel<string>();

const showList = ref(false);
const highlightedIndex = ref(-1);
const dropdownItemRefs = ref<(HTMLElement | null)[]>([]);
const dropdownRef = ref<HTMLElement | null>(null);
const inputRef = ref<{
  inputRef?: { value?: HTMLInputElement | null };
  $el?: Element | null;
} | null>(null);
const caretIndex = ref(0);

const getNativeInput = () => {
  const direct = inputRef.value?.inputRef?.value;
  if (direct) {
    return direct;
  }
  const fallback = inputRef.value?.$el?.querySelector('input');
  return fallback instanceof HTMLInputElement ? fallback : null;
};

const getCurrentToken = (value: string) => {
  if (!multiple.value) {
    return {
      token: value,
      start: 0,
      end: value.length,
    };
  }

  const caret = Math.min(caretIndex.value, value.length);
  const left = value.slice(0, caret);
  const right = value.slice(caret);
  const leftMatch = left.match(/(\S+)$/);
  const rightMatch = right.match(/^(\S+)/);
  const leftToken = leftMatch?.[1] ?? '';
  const rightToken = rightMatch?.[1] ?? '';
  const token = leftToken + rightToken;
  const start = leftMatch ? caret - leftToken.length : caret;
  const end = rightMatch ? caret + rightToken.length : caret;
  return { token, start, end };
};

const updateCaretFromInput = () => {
  const input = getNativeInput();
  caretIndex.value = input?.selectionStart ?? (model.value || '').length;
};

const filteredOptions = computed(() => {
  const value = model.value || '';
  if (!value) {
    return props.options;
  }

  const { token } = getCurrentToken(value);
  if (openOnFocus.value && !token) {
    return props.options;
  }
  if (!token || token.includes('=')) {
    return [];
  }

  const isLongFlag = token.startsWith('--');
  const isShortFlag = allowShortFlags.value && token.startsWith('-') && !token.startsWith('--');
  if (!isLongFlag && !isShortFlag) {
    return [];
  }

  const exactMatch = props.options.find((opt) => opt.value === token);
  if (exactMatch) {
    return [exactMatch];
  }

  const startsWithFlag = [];
  const includesFlag = [];
  const includesDesc = [];

  for (const opt of props.options) {
    const flag = opt.value;
    const desc = opt.description.toLowerCase();

    if (isShortFlag) {
      if (flag === token) {
        startsWithFlag.push(opt);
      } else if (flag.includes(token)) {
        includesFlag.push(opt);
      } else if (desc.includes(token.toLowerCase())) {
        includesDesc.push(opt);
      }
      continue;
    }

    const normalizedToken = token.toLowerCase();
    const flagLower = flag.toLowerCase();
    if (flagLower.startsWith(normalizedToken)) {
      startsWithFlag.push(opt);
    } else if (flagLower.includes(normalizedToken)) {
      includesFlag.push(opt);
    } else if (desc.includes(normalizedToken)) {
      includesDesc.push(opt);
    }
  }

  return [...startsWithFlag, ...includesFlag, ...includesDesc];
});

const isFlagTrigger = computed(() => {
  const { token } = getCurrentToken(model.value || '');
  if (openOnFocus.value && !token) {
    return true;
  }
  if (!token || token.includes('=')) {
    return false;
  }

  const isLongFlag = token.startsWith('--');
  const isShortFlag = allowShortFlags.value && token.startsWith('-') && !token.startsWith('--');
  return isLongFlag || isShortFlag;
});

const onInput = () => {
  updateCaretFromInput();
  showList.value = isFlagTrigger.value && filteredOptions.value.length > 0;
  highlightedIndex.value = showList.value ? 0 : -1;
};

const selectOption = (val: string) => {
  const value = model.value || '';
  const { token, start, end } = getCurrentToken(value);

  if (!multiple.value) {
    const eqPos = token.indexOf('=');
    const after = eqPos !== -1 ? token.slice(eqPos) : '';
    model.value = val + after;
    showList.value = false;
    highlightedIndex.value = -1;
    nextTick(() => getNativeInput()?.focus());
    return;
  }

  if (token) {
    const eqPos = token.indexOf('=');
    const after = eqPos !== -1 ? token.slice(eqPos) : '';
    model.value = value.slice(0, start) + val + after + value.slice(end);
    nextTick(() => {
      const input = getNativeInput();
      const nextPos = start + val.length + after.length;
      input?.focus();
      input?.setSelectionRange(nextPos, nextPos);
      caretIndex.value = nextPos;
    });
  } else {
    model.value = val;
    nextTick(() => {
      const input = getNativeInput();
      input?.focus();
      input?.setSelectionRange(val.length, val.length);
      caretIndex.value = val.length;
    });
  }

  showList.value = false;
  highlightedIndex.value = -1;
};

const hideList = () => {
  setTimeout(() => {
    showList.value = false;
    highlightedIndex.value = -1;
    dropdownItemRefs.value = [];
  }, 100);
};

const onFocus = () => {
  updateCaretFromInput();
  if (!openOnFocus.value) {
    return;
  }
  const hasOptions = filteredOptions.value.length > 0;
  showList.value = hasOptions;
  highlightedIndex.value = hasOptions ? 0 : -1;
};

const setDropdownItemRef = (el: Element | ComponentPublicInstance | null, idx: number) => {
  dropdownItemRefs.value[idx] = el instanceof HTMLElement ? el : null;
};

watch(filteredOptions, () => {
  highlightedIndex.value = filteredOptions.value.length ? 0 : -1;
  dropdownItemRefs.value = Array(filteredOptions.value.length).fill(null);
  nextTick(() => {
    if (dropdownRef.value) {
      dropdownRef.value.scrollTop = 0;
    }
  });
});

const scrollHighlightedIntoView = () => {
  const el = dropdownItemRefs.value[highlightedIndex.value];
  if (!el) {
    return;
  }
  el.scrollIntoView({ block: 'nearest' });
};

const handleKeydown = (e: KeyboardEvent) => {
  updateCaretFromInput();

  if (e.key === 'Escape') {
    showList.value = false;
    highlightedIndex.value = -1;
    return;
  }
  if (!showList.value || !filteredOptions.value.length) {
    return;
  }

  const pageSize = 5;

  if (e.key === 'ArrowDown') {
    e.preventDefault();
    highlightedIndex.value = Math.min(highlightedIndex.value + 1, filteredOptions.value.length - 1);
    nextTick(scrollHighlightedIntoView);
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    highlightedIndex.value = Math.max(highlightedIndex.value - 1, 0);
    nextTick(scrollHighlightedIntoView);
  } else if (e.key === 'PageDown') {
    e.preventDefault();
    highlightedIndex.value = Math.min(
      highlightedIndex.value + pageSize,
      filteredOptions.value.length - 1,
    );
    nextTick(scrollHighlightedIntoView);
  } else if (e.key === 'PageUp') {
    e.preventDefault();
    highlightedIndex.value = Math.max(highlightedIndex.value - pageSize, 0);
    nextTick(scrollHighlightedIntoView);
  } else if (e.key === 'Enter' || e.key === 'Tab') {
    const selected =
      highlightedIndex.value >= 0 && highlightedIndex.value < filteredOptions.value.length
        ? filteredOptions.value[highlightedIndex.value]
        : undefined;
    if (selected && isFlagTrigger.value) {
      e.preventDefault();
      selectOption(selected.value);
    }
  }
};
</script>
