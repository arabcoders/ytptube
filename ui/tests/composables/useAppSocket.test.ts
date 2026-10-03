import { afterEach, beforeEach, describe, expect, it, mock } from 'bun:test';

import {
  createConnectionAttempt,
  createConnectionDeadline,
  handleNotification,
  withWsTicket,
} from '~/composables/useAppSocket';
import type { EventPayload } from '~/types/sockets';

const event = (message: string): EventPayload<Record<string, unknown>> => ({
  id: 'event-id',
  created_at: '2026-08-25T00:00:00Z',
  event: 'task_finished',
  title: 'Task finished',
  message,
  data: {},
});

describe('createConnectionDeadline', () => {
  const originalSetTimeout = globalThis.setTimeout;
  const originalClearTimeout = globalThis.clearTimeout;
  let timers: Map<number, () => void>;
  let nextTimer = 0;

  beforeEach(() => {
    timers = new Map();
    globalThis.setTimeout = ((callback: TimerHandler) => {
      const id = ++nextTimer;
      timers.set(id, callback as () => void);
      return id as unknown as ReturnType<typeof setTimeout>;
    }) as typeof setTimeout;
    globalThis.clearTimeout = ((id: ReturnType<typeof setTimeout>) => {
      timers.delete(id as unknown as number);
    }) as typeof clearTimeout;
  });

  afterEach(() => {
    globalThis.setTimeout = originalSetTimeout;
    globalThis.clearTimeout = originalClearTimeout;
  });

  it('keeps total deadline', () => {
    let now = 100;
    const deadline = createConnectionDeadline(() => now);

    now += 4900;
    expect(deadline.remaining()).toBe(100);
    now += 100;
    expect(deadline.remaining()).toBe(0);
  });

  it('expires pending timer', () => {
    let called = false;
    const deadline = createConnectionDeadline(() => 0);
    deadline.arm(() => {
      called = true;
    }, 1);

    for (const callback of timers.values()) callback();
    expect(called).toBe(true);
  });

  it('clears pending timer', () => {
    let called = false;
    const deadline = createConnectionDeadline(() => 0);
    deadline.arm(() => {
      called = true;
    }, 1);
    deadline.clear();

    for (const callback of timers.values()) callback();
    expect(called).toBe(false);
  });

  it('replaces pending timer', () => {
    let first = false;
    let second = false;
    const deadline = createConnectionDeadline(() => 0);
    deadline.arm(() => {
      first = true;
    }, 10);
    deadline.arm(() => {
      second = true;
    }, 1);

    for (const callback of timers.values()) callback();
    expect(first).toBe(false);
    expect(second).toBe(true);
  });
});

describe('createConnectionAttempt', () => {
  it('cancels stale attempt', () => {
    const attempt = createConnectionAttempt(createConnectionDeadline(() => 0));

    attempt.cancel();
    expect(attempt.isActive()).toBe(false);
    expect(attempt.recover()).toBe(false);
  });

  it('recovers only once', () => {
    const attempt = createConnectionAttempt(createConnectionDeadline(() => 0));

    expect(attempt.recover()).toBe(true);
    expect(attempt.recover()).toBe(false);
    expect(attempt.isActive()).toBe(false);
  });
});

describe('withWsTicket', () => {
  it('adds_ticket_to_url', () => {
    const url = withWsTicket('wss://backend.example/base-path/ws?_=1', 'ytp_ws_a+b/c?');
    const parsed = new URL(url);
    expect(parsed.origin).toBe('wss://backend.example');
    expect(parsed.pathname).toBe('/base-path/ws');
    expect(parsed.searchParams.get('_')).toBe('1');
    expect(parsed.searchParams.get('ticket')).toBe('ytp_ws_a+b/c?');
  });

  it('keeps_url_without_ticket', () => {
    const url = 'wss://backend.example/base-path/ws?_=1';
    expect(withWsTicket(url)).toBe(url);
  });
});

describe('handleNotification', () => {
  it('hides task completion', () => {
    const success = mock(() => {});
    const toast = {
      info: mock(() => {}),
      success,
      warning: mock(() => {}),
      error: mock(() => {}),
    };

    handleNotification('task_finished', event('Task finished'), toast);

    expect(success).toHaveBeenCalledWith('Task finished', { lowPriority: true });
  });

  it('shows task failure', () => {
    const error = mock(() => {});
    const toast = {
      info: mock(() => {}),
      success: mock(() => {}),
      warning: mock(() => {}),
      error,
    };

    handleNotification('task_error', event('Task failed'), toast);

    expect(error).toHaveBeenCalledWith('Task failed', {});
  });
});
