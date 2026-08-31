<template>
  <main class="flex min-h-0 w-full min-w-0 max-w-full flex-1 flex-col gap-6">
    <div class="ytp-page-header">
      <div class="ytp-page-heading items-start">
        <span class="ytp-page-icon">
          <UIcon :name="pageShell.icon" class="size-5" />
        </span>

        <div class="min-w-0 space-y-2">
          <div class="ytp-page-kicker">
            <span>{{ pageShell.sectionLabel }}</span>
            <span>/</span>
            <span>{{ pageShell.pageLabel }}</span>
          </div>

          <p class="max-w-3xl text-sm text-toned">{{ pageShell.description }}</p>
        </div>
      </div>

      <div class="flex flex-wrap justify-end gap-2 xl:justify-end">
        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-circle-help"
          :disabled="isStartBlocked"
          @click="() => void runHelp()"
        >
          {{ t('common.help') }}
        </UButton>

        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-eraser"
          @click="() => void clearOutput()"
        >
          {{ t('common.clearOutput') }}
        </UButton>
      </div>
    </div>

    <div class="flex min-h-0 flex-1 flex-col gap-4">
      <div
        class="flex min-h-72 min-w-0 flex-1 overflow-hidden rounded-sm border border-default bg-neutral-950/95 shadow-sm"
      >
        <div
          ref="terminal_window"
          class="terminal-host h-full min-h-0 w-full overflow-hidden"
          dir="ltr"
        />
      </div>

      <div class="ytp-card shadow-sm" dir="ltr">
        <div
          class="flex flex-col gap-3 border-b border-default bg-muted/10 px-4 py-3 lg:flex-row lg:items-start lg:justify-between"
        >
          <div class="min-w-0 flex-1 space-y-1">
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div
                class="flex min-w-0 flex-wrap items-center gap-2 text-sm font-semibold text-highlighted"
              >
                <UIcon name="i-lucide-send" class="size-4 shrink-0 text-toned" />
                <span>{{ t('console.command') }}</span>

                <UBadge :color="sessionStatusColor" variant="soft" size="sm">
                  <span class="inline-flex items-center gap-1.5">
                    <UIcon
                      :name="sessionStatusIcon"
                      class="size-3.5"
                      :class="sessionStatusSpinning ? 'animate-spin' : ''"
                    />
                    <span>{{ sessionStatusLabel }}</span>
                  </span>
                </UBadge>
              </div>

              <UBadge :color="isMultiLineInput ? 'info' : 'neutral'" variant="soft" size="sm">
                {{ isMultiLineInput ? t('console.multiLine') : t('console.singleLine') }}
              </UBadge>
            </div>

            <p class="text-xs text-toned">
              {{ t('console.shiftEnterHint') }}
            </p>
          </div>
        </div>

        <div class="space-y-3 px-4 py-4">
          <UAlert
            v-if="sessionError"
            color="error"
            variant="soft"
            icon="i-lucide-triangle-alert"
            :title="sessionErrorTitle"
            :description="sessionError"
          />

          <UAlert
            v-if="sessionStatus === 'reconnecting'"
            color="warning"
            variant="soft"
            icon="i-lucide-rotate-cw"
            :title="t('console.reconnecting')"
            :description="t('console.reconnectingDesc')"
          />

          <UAlert
            v-if="sessionStatus === 'interrupted'"
            color="warning"
            variant="soft"
            icon="i-lucide-circle-off"
            :title="t('console.interrupted')"
            :description="t('console.interruptedDesc')"
          />

          <div class="grid gap-3 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-end">
            <div class="space-y-3">
              <TextareaAutocomplete
                v-if="isMultiLineInput"
                ref="commandTextarea"
                v-model="command"
                class="console-input"
                :options="ytDlpOptions"
                :disabled="isStartBlocked"
                :icon="isLoading ? 'i-lucide-loader-circle' : 'i-lucide-terminal'"
                :icon-class="isLoading ? 'animate-spin' : ''"
                placeholder="--help"
                :rows="5"
                dir="ltr"
                @keydown="handleKeyDown"
              />

              <InputAutocomplete
                v-else
                ref="commandInput"
                v-model="command"
                class="console-input"
                :options="ytDlpOptions"
                :disabled="isStartBlocked"
                :icon="isLoading ? 'i-lucide-loader-circle' : 'i-lucide-terminal'"
                :icon-class="isLoading ? 'animate-spin' : ''"
                placeholder="--help"
                dir="ltr"
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
                  {{ t('common.history') }}
                </UButton>

                <template #content>
                  <UCard
                    class="w-[min(92vw,42rem)] border border-default/70 shadow-sm"
                    dir="ltr"
                    :ui="historyCardUi"
                  >
                    <div class="flex flex-wrap items-center justify-between gap-3">
                      <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
                        <UIcon name="i-lucide-history" class="size-4 text-toned" />
                        <span>{{ t('console.recentRuns') }}</span>
                      </div>

                      <UButton
                        color="neutral"
                        variant="outline"
                        size="sm"
                        icon="i-lucide-eye-off"
                        :disabled="recentSessionEntries.length < 1"
                        @click="() => void hideRecentSessions()"
                      >
                        {{ t('console.hideRecent') }}
                      </UButton>
                    </div>

                    <UAlert
                      v-if="recentSessionEntries.length < 1"
                      color="info"
                      variant="soft"
                      icon="i-lucide-clock-3"
                      :title="t('console.noSessions')"
                    />

                    <div
                      v-else
                      class="max-h-96 w-full min-w-0 max-w-full overflow-hidden ytp-table-surface"
                    >
                      <div class="w-full max-w-full overflow-auto overscroll-contain">
                        <table class="w-full text-sm">
                          <tbody class="divide-y divide-default">
                            <tr
                              v-for="item in recentSessionEntries"
                              :key="item.sessionId"
                              class="transition-colors hover:bg-elevated/70 [&>td]:border-e [&>td]:border-default/60 [&>td:last-child]:border-e-0"
                            >
                              <td class="px-3 py-3 align-middle">
                                <div class="space-y-2">
                                  <button
                                    type="button"
                                    class="block w-full text-start font-mono text-xs text-default hover:text-highlighted"
                                    dir="ltr"
                                    @click="() => void replayRecentSession(item)"
                                  >
                                    {{ item.command }}
                                  </button>

                                  <div
                                    class="flex flex-wrap items-center gap-2 text-[11px] text-toned"
                                  >
                                    <UBadge
                                      :color="recentSessionStatusColor(item)"
                                      variant="soft"
                                      size="sm"
                                    >
                                      <span
                                        v-if="recentSessionStatusSpinning(item)"
                                        class="inline-flex items-center gap-1.5"
                                      >
                                        <UIcon
                                          :name="recentSessionStatusIcon(item)"
                                          class="size-3.5 animate-spin"
                                        />
                                        <span>{{ recentSessionStatusLabel(item) }}</span>
                                      </span>
                                      <span v-else class="inline-flex items-center gap-1.5">
                                        <UIcon
                                          :name="recentSessionStatusIcon(item)"
                                          class="size-3.5"
                                        />
                                        <span>{{ recentSessionStatusLabel(item) }}</span>
                                      </span>
                                    </UBadge>

                                    <UTooltip
                                      v-if="item.finishedAt || item.startedAt || item.createdAt"
                                      :text="
                                        formatDateTime(
                                          item.finishedAt || item.startedAt || item.createdAt || 0,
                                          locale,
                                        )
                                      "
                                    >
                                      <span class="inline-flex items-center gap-1.5 cursor-help">
                                        <UIcon name="i-lucide-clock-3" class="size-3.5" />
                                        <time
                                          :datetime="
                                            toIsoString(
                                              item.finishedAt ||
                                                item.startedAt ||
                                                item.createdAt ||
                                                0,
                                            )
                                          "
                                        >
                                          {{
                                            relativeTime(
                                              item.finishedAt ||
                                                item.startedAt ||
                                                item.createdAt ||
                                                0,
                                            )
                                          }}
                                        </time>
                                      </span>
                                    </UTooltip>
                                  </div>
                                </div>
                              </td>

                              <td class="w-28 px-3 py-3 text-center align-middle whitespace-nowrap">
                                <div class="flex items-center justify-end gap-1">
                                  <UButton
                                    color="neutral"
                                    variant="ghost"
                                    size="xs"
                                    icon="i-lucide-terminal"
                                    @click="() => void loadCommand(item.command)"
                                  >
                                    {{ t('console.fill') }}
                                  </UButton>

                                  <UButton
                                    color="neutral"
                                    variant="ghost"
                                    size="xs"
                                    icon="i-lucide-x"
                                    square
                                    @click="hideRecentSession(item.sessionId)"
                                  />
                                </div>
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
                v-if="showCancelButton"
                color="neutral"
                variant="outline"
                size="lg"
                icon="i-lucide-power"
                :loading="cancelPending"
                class="flex-1 justify-center sm:flex-none sm:min-w-36"
                @click="() => void cancelCommand()"
              >
                {{ t('console.closeOutput') }}
              </UButton>

              <UButton
                v-else-if="canManualReconnect"
                color="neutral"
                variant="outline"
                size="lg"
                icon="i-lucide-rotate-cw"
                :loading="manualReconnectPending"
                class="flex-1 justify-center sm:flex-none sm:min-w-36"
                @click="() => void reconnectSession()"
              >
                {{ t('common.reconnect') }}
              </UButton>

              <UButton
                v-else
                color="primary"
                size="lg"
                :icon="isLoading ? 'i-lucide-loader-circle' : 'i-lucide-send'"
                :loading="isLoading"
                :disabled="!canStartCommand"
                class="flex-1 justify-center sm:flex-none sm:min-w-36"
                @click="() => void runCommand()"
              >
                {{ runButtonLabel }}
              </UButton>
            </div>
          </div>
        </div>
      </div>
    </div>
  </main>
