<template>
  <div v-if="visible" class="modal is-active">
    <div class="modal-background" @click="cancel" />
    <div class="modal-card">
      <header class="modal-card-head">
        <p class="modal-card-title">{{ title }}</p>
        <button class="delete" aria-label="close" @click="cancel" />
      </header>

      <section class="modal-card-body">
        <p class="mb-3 title is-5" v-if="!html_message">{{ message }}</p>
        <div class="content" v-if="html_message" v-html="html_message" style="max-height: 40vh; overflow: auto;" />

        <div v-if="options?.length">
          <hr class="">
          <label v-for="opt in options" :key="opt.key" class="checkbox is-block mb-2 is-unselectable">
            <input type="checkbox" v-model="selected[opt.key]" class="mr-2" />
            {{ opt.label }}
          </label>
        </div>
      </section>

      <footer class="modal-card-foot p-5">
        <div class="field is-grouped" style="width:100%">
          <div class="control is-expanded">
            <button class="button is-fullwidth" :class="confirm_button_color" @click="handleConfirm">
              {{ confirm_button_label }}
            </button>
          </div>
          <div class="control is-expanded">
            <button class="button is-success is-fullwidth" :class="cancel_button_color" @click="cancel">
              {{ cancel_button_label }}
            </button>
          </div>
        </div>
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
const props = defineProps({
  visible: {
    type: Boolean,
    required: true
  },
  title: {
    type: String,
    default: 'Confirm'
  },
  message: {
    type: String,
    default: 'Are you sure?'
  },
  html_message: {
    type: String,
    default: ''
  },
  options: {
    type: Array as () => Array<{ key: string; label: string, checked?: boolean }>,
    default: () => []
  },
  confirm_button_label: {
    type: String,
    default: 'Confirm'
  },
  cancel_button_label: {
    type: String,
    default: 'Cancel'
  },
  confirm_button_color: {
    type: String,
    default: 'is-danger'
  },
  cancel_button_color: {
    type: String,
    default: 'is-success'
  }
})

const emit = defineEmits<{
  (e: 'confirm', options: Record<string, boolean>): void
  (e: 'cancel'): void
}>()

const selected = reactive<Record<string, boolean>>({})

watch(() => props.visible, visible => {
  if (visible && props.options) {
    for (const opt of props.options) {
      selected[opt.key] ??= false
    }
  }
})

function handleConfirm() {
  emit('confirm', { ...selected })
}

function cancel() {
  emit('cancel')
}
</script>
