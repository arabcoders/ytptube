import { afterEach, beforeEach, describe, expect, it, spyOn } from 'bun:test';

import * as utils from '~/utils';
import { useHistoryNfo } from '~/composables/useHistoryNfo';
import type { StoreItem } from '~/types/store';

const response = (ok = true): Response =>
  ({
    ok,
    async json() {
      return ok ? { message: 'done' } : { error: 'failed' };
    },
  }) as Response;

const item = (id: string, filename?: string): StoreItem => ({ _id: id, filename }) as StoreItem;

describe('useHistoryNfo', () => {
  let requestSpy: ReturnType<typeof spyOn>;

  beforeEach(() => {
    requestSpy = spyOn(utils, 'request');
  });

  afterEach(() => {
    requestSpy.mockRestore();
  });

  it('generates eligible items', async () => {
    requestSpy.mockResolvedValue(response());
    const selected = [item('one', 'one.mp4'), item('two')];
    const nfo = useHistoryNfo();

    await nfo.generateSelectedNfo(selected);

    expect(requestSpy).toHaveBeenCalledTimes(1);
    expect(requestSpy.mock.calls[0]?.[0]).toBe('/api/history/one/nfo');
    expect(JSON.parse((requestSpy.mock.calls[0]?.[1] as RequestInit).body as string)).toEqual({
      type: 'tv',
      overwrite: true,
    });
    expect(selected).toHaveLength(2);
  });

  it('processes items sequentially', async () => {
    let resolveFirst: ((value: Response) => void) | undefined;
    const first = new Promise<Response>((resolve) => {
      resolveFirst = resolve;
    });
    requestSpy.mockReturnValueOnce(first).mockResolvedValueOnce(response());
    const nfo = useHistoryNfo();
    const operation = nfo.generateSelectedNfo([item('one', 'one.mp4'), item('two', 'two.mp4')]);

    await Promise.resolve();
    expect(requestSpy).toHaveBeenCalledTimes(1);
    resolveFirst?.(response());
    await operation;

    expect(requestSpy).toHaveBeenCalledTimes(2);
  });

  it('prevents duplicate generation', async () => {
    let resolveRequest: ((value: Response) => void) | undefined;
    const pending = new Promise<Response>((resolve) => {
      resolveRequest = resolve;
    });
    requestSpy.mockReturnValue(pending);
    const nfo = useHistoryNfo();
    const first = nfo.generateSelectedNfo([item('one', 'one.mp4')]);
    const second = await nfo.generateSelectedNfo([item('two', 'two.mp4')]);

    expect(second.failed).toBe(false);
    expect(nfo.isGenerating.value).toBe(true);
    resolveRequest?.(response());
    await first;
    expect(nfo.isGenerating.value).toBe(false);
  });

  it('cleans busy state on failure', async () => {
    requestSpy.mockRejectedValue(new Error('failed'));
    const nfo = useHistoryNfo();

    const result = await nfo.generateSelectedNfo([item('one', 'one.mp4')]);

    expect(result.failed).toBe(true);
    expect(nfo.isGenerating.value).toBe(false);
  });
});