</template>

<style scoped>
.console-input :deep(input),
.console-input :deep(textarea) {
  font-family: 'JetBrains Mono', monospace;
}

.terminal-host :deep(.xterm) {
  height: 100%;
  padding: 0.75rem !important;
}

.terminal-host :deep(.xterm-viewport) {
  -ms-overflow-style: none;
  background-color: transparent !important;
  scrollbar-width: none;
}

.terminal-host :deep(.xterm-viewport::-webkit-scrollbar) {
  width: 0;
  height: 0;
}
</style>

<script setup lang="ts">
import { useStorage } from '@vueuse/core';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';
import { Terminal } from '@xterm/xterm';
import InputAutocomplete from '~/components/InputAutocomplete.vue';
import TextareaAutocomplete from '~/components/TextareaAutocomplete.vue';
import { useConsoleSession } from '~/composables/useConsoleSession';
import { useDialog } from '~/composables/useDialog';
import type { AutoCompleteOptions } from '~/types/autocomplete';
import { disableOpacity, enableOpacity } from '~/utils';
import { formatRelativeTime, type RelativeTimeInput } from '~/utils/relativeTime';
import { formatDateTime, toIsoString } from '~/utils/date';
import { usePageShell } from '~/composables/usePageShell';
const { locale, t } = useI18n();

