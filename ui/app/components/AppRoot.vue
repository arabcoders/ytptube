<template>
  <UApp :toaster="toaster" :locale="uiLocale" :dir="direction">
    <slot :openSettings="open" :reloadBg="loadBg" :bgLoading="bgLoading" :bgSrc="bgOn ? bg : ''" />

    <SettingsPanel
      :isOpen="settings"
      :isLoading="bgLoading"
      :direction="slideoverSide"
      :layout="mode"
      @close="settings = false"
      @reload_bg="loadBg(true)"
    />
  </UApp>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useStorage } from '@vueuse/core';
import SettingsPanel from '~/components/SettingsPanel.vue';
import type { toastPosition } from '~/composables/useNotification';
import type { YTDLPOption } from '~/types/ytdlp';
import { request, syncOpacity } from '~/utils';
import { getUiLocale } from '~/utils/ui-locales';

const { locale } = useI18n();
const { direction, isRtl } = useAppLocale();

const slideoverSide = computed<'left' | 'right'>(() => (isRtl.value ? 'left' : 'right'));
const uiLocale = computed(() => getUiLocale(locale.value));

const props = withDefaults(
  defineProps<{
    mode?: 'regular' | 'simple';
    loadOpts?: boolean;
  }>(),
  {
    mode: 'regular',
    loadOpts: false,
  },
);

const emit = defineEmits<{ ready: [] }>();

const cfg = useYtpConfig();
const sock = useAppSocket();
const bgOn = useStorage<boolean>('random_bg', true);
const bgOpacity = useStorage<number>('random_bg_opacity_v2', 0.75);
const simpleBgOpacity = useStorage<number>('random_bg_opacity_simple', 0.95);
const anim = useStorage<boolean>('page_anims', true);
const toastPos = useStorage<toastPosition>('toast_position', 'top-right');
const settings = ref(false);
const bg = ref('');
const bgLoading = ref(false);
let disposed = false;

const toaster = computed(() => ({
  position: toastPos.value,
  max: 5,
  expand: true,
  progress: true,
}));

const open = (): void => {
  settings.value = true;
};

const setMode = (): void => {
  document.documentElement.classList.toggle('simple-mode', props.mode === 'simple');
};

const clearBg = (): void => {
  const html = document.documentElement;
  const body = document.querySelector('body');

  html.classList.remove('bg-fanart');
  for (const name of [
    'background-color',
    'display',
    'min-height',
    'min-width',
    'background-image',
  ]) {
    html.style.removeProperty(name);
  }
  body?.style.removeProperty('opacity');
  if (bg.value) {
    URL.revokeObjectURL(bg.value);
  }
  bg.value = '';
};

const loadBg = async (force = false): Promise<void> => {
  if (disposed || !bgOn.value || bgLoading.value) {
    return;
  }

  try {
    bgLoading.value = true;
    const resp = await request(`/api/random/background${force ? '?force=true' : ''}`);
    if (resp.status === 200) {
      const image = await resp.blob();
      if (disposed || !bgOn.value) {
        return;
      }
      if (bg.value) {
        URL.revokeObjectURL(bg.value);
      }
      bg.value = URL.createObjectURL(image);
    }
  } catch (e) {
    console.error(e);
  } finally {
    bgLoading.value = false;
  }
};

defineExpose({ open, loadBg });

const syncBg = async (): Promise<void> => {
  if (!bgOn.value) {
    clearBg();
    return;
  }

  if (!bg.value) {
    await loadBg();
  }
};

const loadOptions = async (): Promise<void> => {
  try {
    const resp = await request('/api/yt-dlp/options');
    if (resp.ok) {
      cfg.ytdlp_options = (await resp.json()) as Array<YTDLPOption>;
    }
  } catch {}
};

onMounted(async () => {
  setMode();
  syncOpacity();

  try {
    await cfg.loadConfig();
  } catch {}

  if (props.loadOpts) {
    await loadOptions();
  }

  try {
    sock.connect();
  } catch {}

  await syncBg();
  emit('ready');
});

onBeforeUnmount(() => {
  disposed = true;
  clearBg();
  document.documentElement.style.removeProperty('--ytp-artwork-opacity');
  if (props.mode === 'simple') {
    document.documentElement.classList.remove('simple-mode');
  }
});

watch(bgOn, () => {
  syncOpacity();
  void syncBg();
});
watch([bgOpacity, simpleBgOpacity], () => bgOn.value && syncOpacity());
watch(anim, (on) => document.documentElement.classList.toggle('no-page-anim', !on), {
  immediate: true,
});
watch(bg, () => {
  if (!bgOn.value || !bg.value) {
    return;
  }

  if (props.mode === 'simple') {
    const html = document.documentElement;
    html.style.backgroundColor = 'unset';
    html.style.display = 'block';
    html.style.minHeight = '100%';
    html.style.minWidth = '100%';
    html.style.backgroundImage = `url(${bg.value})`;
    html.classList.add('bg-fanart');
  }
  syncOpacity();
});
</script>
