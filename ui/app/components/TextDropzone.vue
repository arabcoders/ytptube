<template>
  <div class="file-dropzone is-relative" :class="{ 'is-dragging': isDragging }" @drop.prevent="handleDrop"
    @dragover.prevent="handleDragOver" @dragenter.prevent="handleDragEnter" @dragleave.prevent="handleDragLeave"
    @click="handleClick">

    <textarea ref="textareaRef" class="control textarea is-fullwidth" :class="{ 'is-focused': isDragging }"
      :value="model" @input="handleInput" :disabled="disabled" :placeholder="placeholder" :id="id" />

    <div v-if="isDragging"
      class="dropzone-overlay has-background-success-90 is-flex is-align-items-center is-justify-content-center">
      <div class="has-text-centered has-text-dark">
        <span class="icon is-large"><i class="fa-solid fa-file-arrow-down fa-3x" /></span>
        <p class="mt-3 is-size-5 has-text-weight-bold">Drop file here</p>
      </div>
    </div>

    <input ref="fileInputRef" type="file" :accept="accept" @change="handleFileSelect" style="display: none" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

interface Props {
  disabled?: boolean
  placeholder?: string
  id?: string
  accept?: string
  maxSize?: number
}

const props = withDefaults(defineProps<Props>(), {
  disabled: false,
  placeholder: '',
  id: '',
  accept: '',
  maxSize: 2 * 1024 * 1024
})

const model = defineModel<string>({ default: '' })

const emit = defineEmits<{ error: [message: string] }>()

const textareaRef = ref<HTMLTextAreaElement | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const isDragging = ref<boolean>(false)
const dragCounter = ref<number>(0)

const handleInput = (event: Event): void => {
  const target = event.target as HTMLTextAreaElement
  model.value = target.value
}

const handleDragEnter = (event: DragEvent): void => {
  if (props.disabled) {
    return
  }

  dragCounter.value++
  if (event.dataTransfer?.types.includes('Files')) {
    isDragging.value = true
  }
}

const handleDragLeave = (_event: DragEvent): void => {
  if (props.disabled) {
    return
  }

  dragCounter.value--
  if (0 === dragCounter.value) {
    isDragging.value = false
  }
}

const handleDragOver = (event: DragEvent): void => {
  if (props.disabled) {
    return
  }

  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'copy'
  }
}

const handleDrop = async (event: DragEvent): Promise<void> => {
  if (props.disabled) {
    return
  }

  isDragging.value = false
  dragCounter.value = 0

  const files = event.dataTransfer?.files
  if (!files || 0 === files.length) {
    return
  }

  const file = files[0]
  if (file) {
    await processFile(file)
  }
}

const handleClick = (event: MouseEvent): void => {
  if (props.disabled) {
    return
  }

  const selection = window.getSelection()
  if (selection && selection.toString().length > 0) {
    return
  }

  if (event && event.target === textareaRef.value) {
    return
  }
}

const handleFileSelect = async (event: Event): Promise<void> => {
  const target = event.target as HTMLInputElement
  const files = target.files

  if (!files || 0 === files.length) {
    return
  }

  const file = files[0]
  if (file) {
    await processFile(file)
  }

  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }
}

const processFile = async (file: File): Promise<void> => {
  try {
    if (file.size > props.maxSize) {
      const sizeMB = (file.size / 1024 / 1024).toFixed(2)
      const maxSizeMB = (props.maxSize / 1024 / 1024).toFixed(2)
      const errorMsg = `File too large: ${sizeMB}MB. Maximum allowed size is ${maxSizeMB}MB.`
      emit('error', errorMsg)
      console.error(errorMsg)
      return
    }

    const isBinary = await checkIfBinary(file)
    if (isBinary) {
      const errorMsg = 'File appears to be binary. Please provide a text file.'
      emit('error', errorMsg)
      console.error(errorMsg)
      return
    }

    const text = await readFileAsText(file)
    model.value = text
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : 'Failed to read file'
    emit('error', errorMsg)
    console.error('Failed to read file:', error)
  }
}

const checkIfBinary = async (file: File): Promise<boolean> => {
  const chunkSize = 8192
  const blob = file.slice(0, chunkSize)

  return new Promise((resolve, reject) => {
    const reader = new FileReader()

    reader.onload = (e: ProgressEvent<FileReader>) => {
      if (!e.target?.result) {
        resolve(false)
        return
      }

      const bytes = new Uint8Array(e.target.result as ArrayBuffer)

      let nullBytes = 0
      let nonPrintable = 0

      for (let i = 0; i < bytes.length; i++) {
        const byte = bytes[i]

        if (undefined === byte) {
          continue
        }

        if (0 === byte) {
          nullBytes++
        }

        if (9 !== byte && 10 !== byte && 13 !== byte && (byte < 32 || byte > 126)) {
          nonPrintable++
        }
      }

      resolve(nullBytes > 0 || (nonPrintable / bytes.length) > 0.3)
    }

    reader.onerror = () => reject(new Error('Failed to read file for binary check'))
    reader.readAsArrayBuffer(blob)
  })
}

const readFileAsText = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()

    reader.onload = (e: ProgressEvent<FileReader>) => {
      if (e.target?.result) {
        resolve(e.target.result as string)
      } else {
        reject(new Error('Failed to read file'))
      }
    }

    reader.onerror = () => reject(new Error('File reading error'))
    reader.readAsText(file)
  })
}

const triggerFileSelect = (): void => {
  if (props.disabled) {
    return
  }
  fileInputRef.value?.click()
}

defineExpose({ triggerFileSelect })
</script>

<style>
.file-dropzone {
  cursor: text;
}

.dropzone-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  border-radius: 4px;
  pointer-events: none;
  z-index: 10;
}

.file-dropzone.is-dragging textarea {
  box-shadow: --var(--bulma-card-shadow) !important;
  border-color: --var(--bulma-success);
}
</style>