const ACTIVE_SESSION_STATUSES = ['starting', 'running', 'reconnecting'];

let flushFrame: number | null = null;
let fitFrame: number | null = null;
let terminalResizeObserver: ResizeObserver | null = null;
let didInitialRender = false;
let renderedChunkCount = 0;

const config = useYtpConfig();
const toast = useNotification();
const dialog = useDialog();
const consoleSession = useConsoleSession();
const pageShell = usePageShell('console');
const relativeTime = (value: RelativeTimeInput): string => formatRelativeTime(value, locale.value);

const terminal = shallowRef<Terminal | null>(null);
const terminalFit = shallowRef<FitAddon | null>(null);
const command = ref('');
const manualReconnectPending = ref(false);
const cancelPending = ref(false);
const terminal_window = useTemplateRef<HTMLDivElement>('terminal_window');
const commandInput = ref<InstanceType<typeof InputAutocomplete> | null>(null);
const commandTextarea = ref<InstanceType<typeof TextareaAutocomplete> | null>(null);
const storedCommand = useStorage<string>('console_command', '');

const historyCardUi = {
  body: 'space-y-3 p-4',
};

const ytDlpOptions = computed<AutoCompleteOptions>(() =>
  config.ytdlp_options.flatMap((opt) =>
    opt.flags.map((flag) => ({ value: flag, description: opt.description || '' })),
  ),
);

