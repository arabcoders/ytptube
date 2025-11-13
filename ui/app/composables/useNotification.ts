import { useStorage } from '@vueuse/core'
import { POSITION, useToast } from "vue-toastification"

export type notificationType = 'info' | 'success' | 'warning' | 'error'
export type notificationTarget = 'toast' | 'browser'

export interface notification {
  id: string;
  message: string
  level: notificationType
  seen: boolean
  created: Date
};

export interface notificationOptions {
  timeout?: number,
  force?: boolean,
  closeOnClick?: boolean,
  position?: POSITION
  // eslint-disable-next-line @typescript-eslint/no-unsafe-function-type
  onClick?: (closeToast: Function) => void
  store?: boolean,
  lowPriority?: boolean
}

const allowToast = useStorage<boolean>('allow_toasts', true)
const toastPosition = useStorage<POSITION>('toast_position', POSITION.TOP_RIGHT)
const toastDismissOnClick = useStorage<boolean>('toast_dismiss_on_click', true)
const toastTarget = useStorage<notificationTarget>('toast_target', 'toast')
const toast = useToast()

const requestBrowserPermission = async (): Promise<NotificationPermission> => {
  if (!('Notification' in window)) {
    return 'denied'
  }

  if (Notification.permission === 'granted') {
    return 'granted'
  }

  if (Notification.permission !== 'denied') {
    return await Notification.requestPermission()
  }

  return Notification.permission
}

const sendMessage = (type: notificationType, id: string, message: string, opts?: notificationOptions): void => {
  const notificationStore = useNotificationStore()

  const useToastNotification = !window.isSecureContext || 'toast' === toastTarget.value ||
    !('Notification' in window) || 'granted' !== Notification.permission;

  console.log('useToastNotification', useToastNotification,{
    windowIsSecureContext: window.isSecureContext,
    notificationTarget: toastTarget.value,
    notificationInWindow: 'Notification' in window,
    notificationPermission: Notification.permission
  });

  if (useToastNotification) {
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
    return
  }

  const notification = new Notification('YTPTube', {
    body: message,
    icon: '/favicon.ico',
    badge: '/favicon.ico',
    tag: `ytptube-${type}`,
    silent: false
  })

  setTimeout(() => notification.close(), 5000)

  notification.onclick = () => {
    notificationStore.markRead(id)
    window.focus()
    notification.close()
  }
}

const notify = (type: notificationType, message: string, opts?: notificationOptions): void => {
  const notificationStore = useNotificationStore()

  if (!opts) {
    opts = {}
  }

  let id: string = ''
  const force = opts?.force || false;
  const store = opts?.store || true;
  const lowPriority = opts?.lowPriority || false;

  if (notificationStore && (store || true === lowPriority)) {
    id = notificationStore.add(type, message, false)
  }

  if (true === lowPriority || (false === allowToast.value && false === force)) {
    return;
  }

  if (false === document.hasFocus()) {
    return;
  }

  opts.closeOnClick = toastDismissOnClick.value
  opts.position = toastPosition.value ?? POSITION.TOP_RIGHT
  // eslint-disable-next-line @typescript-eslint/no-unsafe-function-type
  opts.onClick = (closeToast: Function) => {
    if (opts?.closeOnClick !== false) {
      closeToast()
    }
    if (notificationStore) {
      notificationStore.markRead(id)
    }
  }

  sendMessage(type, id, message, opts)
}

export const useNotification = () => {
  return {
    info: (message: string, opts?: notificationOptions) => notify('info', message, opts),
    success: (message: string, opts?: notificationOptions) => notify('success', message, opts),
    warning: (message: string, opts?: notificationOptions) => notify('warning', message, opts),
    error: (message: string, opts?: notificationOptions) => notify('error', message, opts),
    notify,
    requestBrowserPermission,
  }
}
