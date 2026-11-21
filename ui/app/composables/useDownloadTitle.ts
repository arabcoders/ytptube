import { useStorage } from '@vueuse/core';
import type { StoreItem } from '~/types/store';
import { basename } from '~/utils';

type TitleItem = Pick<StoreItem, 'title' | 'filename' | 'filename_preview'>;

const downloadFilename = (item: TitleItem) =>
  basename(item.filename ?? '') || item.filename_preview;

export const formatDownloadTitle = (
  item: TitleItem,
  showFilename: boolean,
  fallback = '',
): string => {
  return (showFilename && downloadFilename(item)) || item.title || fallback;
};

export const downloadTitleTooltip = (item: TitleItem, fallback = ''): string => {
  const title = item.title || fallback;
  const filename = downloadFilename(item);
  if (!filename) return title;

  return title ? `${title} (${filename})` : filename;
};

export const useDownloadTitle = () => {
  const showFilename = useStorage('show_filename', false);
  const downloadTitle = (item: TitleItem, fallback?: string): string =>
    formatDownloadTitle(item, showFilename.value, fallback);

  return { showFilename, downloadTitle };
};