const bufferedTranscript = consoleSession.bufferedTranscript;
const recentSessions = consoleSession.recentSessions;
const sessionStatus = computed(() => consoleSession.state.value.status);
const sessionError = computed(() => consoleSession.state.value.error);
const sessionExitCode = computed(() => consoleSession.state.value.exitCode);
const hasActiveSession = computed(() => Boolean(consoleSession.state.value.sessionId));
const displayCommand = computed(() => command.value.trim().replace(/^yt-dlp\b\s*/i, ''));
const runnableCommand = computed(() => displayCommand.value.replace(/\n/g, ' ').trim());
const hasValidCommand = computed(() => Boolean(runnableCommand.value));
const isLoading = computed(() => consoleSession.isLoading.value);
const isMultiLineInput = computed(() => Boolean(command.value && command.value.includes('\n')));
const recentSessionEntries = computed(() => recentSessions.value);
const canManualReconnect = computed(() => sessionStatus.value === 'reconnecting');
const showCancelButton = computed(() =>
  ['starting', 'running', 'reconnecting'].includes(sessionStatus.value),
);
const isStartBlocked = computed(() => isLoading.value);
const canStartCommand = computed(() => !isStartBlocked.value && hasValidCommand.value);
const runButtonLabel = computed(() => {
  if (runnableCommand.value === 'clear') {
    return t('common.clearOutput');
  }

  if (
    consoleSession.state.value.command.trim() &&
    consoleSession.state.value.command.trim() === displayCommand.value &&
    ['finished', 'interrupted', 'expired', 'error'].includes(sessionStatus.value)
  ) {
    return t('console.runAgain');
  }

  return t('console.runCommand');
});
const sessionErrorTitle = computed(() => {
  if (typeof sessionExitCode.value === 'number') {
    return t('console.commandFailed');
  }

  return hasActiveSession.value ? t('console.streamFailed') : t('console.requestFailed');
});
const sessionStatusLabel = computed(() => {
  switch (sessionStatus.value) {
    case 'starting':
      return t('common.starting');

    case 'running':
      return t('common.streaming');

    case 'reconnecting':
      return t('console.reconnectingStatus');

    case 'finished':
      return sessionExitCode.value === 0 ? t('console.finished') : t('console.failed');

    case 'interrupted':
      return t('console.interruptedStatus');

    case 'expired':
      return t('console.expired');

    case 'error':
      return t('console.failed');

    default:
      return t('console.idle');
  }
});
const sessionStatusColor = computed(() => {
  switch (sessionStatus.value) {
    case 'starting':
    case 'running':
      return 'info';

    case 'reconnecting':
    case 'interrupted':
    case 'expired':
      return 'warning';

    case 'finished':
      return sessionExitCode.value === 0 ? 'success' : 'error';

    case 'error':
      return 'error';

    default:
      return 'neutral';
  }
});
const sessionStatusIcon = computed(() => {
  switch (sessionStatus.value) {
    case 'starting':
    case 'running':
    case 'reconnecting':
      return 'i-lucide-loader-circle';

    case 'finished':
      return sessionExitCode.value === 0 ? 'i-lucide-circle-check' : 'i-lucide-triangle-alert';

    case 'interrupted':
      return 'i-lucide-circle-off';

    case 'expired':
      return 'i-lucide-clock-3';

    case 'error':
      return 'i-lucide-triangle-alert';

    default:
      return 'i-lucide-circle-dot';
  }
});
const sessionStatusSpinning = computed(() => ACTIVE_SESSION_STATUSES.includes(sessionStatus.value));

