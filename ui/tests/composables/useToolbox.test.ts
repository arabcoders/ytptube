import { afterEach, beforeAll, beforeEach, describe, expect, it, mock, spyOn } from 'bun:test';
import { isReadonly } from 'vue';
import { useFormSubmit } from '~/composables/useFormSubmit';
import type { WSEP } from '~/types/sockets';
import type { ToolboxJob, ToolboxTool } from '~/types/toolbox';
import { createMockResponse } from '../helpers/mockResponse';

const errorMock = mock(() => {});
mock.module('~/composables/useNotification', () => ({
  useNotification: () => ({ error: errorMock }),
}));

let utils: typeof import('~/utils');
let toolboxModule: typeof import('~/composables/useToolbox');
let state: ReturnType<typeof toolboxModule.useToolbox>;
let requests: ReturnType<typeof spyOn<typeof utils, 'request'>>;

const job = (patch: Partial<ToolboxJob> = {}): ToolboxJob => ({
  id: 1,
  tool: 'remux',
  file: 'shows/episode.mp4',
  extra: { overwrite_source: true, options: {} },
  status: 'queued',
  created_at: '2026-10-31T10:00:00Z',
  started_at: null,
  finished_at: null,
  progress: null,
  message: null,
  result: null,
  error: null,
  error_code: null,
  log: '',
  ...patch,
});
const tool: ToolboxTool = {
  id: 'custom-copy',
  name: 'Custom copy',
  description: 'Copy all streams.',
  available: true,
  reason: null,
  options_schema: {},
};
const response = (data: unknown, status = 200): Response =>
  createMockResponse({ ok: status < 400, status, jsonData: data });
const listing = (items: ToolboxJob[], page = 1, perPage = 50, total = items.length) => ({
  items,
  pagination: {
    page,
    per_page: perPage,
    total,
    total_pages: Math.max(1, Math.ceil(total / perPage)),
    has_next: page < Math.ceil(total / perPage),
    has_prev: page > 1,
  },
});

beforeAll(async () => {
  utils = await import('~/utils');
  toolboxModule = await import('~/composables/useToolbox');
});
beforeEach(async () => {
  state = toolboxModule.useToolbox();
  requests = spyOn(utils, 'request');
  requests.mockResolvedValueOnce(response(listing([])));
  await state.loadJobs(1);
  requests.mockResolvedValueOnce(response({ items: [] }));
  await state.loadTools();
  requests.mockClear();
  errorMock.mockClear();
});
afterEach(() => {
  requests.mockRestore();
});

