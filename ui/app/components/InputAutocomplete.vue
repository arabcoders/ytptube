<template>
  <div class="dropdown" :class="{ 'is-active': showList && filteredOptions.length }" style="width:100%;">
    <div class="control" style="width:100%;">
      <input v-model="model" @focus="onFocus" @blur="hideList" @keydown="handleKeydown" @input="onInput" class="input"
        :placeholder="placeholder" autocomplete="new-password" style="width:100%; position:relative; z-index:2;"
        :disabled="disabled" :id="id" />
    </div>
    <div class="dropdown-menu" role="menu" style="width:100%; z-index:3;">
      <div class="dropdown-content" style="width:100%; max-height:10em; overflow-y:auto;">
        <a v-for="(option, idx) in filteredOptions" :key="option.value" @mousedown.prevent="selectOption(option.value)"
          :class="['dropdown-item', { 'is-active': idx === highlightedIndex }]"
          style="display:flex; justify-content:space-between;" :ref="el => setDropdownItemRef(el, idx)">
          <span class="has-text-weight-bold">{{ option.value }}</span>
          <abbr class="has-text-grey-light is-text-overflow" :title="option.description" style="margin-left:1em;">
            {{ option.description }}
          </abbr>
        </a>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed, defineModel, defineProps, nextTick } from 'vue'
import type { AutoCompleteOptions } from '~/types/autocomplete'

const props = defineProps<{
  options: AutoCompleteOptions
  placeholder?: string
  disabled?: boolean,
  id?: string
}>()

const model = defineModel<string>()

const onInput = () => {
  if (false === showList.value) {
    showList.value = true
  }
  highlightedIndex.value = filteredOptions.value.length ? 0 : -1
}

const showList = ref(false)
const highlightedIndex = ref(-1)
const dropdownItemRefs = ref<(HTMLElement | null)[]>([])

const filteredOptions = computed(() => {
  if (!model.value) {
    return props.options
  }
  const val = model.value.toLowerCase()
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

const selectOption = (val: string) => {
  model.value = val
  showList.value = false
  highlightedIndex.value = -1
}

const hideList = () => {
  setTimeout(() => {
    showList.value = false
    highlightedIndex.value = -1
    dropdownItemRefs.value = []
  }, 100)
}

const onFocus = () => {
  showList.value = true
  highlightedIndex.value = filteredOptions.value.length ? 0 : -1
}

const setDropdownItemRef = (el: Element | ComponentPublicInstance | null, idx: number) => {
  dropdownItemRefs.value[idx] = el instanceof HTMLElement ? el : null
}

watch(filteredOptions, () => {
  highlightedIndex.value = filteredOptions.value.length ? 0 : -1
  dropdownItemRefs.value = Array(filteredOptions.value.length).fill(null)
  nextTick(() => {
    const dropdown = document.querySelector('.dropdown-content')
    if (dropdown) {
      dropdown.scrollTop = 0
    }
  })
})

const handleKeydown = (e: KeyboardEvent) => {
  if (!filteredOptions.value.length) {
    return
  }

  const pageSize = 5

  if (e.key === 'ArrowDown') {
    e.preventDefault()
    highlightedIndex.value = Math.min(highlightedIndex.value + 1, filteredOptions.value.length - 1)
    nextTick(() => scrollHighlightedIntoView())
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    highlightedIndex.value = Math.max(highlightedIndex.value - 1, 0)
    nextTick(() => scrollHighlightedIntoView())
  } else if (e.key === 'PageDown') {
    e.preventDefault()
    highlightedIndex.value = Math.min(highlightedIndex.value + pageSize, filteredOptions.value.length - 1)
    nextTick(() => scrollHighlightedIntoView())
  } else if (e.key === 'PageUp') {
    e.preventDefault()
    highlightedIndex.value = Math.max(highlightedIndex.value - pageSize, 0)
    nextTick(() => scrollHighlightedIntoView())
  } else if (e.key === 'Enter' || e.key === 'Tab') {
    const selected = highlightedIndex.value >= 0 && highlightedIndex.value < filteredOptions.value.length ?
      filteredOptions.value[highlightedIndex.value] : undefined
    if (selected) {
      e.preventDefault()
      selectOption(selected.value)
    }
  }
}

function scrollHighlightedIntoView() {
  const el = dropdownItemRefs.value[highlightedIndex.value]
  if (!el) {
    return
  }
  el.scrollIntoView({ block: 'nearest' })
}
</script>