const isRecentSessionFailed = (item: (typeof recentSessions.value)[number]): boolean => {
  return item.status === 'completed' && item.exitCode !== null && item.exitCode !== 0;
};

const recentSessionStatusLabel = (item: (typeof recentSessions.value)[number]): string => {
  if (isRecentSessionFailed(item)) {
    return t('console.failed');
  }

  switch (item.status) {
    case 'starting':
      return t('common.starting');

    case 'running':
      return t('common.running');

    default:
      return t('common.completed');
  }
};

const recentSessionStatusColor = (
  item: (typeof recentSessions.value)[number],
): 'success' | 'error' | 'info' | 'neutral' => {
  if (isRecentSessionFailed(item)) {
    return 'error';
  }

  switch (item.status) {
    case 'starting':
    case 'running':
      return 'info';

    default:
      return item.exitCode === 0 ? 'success' : 'neutral';
  }
};

const recentSessionStatusIcon = (item: (typeof recentSessions.value)[number]): string => {
  if (isRecentSessionFailed(item)) {
    return 'i-lucide-triangle-alert';
  }

  switch (item.status) {
    case 'starting':
    case 'running':
      return 'i-lucide-loader-circle';

    default:
      return item.exitCode === 0 ? 'i-lucide-circle-check' : 'i-lucide-circle-dot';
  }
};

const recentSessionStatusSpinning = (item: (typeof recentSessions.value)[number]): boolean => {
  return ['starting', 'running'].includes(item.status);
};
watch(command, (value) => {
  storedCommand.value = value;
});

watch(
  () => sessionStatus.value,
  async (value, oldValue) => {
    const sessionCommand = consoleSession.state.value.command.trim();
    if (sessionCommand && (!command.value.trim() || ['expired', 'interrupted'].includes(value))) {
      command.value = sessionCommand;
    }

    if (
      oldValue &&
      oldValue !== value &&
      ACTIVE_SESSION_STATUSES.includes(oldValue) &&
      !ACTIVE_SESSION_STATUSES.includes(value)
    ) {
      await nextTick();
      await focusInput();
    }
  },
);

watch(
  () => sessionError.value,
  (value, oldValue) => {
    if (!value || value === oldValue) {
      return;
    }

    toast.error(value);
  },
);

watch(
  () => bufferedTranscript.value.length,
  (length, previousLength = 0) => {
    if (!terminal.value) {
      return;
    }

    if (!didInitialRender) {
      restoreBufferedTerminalOutput();
      return;
    }

    if (length < previousLength) {
      restoreBufferedTerminalOutput();
      return;
    }

    scheduleFlush();
  },
);

watch(isMultiLineInput, async (value, oldValue) => {
  if (value === oldValue) {
    return;
  }

  await focusInput();
});

watch(
  () => config.app.console_enabled,
  async () => {
    if (config.app.console_enabled) {
      return;
    }

    toast.error(t('console.disabled'));
    await navigateTo('/');
  },
);

const getInputElement = (): HTMLInputElement | HTMLTextAreaElement | null => {
  const element = isMultiLineInput.value
    ? commandTextarea.value?.$el?.querySelector('textarea')
    : commandInput.value?.$el?.querySelector('input');

  if (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement) {
    return element;
  }

  return null;
};

const focusInput = async (): Promise<void> => {
  await nextTick();
  getInputElement()?.focus();
};

const scheduleTerminalFit = (): void => {
  if (!terminal.value || !terminalFit.value || fitFrame) {
    return;
  }

  fitFrame = window.requestAnimationFrame(() => {
    fitFrame = null;

    if (!terminal.value || !terminalFit.value) {
      return;
    }

    terminalFit.value.fit();
  });
};

