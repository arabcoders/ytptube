<template>
  <div class="dropdown" :class="{ 'is-active': showList && filteredOptions.length }" style="width:100%;">
    <div class="control" style="width:100%;">
      <textarea :id="id" ref="textareaRef" v-model="localValue" @input="onInput" @focus="onFocus" @blur="hideList"
        @keydown="onKeydown" @keyup="updateCaret" @click="updateCaret" @mouseup="updateCaret"
        class="control is-fullwidth textarea" :placeholder="placeholder" autocomplete="off"
        style="width:100%; position:relative; z-index:2;" rows="4" :disabled="disabled" />
    </div>
    <div class="dropdown-menu" role="menu" style="width:100%; z-index:3;">
      <div class="dropdown-content" style="width:100%; max-height:11em; overflow-y:auto;">
        <a v-for="(option, idx) in filteredOptions" :key="option.value" @mousedown.prevent="appendFlag(option.value)"
          :class="['dropdown-item', { 'is-active': idx === highlightedIndex }]"
          style="display:flex; justify-content:space-between;" ref="dropdownItems">
          <span class="has-text-weight-bold">{{ option.value }}</span>
          <span class="has-text-grey-light is-text-overflow" style="margin-left:1em;">{{ option.description }}</span>
        </a>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import type { AutoCompleteOptions } from '~/types/autocomplete'

const props = defineProps<{
  options: AutoCompleteOptions
  placeholder?: string
  disabled?: boolean
  id?: string
}>()

const model = defineModel<string>()
const localValue = ref(model.value || '')
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const caretIndex = ref(0)
const showList = ref(false)
const highlightedIndex = ref(-1)
const dropdownItems = ref<HTMLElement[]>([])

watch(model, val => localValue.value = val || '')
watch(localValue, val => model.value = val)

// Compute token at caret position
const getCurrentToken = (value: string, caret: number) => {
  const left = value.slice(0, caret)
  const right = value.slice(caret)
  const leftMatch = left.match(/(\S+)$/)
  const rightMatch = right.match(/^(\S+)/)
  const leftToken: string = (leftMatch?.[1] ?? '') as string
  const rightToken: string = (rightMatch?.[1] ?? '') as string
  const token = leftToken + rightToken
  const start = leftMatch ? caret - leftToken.length : caret
  const end = rightMatch ? caret + rightToken.length : caret
  return { token, start, end }
}

const filteredOptions = computed(() => {
  const { token } = getCurrentToken(localValue.value, caretIndex.value)
  // Hide suggestions once '=' is present in the current token
  if (!token || token.includes('=')) {
    return []
  }
  // Only suggest when typing a long flag starting with `--`
  if (!token.startsWith('--')) {
    return []
  }
  // Hide suggestions if token exactly matches an option value
  if (props.options.some(opt => opt.value === token)) {
    return []
  }
  const val = token.toLowerCase()
  const startsWithFlag = []
  const includesFlag = []
  const includesDesc = []
  for (const opt of props.options) {
    const flag = opt.value.toLowerCase()
    const desc = opt.description.toLowerCase()
    if (flag.startsWith(val)) {
      startsWithFlag.push(opt)
    } else if (flag.includes(val)) {
      includesFlag.push(opt)
    } else if (desc.includes(val)) {
      includesDesc.push(opt)
    }
  }
  return [...startsWithFlag, ...includesFlag, ...includesDesc]
})

const appendFlag = (flag: string) => {
  const value = localValue.value
  const caret = caretIndex.value
  const { token, start, end } = getCurrentToken(value, caret)
  if (token) {
    // Replace only the flag part of the token, preserving any '=value' suffix in the same token
    const eqPos = token.indexOf('=')
    const after = eqPos !== -1 ? token.slice(eqPos) : ''
    localValue.value = value.slice(0, start) + flag + after + value.slice(end)
    nextTick(() => {
      const pos = start + flag.length + after.length
      if (textareaRef.value) {
        textareaRef.value.selectionStart = textareaRef.value.selectionEnd = pos
        caretIndex.value = pos
      }
    })
  } else {
    // No token at caret: append at caret position
    const needsSpace = caret > 0 && value[caret - 1] !== ' '
    localValue.value = value.slice(0, caret) + (needsSpace ? ' ' : '') + flag + value.slice(caret)
    nextTick(() => {
      const pos = caret + (needsSpace ? 1 : 0) + flag.length
      if (textareaRef.value) {
        textareaRef.value.selectionStart = textareaRef.value.selectionEnd = pos
        caretIndex.value = pos
      }
    })
  }
  showList.value = false
  highlightedIndex.value = -1
}

