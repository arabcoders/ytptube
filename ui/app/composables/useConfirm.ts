import { useDialog, type ConfirmOptions, type AlertOptions, type PromptOptions } from './useDialog';

export const useConfirm = () => {
  const { t } = useI18n();
  const dialog = useDialog();

  const confirm = async (msg: string, opts: ConfirmOptions = {}) => {
    const { status } = await dialog.confirmDialog(
      Object.assign(
        {
          title: t('common.pleaseConfirm'),
          message: msg,
          cancelText: t('common.cancel'),
          confirmText: t('common.ok'),
        } as ConfirmOptions,
        opts || {},
      ),
    );

    return status;
  };

  const alert = async (msg: string, opts: AlertOptions = {}) => {
    const { status } = await dialog.alertDialog(
      Object.assign(
        {
          title: t('common.alert'),
          message: msg,
          confirmText: t('common.ok'),
        } as AlertOptions,
        opts || {},
      ),
    );
    return status;
  };

  const prompt = async (msg: string, opts: PromptOptions = {}) => {
    const { status, value } = await dialog.promptDialog(
      Object.assign({ message: msg } as PromptOptions, opts || {}),
    );

    if (status) {
      return value;
    }

    return null;
  };

  return { confirm, alert, prompt };
};
