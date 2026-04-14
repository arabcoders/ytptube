import { fetchEventSource } from '@microsoft/fetch-event-source';
import type { EventSourceMessage } from '@microsoft/fetch-event-source';
import { useStorage } from '@vueuse/core';
import { computed, ref } from 'vue';

import { parse_api_error, parse_api_response, request, uri } from '~/utils';

type ConsoleSessionStatus =
  | 'idle'
  | 'starting'
  | 'running'
  | 'reconnecting'
  | 'finished'
  | 'interrupted'
  | 'expired'
  | 'error';

type ConsoleSessionState = {
  sessionId: string | null;
  command: string;
  status: ConsoleSessionStatus;
  lastEventId: string | null;
  exitCode: number | null;
  transcript: Array<string>;
  error: string;
};

type ConsoleSessionResponse = {
  session_id?: string | null;
  sessionId?: string | null;
  command?: string | null;
  status?: string | null;
  last_event_id?: string | number | null;
  lastEventId?: string | number | null;
  exit_code?: number | null;
  exitCode?: number | null;
  expired?: boolean | null;
  not_found?: boolean | null;
};

type StartConsoleSessionInput = {
  command: string;
  displayCommand?: string;
};

type CancelConsoleSessionResult = {
  status: 'cancelled' | 'missing' | 'error';
  message?: string;
};

const STORAGE_KEY = 'console_session_state';
const MAX_TRANSCRIPT_CHUNKS = 1500;
const MAX_TRANSCRIPT_CHARS = 120000;
const RECONNECT_DELAY_MS = 1500;

const DEFAULT_STATE: ConsoleSessionState = {
  sessionId: null,
  command: '',
  status: 'idle',
  lastEventId: null,
  exitCode: null,
  transcript: [],
  error: '',
};

class ConsoleSessionExpiredError extends Error {}

const trimTranscript = (transcript: Array<string>): Array<string> => {
  const next = [...transcript];

  while (next.length > MAX_TRANSCRIPT_CHUNKS) {
    next.shift();
  }

  let totalChars = next.reduce((sum, chunk) => sum + chunk.length, 0);
  while (next.length > 1 && totalChars > MAX_TRANSCRIPT_CHARS) {
    totalChars -= next[0]?.length || 0;
    next.shift();
  }

  return next;
};

const isActiveSessionStatus = (status: ConsoleSessionStatus | null | undefined): boolean => {
  return ['starting', 'running', 'reconnecting'].includes(status || '');
};

const normalizeStatus = (
  status: string | null | undefined,
  fallback: ConsoleSessionStatus = 'idle',
): ConsoleSessionStatus => {
  switch ((status || '').trim().toLowerCase()) {
    case 'starting':
    case 'pending':
    case 'queued':
      return 'starting';

    case 'active':
    case 'open':
    case 'running':
    case 'streaming':
      return 'running';

    case 'reconnecting':
      return 'reconnecting';

    case 'complete':
    case 'completed':
    case 'closed':
    case 'done':
    case 'exited':
    case 'finished':
      return 'finished';

    case 'interrupted':
      return 'interrupted';

    case 'failed':
    case 'error':
      return 'error';

    case 'expired':
    case 'missing':
    case 'not_found':
      return 'expired';

    case 'idle':
      return 'idle';

    default:
      return fallback;
  }
};

const normalizePersistedState = (
  input: Partial<ConsoleSessionState> | null | undefined,
  { allowActiveWithoutSessionId = false }: { allowActiveWithoutSessionId?: boolean } = {},
): ConsoleSessionState => {
  const sessionId =
    typeof input?.sessionId === 'string' && input.sessionId.trim() ? input.sessionId : null;
  const status = normalizeStatus(input?.status, DEFAULT_STATE.status);
  const hasDetachedActiveStatus = isActiveSessionStatus(status) && sessionId === null;

  return {
    sessionId,
    command: typeof input?.command === 'string' ? input.command : DEFAULT_STATE.command,
    status: hasDetachedActiveStatus && !allowActiveWithoutSessionId ? 'idle' : status,
    lastEventId:
      input?.lastEventId === null || input?.lastEventId === undefined
        ? null
        : String(input.lastEventId),
    exitCode: typeof input?.exitCode === 'number' ? input.exitCode : null,
    transcript: trimTranscript(
      Array.isArray(input?.transcript)
        ? input.transcript.filter((chunk): chunk is string => typeof chunk === 'string')
        : DEFAULT_STATE.transcript,
    ),
    error: typeof input?.error === 'string' ? input.error : DEFAULT_STATE.error,
  };
};

