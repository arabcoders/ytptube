import { useDialog } from './useDialog';
import { useYtpConfig } from './useYtpConfig';
import { makeDownload } from '~/utils';
import type { StoreItem } from '~/types/store';

export const useWebShare = () => {
  const { t } = useI18n();

  const canShare = (): boolean =>
    typeof navigator !== 'undefined' && typeof navigator.share === 'function';

  const shareUrl = async (download: StoreItem): Promise<void> => {
    if (!canShare()) {
      useNotification().error(t('common.shareUnsupported'));
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
        title: t('common.shareFailedTitle'),
        message: t('common.shareFailed', { error: err?.message || t('common.unknownError') }),
      });
    }
  };

  return { canShare, shareUrl };
};
