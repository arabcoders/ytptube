import { afterEach, beforeAll, beforeEach, describe, expect, it, mock, spyOn } from 'bun:test';

const successMock = mock(() => {});
const errorMock = mock(() => {});

mock.module('~/composables/useNotification', () => ({
  useNotification: () => ({ success: successMock, error: errorMock }),
}));

type MockResponseInput = {
  ok: boolean;
  status: number;
  jsonData: unknown;
};

const createMockResponse = ({ ok, status, jsonData }: MockResponseInput): Response => {
  return {
    ok,
    status,
    headers: new Headers({ 'Content-Type': 'application/json' }),
    redirected: false,
    statusText: ok ? 'OK' : 'Error',
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

let utils: Awaited<typeof import('~/utils/index')>;
let useDiagnostics: typeof import('~/composables/useDiagnostics').useDiagnostics;

beforeAll(async () => {
  utils = await import('~/utils/index');
  ({ useDiagnostics } = await import('~/composables/useDiagnostics'));
});

beforeEach(() => {
  successMock.mockClear();
  errorMock.mockClear();
  useDiagnostics().__resetForTesting();
});

afterEach(() => {
  useDiagnostics().__resetForTesting();
});

describe('useDiagnostics', () => {
  it('load_diagnostics', async () => {
    const requestSpy = spyOn(utils, 'request');
    requestSpy.mockResolvedValueOnce(
      createMockResponse({
        ok: true,
        status: 200,
        jsonData: {
          status: 'error',
          generated_at: 1,
          summary: { total: 2, pass: 0, fail: 1, warn: 0, skip: 1, required_failed: 1 },
          runtime: {
            app_version: '1.0.0',
            app_branch: 'main',
            app_commit_sha: 'abc123',
            app_build_date: '20260526',
            started: 1,
            uptime_seconds: 15,
            platform: 'linux',
            platform_release: '6.8',
            platform_machine: 'x86_64',
            python_version: '3.13.1',
            python_minimum: '3.13',
            is_native: false,
            console_enabled: false,
          },
          requirements: {
            python: {
              current: '3.13.1',
              required: '3.13',
              supported: true,
              note: 'Python runtime context.',
            },
          },
          checks: [
            {
              id: 'deno',
              label: 'deno',
              required: true,
              group: 'youtube',
              status: 'fail',
              description: 'Used for yt-dlp YouTube support.',
              message: 'Missing.',
              details: { command: 'deno' },
            },
            {
              id: 'browser_endpoint',
              label: 'Remote browser',
              group: 'browser',
              status: 'skip',
              description: 'Endpoint used by the browser extractor.',
              message: 'Not configured.',
              details: {},
            },
          ],
        },
      }),
    );

    const diagnostics = useDiagnostics();
    const result = await diagnostics.loadDiagnostics(true);

    expect(requestSpy).toHaveBeenCalledWith('/api/system/diagnostics?refresh=1');
    expect(result?.status).toBe('error');
    expect(diagnostics.diagnostics.value?.summary.required_failed).toBe(1);
    expect(diagnostics.groupOrder.value).toEqual(['youtube', 'browser']);
    expect(diagnostics.groupedChecks.value.youtube?.[0]?.id).toBe('deno');

    requestSpy.mockRestore();
  });

  it('store_load_error', async () => {
    const requestSpy = spyOn(utils, 'request');
    requestSpy.mockResolvedValueOnce(
      createMockResponse({
        ok: false,
        status: 500,
        jsonData: { error: 'Backend exploded' },
      }),
    );

    const diagnostics = useDiagnostics();
    const result = await diagnostics.loadDiagnostics(true);

    expect(result).toBeNull();
    expect(diagnostics.lastError.value).toBe('Backend exploded');
    expect(errorMock).toHaveBeenCalledWith('Backend exploded');

    requestSpy.mockRestore();
  });
});
