<template>
  <div class="relative flex h-full w-full flex-col">
    <UTextarea
      :id="id"
      ref="textareaRef"
      v-model="localValue"
      :placeholder="placeholder"
      autocomplete="off"
      :rows="rows ?? 4"
      :disabled="disabled"
      size="lg"
      variant="outline"
      color="neutral"
      class="h-full w-full"
      :ui="{
        root: 'w-full',
        base: 'min-h-[10rem] w-full bg-elevated/60 font-mono text-sm ring-default focus-visible:ring-primary',
      }"
      @input="onInput"
      @focus="onFocus"
      @blur="hideList"
      @keydown="onKeydown"
      @keyup="updateCaret"
      @click="updateCaret"
      @mouseup="updateCaret"
    />

    <UIcon
      v-if="icon"
      :name="icon"
      class="pointer-events-none absolute top-3 right-3 z-10 size-4 text-toned"
      :class="iconClass"
    />

    <div
      v-if="showList && filteredOptions.length"
      class="absolute inset-x-0 top-full z-20 mt-1 overflow-hidden rounded-md border border-default bg-default shadow-lg"
      role="menu"
    >
      <button
        v-for="(option, idx) in filteredOptions"
        :key="option.value"
        ref="dropdownItems"
        data-autocomplete-item
        type="button"
        class="flex w-full items-start justify-between gap-4 px-3 py-2 text-left text-sm transition-colors"
        :class="
          idx === highlightedIndex
            ? 'bg-elevated text-highlighted'
            : 'text-default hover:bg-elevated/60'
        "
        @mousedown.prevent="appendFlag(option.value)"
      >
        <span class="shrink-0 font-semibold text-highlighted">{{ option.value }}</span>
        <span class="min-w-0 flex-1 truncate text-xs text-toned">{{ option.description }}</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue';
import type { AutoCompleteOptions } from '~/types/autocomplete';

const props = withDefaults(
  defineProps<{
    options: AutoCompleteOptions;
    placeholder?: string;
    disabled?: boolean;
    id?: string;
    rows?: number;
    icon?: string;
    iconClass?: string;
  }>(),
  {
    placeholder: '',
    disabled: false,
    id: '',
    rows: 4,
    icon: undefined,
    iconClass: '',
  },
);

const model = defineModel<string>();
const localValue = ref(model.value || '');
const textareaRef = ref<{ textareaRef?: HTMLTextAreaElement | null } | null>(null);
const caretIndex = ref(0);
const showList = ref(false);
const highlightedIndex = ref(-1);
const dropdownItems = ref<HTMLElement[]>([]);

watch(model, (val) => (localValue.value = val || ''));
watch(localValue, (val) => (model.value = val));

const getCurrentToken = (value: string, caret: number) => {
  const left = value.slice(0, caret);
  const right = value.slice(caret);
  const leftMatch = left.match(/(\S+)$/);
  const rightMatch = right.match(/^(\S+)/);
  const leftToken: string = (leftMatch?.[1] ?? '') as string;
  const rightToken: string = (rightMatch?.[1] ?? '') as string;
  const token = leftToken + rightToken;
  const start = leftMatch ? caret - leftToken.length : caret;
  const end = rightMatch ? caret + rightToken.length : caret;
  return { token, start, end };
};

const filteredOptions = computed(() => {
  const { token } = getCurrentToken(localValue.value, caretIndex.value);
  if (!token || token.includes('=')) {
    return [];
  }
  if (!token.startsWith('--')) {
    return [];
  }
  if (props.options.some((opt) => opt.value === token)) {
    return [];
  }
  const val = token.toLowerCase();
  const startsWithFlag = [];
  const includesFlag = [];
  const includesDesc = [];
  for (const opt of props.options) {
    const flag = opt.value.toLowerCase();
    const desc = opt.description.toLowerCase();
    if (flag.startsWith(val)) {
      startsWithFlag.push(opt);
    } else if (flag.includes(val)) {
      includesFlag.push(opt);
    } else if (desc.includes(val)) {
      includesDesc.push(opt);
    }
  }
  return [...startsWithFlag, ...includesFlag, ...includesDesc];
});

