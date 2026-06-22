<template>
  <USlideover
    :open="isOpen"
    :side="direction"
    :dismissible="true"
    :overlay="true"
    :ui="{ content: 'yt-settings-panel w-full sm:max-w-xl' }"
    @update:open="(open) => !open && emitter('close')"
  >
    <template #header>
      <div class="flex w-full items-start gap-3">
        <div class="min-w-0 flex-1">
          <p class="text-base font-semibold text-highlighted">WebUI Settings</p>
          <p class="text-sm text-toned">Adjust interface behavior.</p>
        </div>

        <UButton
          color="neutral"
          variant="ghost"
          size="sm"
          square
          icon="i-lucide-x"
          aria-label="Close settings"
          title="Close settings"
          class="ml-auto shrink-0"
          @click="emitter('close')"
        />
      </div>
    </template>

    <template #body>
      <div class="w-full space-y-6">
        <div class="ytp-card w-full">
          <div class="p-4 sm:p-5 ytp-border-bottom-soft">
            <div class="flex items-center gap-2">
              <UIcon name="i-lucide-layout-dashboard" class="size-4 text-toned" />
              <span class="text-sm font-semibold text-highlighted">Page View</span>
            </div>
          </div>

          <div class="p-4 sm:p-5 space-y-4">
            <UFormField label="" class="w-full" :ui="settingsFieldUi">
              <USelect
                v-model="draftMode"
                :items="modeItems"
                value-key="value"
                label-key="label"
                size="lg"
                class="w-full"
                :ui="{ base: 'w-full' }"
              />

              <div class="mt-3 flex justify-end">
                <UButton
                  color="primary"
                  variant="soft"
                  size="sm"
                  icon="i-lucide-save"
                  :disabled="!modeChanged || savingMode"
                  :loading="savingMode"
                  @click="saveMode"
                >
                  Save layout
                </UButton>
              </div>
            </UFormField>

            <USwitch
              v-model="page_anims"
              class="w-full"
              size="lg"
              :ui="settingsSwitchUi"
              :label="page_anims ? 'Animations On' : 'Animations Off'"
              description="Enable page transition animations."
            />
          </div>
        </div>

        <div class="ytp-card w-full">
          <div class="p-4 sm:p-5 ytp-border-bottom-soft">
            <div class="flex items-center gap-2">
              <UIcon name="i-lucide-image" class="size-4 text-toned" />
              <span class="text-sm font-semibold text-highlighted">Background</span>
            </div>
          </div>

          <div class="p-4 sm:p-5 space-y-4">
            <USwitch
              v-model="bg_enable"
              class="w-full"
              size="lg"
              :ui="settingsSwitchUi"
              :label="bg_enable ? 'Shown' : 'Hidden'"
            />

            <UButton
              v-if="bg_enable"
              color="neutral"
              variant="outline"
              icon="i-lucide-image-up"
              class="w-full justify-center"
              :disabled="isLoading"
              :loading="isLoading"
              @click="$emit('reload_bg')"
            >
              Reload Background
            </UButton>

            <UFormField
              class="w-full"
              v-if="bg_enable"
              label="Background visibility"
              :hint="`${Math.round(bgVisibilityModel * 100)}%`"
            >
              <USlider
                v-model="bgVisibilityModel"
                :min="0"
                :max="0.5"
                :step="0.01"
                size="lg"
                class="w-full"
              />
            </UFormField>
          </div>
        </div>

        <div class="ytp-card w-full">
          <div class="p-4 sm:p-5 ytp-border-bottom-soft">
            <div class="flex items-center gap-2">
              <UIcon name="i-lucide-monitor" class="size-4 text-toned" />
              <span class="text-sm font-semibold text-highlighted">Downloads</span>
            </div>
          </div>

          <div class="p-4 sm:p-5 space-y-4">
            <UFormField v-if="!modeOn" label="URL Separator" class="w-full" :ui="settingsFieldUi">
              <USelect
                v-model="separator"
                :items="separatorItems"
                value-key="value"
                label-key="label"
                size="lg"
                class="w-full"
                :ui="{ base: 'w-full' }"
              />
            </UFormField>

            <USwitch
              v-model="show_thumbnail"
              class="w-full"
              size="lg"
              :ui="settingsSwitchUi"
              :label="show_thumbnail ? 'Show Thumbnails' : 'Hide Thumbnails'"
              description="Show videos thumbnail if available"
            />

            <UFormField
              v-if="show_thumbnail"
              label="Aspect Ratio"
              class="w-full"
              :ui="settingsFieldUi"
            >
              <USelect
                v-model="thumbnail_ratio"
                :items="thumbnailRatioItems"
                value-key="value"
                label-key="label"
                size="lg"
                class="w-full"
                :ui="{ base: 'w-full' }"
              />
            </UFormField>

            <USwitch
              v-model="show_popover"
              class="w-full"
              size="lg"
              :ui="settingsSwitchUi"
              :label="show_popover ? 'Popover On' : 'Popover Off'"
              description="Show additional information over certain elements."
            />
          </div>
        </div>

        <div class="ytp-card w-full">
          <div class="p-4 sm:p-5 ytp-border-bottom-soft">
            <div class="flex items-center gap-2">
              <UIcon name="i-lucide-download" class="size-4 text-toned" />
              <span class="text-sm font-semibold text-highlighted">Queue</span>
            </div>
          </div>

          <div class="p-4 sm:p-5 space-y-4">
            <USwitch
              v-model="queue_auto_refresh"
              class="w-full"
              size="lg"
              :ui="settingsSwitchUi"
              :label="queue_auto_refresh ? 'Auto-refresh Enabled' : 'Auto-refresh Disabled'"
              description="Automatically refresh queue data when WebSocket connection is unavailable."
            />

            <UFormField
              class="w-full"
              v-if="queue_auto_refresh"
              label="Auto-refresh interval"
              :hint="`${queue_auto_refresh_delay / 1000}s`"
              :ui="settingsFieldUi"
            >
              <USlider
                v-model="queueRefreshDelayModel"
                :min="5000"
                :max="60000"
                :step="5000"
                size="lg"
                class="w-full"
              />
              <p class="mt-2 text-sm text-toned">
                How often to refresh the queue (5-60 seconds). Lower values increase server load.
              </p>
            </UFormField>
          </div>
        </div>

        <div class="ytp-card w-full">
          <div class="p-4 sm:p-5 ytp-border-bottom-soft">
            <div class="flex items-center gap-2">
              <UIcon name="i-lucide-bell" class="size-4 text-toned" />
              <span class="text-sm font-semibold text-highlighted">Notifications</span>
            </div>
          </div>

          <div class="p-4 sm:p-5 space-y-4">
            <USwitch
              v-model="allow_toasts"
              class="w-full"
              size="lg"
              :ui="settingsSwitchUi"
              :label="allow_toasts ? 'Shown' : 'Hidden'"
            />

            <UFormField
              v-if="allow_toasts"
              label="Notification target"
              class="w-full"
              :ui="settingsFieldUi"
            >
              <USelect
                v-model="toast_target"
                :items="notificationTargetItems"
                value-key="value"
                label-key="label"
                size="lg"
                class="w-full"
                :ui="{ base: 'w-full' }"
                @update:model-value="() => void onNotificationTargetChange()"
              />
              <p class="mt-2 text-sm text-toned">
                <template v-if="!isSecureContext">
                  Browser notifications require HTTPS connection.
                </template>
                <template v-else>
                  Choose where to display notifications. Browser requires permission.
                </template>
              </p>
            </UFormField>

            <UFormField
              v-if="allow_toasts && toast_target === 'toast'"
              label="Notifications position"
              class="w-full"
              :ui="settingsFieldUi"
            >
              <USelect
                v-model="toast_position"
                :items="toastPositionItems"
                size="lg"
                class="w-full"
                :ui="{ base: 'w-full' }"
              />
            </UFormField>

            <USwitch
              v-if="allow_toasts && toast_target === 'toast'"
              v-model="toast_dismiss_on_click"
              class="w-full"
              size="lg"
              :ui="settingsSwitchUi"
              :label="toast_dismiss_on_click ? 'Dismiss on click' : 'Keep on click'"
            />
          </div>
        </div>
      </div>
    </template>
  </USlideover>
