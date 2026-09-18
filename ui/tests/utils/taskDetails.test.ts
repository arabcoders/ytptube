import { describe, expect, it } from 'vitest';
import { normalizeDownloadStatus, taskHistoryUrl } from '~/utils/taskDetails';

describe('task details helpers', () => {
  it('builds history queries', () => {
    expect(taskHistoryUrl('done', 4, 2, 1, 'error')).toBe(
      '/api/history?type=done&page=2&per_page=1&source_id=4&status=error',
    );
  });

  it('normalizes download statuses', () => {
    expect(normalizeDownloadStatus('finished')).toBe('completed');
    expect(normalizeDownloadStatus('download_skipped')).toBe('skipped');
    expect(normalizeDownloadStatus('error')).toBe('failed');
    expect(normalizeDownloadStatus(null)).toBe('queued');
  });
});