const appendFlag = (flag: string) => {
  const value = localValue.value;
  const caret = caretIndex.value;
  const { token, start, end } = getCurrentToken(value, caret);
  if (token) {
    const eqPos = token.indexOf('=');
    const after = eqPos !== -1 ? token.slice(eqPos) : '';
    localValue.value = value.slice(0, start) + flag + after + value.slice(end);
    nextTick(() => {
      const pos = start + flag.length + after.length;
      if (textareaRef.value?.textareaRef) {
        textareaRef.value.textareaRef.selectionStart = textareaRef.value.textareaRef.selectionEnd =
          pos;
        caretIndex.value = pos;
      }
    });
  } else {
    const needsSpace = caret > 0 && value[caret - 1] !== ' ';
    localValue.value = value.slice(0, caret) + (needsSpace ? ' ' : '') + flag + value.slice(caret);
    nextTick(() => {
      const pos = caret + (needsSpace ? 1 : 0) + flag.length;
      if (textareaRef.value?.textareaRef) {
        textareaRef.value.textareaRef.selectionStart = textareaRef.value.textareaRef.selectionEnd =
          pos;
        caretIndex.value = pos;
      }
    });
  }
  showList.value = false;
  highlightedIndex.value = -1;
};

const updateCaret = () => {
  caretIndex.value = textareaRef.value?.textareaRef
    ? (textareaRef.value.textareaRef.selectionStart ?? localValue.value.length)
    : localValue.value.length;
};

const onFocus = () => {
  updateCaret();
  showList.value = true;
};

const onInput = () => {
  updateCaret();
  const { token } = getCurrentToken(localValue.value, caretIndex.value);
  const hasEqual = token.includes('=');
  const isFlagTrigger = token.startsWith('--') && !hasEqual;
  showList.value = isFlagTrigger && filteredOptions.value.length > 0;
  highlightedIndex.value = showList.value ? 0 : -1;
};

watch(filteredOptions, () => {
  highlightedIndex.value = filteredOptions.value.length > 0 && showList.value ? 0 : -1;
  nextTick(() => {
    dropdownItems.value = Array.from(
      document.querySelectorAll('[data-autocomplete-item]'),
    ) as HTMLElement[];
  });
});

const hideList = () =>
  setTimeout(() => {
    showList.value = false;
    highlightedIndex.value = -1;
  }, 100);

const onKeydown = (e: KeyboardEvent) => {
  updateCaret();
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
    nextTick(() =>
      dropdownItems.value[highlightedIndex.value]?.scrollIntoView({ block: 'nearest' }),
    );
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    highlightedIndex.value = Math.max(highlightedIndex.value - 1, 0);
    nextTick(() =>
      dropdownItems.value[highlightedIndex.value]?.scrollIntoView({ block: 'nearest' }),
    );
  } else if (e.key === 'PageDown') {
    e.preventDefault();
    highlightedIndex.value = Math.min(
      highlightedIndex.value + pageSize,
      filteredOptions.value.length - 1,
    );
    nextTick(() =>
      dropdownItems.value[highlightedIndex.value]?.scrollIntoView({ block: 'nearest' }),
    );
  } else if (e.key === 'PageUp') {
    e.preventDefault();
    highlightedIndex.value = Math.max(highlightedIndex.value - pageSize, 0);
    nextTick(() =>
      dropdownItems.value[highlightedIndex.value]?.scrollIntoView({ block: 'nearest' }),
    );
  } else if (e.key === 'Enter' || e.key === 'Tab') {
    const { token } = getCurrentToken(localValue.value, caretIndex.value);
    const hasEqual = token.includes('=');
    const isFlagTrigger = token.startsWith('--') && !hasEqual;
    const selected =
      highlightedIndex.value >= 0 && highlightedIndex.value < filteredOptions.value.length
        ? filteredOptions.value[highlightedIndex.value]
        : undefined;
    if (selected && isFlagTrigger) {
      e.preventDefault();
      appendFlag(selected.value);
    }
  }
};
</script>
