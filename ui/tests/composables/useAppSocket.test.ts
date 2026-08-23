import { describe, expect, it } from 'bun:test';

import {
  createConnectionAttempt,
  createConnectionDeadline,
  withWsTicket,
} from '~/composables/useAppSocket';

describe('createConnectionDeadline', () => {
  it('keeps total deadline', () => {
    let now = 100;
    const deadline = createConnectionDeadline(() => now);

    now += 4900;
    expect(deadline.remaining()).toBe(100);
    now += 100;
    expect(deadline.remaining()).toBe(0);
  });

  it('expires pending timer', async () => {
    let called = false;
    const deadline = createConnectionDeadline(() => 0);
    deadline.arm(() => {
      called = true;
    }, 1);

    await new Promise((resolve) => setTimeout(resolve, 5));
    expect(called).toBe(true);
  });

  it('clears pending timer', async () => {
    let called = false;
    const deadline = createConnectionDeadline(() => 0);
    deadline.arm(() => {
      called = true;
    }, 1);
    deadline.clear();

    await new Promise((resolve) => setTimeout(resolve, 5));
    expect(called).toBe(false);
  });

  it('replaces pending timer', async () => {
    let first = false;
    let second = false;
    const deadline = createConnectionDeadline(() => 0);
    deadline.arm(() => {
      first = true;
    }, 10);
    deadline.arm(() => {
      second = true;
    }, 1);

    await new Promise((resolve) => setTimeout(resolve, 5));
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
