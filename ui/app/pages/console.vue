<template>
  <main class="w-full min-w-0 max-w-full space-y-4">
    <div class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
      <div class="min-w-0 space-y-1">
        <div class="flex flex-wrap items-center gap-2 text-lg font-semibold text-highlighted">
          <UIcon name="i-lucide-terminal" class="size-5 text-toned" />
          <span>Console</span>

          <UBadge :color="isLoading ? 'info' : 'neutral'" variant="soft" size="sm">
            {{ isLoading ? 'Streaming output' : 'Idle' }}
          </UBadge>

          <UBadge v-if="commandHistory.length > 0" color="neutral" variant="outline" size="sm">
            {{ commandHistory.length }} saved
          </UBadge>
        </div>

        <p class="text-sm text-toned">Run yt-dlp commands directly in a non-interactive session.</p>
      </div>

      <div class="flex flex-wrap items-center justify-end gap-2">
        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-eraser"
          @click="() => void clearOutput()"
        >
          Clear output
        </UButton>
      </div>
    </div>

    <UPageCard variant="naked" :ui="pageCardUi">
      <template #body>
        <div class="space-y-4">
          <div>
            <div>
              <div
                ref="terminal_window"
                class="terminal-host min-h-[55vh] max-h-[55vh] overflow-hidden rounded-xl scroll-none"
              />
            </div>
          </div>

          <div class="rounded-xl border border-default bg-default">
            <div
              class="flex flex-col gap-3 border-b border-default bg-muted/10 px-4 py-3 lg:flex-row lg:items-start lg:justify-between"
            >
              <div class="min-w-0 space-y-1">
                <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
                  <UIcon name="i-lucide-send" class="size-4 text-toned" />
                  <span>Command</span>
                </div>

                <p class="text-xs text-toned">
                  Press <code>Enter</code> to run single-line input, <code>Shift+Enter</code> to
                  switch to multi-line, and <code>Ctrl+Enter</code> to run multi-line input.
                </p>
              </div>
            </div>

            <div class="grid gap-3 px-4 py-4 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-end">
              <div class="space-y-3">
                <TextareaAutocomplete
                  v-if="isMultiLineInput"
                  ref="commandTextarea"
                  v-model="command"
                  :options="ytDlpOptions"
                  :disabled="isLoading"
                  placeholder="--help"
                  :rows="5"
                  @keydown="handleKeyDown"
                />

                <InputAutocomplete
                  v-else
                  ref="commandInput"
                  v-model="command"
                  :options="ytDlpOptions"
                  :disabled="isLoading"
                  placeholder="--help"
                  :multiple="true"
                  :allowShortFlags="true"
                  @keydown="handleKeyDown"
                  @paste="handlePaste"
                />
              </div>

              <div class="flex flex-wrap items-center justify-end gap-2 xl:self-end">
                <UPopover :content="{ side: 'top', align: 'end', sideOffset: 8 }">
                  <UButton
                    color="neutral"
                    variant="outline"
                    size="lg"
                    icon="i-lucide-history"
                    trailing-icon="i-lucide-chevron-up"
                    class="flex-1 justify-center sm:flex-none sm:min-w-36"
                  >
                    History
                  </UButton>

                  <template #content>
                    <UCard class="w-[min(92vw,42rem)]" :ui="{ body: 'space-y-3 p-4' }">
                      <div class="flex flex-wrap items-center justify-between gap-3">
                        <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
                          <UIcon name="i-lucide-history" class="size-4 text-toned" />
                          <span>Command history</span>
                        </div>

                        <UButton
                          color="error"
                          variant="outline"
                          size="sm"
                          icon="i-lucide-trash"
                          :disabled="commandHistory.length < 1"
                          @click="() => void clearHistory()"
                        >
                          Clear history
                        </UButton>
                      </div>

                      <UAlert
                        v-if="commandHistory.length < 1"
                        color="info"
                        variant="soft"
                        icon="i-lucide-clock-3"
                        title="Commands history is empty"
                      />

                      <div
                        v-else
                        class="max-h-96 w-full min-w-0 max-w-full overflow-hidden rounded-lg border border-default bg-default"
                      >
                        <div class="w-full max-w-full overflow-auto overscroll-contain">
                          <table class="min-w-155 w-full text-sm">
                            <tbody class="divide-y divide-default">
                              <tr
                                v-for="(cmd, index) in commandHistory"
                                :key="`${index}-${cmd}`"
                                class="hover:bg-muted/20"
                              >
                                <td class="px-3 py-3 align-middle">
                                  <button
                                    type="button"
                                    class="block w-full text-left font-mono text-xs text-default hover:text-highlighted"
                                    @click="() => void loadCommand(cmd)"
                                  >
                                    {{ cmd.replace(/\n/g, ' ') }}
                                  </button>
                                </td>

                                <td
                                  class="w-[2%] px-3 py-3 text-center align-middle whitespace-nowrap"
                                >
                                  <UButton
                                    color="error"
                                    variant="ghost"
                                    size="xs"
                                    icon="i-lucide-x"
                                    square
                                    @click="removeFromHistory(index)"
                                  />
                                </td>
                              </tr>
                            </tbody>
                          </table>
                        </div>
                      </div>
                    </UCard>
                  </template>
                </UPopover>

                <UButton
                  color="primary"
                  size="lg"
                  :icon="isLoading ? 'i-lucide-loader-circle' : 'i-lucide-send'"
                  :loading="isLoading"
                  :disabled="isLoading || !hasValidCommand"
                  class="flex-1 justify-center sm:flex-none sm:min-w-36"
                  @click="() => void runCommand()"
                >
                  Run command
                </UButton>
              </div>
            </div>
          </div>
        </div>
      </template>
    </UPageCard>
  </main>
