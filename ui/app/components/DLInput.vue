<template>
  <div class="field">
    <label :for="`dlf-${id}`" class="label is-unselectable">
      <template v-if="$slots.title">
        <slot name="title"></slot>
      </template>
      <template v-else>
        <span v-if="icon" class="icon"><i :class="icon" /></span>
        <span v-tooltip="field ? `yt-dlp option: ${field}` : null" :class="{ 'has-tooltip': field }">{{ label }}</span>
      </template>
    </label>
    <div class="control is-expanded" v-if="'string' === type">
      <input :id="`dlf-${id}`" :type="type" class="input" v-model="model" :placeholder="placeholder"
        :disabled="disabled" />
    </div>
    <div class="control is-expanded" v-if="'text' === type">
      <textarea class="textarea is-pre" :id="`dlf-${id}`" v-model="model" :placeholder="placeholder"
        :disabled="disabled"></textarea>
    </div>
    <div class="control is-expanded" v-if="'bool' === type">
      <input type="checkbox" :id="`dlf-${id}`" v-model="model" class="switch is-success" :disabled="disabled" />
      <label :for="`dlf-${id}`" class="label is-unselectable">
        {{ model ? 'Yes' : 'No' }}
      </label>
    </div>
    <span class="help is-bold is-unselectable">
      <template v-if="description">
        <span class="icon"><i class="fa-solid fa-info" /></span>
        <span v-text="description" />
      </template>
      <template v-if="$slots.help">
        <slot name="help"></slot>
      </template>
    </span>
  </div>
</template>

<script setup lang="ts">
import type { ModelRef } from 'vue';
import type { DLFieldType } from '~/types/dl_fields';
defineProps<{
  id: number|string,
  label: string,
  field?: string,
  type: DLFieldType,
  description?: string
  icon?: string
  placeholder?: string
  disabled?: boolean
}>()
const model = defineModel() as ModelRef<string>
</script>
