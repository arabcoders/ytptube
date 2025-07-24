<template>
  <div class="notification" :class="props.message_class">
    <button class="delete" @click="emit('close')" v-if="!props.useToggle && props.useClose"></button>

    <div @click="emit('toggle')" class="is-clickable is-pulled-right is-unselectable" v-if="props.useToggle">
      <span class="icon">
        <i class="fas" :class="{ 'fa-arrow-up': props.toggle, 'fa-arrow-down': !props.toggle }"></i>
      </span>
      <span>{{ props.toggle ? 'Close' : 'Open' }}</span>
    </div>

    <div class="notification-title is-unselectable" :class="{ 'is-clickable': props.useToggle }"
      v-if="props.title || props.icon" @click="props.useToggle ? emit('toggle', props.toggle) : null">
      <template v-if="props.icon">
        <span class="icon-text">
          <span class="icon"><i :class="props.icon"></i></span>
          <span>{{ props.title }}</span>
        </span>
      </template>
      <template v-else>{{ props.title }}</template>
    </div>

    <div class="notification-content content" v-if="!props.useToggle || props.toggle">
      <template v-if="props.message">{{ props.message }}</template>
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
const props = defineProps < {
  title?: string
  icon?: string
  message?: string
  message_class?: string
  useToggle?: boolean
  toggle?: boolean
  useClose?: boolean
} > ()

const emit = defineEmits < {
  (e: 'toggle', value ?: boolean): void
  (e: 'close'): void
}> ()
</script>
