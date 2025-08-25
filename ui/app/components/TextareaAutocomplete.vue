<template>
  <div class="dropdown" :class="{ 'is-active': showList && filteredOptions.length }" style="width:100%;">
    <div class="control" style="width:100%;">
      <textarea :id="id" v-model="localValue" @input="onInput" @focus="showList = true" @blur="hideList" @keydown="onKeydown"
        class="textarea" :placeholder="placeholder" autocomplete="off" style="width:100%; position:relative; z-index:2;"
        rows="4" :disabled="disabled" />
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
import { ref, computed, defineModel, defineProps, watch, nextTick } from 'vue'
import type { AutoCompleteOptions } from '~/types/autocomplete'

const props = defineProps<{
  options: AutoCompleteOptions
  placeholder?: string
  disabled?: boolean
  id?: string
}>()

const model = defineModel<string>()
const localValue = ref(model.value || '')
const showList = ref(false)
const highlightedIndex = ref(-1)
const dropdownItems = ref<HTMLElement[]>([])

watch(model, val => localValue.value = val || '')
watch(localValue, val => model.value = val)

const filteredOptions = computed(() => {
  const lastWord = localValue.value.split(/\s+/).pop() || ''
  if (!lastWord) {
    return props.options
  }
  const val = lastWord.toLowerCase()
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
  // Only replace the last word if the cursor is at the end and the last word is not followed by a space
  const value = localValue.value
  const cursorAtEnd = true // textarea autocomplete only works at end
  const match = value.match(/(\S+)$/)
  if (match && cursorAtEnd && !value.endsWith(' ')) {
    // Replace last word
    localValue.value = value.slice(0, match.index) + flag
  } else {
    // Just append
    localValue.value += (value && !value.endsWith(' ') ? ' ' : '') + flag
  }
  showList.value = false
  highlightedIndex.value = -1
}

const onInput = () => {
  const lastWord = localValue.value.split(/\s+/).pop() || ''
  showList.value = lastWord.length > 0
  highlightedIndex.value = (showList.value && filteredOptions.value.length && lastWord.length > 0) ? 0 : -1
}

// Reset scroll position when filtered options change
watch(filteredOptions, () => {
  highlightedIndex.value = filteredOptions.value.length > 0 && showList.value ? 0 : -1
  nextTick(() => {
    const dropdown = document.querySelector('.dropdown-content')
    if (dropdown) {
      dropdown.scrollTop = 0
    }
  })
})

const hideList = () => setTimeout(() => { showList.value = false; highlightedIndex.value = -1 }, 100)

const onKeydown = (e: KeyboardEvent) => {
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
    const lastWord = localValue.value.split(/\s+/).pop() || ''
    const selected = highlightedIndex.value >= 0 && highlightedIndex.value < filteredOptions.value.length ?
      filteredOptions.value[highlightedIndex.value] : undefined
    // Only autocomplete if there's a partial word being typed
    if (selected && lastWord.trim().length > 0) {
      e.preventDefault()
      appendFlag(selected.value)
    }
  }

  // Keep dropdownItems ref in sync with rendered items
  watch(filteredOptions, () => nextTick(() => {
    const items = document.querySelectorAll('.dropdown-item')
    dropdownItems.value = Array.from(items) as HTMLElement[]
  }))
}
</script>