</template>

<script setup lang="ts">
import { watch, onMounted, onBeforeUnmount, ref, computed } from 'vue';
import { useStorage } from '@vueuse/core';
import { useNotification } from '~/composables/useNotification';
import type { notificationTarget, toastPosition } from '~/composables/useNotification';
import { useMode, type Mode } from '~/composables/useMode';

const props = withDefaults(
  defineProps<{
    isOpen?: boolean;
    direction?: 'left' | 'right';
    isLoading?: boolean;
  }>(),
  {
    isOpen: false,
    direction: 'right',
    isLoading: false,
  },
);

const emitter = defineEmits<{ (e: 'close' | 'reload_bg'): void }>();

const notification = useNotification();

const bg_enable = useStorage<boolean>('random_bg', true);
const bg_opacity = useStorage<number>('random_bg_opacity', 0.95);
const allow_toasts = useStorage<boolean>('allow_toasts', true);
const toast_position = useStorage<toastPosition>('toast_position', 'top-right');
const toast_dismiss_on_click = useStorage<boolean>('toast_dismiss_on_click', true);
const toast_target = useStorage<notificationTarget>('toast_target', 'toast');
const show_thumbnail = useStorage<boolean>('show_thumbnail', true);
const show_popover = useStorage<boolean>('show_popover', true);
const thumbnail_ratio = useStorage<'is-16by9' | 'is-3by1'>('thumbnail_ratio', 'is-3by1');
const separator = useStorage<string>('url_separator', separators[0]?.value ?? ',');
const { mode, on: modeOn, save: applyMode } = useMode();
const draftMode = ref<Mode>(mode.value);
const savingMode = ref(false);
const page_anims = useStorage<boolean>('page_anims', true);
const queue_auto_refresh = useStorage<boolean>('queue_auto_refresh', true);
const queue_auto_refresh_delay = useStorage<number>('queue_auto_refresh_delay', 10000);
const isSecureContext = ref<boolean>(false);

