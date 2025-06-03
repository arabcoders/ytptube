import { useStorage } from '@vueuse/core'
import { useToast } from "vue-toastification"

type notificationType = 'info' | 'success' | 'warning' | 'error'
type notificationOptions = {
  timeout?: number,
  force?: boolean,
}

const allowToast = useStorage<boolean>('allow_toasts', true)
const toast = useToast()

function notify(type: notificationType, message: string, opts?: notificationOptions): void {
  let force = opts?.force || false;
  if (false === allowToast.value && false === force) {
    return;
  }

  if (!opts) {
    opts = {}
  }

  switch (type) {
    case 'info':
      toast.info(message, opts)
      break;
    case 'success':
      toast.success(message, opts)
      break;
    case 'warning':
      toast.warning(message, opts)
      break;
    case 'error':
      toast.error(message, opts)
      break;
    default:
      toast.error(`Unknown notification type: ${type}. ${message}`, opts)
      break;
  }
}

export default function useNotification() {
  return {
    info: (message: string, opts?: notificationOptions) => notify('info', message, opts),
    success: (message: string, opts?: notificationOptions) => notify('success', message, opts),
    warning: (message: string, opts?: notificationOptions) => notify('warning', message, opts),
    error: (message: string, opts?: notificationOptions) => notify('error', message, opts),
  }
}
