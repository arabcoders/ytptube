import { useStorage } from '@vueuse/core'

const reduceConfirm = useStorage<boolean>('reduce_confirm', false)

function confirm(msg: string, force: boolean = false): boolean {
  if (false === force && true === reduceConfirm.value) {
    return true
  }

  return window.confirm(msg)
}

function alert(msg: string): boolean {
  return window.confirm(msg)
}

export default function useConfirm() {
  return { confirm, alert, reduceConfirm }
}
