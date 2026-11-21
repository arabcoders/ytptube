import { expect, it } from 'bun:test';
import { downloadTitleTooltip, formatDownloadTitle } from '~/composables/useDownloadTitle';

it('prefers the actual filename', () => {
  const item = { title: 'Concert', filename: 'Shows/Final.mkv', filename_preview: 'Preview.mp4' };

  expect(formatDownloadTitle(item, true)).toBe('Final.mkv');
});

it('shows filenames without previews', () => {
  const item = {
    title: 'Episode 1',
    filename: 'Khareef Al Qalb, E1.mp4',
    filename_preview: null,
  };

  expect(formatDownloadTitle(item, true)).toBe('Khareef Al Qalb, E1.mp4');
});

it('uses the available preview', () => {
  const item = { title: 'Concert', filename: null, filename_preview: 'Preview.mp4' };

  expect(formatDownloadTitle(item, true)).toBe('Preview.mp4');
  expect(formatDownloadTitle({ title: 'Concert' }, true)).toBe('Concert');
});

it('honors the title preference', () => {
  expect(formatDownloadTitle({ title: 'Concert', filename_preview: 'Preview.mp4' }, false)).toBe(
    'Concert',
  );
});

it('uses the untitled fallback', () => {
  expect(formatDownloadTitle({ title: '' }, true, 'Untitled')).toBe('Untitled');
});

it('tooltip prefers actual filename', () => {
  const item = { title: 'Concert', filename: 'Shows/Final.mkv', filename_preview: 'Preview.mp4' };

  expect(downloadTitleTooltip(item)).toBe('Concert (Final.mkv)');
});

it('tooltip falls back to preview', () => {
  expect(downloadTitleTooltip({ title: 'Concert', filename_preview: 'Preview.mp4' })).toBe(
    'Concert (Preview.mp4)',
  );
  expect(downloadTitleTooltip({ title: 'Concert' })).toBe('Concert');
});
