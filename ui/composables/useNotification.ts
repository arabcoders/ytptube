import { useStorage } from '@vueuse/core'
import { POSITION, useToast } from "vue-toastification"

type notificationType = 'info' | 'success' | 'warning' | 'error'
type notificationOptions = {
  timeout?: number,
  force?: boolean,
  closeOnClick?: boolean,
  position?: POSITION
}

const allowToast = useStorage<boolean>('allow_toasts', true)
const toastPosition = useStorage<POSITION>('toast_position', POSITION.TOP_RIGHT)
const toastDismissOnClick = useStorage<boolean>('toast_dismiss_on_click', true)
const toast = useToast()

function notify(type: notificationType, message: string, opts?: notificationOptions): void {
  let force = opts?.force || false;
  if (false === allowToast.value && false === force) {
    return;
  }

  if (!opts) {
    opts = {}
  }

  if (opts?.force) {
    delete opts.force
  }

  opts.closeOnClick = toastDismissOnClick.value
  opts.position = toastPosition.value ?? POSITION.TOP_RIGHT

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