</template>

<script setup lang="ts">
import { fetchEventSource } from '@microsoft/fetch-event-source';
import type { EventSourceMessage } from '@microsoft/fetch-event-source';
import { useStorage } from '@vueuse/core';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';
import { Terminal } from '@xterm/xterm';
import InputAutocomplete from '~/components/InputAutocomplete.vue';
import TextareaAutocomplete from '~/components/TextareaAutocomplete.vue';
import { useDialog } from '~/composables/useDialog';
import type { AutoCompleteOptions } from '~/types/autocomplete';
import { disableOpacity, enableOpacity, parse_api_error, uri } from '~/utils';

const config = useConfigStore();
const toast = useNotification();
const dialog = useDialog();

const terminal = ref<Terminal>();
const terminalFit = ref<FitAddon>();
const command = ref('');
const terminal_window = useTemplateRef<HTMLDivElement>('terminal_window');
const commandInput = ref<InstanceType<typeof InputAutocomplete> | null>(null);
const commandTextarea = ref<InstanceType<typeof TextareaAutocomplete> | null>(null);
const isLoading = ref(false);
const storedCommand = useStorage<string>('console_command', '');
const commandHistory = useStorage<string[]>('console_command_history', []);
const sseController = ref<AbortController | null>(null);

const MAX_HISTORY_ITEMS = 50;

const pageCardUi = {
  root: 'w-full bg-transparent',
  container: 'w-full p-0 sm:p-0',
  wrapper: 'w-full items-stretch',
  body: 'w-full',
};

const ytDlpOptions = computed<AutoCompleteOptions>(() =>
  config.ytdlp_options.flatMap((opt) =>
    opt.flags.map((flag) => ({ value: flag, description: opt.description || '' })),
  ),
);

const hasValidCommand = computed(() => Boolean(command.value && command.value.trim().length > 0));
const isMultiLineInput = computed(() => Boolean(command.value && command.value.includes('\n')));

watch(command, (value) => {
  storedCommand.value = value;
});