const bindTerminalResizeObserver = (): void => {
  if (!terminal_window.value || typeof ResizeObserver === 'undefined') {
    return;
  }

  terminalResizeObserver?.disconnect();
  terminalResizeObserver = new ResizeObserver(() => {
    scheduleTerminalFit();
  });
  terminalResizeObserver.observe(terminal_window.value);
};

const restoreBufferedTerminalOutput = (): void => {
  if (!terminal.value) {
    return;
  }

  terminal.value.clear();
  renderedChunkCount = 0;

  if (bufferedTranscript.value.length < 1) {
    didInitialRender = true;
    scheduleTerminalFit();
    return;
  }

  terminal.value.write(bufferedTranscript.value.join(''));
  renderedChunkCount = bufferedTranscript.value.length;
  didInitialRender = true;
  scheduleTerminalFit();

  window.requestAnimationFrame(() => {
    scheduleTerminalFit();
  });
};

const flushTerminal = (): void => {
  if (!terminal.value) {
    return;
  }

  if (!didInitialRender) {
    didInitialRender = true;
  }

  if (bufferedTranscript.value.length < renderedChunkCount) {
    restoreBufferedTerminalOutput();
    return;
  }

  if (bufferedTranscript.value.length === renderedChunkCount) {
    return;
  }

  const chunk = bufferedTranscript.value.slice(renderedChunkCount).join('');
  if (!chunk) {
    return;
  }

  terminal.value.write(chunk);
  renderedChunkCount = bufferedTranscript.value.length;
};

const scheduleFlush = (): void => {
  if (flushFrame) {
    return;
  }

  flushFrame = window.requestAnimationFrame(() => {
    flushFrame = null;
    flushTerminal();
  });
};

const handleTerminalResize = (): void => {
  scheduleTerminalFit();
};

const handlePageLeave = (): void => {
  consoleSession.disconnect();
};

const ensureTerminal = async (): Promise<void> => {
  if (terminal.value) {
    return;
  }

  terminalFit.value = new FitAddon();
  terminal.value = new Terminal({
    fontSize: 14,
    fontFamily: "'JetBrains Mono', monospace",
    cursorBlink: false,
    cursorStyle: 'underline',
    convertEol: true,
    disableStdin: true,
    scrollback: 2000,
    theme: {
      background: '#09090b',
      foreground: '#f4f4f5',
      cursor: '#60a5fa',
      selectionBackground: 'rgba(255, 255, 255, 0.18)',
    },
  });

  terminal.value.loadAddon(terminalFit.value);

  await nextTick();

  if (terminal_window.value) {
    terminal.value.open(terminal_window.value);
  }

  bindTerminalResizeObserver();
  scheduleTerminalFit();
};

const handleKeyDown = async (event: KeyboardEvent): Promise<void> => {
  if (event.defaultPrevented || event.isComposing || event.key !== 'Enter') {
    return;
  }

  const target = event.target as HTMLInputElement | HTMLTextAreaElement;
  const isTextarea = target.tagName === 'TEXTAREA';

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

    const textarea = commandTextarea.value?.$el?.querySelector('textarea');
    if (textarea instanceof HTMLTextAreaElement) {
      textarea.setSelectionRange(cursorPos + 1, cursorPos + 1);
      textarea.focus();
    }
  }
};

const handlePaste = async (event: ClipboardEvent): Promise<void> => {
  if (event.defaultPrevented) {
    return;
  }

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

  const textarea = commandTextarea.value?.$el?.querySelector('textarea');
  if (textarea instanceof HTMLTextAreaElement) {
    const newPos = start + pastedText.length;
    textarea.setSelectionRange(newPos, newPos);
    textarea.focus();
  }
};

const runCommand = async (): Promise<void> => {
  if (!canStartCommand.value) {
    return;
  }

  if (config.app.console_enabled !== true) {
    await navigateTo('/');
    toast.error(t('console.disabled'));
    return;
  }

  if (displayCommand.value !== command.value.trim()) {
    command.value = displayCommand.value;
    await nextTick();
  }

  if (runnableCommand.value === 'clear') {
    await clearOutput(true);
    return;
  }

  await ensureTerminal();

  const started = await consoleSession.startSession({
    command: runnableCommand.value,
    displayCommand: displayCommand.value,
  });

  if (started) {
    storedCommand.value = '';
  }
};