const sessionState = useStorage<ConsoleSessionState>(STORAGE_KEY, { ...DEFAULT_STATE });
const streamController = ref<AbortController | null>(null);
const reconnectTimer = ref<ReturnType<typeof setTimeout> | null>(null);
const connectionNonce = ref(0);

sessionState.value = normalizePersistedState(sessionState.value);

const updateState = (patch: Partial<ConsoleSessionState>): void => {
  sessionState.value = normalizePersistedState(
    {
      ...sessionState.value,
      ...patch,
    },
    { allowActiveWithoutSessionId: true },
  );
};

const appendTranscript = (chunk: string): void => {
  if (!chunk) {
    return;
  }

  updateState({ transcript: trimTranscript([...sessionState.value.transcript, chunk]) });
};

const stopReconnectTimer = (): void => {
  if (!reconnectTimer.value) {
    return;
  }

  clearTimeout(reconnectTimer.value);
  reconnectTimer.value = null;
};

const stopStream = (): void => {
  stopReconnectTimer();
  streamController.value?.abort();
  streamController.value = null;
};

const clearTranscript = (): void => {
  const isActive = isActiveSessionStatus(sessionState.value.status);

  updateState({
    transcript: [],
    sessionId: isActive ? sessionState.value.sessionId : null,
    status: isActive ? sessionState.value.status : 'idle',
    lastEventId: isActive ? sessionState.value.lastEventId : null,
    exitCode: isActive ? sessionState.value.exitCode : null,
    error: '',
  });
};

const markExpired = (): void => {
  stopStream();
  updateState({ status: 'expired', error: '' });
};

const finishSession = (
  status: ConsoleSessionStatus = 'finished',
  exitCode: number | null = sessionState.value.exitCode,
): void => {
  stopStream();
  updateState({
    status,
    exitCode,
    error: '',
  });
};

const scheduleReconnect = (): void => {
  if (!sessionState.value.sessionId) {
    return;
  }

  stopReconnectTimer();
  updateState({ status: 'reconnecting', error: '' });
  reconnectTimer.value = setTimeout(() => {
    reconnectTimer.value = null;
    if (!sessionState.value.sessionId || !isActiveSessionStatus(sessionState.value.status)) {
      return;
    }

    void connectStream();
  }, RECONNECT_DELAY_MS);
};

const shouldSkipEvent = (eventId: string): boolean => {
  const lastEventId = sessionState.value.lastEventId;
  if (!lastEventId) {
    return false;
  }

  if (eventId === lastEventId) {
    return true;
  }

  if (/^\d+$/.test(eventId) && /^\d+$/.test(lastEventId)) {
    return Number(eventId) <= Number(lastEventId);
  }

  return false;
};

const readJson = async (response: Response): Promise<unknown> => {
  try {
    return await response.clone().json();
  } catch {
    return null;
  }
};

const parseResponseError = async (response: Response): Promise<string> => {
  const payload = await readJson(response);
  if (payload) {
    return await parse_api_error(payload);
  }

  try {
    const text = await response.text();
    if (text) {
      return text;
    }
  } catch {
    return response.statusText || 'Request failed.';
  }

  return response.statusText || 'Request failed.';
};

const refreshSessionMetadata = async (): Promise<void> => {
  if (!sessionState.value.sessionId) {
    return;
  }

  try {
    const payload = await readSessionResponse(
      `/api/system/terminal/${encodeURIComponent(sessionState.value.sessionId)}`,
    );
    if (!payload) {
      return;
    }

    updateState(normalizeResponse(payload));
  } catch (error) {
    if (error instanceof ConsoleSessionExpiredError) {
      markExpired();
    }
  }
};