const settingsFieldUi = {
  root: 'w-full',
  container: 'mt-2 w-full',
};

const settingsSwitchUi = {
  root: 'w-full items-start justify-between gap-4',
  wrapper: 'ms-0 flex-1 text-sm',
};

const bgVisibilityModel = computed<number>({
  get: () => Number((1 - Number(bg_opacity.value)).toFixed(2)),
  set: (value) => {
    bg_opacity.value = Number((1 - Number(value)).toFixed(2));
  },
});

const queueRefreshDelayModel = computed<number>({
  get: () => Number(queue_auto_refresh_delay.value),
  set: (value) => {
    queue_auto_refresh_delay.value = Number(value);
  },
});

const separatorItems = computed(() =>
  separators.map((sep) => ({ label: `${sep.name} (${sep.value})`, value: sep.value })),
);

const modeItems = computed<Array<{ label: string; value: Mode }>>(() => [
  {
    label: `Default`,
    value: 'default',
  },
  { label: 'Simple', value: 'simple' },
  { label: 'Regular', value: 'regular' },
]);

const modeChanged = computed(() => draftMode.value !== mode.value);

const saveMode = async (): Promise<void> => {
  if (!modeChanged.value || savingMode.value) {
    return;
  }

  savingMode.value = true;
  try {
    await applyMode(draftMode.value);
  } finally {
    savingMode.value = false;
  }
};

const thumbnailRatioItems = [
  { label: '16:9', value: 'is-16by9' },
  { label: '3:1', value: 'is-3by1' },
];

const notificationTargetItems = computed(() => [
  { label: 'Toast', value: 'toast' },
  { label: 'Browser', value: 'browser', disabled: !isSecureContext.value },
]);

const toastPositionItems: Array<{ label: string; value: toastPosition }> = [
  { label: 'top-left', value: 'top-left' },
  { label: 'top-center', value: 'top-center' },
  { label: 'top-right', value: 'top-right' },
  { label: 'bottom-left', value: 'bottom-left' },
  { label: 'bottom-center', value: 'bottom-center' },
  { label: 'bottom-right', value: 'bottom-right' },
];

const closeScrollLock = (): void => {
  document.body.classList.remove('settings-panel-open');
};

const handleKeydown = (e: KeyboardEvent) => {
  if ('Escape' === e.key && props.isOpen) {
    e.preventDefault();
    e.stopPropagation();
    emitter('close');
  }
};

onMounted(async () => {
  isSecureContext.value = window.isSecureContext;
  await nextTick();

  if ('browser' === toast_target.value && !isSecureContext.value) {
    toast_target.value = 'toast';
  }

  document.addEventListener('keydown', handleKeydown);
});

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleKeydown);
  closeScrollLock();
});

const onNotificationTargetChange = async (): Promise<void> => {
  if ('browser' === toast_target.value) {
    const permission = await notification.requestBrowserPermission();
    if ('granted' !== permission) {
      toast_target.value = 'toast';
      notification.warning(
        'Browser notification permission denied. Reverting to toast notifications.',
      );
    }
  }
};

watch(
  () => props.isOpen,
  (isOpen) => {
    if (isOpen) {
      draftMode.value = mode.value;
      document.body.classList.add('settings-panel-open');
    } else {
      closeScrollLock();
    }
  },
);

watch(mode, (value) => {
  if (props.isOpen && modeChanged.value) {
    return;
  }

  draftMode.value = value;
});
</script>

<style scoped>
:global(body.settings-panel-open) {
  overflow: hidden;
}
</style>
