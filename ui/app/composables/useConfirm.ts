import { useStorage } from '@vueuse/core'
import { useDialog } from './useDialog'

const dialog = useDialog()

const reduceConfirm = useStorage<boolean>('reduce_confirm', false)

const confirm = async (msg: string, force: boolean = false) => {
  if (false === force && true === reduceConfirm.value) {
    return true
  }

  const { status } = await dialog.confirmDialog({
    title: 'Please Confirm',
    message: msg,
    cancelText: 'Cancel',
    confirmText: 'OK',
  })

  return status
}

const alert = async (msg: string) => {
  const { status } = await dialog.alertDialog({
    title: 'Alert',
    message: msg,
    confirmText: 'OK',
  })
  return status
}

const prompt = async (msg: string, defaultValue: string = '') => {
  const { status, value } = await dialog.promptDialog({
    title: 'Input Required',
    message: msg,
    initial: defaultValue,
    cancelText: 'Cancel',
    confirmText: 'OK',
  })

  if (status) {
    return value
  }

  return null
}

export default function useConfirm() {
  return { confirm, alert, prompt, reduceConfirm }
}