const normalizeResponse = (payload: ConsoleSessionResponse): Partial<ConsoleSessionState> => {
  const status =
    payload.expired || payload.not_found
      ? 'expired'
      : normalizeStatus(payload.status, sessionState.value.status);

  const sessionId = payload.session_id ?? payload.sessionId;
  const lastEventId = payload.last_event_id ?? payload.lastEventId;
  const exitCode = payload.exit_code ?? payload.exitCode;

  return {
    sessionId: sessionId === undefined ? sessionState.value.sessionId : sessionId,
    command: payload.command ?? sessionState.value.command,
    status,
    lastEventId:
      lastEventId === undefined || lastEventId === null
        ? sessionState.value.lastEventId
        : String(lastEventId),
    exitCode: exitCode === undefined ? sessionState.value.exitCode : exitCode,
    error:
      status === 'error'
        ? sessionState.value.error ||
          (typeof exitCode === 'number' && exitCode !== 0
            ? `Command exited with code ${exitCode}.`
            : '')
        : '',
  };
};

const readSessionResponse = async (
  path: string,
  { allowMissing = false }: { allowMissing?: boolean } = {},
): Promise<ConsoleSessionResponse | null> => {
  const response = await request(path);

  if ([404, 410].includes(response.status)) {
    if (allowMissing) {
      return null;
    }

    throw new ConsoleSessionExpiredError(await parseResponseError(response));
  }

  if (!response.ok) {
    throw new Error(await parseResponseError(response));
  }

  return await parse_api_response<ConsoleSessionResponse>(response.json());
};

const connectStream = async (): Promise<void> => {
  if (!sessionState.value.sessionId) {
    return;
  }

  stopStream();

  const controller = new AbortController();
  let finalMetadataRefresh: Promise<void> | null = null;
  const nonce = connectionNonce.value + 1;
  connectionNonce.value = nonce;
  streamController.value = controller;

  const search = new URLSearchParams();
  if (sessionState.value.lastEventId) {
    search.set('since', sessionState.value.lastEventId);
  }

  const url = uri(
    `/api/system/terminal/${encodeURIComponent(sessionState.value.sessionId)}/stream${search.size > 0 ? `?${search.toString()}` : ''}`,
  );

  const headers: Record<string, string> = {
    Accept: 'text/event-stream',
  };

  if (sessionState.value.lastEventId) {
    headers['Last-Event-ID'] = sessionState.value.lastEventId;
  }

  try {
    await fetchEventSource(url, {
      method: 'GET',
      headers,
      credentials: 'same-origin',
      signal: controller.signal,
      openWhenHidden: true,
      onopen: async (response) => {
        if (response.ok) {
          updateState({ status: 'running', error: '' });
          return;
        }

        if ([404, 410].includes(response.status)) {
          throw new ConsoleSessionExpiredError(await parseResponseError(response));
        }

        throw new Error(await parseResponseError(response));
      },
      onmessage: (event: EventSourceMessage) => {
        if (event.id && shouldSkipEvent(event.id)) {
          return;
        }

        let payload: Record<string, unknown> | null = null;
        if (event.data) {
          try {
            payload = JSON.parse(event.data) as Record<string, unknown>;
          } catch {
            payload = null;
          }
        }

        if (event.id) {
          updateState({ lastEventId: event.id });
        }

        if (event.event === 'expired' || payload?.type === 'expired' || payload?.expired === true) {
          markExpired();
          return;
        }

        if (event.event === 'status') {
          updateState(normalizeResponse(payload as ConsoleSessionResponse));
          return;
        }

        if (event.event === 'output') {
          const line = typeof payload?.line === 'string' ? payload.line : event.data;
          appendTranscript(`${line || ''}\n`);
          return;
        }

        if (event.event === 'close') {
          const nextExitCode =
            typeof payload?.exitcode === 'number'
              ? payload.exitcode
              : typeof payload?.exit_code === 'number'
                ? payload.exit_code
                : sessionState.value.exitCode;
          const nextStatus = normalizeStatus(
            typeof payload?.status === 'string' ? payload.status : null,
            'finished',
          );

          if (payload?.expired === true || payload?.status === 'expired') {
            markExpired();
            return;
          }

          finishSession(nextStatus === 'error' ? 'error' : nextStatus, nextExitCode);
          finalMetadataRefresh = refreshSessionMetadata();
        }
      },
      onclose: () => {
        if (controller.signal.aborted || nonce !== connectionNonce.value) {
          return;
        }

        if (!sessionState.value.sessionId || !isActiveSessionStatus(sessionState.value.status)) {
          return;
        }

        scheduleReconnect();
      },
      onerror: (error) => {
        throw error instanceof Error ? error : new Error(String(error));
      },
    });

    if (finalMetadataRefresh) {
      await finalMetadataRefresh;
    }
  } catch (error) {
    if (controller.signal.aborted || nonce !== connectionNonce.value) {
      return;
    }

    if (error instanceof ConsoleSessionExpiredError) {
      markExpired();
      return;
    }

    if (sessionState.value.sessionId && isActiveSessionStatus(sessionState.value.status)) {
      scheduleReconnect();
      return;
    }

    const message = error instanceof Error ? error.message : String(error);
    appendTranscript(`Error: ${message}\n`);
    updateState({ status: 'error', error: message });
  } finally {
    if (streamController.value === controller) {
      streamController.value = null;
    }
  }
};

