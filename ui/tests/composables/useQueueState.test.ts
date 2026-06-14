import { beforeEach, describe, expect, it, spyOn } from 'bun:test';

import * as utils from '~/utils/index';
import { useQueueState } from '~/composables/useQueueState';
import type { StoreItem } from '~/types/store';

const createMockResponse = (jsonData: unknown): Response => {
  return {
    ok: true,
    status: 200,
    headers: new Headers({ 'Content-Type': 'application/json' }),
    redirected: false,
    statusText: 'OK',
    type: 'basic',
    url: '',
    body: null,
    bodyUsed: false,
    clone() {
      return this;
    },
    async json() {
      return jsonData;
    },
    text: async () => JSON.stringify(jsonData),
    arrayBuffer: async () => new ArrayBuffer(0),
    blob: async () => new Blob(),
    formData: async () => new FormData(),
  } as Response;
};

const makeItem = (id: string, status: StoreItem['status'] = null): StoreItem => {
  return {
    _id: id,
    id,
    title: `Video ${id}`,
    description: '',
    url: `https://example.com/${id}`,
    preset: 'default',
    folder: '',
    download_dir: '/downloads',
    temp_dir: '/tmp',
    status,
    error: null,
    cookies: '',
    template: '',
    template_chapter: '',
    timestamp: 0,
    is_live: false,
    datetime: '',
    live_in: null,
    file_size: null,
    cli: '',
    auto_start: true,
    options: {},
    sidecar: {},
    extras: {},
  };
};

describe('useQueueState', () => {
  beforeEach(() => {
    useQueueState().clearAll();
  });

  it('load_metadata', async () => {
    const requestSpy = spyOn(utils, 'request');
    requestSpy.mockResolvedValueOnce(
      createMockResponse({
        queue: { a: makeItem('a') },
        queue_count: 3,
        queue_loaded: 1,
        queue_limit: 1,
      }),
    );

    const queue = useQueueState();
    await queue.loadQueue();

    expect(queue.count()).toBe(3);
    expect(queue.shown()).toBe(1);
    expect(queue.hasMore()).toBe(true);
    expect(queue.limit).toBe(1);
    expect(queue.get('a')?.title).toBe('Video a');

    requestSpy.mockRestore();
  });

  it('add_respects_limit', () => {
    const queue = useQueueState();
    queue.addAll({ a: makeItem('a') }, { queue_count: 1, queue_loaded: 1, queue_limit: 1 });

    queue.add('b', makeItem('b'));

    expect(queue.count()).toBe(2);
    expect(queue.shown()).toBe(1);
    expect(queue.get('b')).toBeNull();
  });

  it('update_reveals_active', () => {
    const queue = useQueueState();
    queue.addAll({ a: makeItem('a') }, { queue_count: 2, queue_loaded: 1, queue_limit: 1 });

    queue.update('b', makeItem('b', 'downloading'));

    expect(queue.count()).toBe(2);
    expect(queue.shown()).toBe(2);
    expect(queue.get('b')?.status).toBe('downloading');
  });

  it('drop_hidden_decrements_total', () => {
    const queue = useQueueState();
    queue.addAll({ a: makeItem('a') }, { queue_count: 2, queue_loaded: 1, queue_limit: 1 });

    queue.drop('b');

    expect(queue.count()).toBe(1);
    expect(queue.shown()).toBe(1);
  });
});