watch(
  () => isLoading.value,
  async (value) => {
    if (value) {
      return;
    }

    if (command.value.trim()) {
      addToHistory(command.value.trim());
    }

    command.value = '';
    await nextTick();
    await focusInput();
  },
  { immediate: true },
);

watch(
  () => config.app.console_enabled,
  async () => {
    if (config.app.console_enabled) {
      return;
    }

    toast.error('Console is disabled in the configuration. Please enable it to use this feature.');
    await navigateTo('/');
  },
);

const handleKeyDown = async (event: KeyboardEvent): Promise<void> => {
  const target = event.target as HTMLInputElement | HTMLTextAreaElement;
  const isTextarea = target.tagName === 'TEXTAREA';

  if (event.key !== 'Enter') {
    return;
  }

  if (((event.ctrlKey && isTextarea) || !isTextarea) && hasValidCommand.value) {
    event.preventDefault();
    await runCommand();
    return;
  }

  if (event.shiftKey && !isTextarea) {
    event.preventDefault();
    const cursorPos = target.selectionStart || command.value.length;
    command.value =
      command.value.substring(0, cursorPos) +
      '\n' +
      command.value.substring(target.selectionEnd || cursorPos);

    await nextTick();

    if (commandTextarea.value) {
      const textarea = commandTextarea.value.$el?.querySelector('textarea') as HTMLTextAreaElement;
      if (textarea) {
        textarea.setSelectionRange(cursorPos + 1, cursorPos + 1);
        textarea.focus();
      }
    }
  }
};

const handlePaste = async (event: ClipboardEvent): Promise<void> => {
  const pastedText = event.clipboardData?.getData('text') || '';
  if (!pastedText.includes('\n')) {
    return;
  }

  event.preventDefault();
  const target = event.target as HTMLInputElement;
  const currentValue = command.value || '';
  const start = target.selectionStart || currentValue.length;
  const end = target.selectionEnd || currentValue.length;
  command.value = currentValue.substring(0, start) + pastedText + currentValue.substring(end);
  await nextTick();

  if (!commandTextarea.value) {
    return;
  }

  const textarea = commandTextarea.value.$el?.querySelector('textarea') as HTMLTextAreaElement;
  if (textarea) {
    const newPos = start + pastedText.length;
    textarea.setSelectionRange(newPos, newPos);
    textarea.focus();
  }
};

const handle_event = (): void => {
  terminalFit.value?.fit();
};

const handleStreamMessage = (event: EventSourceMessage): void => {
  if (!terminal.value) {
    return;
  }

  let payload: { type?: string; line?: string; exitcode?: number } | null = null;
  if (event.data) {
    try {
      payload = JSON.parse(event.data) as { type?: string; line?: string; exitcode?: number };
    } catch {
      payload = null;
    }
  }

  if (event.event === 'output') {
    terminal.value.writeln(payload?.line ?? '');
    return;
  }

  if (event.event === 'close') {
    isLoading.value = false;
    sseController.value?.abort();
  }
};

const startStream = async (cmd: string): Promise<void> => {
  sseController.value?.abort();
  const controller = new AbortController();
  sseController.value = controller;
  isLoading.value = true;

  try {
    await fetchEventSource(uri('/api/system/terminal'), {
      method: 'POST',
      body: JSON.stringify({ command: cmd }),
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      credentials: 'same-origin',
      signal: controller.signal,
      onopen: async (response) => {
        if (response.ok) {
          return;
        }

        let message = response.statusText || 'Failed to start command stream.';

        try {
          message = await parse_api_error(response.clone().json());
        } catch {
          try {
            const text = await response.text();
            if (text) {
              message = text;
            }
          } catch {
            message = response.statusText || 'Failed to start command stream.';
          }
        }

        throw new Error(message);
      },
      onmessage: handleStreamMessage,
      onerror: (error) => {
        if (controller.signal.aborted) {
          return;
        }

        terminal.value?.writeln(`Error: ${error}`);
        isLoading.value = false;
      },
    });
  } catch (error) {
    if (!controller.signal.aborted) {
      terminal.value?.writeln(`Error: ${error}`);
      isLoading.value = false;
    }
  } finally {
    if (controller === sseController.value) {
      sseController.value = null;
    }
  }
};

