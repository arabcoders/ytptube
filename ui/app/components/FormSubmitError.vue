<template>
  <UAlert
    v-if="message && !dismissed"
    color="error"
    variant="solid"
    icon="i-lucide-circle-alert"
    role="button"
    tabindex="0"
    class="sticky top-0 z-20 mb-4 cursor-pointer bg-error/90 shadow-md backdrop-blur-sm"
    @click="dismiss"
    @keydown.enter="dismiss"
    @keydown.space.prevent="dismiss"
  >
    <template #description>
      <p class="whitespace-pre-line text-inverted">{{ message }}</p>
    </template>
  </UAlert>
</template>

<script setup lang="ts">
const props = defineProps<{
  message?: string | null;
}>();

const dismissed = ref(false);

const dismiss = (): void => {
  dismissed.value = true;
};

watch(
  () => props.message,
  () => {
    dismissed.value = false;
  },
);
</script>
