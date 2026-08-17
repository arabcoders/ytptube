import { describe, expect, it } from 'bun:test';

import { withWsTicket } from '~/composables/useAppSocket';

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
