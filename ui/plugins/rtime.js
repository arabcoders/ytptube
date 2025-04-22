import { defineNuxtPlugin } from '#app'
import moment from 'moment'

const parseInterval = arg => {
  const match = arg.match(/^(\d+)([smhd])$/)
  if (!match) {
    return 60 * 1000
  }

  const [, numStr, unit] = match
  const num = parseInt(numStr, 10)

  switch (unit) {
    case 'd': return num * 24 * 3600 * 1000
    case 'h': return num * 3600 * 1000
    case 'm': return num * 60 * 1000
    case 's': return num * 1000
    default: return 60 * 1000
  }
}

export default defineNuxtPlugin(nuxtApp => nuxtApp.vueApp.directive('rtime', {
  mounted(el, binding) {
    const intervalMs = binding.arg ? parseInterval(binding.arg) : 60 * 1000
    const update = () => el.textContent = moment(binding.value).fromNow()

    update()
    el._next_timer = window.setInterval(update, intervalMs)
  },
  updated(el, binding) {
    if (binding.oldValue !== binding.value) {
      if (null != el._next_timer) {
        clearInterval(el._next_timer)
      }

      const intervalMs = binding.arg ? parseInterval(binding.arg) : 60 * 1000

      const update = () => el.textContent = moment(binding.value).fromNow()
      update()

      el._next_timer = window.setInterval(update, intervalMs)
    }
  },
  beforeUnmount(el) {
    if (null != el._next_timer) {
      clearInterval(el._next_timer)
    }
  }
}))
