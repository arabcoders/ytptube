import { defineStore } from 'pinia'
import { useStorage } from '@vueuse/core'
import type { notification, notificationType } from '~/composables/useNotification'

const _map: Record<notificationType, { level: number; color: string; icon: string }> = {
  'error': { level: 3, color: 'is-danger', icon: 'fas fa-triangle-exclamation' },
  'warning': { level: 2, color: 'is-warning', icon: 'fas fa-circle-exclamation' },
  'success': { level: 1, color: 'is-primary', icon: 'fas fa-circle-check' },
  'info': { level: 0, color: 'is-info', icon: 'fas fa-circle-info' }
}

export const useNotificationStore = defineStore('notifications', () => {
  const notifications = useStorage<notification[]>('notifications', [])
  const unreadCount = computed<number>(() => notifications.value.filter(n => !n.seen).length)

  const severityLevel = computed<notificationType | null>(() => {
    const unread = notifications.value.filter(n => !n.seen)
    if (0 === unread.length) {
      return null
    }

    return unread.reduce((h, n) => _map[n.level].level > _map[h.level].level ? n : h).level
  })

  const severityColor = computed<string>(() => {
    const level = severityLevel.value
    return level ? _map[level].color : ''
  })

  const severityIcon = computed<string>(() => {
    const level = severityLevel.value
    return level ? _map[level].icon : ''
  })

  const sortedNotifications = computed<notification[]>(() => {
    return [...notifications.value].sort((a, b) => {
      const severityDiff = _map[b.level].level - _map[a.level].level
      if (0 !== severityDiff) {
        return severityDiff
      }
      return (new Date(b.created).getTime()) - (new Date(a.created).getTime())
    })
  })

  const add = (level: notificationType, message: string, seen: boolean = false): string => {
    const id = Array.from(
      window.crypto.getRandomValues(new Uint8Array(14 / 2)),
      (dec: any) => dec.toString(16).padStart(2, "0")
    ).join('')

    notifications.value.unshift({
      id: id,
      message,
      level,
      seen: seen,
      created: new Date()
    })

    if (notifications.value.length > 99) {
      notifications.value.length = 99
    }

    return id
  }

  const clear = () => notifications.value = []
  const markAllRead = () => notifications.value.forEach(n => n.seen = true)

  const markRead = (id: string) => {
    console.log(`Marking notification ${id} as read`)
    const n = notifications.value.find(n => n.id === id)
    if (!n) {
      return
    }
    n.seen = true
  }

  const get = (id: string): notification | undefined => notifications.value.find(n => n.id === id)

  const remove = (id: string) => notifications.value = notifications.value.filter(n => n.id !== id)

  return {
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
    remove
  }
})
