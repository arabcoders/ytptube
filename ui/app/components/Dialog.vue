<template>
  <UModal
    v-if="state.current"
    :open="true"
    :title="state.current?.opts.title ?? defaultTitle"
    :dismissible="true"
    :ui="{ content: 'max-w-lg', body: 'space-y-4', footer: 'justify-end gap-2' }"
    @update:open="(open) => !open && onCancel()"
    @after:enter="focusInput"
  >
    <template #body>
      <p v-if="state.current?.opts.message" class="whitespace-pre-line wrap-break-word">
        {{ state.current?.opts.message }}
      </p>

      <UFormField v-if="'prompt' === state.current?.type" :error="state.errorMsg || undefined">
        <UInput
          ref="inputEl"
          v-model="localInput"
          :placeholder="(state.current?.opts as PromptOptions)?.placeholder ?? ''"
          class="w-full"
          @keydown.enter.stop.prevent="onEnter"
        />
      </UFormField>

      <div
        v-if="
          'confirm' === state.current?.type &&
          (state.current?.opts as ConfirmOptions)?.options?.length
        "
        class="space-y-3 border-t border-default pt-4"
      >
        <UCheckbox
          v-for="opt in (state.current?.opts as ConfirmOptions).options"
          :key="opt.key"
          v-model="selected[opt.key]"
          :label="opt.label"
        />
      </div>
    </template>

    <template #footer>
      <template v-if="'alert' === state.current?.type">
        <UButton
          id="primaryButton"
          :color="state.current?.opts.confirmColor ?? 'primary'"
          @click="onEnter"
        >
          {{ state.current?.opts.confirmText ?? 'OK' }}
        </UButton>
      </template>

      <template v-else-if="'confirm' === state.current?.type || 'prompt' === state.current?.type">
        <UButton
          id="primaryButton"
          :color="state.current?.opts.confirmColor ?? 'primary'"
          :disabled="
            'prompt' === state.current?.type &&
            localInput === (state.current?.opts as PromptOptions)?.initial
          "
          @click="onEnter"
        >
          {{ state.current?.opts.confirmText ?? 'OK' }}
        </UButton>

        <UButton color="neutral" variant="outline" @click="onCancel">
          {{ (state.current?.opts as PromptOptions | ConfirmOptions)?.cancelText ?? 'Cancel' }}
        </UButton>
      </template>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, computed } from 'vue';
import { UButton, UCheckbox, UInput } from '#components';
import { disableOpacity, enableOpacity } from '~/utils';
import { useDialog, type ConfirmOptions, type PromptOptions } from '~/composables/useDialog';

const { state, confirm, cancel } = useDialog();

const localInput = ref('');
const selected = ref<Record<string, boolean>>({});

watch(
  () => state.current,
  (cur) => {
    if (state.current) {
      disableOpacity();
    } else {
      enableOpacity();
    }

    localInput.value = 'prompt' === cur?.type ? ((cur.opts as PromptOptions).initial ?? '') : '';

    if ('confirm' === cur?.type) {
      selected.value = Object.fromEntries(
        ((cur.opts as ConfirmOptions).options ?? []).map((opt) => [opt.key, Boolean(opt.checked)]),
      );
      return;
    }

    selected.value = {};
  },
  { immediate: true },
);

const inputEl = ref<{ inputRef?: { value?: HTMLInputElement | null } } | null>(null);

const focusPrimary = () => {
  const root = document.getElementById('primaryButton');
  root?.focus();
};

const focusInput = async () => {
  await nextTick();
  if ('prompt' === state.current?.type) {
    requestAnimationFrame(() => inputEl.value?.inputRef?.value?.focus?.({ preventScroll: true }));
    return;
  }
  requestAnimationFrame(focusPrimary);
};

const onCancel = () => cancel();
const onEnter = () =>
  confirm('confirm' === state.current?.type ? selected.value : localInput.value);

const defaultTitle = computed(() => {
  if (!state.current) {
    return '';
  }
  switch (state.current.type) {
    case 'alert':
      return 'Alert';
    case 'confirm':
      return 'Confirm';
    case 'prompt':
      return 'Input required';
    default:
      return 'Dialog';
  }
});
</script>
