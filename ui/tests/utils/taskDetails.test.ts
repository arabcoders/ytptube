import { describe, expect, it } from 'vitest';
import { normalizeDownloadStatus, taskHistoryUrl, taskSourceUrl } from '~/utils/taskDetails';

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

  it('links task sources', () => {
    expect(taskSourceUrl({ source_handler: 'Tasks', source_id: '12' })).toBe('/tasks/12');
    expect(taskSourceUrl({ source_handler: ' web ', source_id: 4 })).toBe('/tasks/4');
  });

  it('rejects other sources', () => {
    expect(taskSourceUrl({ source_handler: 'YoutubeHandler', source_id: 12 })).toBe('');
    expect(taskSourceUrl({ source_handler: 'Tasks', source_id: 'invalid' })).toBe('');
    expect(taskSourceUrl({ source_handler: 'Tasks', source_id: 0 })).toBe('');
  });
});
