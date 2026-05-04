import { computed } from 'vue';
import { useStorage } from '@vueuse/core';

function clampVolume(volume: number): number {
  if (!Number.isFinite(volume)) return 1;
  return Math.min(1, Math.max(0, volume));
}

export function usePlayerMediaVolume() {
  const volume = useStorage<number>('player_volume', 1);
  const muted = useStorage<boolean>('player_muted', false);
  const effectiveVolume = computed(() => {
    return muted.value ? 0 : clampVolume(volume.value);
  });

  function setVolume(nextVolume: number) {
    const value = clampVolume(nextVolume);
    volume.value = value;
    muted.value = value <= 0;
  }

  function changeVolume(delta: number) {
    setVolume(volume.value + delta);
  }

  function toggleMute() {
    if (muted.value || effectiveVolume.value <= 0) {
      volume.value = volume.value > 0 ? clampVolume(volume.value) : 1;
      muted.value = false;
      return;
    }

    muted.value = true;
  }

  return {
    volume,
    muted,
    effectiveVolume,
    setVolume,
    changeVolume,
    toggleMute,
  };
}
