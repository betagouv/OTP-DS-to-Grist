import { ref } from 'vue'

let nextId = 0
const notifications = ref([])
const timers = new Map()

export const useNotification = () => {

  const notify = (message, type = 'info') => {
    const id = nextId++
    const duration = type === 'error' ? 10000 : 5000

    notifications.value.push({ id, message, type })

    if (duration) {
      timers.set(id, setTimeout(() => {
        timers.delete(id)
        remove(id)
      }, duration))
    }
  }

  const remove = (id) => {
    if (timers.has(id)) {
      clearTimeout(timers.get(id))
      timers.delete(id)
    }
    notifications.value = notifications.value.filter(n => n.id !== id)
  }

  return { notifications, notify, remove }
}
