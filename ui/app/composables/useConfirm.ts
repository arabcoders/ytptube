import { useDialog, type ConfirmOptions, type AlertOptions, type PromptOptions } from './useDialog'

const dialog = useDialog()

const confirm = async (msg: string, opts: ConfirmOptions = {}) => {
  const { status } = await dialog.confirmDialog(Object.assign({
    title: 'Please Confirm',
    message: msg,
    cancelText: 'Cancel',
    confirmText: 'OK',
  } as ConfirmOptions, opts || {}))

  return status
}

const alert = async (msg: string, opts: AlertOptions = {}) => {
  const { status } = await dialog.alertDialog(Object.assign({
    title: 'Alert',
    message: msg,
    confirmText: 'OK',
  } as AlertOptions, opts || {}))
  return status
}

const prompt = async (msg: string, opts: PromptOptions = {}) => {
  const { status, value } = await dialog.promptDialog(Object.assign({ message: msg } as PromptOptions, opts || {}))

  if (status) {
    return value
  }

  return null
}

export const useConfirm = () => ({ confirm, alert, prompt })
