import { useStorage } from '@vueuse/core'
import { POSITION, useToast } from "vue-toastification"

export type notificationType = 'info' | 'success' | 'warning' | 'error'

export interface Notification {
  id: string;
  message: string
  level: notificationType
  seen: boolean
  created: Date
};

export interface notificationOptions {
  timeout?: number,
  force?: boolean,
  store?: boolean,
  closeOnClick?: boolean,
  position?: POSITION
  onClick?: (closeToast: Function) => void
}

const allowToast = useStorage<boolean>('allow_toasts', true)
const toastPosition = useStorage<POSITION>('toast_position', POSITION.TOP_RIGHT)
const toastDismissOnClick = useStorage<boolean>('toast_dismiss_on_click', true)
const toast = useToast()

function notify(type: notificationType, message: string, opts?: notificationOptions): void {
  const notificationStore = useNotificationStore()

  let id: string = ''
  const force = opts?.force || false;
  const store = opts?.store || true;

  if (store && notificationStore) {
    id = notificationStore.add(type, message, false)
  }

  if (false === allowToast.value && false === force) {
    return;
  }

  if (false === document.hasFocus()) {
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
  opts.onClick = (closeToast: Function) => {
    if (opts?.closeOnClick !== false) {
      closeToast()
    }
    if (notificationStore) {
      notificationStore.markRead(id)
    }
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
