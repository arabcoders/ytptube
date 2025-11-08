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
import { ref, watch, computed, nextTick } from 'vue'
import type { AutoCompleteOptions } from '~/types/autocomplete'

const props = withDefaults(defineProps<{
  options: AutoCompleteOptions
  placeholder?: string
  disabled?: boolean
  id?: string
  multiple?: boolean
  openOnFocus?: boolean
  allowShortFlags?: boolean
}>(), {
  placeholder: '',
  disabled: false,
  id: '',
  multiple: true,
  openOnFocus: false,
  allowShortFlags: false
})

const model = defineModel<string>()

const onInput = () => {
  showList.value = isFlagTrigger.value && filteredOptions.value.length > 0
  highlightedIndex.value = showList.value ? 0 : -1
}

const showList = ref(false)
const highlightedIndex = ref(-1)
const dropdownItemRefs = ref<(HTMLElement | null)[]>([])

// Extract the last non-space token and its bounds
const getLastToken = (value: string) => {
  // If multiple is disabled, treat the entire input as a single token
  if (!props.multiple) {
    return {
      token: value,
      start: 0,
      end: value.length
    }
  }

  // Multiple enabled: extract last token for multi-flag support
  const m = (value || '').match(/(\S+)$/)
  const token: string = m?.[1] ?? ''
  const start = m ? (m.index as number) : value.length
  const end = m ? start + token.length : value.length
  return { token, start, end }
}

const filteredOptions = computed(() => {
  const value = model.value || ''
  if (!value) {
    return props.options
  }
  const { token } = getLastToken(value)

  // If openOnFocus is enabled and token is empty/just whitespace, show all options
  if (props.openOnFocus && !token) {
    return props.options
  }

  // Hide suggestions when token has '='
  if (!token || token.includes('=')) {
    return []
  }

  // Check if token is a valid flag format
  const isLongFlag = token.startsWith('--')
  const isShortFlag = props.allowShortFlags && token.startsWith('-') && !token.startsWith('--')

  if (!isLongFlag && !isShortFlag) {
    return []
  }

  // Check for exact match first - if found, only show that
  const exactMatch = props.options.find(opt => opt.value === token)
  if (exactMatch) {
    return [exactMatch]
  }

  const startsWithFlag = []
  const includesFlag = []
  const includesDesc = []

  for (const opt of props.options) {
    const flag = opt.value
    const desc = opt.description.toLowerCase()

    if (isShortFlag) {
      // Short flags: case-sensitive matching for flag, case-insensitive for description
      if (flag === token) {
        startsWithFlag.push(opt)
      } else if (flag.includes(token)) {
        includesFlag.push(opt)
      } else if (desc.includes(token.toLowerCase())) {
        includesDesc.push(opt)
      }
    } else {
      // Long flags: case-insensitive matching
      const val = token.toLowerCase()
      const flagLower = flag.toLowerCase()

      if (flagLower.startsWith(val)) {
        startsWithFlag.push(opt)
      } else if (flagLower.includes(val)) {
        includesFlag.push(opt)
      } else if (desc.includes(val)) {
        includesDesc.push(opt)
      }
    }
  }

  return [...startsWithFlag, ...includesFlag, ...includesDesc]
})

const selectOption = (val: string) => {
  const value = model.value || ''
  const { token, start, end } = getLastToken(value)

  // If multiple is disabled, replace entire value
  if (!props.multiple) {
    // Preserve any '=value' suffix already typed
    const eqPos = token.indexOf('=')
    const after = eqPos !== -1 ? token.slice(eqPos) : ''
    model.value = val + after
    showList.value = false
    highlightedIndex.value = -1
    return
  }

  // Multiple enabled: replace only the last token
  if (token) {
    // Preserve any '=value' suffix already typed for this token
    const eqPos = token.indexOf('=')
    const after = eqPos !== -1 ? token.slice(eqPos) : ''
    model.value = value.slice(0, start) + val + after + value.slice(end)
  } else {
    model.value = val
  }
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
  if (!props.openOnFocus) {
    return
  }
  // When openOnFocus is enabled, show dropdown if there are options
  const hasOptions = filteredOptions.value.length > 0
  showList.value = hasOptions
  highlightedIndex.value = hasOptions ? 0 : -1
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

const isFlagTrigger = computed(() => {
  const { token } = getLastToken(model.value || '')

  // If openOnFocus is enabled and input is empty, allow trigger
  if (props.openOnFocus && !token) {
    return true
  }

  if (!token || token.includes('=')) return false

  // Check if token is a valid flag format
  const isLongFlag = token.startsWith('--')
  const isShortFlag = props.allowShortFlags && token.startsWith('-') && !token.startsWith('--')

  if (!isLongFlag && !isShortFlag) {
    return false
  }

  // Allow trigger even for exact matches so users can see descriptions
  return true
})

const handleKeydown = (e: KeyboardEvent) => {
  // Escape closes dropdown and lets arrows navigate the input
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
    if (selected && isFlagTrigger.value) {
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