const ensureTerminal = async (): Promise<void> => {
  if (terminal.value) {
    return;
  }

  terminal.value = new Terminal({
    fontSize: 14,
    fontFamily: "'JetBrains Mono', monospace",
    cursorBlink: false,
    cursorStyle: 'underline',
    cols: 108,
    rows: 10,
    disableStdin: true,
    scrollback: 1000,
    theme: {
      background: '#09090b',
      foreground: '#f4f4f5',
    },
  });

  terminalFit.value = new FitAddon();
  terminal.value.loadAddon(terminalFit.value);

  await nextTick();

  if (terminal_window.value) {
    terminal.value.open(terminal_window.value);
  }

  terminalFit.value.fit();
};

const runCommand = async (): Promise<void> => {
  if (!hasValidCommand.value) {
    return;
  }

  if (config.app.console_enabled !== true) {
    await navigateTo('/');
    toast.error('Console is disabled in the configuration. Please enable it to use this feature.');
    return;
  }

  let cmd = command.value.trim().replace(/\n/g, ' ').trim();

  if (cmd.startsWith('yt-dlp')) {
    cmd = cmd.replace(/^yt-dlp/, '').trim();
    await nextTick();
    if (cmd === '') {
      return;
    }
  }

  await ensureTerminal();

  if (cmd === 'clear') {
    await clearOutput(true);
    return;
  }

  await startStream(cmd);
  terminal.value?.writeln('user@YTPTube ~');
  terminal.value?.writeln(`$ yt-dlp ${command.value}`);
  storedCommand.value = '';
};

const clearOutput = async (withCommand: boolean = false): Promise<void> => {
  terminal.value?.clear();

  if (withCommand === true) {
    command.value = '';
  }

  await focusInput();
};

const focusInput = async (): Promise<void> => {
  await nextTick();

  let elm: HTMLInputElement | HTMLTextAreaElement | undefined;
  if (isMultiLineInput.value) {
    elm = commandTextarea.value?.$el?.querySelector('textarea') as HTMLTextAreaElement;
  } else {
    elm = commandInput.value?.$el?.querySelector('input') as HTMLInputElement;
  }

  elm?.focus();
};

const addToHistory = (cmd: string): void => {
  commandHistory.value = [cmd, ...commandHistory.value.filter((h) => h !== cmd)].slice(
    0,
    MAX_HISTORY_ITEMS,
  );
};

const loadCommand = async (cmd: string): Promise<void> => {
  command.value = cmd;
  await nextTick();
  await focusInput();
};

const clearHistory = async (): Promise<void> => {
  if (commandHistory.value.length === 0) {
    return;
  }

  const { status } = await dialog.confirmDialog({
    title: 'Confirm Action',
    message: 'Clear commands history?',
    confirmColor: 'error',
  });

  if (!status) {
    return;
  }

  commandHistory.value = [];
};

const removeFromHistory = (index: number): void => {
  commandHistory.value = commandHistory.value.filter((_, i) => i !== index);
};

watch(isMultiLineInput, async () => {
  await focusInput();
});

onMounted(async () => {
  if (config.app.console_enabled !== true) {
    toast.error('Console is disabled in the configuration. Please enable it to use this feature.');
    await navigateTo('/');
    return;
  }

  window.addEventListener('resize', handle_event);
  disableOpacity();

  await ensureTerminal();

  if (storedCommand.value) {
    command.value = storedCommand.value;
    await nextTick();
  }

  await focusInput();
});

onBeforeUnmount(() => {
  sseController.value?.abort();
  window.removeEventListener('resize', handle_event);
  enableOpacity();
});
</script>
