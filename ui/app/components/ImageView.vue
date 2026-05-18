<style scoped>
img {
  max-width: 100%;
  max-height: 100%;
  margin: auto;
  display: block;
}
</style>

<template>
  <div class="relative min-h-[50vh]">
    <div v-if="isLoading" class="absolute inset-0 flex items-center justify-center">
      <UIcon name="i-lucide-loader-circle" class="size-20 animate-spin text-toned sm:size-24" />
    </div>

    <div v-else-if="hasError" class="flex min-h-[50vh] items-center justify-center">
      <UAlert
        color="error"
        variant="soft"
        icon="i-lucide-triangle-alert"
        title="Unable to load image"
        description="The preview could not be loaded."
        class="w-full max-w-2xl"
      />
    </div>

    <img
      v-if="link"
      :src="link"
      alt="Image preview"
      :class="{ invisible: isLoading || hasError }"
      @load="handle_load"
      @error="handle_error"
    />
  </div>
</template>

<script setup lang="ts">
import { disableOpacity, enableOpacity } from '~/utils';

const emitter = defineEmits(['closeModel']);

const isLoading = ref<boolean>(true);
const hasError = ref<boolean>(false);

const props = defineProps({
  link: {
    type: String,
    required: true,
  },
});

const handle_event = (e: KeyboardEvent) => {
  if (e.key !== 'Escape') {
    return;
  }
  emitter('closeModel');
};

const handle_load = () => {
  isLoading.value = false;
  hasError.value = false;
};

const handle_error = () => {
  isLoading.value = false;
  hasError.value = true;
};

onMounted(() => {
  disableOpacity();
  document.addEventListener('keydown', handle_event);

  if (!props.link) {
    hasError.value = true;
    isLoading.value = false;
  }
});

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handle_event);
  enableOpacity();
});
</script>
