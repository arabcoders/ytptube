import { computed, proxyRefs } from 'vue';
import { useStorage } from '@vueuse/core';
import type { notification, notificationType } from '~/composables/useNotification';

const NOTIFICATION_META: Record<notificationType, { level: number; color: string; icon: string }> =
  {
    error: { level: 3, color: 'error', icon: 'i-lucide-triangle-alert' },
    warning: { level: 2, color: 'warning', icon: 'i-lucide-circle-alert' },
    success: { level: 1, color: 'success', icon: 'i-lucide-badge-check' },
    info: { level: 0, color: 'info', icon: 'i-lucide-info' },
  };

const notifications = useStorage<notification[]>('notifications', []);

const unreadCount = computed<number>(() => notifications.value.filter((n) => !n.seen).length);

const severityLevel = computed<notificationType | null>(() => {
  const unread = notifications.value.filter((n) => !n.seen);

  if (0 === unread.length) {
    return null;
  }

  return unread.reduce((highest, current) =>
    NOTIFICATION_META[current.level].level > NOTIFICATION_META[highest.level].level
      ? current
      : highest,
  ).level;
});

const severityColor = computed<string>(() => {
  const level = severityLevel.value;
  return level ? NOTIFICATION_META[level].color : '';
});

const severityIcon = computed<string>(() => {
  const level = severityLevel.value;
  return level ? NOTIFICATION_META[level].icon : '';
});

const sortedNotifications = computed<notification[]>(() => {
  return [...notifications.value].sort((left, right) => {
    const severityDiff = NOTIFICATION_META[right.level].level - NOTIFICATION_META[left.level].level;

    if (0 !== severityDiff) {
      return severityDiff;
    }

    return new Date(right.created).getTime() - new Date(left.created).getTime();
  });
});

const add = (level: notificationType, message: string, seen: boolean = false): string => {
  const id = Array.from(window.crypto.getRandomValues(new Uint8Array(14 / 2)), (dec: number) =>
    dec.toString(16).padStart(2, '0'),
  ).join('');

  notifications.value.unshift({
    id,
    message,
    level,
    seen,
    created: new Date(),
  });

  if (notifications.value.length > 99) {
    notifications.value.length = 99;
  }

  return id;
};

const clear = (): void => {
  notifications.value = [];
};

const markAllRead = (): void => {
  notifications.value.forEach((item) => {
    item.seen = true;
  });
};

const markRead = (id: string): void => {
  const entry = notifications.value.find((item) => item.id === id);

  if (!entry) {
    return;
  }

  entry.seen = true;
};

const get = (id: string): notification | undefined =>
  notifications.value.find((item) => item.id === id);

const remove = (id: string): void => {
  notifications.value = notifications.value.filter((item) => item.id !== id);
};

const notificationCenterApi = proxyRefs({
  notifications,
  unreadCount,
  severityLevel,
  severityColor,
  severityIcon,
  sortedNotifications,
  add,
  get,
  markAllRead,
  clear,
  markRead,
  remove,
});

export const useNotificationCenter = () => notificationCenterApi;
