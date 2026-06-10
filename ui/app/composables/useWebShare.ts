import { useDialog } from './useDialog';
import { useYtpConfig } from './useYtpConfig';
import { makeDownload } from '~/utils';
import type { StoreItem } from '~/types/store';

export const useWebShare = () => {
  const canShare = (): boolean =>
    typeof navigator !== 'undefined' && typeof navigator.share === 'function';

  const shareUrl = async (download: StoreItem): Promise<void> => {
    if (!canShare()) {
      useNotification().error('Web Share API is not supported in this browser.');
      return;
    }

    try {
      const title = download.title || download.filename || 'Download';
      await navigator.share({
        title: title,
        text: download.description || title,
        url: makeDownload(useYtpConfig(), download),
      });
    } catch (err: any) {
      if (err?.name === 'AbortError') {
        return;
      }

      console.error('Share failed:', err);

      await useDialog().alertDialog({
        title: 'Share Failed',
        message: `Share failed: ${err?.message || 'unknown error'}`,
      });
    }
  };

  return { canShare, shareUrl };
};
