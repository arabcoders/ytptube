<template>
  <div
    class="relative flex h-full w-full cursor-text flex-col"
    :class="{ 'is-dragging': isDragging }"
    @drop.prevent="handleDrop"
    @dragover.prevent="handleDragOver"
    @dragenter.prevent="handleDragEnter"
    @dragleave.prevent="handleDragLeave"
    @click="handleClick"
  >
    <UTextarea
      :id="id"
      ref="textareaRef"
      v-model="model"
      :disabled="disabled"
      :placeholder="placeholder"
      :rows="rows"
      size="lg"
      variant="outline"
      color="neutral"
      class="h-full w-full"
      :ui="{
        root: 'w-full',
        base: 'min-h-[10rem] w-full bg-elevated/60 font-mono text-sm ring-default focus-visible:ring-primary',
      }"
    />

    <div
      v-if="isDragging"
      class="pointer-events-none absolute inset-0 z-10 flex items-center justify-center rounded-md border border-dashed border-success bg-success/15"
    >
      <div class="text-center text-success">
        <span
          class="mb-3 inline-flex size-12 items-center justify-center rounded-full bg-success/15"
        >
          <UIcon name="i-lucide-file-down" class="size-5" />
        </span>
        <p class="text-sm font-semibold">Drop file here</p>
      </div>
    </div>

    <input
      ref="fileInputRef"
      type="file"
      :accept="accept"
      class="hidden"
      @change="handleFileSelect"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';

const props = withDefaults(
  defineProps<{
    disabled?: boolean;
    placeholder?: string;
    id?: string;
    accept?: string;
    maxSize?: number;
    rows?: number;
  }>(),
  {
    disabled: false,
    placeholder: '',
    id: '',
    accept: '',
    maxSize: 2 * 1024 * 1024,
    rows: 5,
  },
);

const model = defineModel<string>({ default: '' });

const emit = defineEmits<{ error: [message: string] }>();

const textareaRef = ref<{ textareaRef?: HTMLTextAreaElement | null } | null>(null);
const fileInputRef = ref<HTMLInputElement | null>(null);
const isDragging = ref<boolean>(false);
const dragCounter = ref<number>(0);

const handleDragEnter = (event: DragEvent): void => {
  if (props.disabled) {
    return;
  }

  dragCounter.value++;
  if (event.dataTransfer?.types.includes('Files')) {
    isDragging.value = true;
  }
};

const handleDragLeave = (): void => {
  if (props.disabled) {
    return;
  }

  dragCounter.value--;
  if (dragCounter.value <= 0) {
    isDragging.value = false;
    dragCounter.value = 0;
  }
};

const handleDragOver = (event: DragEvent): void => {
  if (props.disabled) {
    return;
  }

  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'copy';
  }
};

const handleDrop = async (event: DragEvent): Promise<void> => {
  if (props.disabled) {
    return;
  }

  isDragging.value = false;
  dragCounter.value = 0;

  const files = event.dataTransfer?.files;
  if (!files || 0 === files.length) {
    return;
  }

  const file = files[0];
  if (file) {
    await processFile(file);
  }
};

const handleClick = (event: MouseEvent): void => {
  if (props.disabled) {
    return;
  }

  const selection = window.getSelection();
  if (selection && selection.toString().length > 0) {
    return;
  }

  if (event.target === textareaRef.value?.textareaRef) {
    return;
  }
};

const handleFileSelect = async (event: Event): Promise<void> => {
  const target = event.target as HTMLInputElement;
  const files = target.files;

  if (!files || 0 === files.length) {
    return;
  }

  const file = files[0];
  if (file) {
    await processFile(file);
  }

  if (fileInputRef.value) {
    fileInputRef.value.value = '';
  }
};

const processFile = async (file: File): Promise<void> => {
  try {
    if (file.size > props.maxSize) {
      const sizeMB = (file.size / 1024 / 1024).toFixed(2);
      const maxSizeMB = (props.maxSize / 1024 / 1024).toFixed(2);
      emit('error', `File too large: ${sizeMB}MB. Maximum allowed size is ${maxSizeMB}MB.`);
      return;
    }

    const isBinary = await checkIfBinary(file);
    if (isBinary) {
      emit('error', 'File appears to be binary. Please provide a text file.');
      return;
    }

    model.value = await readFileAsText(file);
  } catch (error) {
    emit('error', error instanceof Error ? error.message : 'Failed to read file');
  }
};

const checkIfBinary = async (file: File): Promise<boolean> => {
  const chunkSize = 8192;
  const blob = file.slice(0, chunkSize);

  return new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.onload = (e: ProgressEvent<FileReader>) => {
      if (!e.target?.result) {
        resolve(false);
        return;
      }

      const bytes = new Uint8Array(e.target.result as ArrayBuffer);
      let nullBytes = 0;
      let nonPrintable = 0;

      for (const byte of bytes) {
        if (0 === byte) {
          nullBytes++;
        }
        if (9 !== byte && 10 !== byte && 13 !== byte && (byte < 32 || byte > 126)) {
          nonPrintable++;
        }
      }

      resolve(nullBytes > 0 || nonPrintable / bytes.length > 0.3);
    };

    reader.onerror = () => reject(new Error('Failed to read file for binary check'));
    reader.readAsArrayBuffer(blob);
  });
};

const readFileAsText = (file: File): Promise<string> =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.onload = (e: ProgressEvent<FileReader>) => {
      if (e.target?.result) {
        resolve(e.target.result as string);
      } else {
        reject(new Error('Failed to read file'));
      }
    };

    reader.onerror = () => reject(new Error('File reading error'));
    reader.readAsText(file);
  });

const triggerFileSelect = (): void => {
  if (props.disabled) {
    return;
  }
  fileInputRef.value?.click();
};

defineExpose({ triggerFileSelect, textareaRef });
</script>