const restoreSession = async (): Promise<void> => {
  try {
    if (sessionState.value.sessionId) {
      const payload = await readSessionResponse(
        `/api/system/terminal/${encodeURIComponent(sessionState.value.sessionId)}`,
      );

      if (payload) {
        updateState(normalizeResponse(payload));
      }

      if (sessionState.value.sessionId && isActiveSessionStatus(sessionState.value.status)) {
        await connectStream();
      }

      return;
    }

    if (
      sessionState.value.sessionId ||
      sessionState.value.command ||
      sessionState.value.transcript.length > 0
    ) {
      return;
    }

    const active = await readSessionResponse('/api/system/terminal/active', { allowMissing: true });
    if (!active) {
      return;
    }

    updateState(normalizeResponse(active));

    if (sessionState.value.sessionId && isActiveSessionStatus(sessionState.value.status)) {
      await connectStream();
    }
  } catch (error) {
    if (error instanceof ConsoleSessionExpiredError) {
      markExpired();
      return;
    }

    if (sessionState.value.sessionId && isActiveSessionStatus(sessionState.value.status)) {
      await connectStream();
    }
  }
};

const startSession = async ({
  command,
  displayCommand = command,
}: StartConsoleSessionInput): Promise<boolean> => {
  stopStream();
  updateState({
    sessionId: null,
    command: displayCommand,
    status: 'starting',
    lastEventId: null,
    exitCode: null,
    error: '',
  });

  try {
    const response = await request('/api/system/terminal', {
      method: 'POST',
      body: JSON.stringify({ command }),
    });

    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }

    const payload = await parse_api_response<ConsoleSessionResponse>(response.json());
    updateState({
      ...normalizeResponse(payload),
      command: displayCommand,
      status: normalizeStatus(payload.status, 'running'),
      lastEventId: null,
      exitCode: null,
      transcript: trimTranscript([
        ...sessionState.value.transcript,
        'user@YTPTube ~\n',
        `$ yt-dlp ${displayCommand}\n`,
      ]),
      error: '',
    });

    if (sessionState.value.sessionId && isActiveSessionStatus(sessionState.value.status)) {
      await connectStream();
    }

    return Boolean(sessionState.value.sessionId);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    appendTranscript(`Error: ${message}\n`);
    updateState({ status: 'error', error: message });
    return false;
  }
};

const cancelSession = async (): Promise<CancelConsoleSessionResult> => {
  if (!sessionState.value.sessionId) {
    return { status: 'missing', message: 'No active terminal session found.' };
  }

  try {
    const response = await request(
      `/api/system/terminal/${encodeURIComponent(sessionState.value.sessionId)}`,
      {
        method: 'DELETE',
      },
    );

    if (response.status === 404) {
      await refreshSessionMetadata();
      return { status: 'missing', message: 'Terminal session not found.' };
    }

    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }

    updateState({ error: '' });
    return { status: 'cancelled' };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    updateState({ error: message });
    return { status: 'error', message };
  }
};

const resetState = (): void => {
  stopStream();
  sessionState.value = { ...DEFAULT_STATE };
};

const useConsoleSession = () => {
  return {
    state: sessionState,
    bufferedTranscript: computed(() => sessionState.value.transcript.slice()),
    isLoading: computed(() => isActiveSessionStatus(sessionState.value.status)),
    clearTranscript,
    restoreSession,
    startSession,
    cancelSession,
    disconnect: stopStream,
    __resetForTesting: resetState,
  };
};

export { useConsoleSession };