describe('shared toolbox', () => {
  it('shares readonly state', async () => {
    const other = toolboxModule.useToolbox();
    requests.mockResolvedValueOnce(response(listing([job()])));
    await state.loadJobs();
    expect(other.jobs).toBe(state.jobs);
    expect(other.jobs.value).toEqual([job()]);
    for (const value of [state.jobs, state.tools, state.pagination, state.inProgressIds])
      expect(isReadonly(value)).toBe(true);
    expect(isReadonly(other.jobs.value[0])).toBe(true);
  });

  it.each([25, 60])('honors server pagination', async (perPage) => {
    const data = listing([job()], 2, perPage, perPage * 3);
    requests.mockResolvedValueOnce(response(data));
    await state.loadJobs(2);
    expect(state.pagination.value).toEqual(data.pagination);
    requests.mockResolvedValueOnce(response(data));
    await state.loadJobs();
    expect(requests.mock.calls.map(([url]) => url)).toEqual([
      '/api/toolbox/jobs?page=2',
      '/api/toolbox/jobs?page=2',
    ]);
  });

  it('awaits concurrent catalog', async () => {
    const catalog = Promise.withResolvers<Response>();
    requests.mockReturnValueOnce(catalog.promise);
    const first = state.loadTools();
    const other = toolboxModule.useToolbox();
    const second = other.loadTools();
    try {
      expect(second).toBe(first);
      expect(other.isToolsLoading.value).toBe(true);
      expect(requests).toHaveBeenCalledTimes(1);
      catalog.resolve(response({ items: [tool] }));
      await Promise.all([first, second]);
      expect(other.tools.value.find((item) => item.available)?.id).toBe(tool.id);
      expect(other.isToolsLoading.value).toBe(false);
    } finally {
      catalog.resolve(response({ items: [] }));
      await Promise.all([first, second]);
    }
  });

  it('loads shared collection', async () => {
    state.upsert(job());
    const snapshot = Promise.withResolvers<Response>();
    requests.mockReturnValueOnce(snapshot.promise);
    const data = listing([job({ id: 26 })], 2, 25, 30);
    const loading = state.loadJobs(2);
    const other = toolboxModule.useToolbox();
    try {
      expect(other.isLoading.value).toBe(true);
      expect(other.jobs.value).toEqual([job()]);
      await other.loadJobs(2);
      expect(requests).toHaveBeenCalledTimes(1);
      snapshot.resolve(response(data));
      await loading;
      expect(other.jobs.value).toEqual(data.items);
      expect(other.pagination.value).toEqual(data.pagination);
      expect(other.isLoading.value).toBe(false);
    } finally {
      snapshot.resolve(response(listing([])));
      await loading;
    }
  });

  it('keeps page boundaries', async () => {
    const first = job();
    const second = job({ id: 2, created_at: '2026-10-31T09:00:00Z' });
    requests.mockResolvedValueOnce(response(listing([first, second], 1, 2, 3)));
    await state.loadJobs();
    const event: WSEP['toolbox_job'] = {
      id: 'toolbox-update',
      created_at: '2026-10-31T10:00:01Z',
      event: 'toolbox_job',
      title: null,
      message: null,
      data: { ...second, status: 'running', progress: 45 },
    };
    state.upsert(event.data);
    expect(state.jobs.value.map((item) => item.id)).toEqual([first.id, second.id]);
    expect(state.jobs.value.find((item) => item.id === event.data.id)?.progress).toBe(45);
    const created = job({ id: 3, created_at: '2026-10-31T11:00:00Z' });
    state.upsert(created);
    expect(state.jobs.value.map((item) => item.id)).toEqual([created.id, first.id]);
    expect(state.pagination.value.total).toBe(4);

    requests.mockResolvedValueOnce(response(listing([second], 2, 2, 3)));
    await state.loadJobs(2);
    state.upsert(created);
    expect(state.jobs.value).toEqual([second]);
    expect(state.pagination.value.page).toBe(2);
  });

  it('keeps local errors', async () => {
    const submission = useFormSubmit();
    const otherForm = useFormSubmit();
    const invalid = new utils.ApiError('Invalid mode', {
      payload: { detail: [{ loc: ['extra', 'options', 'mode'], msg: 'Choose a mode' }] },
    });
    requests.mockRejectedValueOnce(invalid);
    expect(await submission.run(() => state.createJob('remux', 'shows/episode.mp4'))).toBeNull();
    expect(submission.fields.value).toEqual({ mode: 'Choose a mode' });
    expect(otherForm.message.value).toBe('');
    requests.mockRejectedValueOnce(new Error('Job not found'));
    await expect(state.getJob(404)).rejects.toThrow('Job not found');
    expect(state.lastError.value).toBeNull();
    expect(errorMock).not.toHaveBeenCalled();

    requests.mockRejectedValueOnce(new Error('List unavailable'));
    await state.loadJobs();
    requests.mockRejectedValueOnce(new Error('Tools unavailable'));
    await state.loadTools();
    expect(state.lastError.value).toBe('List unavailable');
    expect(state.toolsError.value).toBe('Tools unavailable');
    expect(submission.message.value).toBe('Invalid mode');
    expect(submission.fields.value).toEqual({ mode: 'Choose a mode' });
    expect(requests).toHaveBeenCalledTimes(4);
  });

  it('creates typed payload', async () => {
    const options = { enabled: false, count: 0, title: '', mode: 'copy', gain: null };
    const draft = { ...options, optional: undefined };
    const saved = job({ extra: { overwrite_source: false, options } });
    requests.mockResolvedValueOnce(response(saved, 202));
    expect(await state.createJob('remux', saved.file, false, draft)).toEqual(saved);
    expect(JSON.parse(String(requests.mock.calls[0]?.[1]?.body))).toEqual({
      tool: 'remux',
      file: saved.file,
      extra: { overwrite_source: false, options },
    });
    expect(state.jobs.value).toEqual([saved]);
    expect(state.jobs.value[0]?.id).toBe(1);
    expect(draft).toEqual({ ...options, optional: undefined });
    expect(requests).toHaveBeenCalledTimes(1);
    requests.mockResolvedValueOnce(response(saved));
    expect(await state.getJob(saved.id)).toEqual(saved);
    expect(requests.mock.calls[1]?.[0]).toBe('/api/toolbox/jobs/1');
  });

  it('never retries creation', async () => {
    requests.mockRejectedValueOnce(new Error('Response lost'));
    await expect(state.createJob('remux', 'shows/episode.mp4')).rejects.toThrow('Response lost');
    expect(requests).toHaveBeenCalledTimes(1);
    expect(requests.mock.calls[0]?.[1]?.method).toBe('POST');
  });

  it.each(['succeeded', 'skipped'] as const)('keeps terminal cancellation', async (status) => {
    const running = job({ status: 'running', progress: 100 });
    state.upsert(running);
    const snapshot = Promise.withResolvers<Response>();
    requests.mockReturnValueOnce(snapshot.promise);
    const cancelling = state.cancelJob(running);
    const terminal = job({ status, message: 'Already matches the target format.' });
    try {
      expect(toolboxModule.useToolbox().inProgressIds.value.has(running.id)).toBe(true);
      expect(await toolboxModule.useToolbox().cancelJob(running)).toBe(false);
      expect(await state.deleteJob(terminal)).toBe(false);
      state.upsert(terminal);
      snapshot.resolve(response({ ...running, message: 'Cancelling' }));
      expect(await cancelling).toBe(true);
      expect(state.jobs.value[0]).toEqual(terminal);
      expect(state.inProgressIds.value.size).toBe(0);
      expect(await state.cancelJob(running)).toBe(false);
      expect(requests).toHaveBeenCalledTimes(1);
      expect(requests.mock.calls[0]?.[0]).toBe('/api/toolbox/jobs/1/cancel');
    } finally {
      snapshot.resolve(response(running));
      await cancelling;
    }
  });

  it('updates partial mutations', async () => {
    const first = job({ status: 'succeeded' });
    const failed = job({ id: 2, status: 'failed' });
    state.upsert(first);
    state.upsert(failed);
    requests.mockResolvedValueOnce(new Response(null, { status: 204 }));
    requests.mockRejectedValueOnce(new Error('Delete unavailable'));
    expect(await state.deleteJob(first)).toBe(true);
    expect(await state.deleteJob(failed)).toBe(false);
    expect(state.jobs.value).toEqual([failed]);
    expect(state.pagination.value.total).toBe(1);
    expect(state.inProgressIds.value.size).toBe(0);
    expect(errorMock).toHaveBeenCalledWith('Delete unavailable');
    expect(requests.mock.calls.map(([url]) => url)).toEqual([
      '/api/toolbox/jobs/1',
      '/api/toolbox/jobs/2',
    ]);
  });
});