const runHelp = async (): Promise<void> => {
  if (isStartBlocked.value) {
    return;
  }

  command.value = '--help';
  await nextTick();
  await runCommand();
};

const reconnectSession = async (): Promise<void> => {
  if (!canManualReconnect.value || manualReconnectPending.value) {
    return;
  }

  manualReconnectPending.value = true;

  try {
    await consoleSession.restoreSession();
    restoreBufferedTerminalOutput();
  } finally {
    manualReconnectPending.value = false;
    await focusInput();
  }
};

const cancelCommand = async (): Promise<void> => {
  if (!showCancelButton.value || cancelPending.value) {
    return;
  }

  cancelPending.value = true;

  try {
    const result = await consoleSession.cancelSession();
    if (result.status === 'error' && result.message) {
      toast.error(result.message);
    }
  } finally {
    cancelPending.value = false;
    await focusInput();
  }
};

const clearOutput = async (withCommand: boolean = false): Promise<void> => {
  consoleSession.clearTranscript();
  terminal.value?.clear();
  renderedChunkCount = 0;
  didInitialRender = true;

  if (withCommand) {
    command.value = '';
    storedCommand.value = '';
  }

  await focusInput();
};

const loadCommand = async (cmd: string): Promise<void> => {
  command.value = cmd;
  await nextTick();
  await focusInput();
};

const hideRecentSession = (sessionId: string): void => {
  consoleSession.hideRecentSession(sessionId);
};

const hideRecentSessions = async (): Promise<void> => {
  if (recentSessionEntries.value.length < 1) {
    return;
  }

  const { status } = await dialog.confirmDialog({
    title: t('common.pleaseConfirm'),
    message: t('console.hideRunsConfirm'),
    confirmText: t('console.hideRuns'),
    confirmColor: 'error',
  });

  if (!status) {
    return;
  }

  consoleSession.clearRecentSessions();
  await focusInput();
};

const replayRecentSession = async (item: (typeof recentSessions.value)[number]): Promise<void> => {
  try {
    await consoleSession.replaySession(item);
    restoreBufferedTerminalOutput();
  } catch {
    consoleSession.hideRecentSession(item.sessionId);
  } finally {
    await nextTick();
    await focusInput();
  }
};

onMounted(async () => {
  if (config.app.console_enabled !== true) {
    toast.error(t('console.disabled'));
    await navigateTo('/');
    return;
  }

  window.addEventListener('resize', handleTerminalResize);
  window.addEventListener('pagehide', handlePageLeave);
  window.addEventListener('beforeunload', handlePageLeave);
  disableOpacity();

  await ensureTerminal();
  await consoleSession.restoreSession();
  await consoleSession.fetchRecentSessions();
  restoreBufferedTerminalOutput();

  if (storedCommand.value.trim()) {
    command.value = storedCommand.value;
    await nextTick();
  } else if (consoleSession.state.value.command.trim()) {
    command.value = consoleSession.state.value.command;
    await nextTick();
  }

  await focusInput();
});

onBeforeUnmount(() => {
  consoleSession.disconnect();
  window.removeEventListener('pagehide', handlePageLeave);
  window.removeEventListener('beforeunload', handlePageLeave);
  terminalResizeObserver?.disconnect();
  terminalResizeObserver = null;

  if (flushFrame) {
    window.cancelAnimationFrame(flushFrame);
    flushFrame = null;
  }

  if (fitFrame) {
    window.cancelAnimationFrame(fitFrame);
    fitFrame = null;
  }

  terminal.value?.dispose();
  terminal.value = null;
  terminalFit.value = null;
  didInitialRender = false;
  renderedChunkCount = 0;
  manualReconnectPending.value = false;
  cancelPending.value = false;

  window.removeEventListener('resize', handleTerminalResize);
  enableOpacity();
});
</script>
