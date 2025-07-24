import { defineStore } from 'pinia'
import { useStorage } from '@vueuse/core'
import type { Notification, notificationType } from '~/composables/useNotification'

export const useNotificationStore = defineStore('notifications', () => {
  const notifications = useStorage<Notification[]>('notifications', [])
  const unreadCount = computed<number>(() => notifications.value.filter(n => !n.seen).length)

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

  const get = (id: string): Notification | undefined => notifications.value.find(n => n.id === id)

  const remove = (id: string) => notifications.value = notifications.value.filter(n => n.id !== id)

  return { notifications, unreadCount, add, get, markAllRead, clear, markRead, remove }
})
