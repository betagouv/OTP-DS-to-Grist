import { ref } from 'vue'

let nextId = 0
const notifications = ref([])

export const useNotification = () => {

  const notify = (message, type = 'info') => {
    if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
      try {
        new Notification(message)
        return
      } catch {
        // Fallback toast si le constructeur échoue
      }
    }

    const id = nextId++
    const duration = type === 'error' ? 10000 : 5000

    notifications.value.push({ id, message, type })

    if (duration) {
      setTimeout(() => remove(id), duration)
    }
  }

  const remove = (id) => {
    notifications.value = notifications.value.filter(n => n.id !== id)
  }

  return { notifications, notify, remove }
}
