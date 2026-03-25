import { useStorage } from '@vueuse/core';
import { getNuxtToastManager } from '~/utils/nuxtToastManager';

export type notificationType = 'info' | 'success' | 'warning' | 'error';
export type notificationTarget = 'toast' | 'browser';
export type toastPosition =
  | 'top-left'
  | 'top-center'
  | 'top-right'
  | 'bottom-left'
  | 'bottom-center'
  | 'bottom-right';

export interface notification {
  id: string;
  message: string;
  level: notificationType;
  seen: boolean;
  created: Date;
}

export interface notificationOptions {
  timeout?: number;
  force?: boolean;
  closeOnClick?: boolean;
  position?: toastPosition;
  onClick?: (toast: { id: string | number }) => void;
  store?: boolean;
  lowPriority?: boolean;
}

const allowToast = useStorage<boolean>('allow_toasts', true);
const toastPosition = useStorage<toastPosition>('toast_position', 'top-right');
const toastDismissOnClick = useStorage<boolean>('toast_dismiss_on_click', true);
const toastTarget = useStorage<notificationTarget>('toast_target', 'toast');

const toastMeta = (type: notificationType) => {
  switch (type) {
    case 'success':
      return { color: 'success' as const, icon: 'i-lucide-badge-check' };
    case 'warning':
      return { color: 'warning' as const, icon: 'i-lucide-circle-alert' };
    case 'error':
      return { color: 'error' as const, icon: 'i-lucide-triangle-alert' };
    case 'info':
    default:
      return { color: 'info' as const, icon: 'i-lucide-info' };
  }
};

const requestBrowserPermission = async (): Promise<NotificationPermission> => {
  if (!('Notification' in window)) {
    return 'denied';
  }

  if (Notification.permission === 'granted') {
    return 'granted';
  }

  if (Notification.permission !== 'denied') {
    return await Notification.requestPermission();
  }

  return Notification.permission;
};

const sendMessage = (
  type: notificationType,
  id: string,
  message: string,
  opts?: notificationOptions,
): void => {
  const notificationStore = useNotificationStore();

  const useToastNotification =
    !window.isSecureContext ||
    'toast' === toastTarget.value ||
    !('Notification' in window) ||
    'granted' !== Notification.permission;

  if (useToastNotification) {
    const toast = getNuxtToastManager();
    if (!toast) {
      console.warn('Nuxt toast manager is not ready yet; skipping toast notification.');
      return;
    }

    const meta = toastMeta(type);
    toast.add({
      title: message,
      color: meta.color,
      icon: meta.icon,
      duration: opts?.timeout,
      close: true,
      onClick: opts?.onClick,
    });
    return;
  }

  const notification = new Notification('YTPTube', {
    body: message,
    icon: '/favicon.ico',
    badge: '/favicon.ico',
    tag: `ytptube-${type}`,
    silent: false,
  });

  setTimeout(() => notification.close(), 5000);

  notification.onclick = () => {
    notificationStore.markRead(id);
    window.focus();
    notification.close();
  };
};

const notify = (type: notificationType, message: string, opts?: notificationOptions): void => {
  const notificationStore = useNotificationStore();

  if (!opts) {
    opts = {};
  }

  let id: string = '';
  const force = opts?.force || false;
  const store = opts?.store || true;
  const lowPriority = opts?.lowPriority || false;

  if (notificationStore && (store || true === lowPriority)) {
    id = notificationStore.add(type, message, false);
  }

  if (true === lowPriority || (false === allowToast.value && false === force)) {
    return;
  }

  if (false === document.hasFocus()) {
    return;
  }

  opts.closeOnClick = toastDismissOnClick.value;
  opts.position = toastPosition.value ?? 'top-right';
  opts.onClick = (toastInstance: { id: string | number }) => {
    if (notificationStore) {
      notificationStore.markRead(id);
    }
    if (opts?.closeOnClick !== false) {
      const toast = getNuxtToastManager();
      if (!toast) {
        return;
      }
      toast.remove(toastInstance.id);
    }
  };

  sendMessage(type, id, message, opts);
};

export const useNotification = () => {
  return {
    info: (message: string, opts?: notificationOptions) => notify('info', message, opts),
    success: (message: string, opts?: notificationOptions) => notify('success', message, opts),
    warning: (message: string, opts?: notificationOptions) => notify('warning', message, opts),
    error: (message: string, opts?: notificationOptions) => notify('error', message, opts),
    notify,
    requestBrowserPermission,
  };
};
