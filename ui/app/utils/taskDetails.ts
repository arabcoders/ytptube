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
