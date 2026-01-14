<template>
  <div class="message">
    <div @click="$emit('toggle')" class="is-clickable is-pulled-right is-unselectable" v-if="useToggle">
      <span class="icon">
        <i class="fas" :class="{ 'fa-arrow-up': toggle, 'fa-arrow-down': !toggle }"></i>
      </span>
      <span>{{ toggle ? 'Close' : 'Open' }}</span>
    </div>
    <div class="is-unselectable message-header" :class="{ 'is-clickable': useToggle, }" v-if="title || icon"
      @click="true === useToggle ? $emit('toggle', toggle) : null">
      <template v-if="icon">
        <span class="icon-text">
          <span class="icon"><i :class="icon"></i></span>
          <span>{{ title }}</span>
        </span>
      </template>
      <template v-else>{{ title }}</template>
      <button class="delete" @click="$emit('close')" v-if="!useToggle && useClose" />
    </div>
    <div class="content message-body is-text-break" v-if="false === useToggle || toggle" :class="body_class">
      <template v-if="message">{{ message }}</template>
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  /** Title text for the notification */
  title?: string | null
  /** Icon class for the notification */
  icon?: string | null
  /** Main message content */
  message?: string | null
  /** If true, show toggle button */
  useToggle?: boolean
  /** Current toggle state */
  toggle?: boolean
  /** If true, show close button */
  useClose?: boolean,
  body_class?: string | null,
}>(), {
  title: null,
  icon: null,
  message: null,
  useToggle: false,
  toggle: false,
  useClose: false,
  body_class: null,
})

defineEmits<{
  /** Emitted when the toggle button is clicked */
  (e: 'toggle', value?: boolean): void
  /** Emitted when the close button is clicked */
  (e: 'close'): void
}>()
</script>