const updateCaret = () => {
  caretIndex.value = textareaRef.value ? (textareaRef.value.selectionStart ?? localValue.value.length) : localValue.value.length
}

const onFocus = () => {
  updateCaret()
  showList.value = true
}

const onInput = () => {
  updateCaret()
  const { token } = getCurrentToken(localValue.value, caretIndex.value)
  const hasEqual = token.includes('=')
  const isFlagTrigger = token.startsWith('--') && !hasEqual
  showList.value = isFlagTrigger && filteredOptions.value.length > 0
  highlightedIndex.value = showList.value ? 0 : -1
}

// Reset scroll position when filtered options change
watch(filteredOptions, () => {
  highlightedIndex.value = filteredOptions.value.length > 0 && showList.value ? 0 : -1
  nextTick(() => {
    const dropdown = document.querySelector('.dropdown-content')
    if (dropdown) {
      dropdown.scrollTop = 0
    }
    const items = document.querySelectorAll('.dropdown-item')
    dropdownItems.value = Array.from(items) as HTMLElement[]
  })
})

const hideList = () => setTimeout(() => { showList.value = false; highlightedIndex.value = -1 }, 100)

const onKeydown = (e: KeyboardEvent) => {
  // Track caret and allow ESC to immediately close suggestions and restore normal keys
  updateCaret()
  if (e.key === 'Escape') {
    showList.value = false
    highlightedIndex.value = -1
    return
  }
  if (!showList.value || !filteredOptions.value.length) {
    return
  }

  const pageSize = 5

  if (e.key === 'ArrowDown') {
    e.preventDefault()
    highlightedIndex.value = Math.min(highlightedIndex.value + 1, filteredOptions.value.length - 1)
    nextTick(() => {
      const el = dropdownItems.value[highlightedIndex.value]
      if (el) el.scrollIntoView({ block: 'nearest' })
    })
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    highlightedIndex.value = Math.max(highlightedIndex.value - 1, 0)
    nextTick(() => {
      const el = dropdownItems.value[highlightedIndex.value]
      if (el) el.scrollIntoView({ block: 'nearest' })
    })
  } else if (e.key === 'PageDown') {
    e.preventDefault()
    highlightedIndex.value = Math.min(highlightedIndex.value + pageSize, filteredOptions.value.length - 1)
    nextTick(() => {
      const el = dropdownItems.value[highlightedIndex.value]
      if (el) el.scrollIntoView({ block: 'nearest' })
    })
  } else if (e.key === 'PageUp') {
    e.preventDefault()
    highlightedIndex.value = Math.max(highlightedIndex.value - pageSize, 0)
    nextTick(() => {
      const el = dropdownItems.value[highlightedIndex.value]
      if (el) el.scrollIntoView({ block: 'nearest' })
    })
  } else if (e.key === 'Enter' || e.key === 'Tab') {
    const { token } = getCurrentToken(localValue.value, caretIndex.value)
    const hasEqual = token.includes('=')
    const isFlagTrigger = token.startsWith('--') && !hasEqual
    const selected = highlightedIndex.value >= 0 && highlightedIndex.value < filteredOptions.value.length ?
      filteredOptions.value[highlightedIndex.value] : undefined
    // Only autocomplete if there's a partial word being typed
    if (selected && isFlagTrigger) {
      e.preventDefault()
      appendFlag(selected.value)
    }
  }

  // dropdownItems is updated via a single top-level watch(filteredOptions)
}
</script>
