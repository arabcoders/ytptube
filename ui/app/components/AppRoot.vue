<template>
  <UApp :toaster="toaster">
    <slot :openSettings="open" :reloadBg="loadBg" :bgLoading="bgLoading" />

    <SettingsPanel
      :isOpen="settings"
      :isLoading="bgLoading"
      direction="right"
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
const bgOpacity = useStorage<number>('random_bg_opacity', 0.95);
const anim = useStorage<boolean>('page_anims', true);
const toastPos = useStorage<toastPosition>('toast_position', 'top-right');
const settings = ref(false);
const bg = ref('');
const bgLoading = ref(false);

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
  html.removeAttribute('style');
  body?.removeAttribute('style');
  bg.value = '';
};

const loadBg = async (force = false): Promise<void> => {
  if (bgLoading.value) {
    return;
  }

  try {
    bgLoading.value = true;
    const resp = await request(`/api/random/background${force ? '?force=true' : ''}`);
    if (resp.status === 200) {
      bg.value = URL.createObjectURL(await resp.blob());
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
  if (props.mode === 'simple') {
    document.documentElement.classList.remove('simple-mode');
  }
});

watch(bgOn, () => void syncBg());
watch(bgOpacity, () => bgOn.value && syncOpacity());
watch(anim, (on) => document.documentElement.classList.toggle('no-page-anim', !on), {
  immediate: true,
});
watch(bg, () => {
  if (!bgOn.value || !bg.value) {
    return;
  }

  document.documentElement.setAttribute(
    'style',
    [
      'background-color: unset',
      'display: block',
      'min-height: 100%',
      'min-width: 100%',
      `background-image: url(${bg.value})`,
    ].join('; '),
  );
  document.documentElement.classList.add('bg-fanart');
  syncOpacity();
});
</script>
