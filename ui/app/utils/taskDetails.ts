import type { StoreItem } from '~/types/store';

type TaskSource = Pick<StoreItem['extras'], 'source_handler' | 'source_id'>;

export const taskSourceUrl = (source: TaskSource | null | undefined): string => {
  const handler = source?.source_handler?.trim().toLowerCase();
  if (handler !== 'tasks' && handler !== 'web') return '';

  const id = Number(source?.source_id);
  return Number.isSafeInteger(id) && id > 0 ? `/tasks/${id}` : '';
};

export const taskHistoryUrl = (
  type: 'queue' | 'done',
  sourceId: number,
  page = 1,
  perPage = 10,
  status?: string,
): string => {
  const params = new URLSearchParams({
    type,
    page: String(page),
    per_page: String(perPage),
    source_id: String(sourceId),
  });
  if (status) params.set('status', status);
  return `/api/history?${params}`;
};

export const normalizeDownloadStatus = (
  status: string | null | undefined,
  skipped = false,
): string => {
  if (skipped || status === 'download_skipped') return 'skipped';
  if (!status) return 'queued';
  if (status === 'finished') return 'completed';
  if (status === 'error' || status === 'partial') return 'failed';
  return status || 'unknown';
};
