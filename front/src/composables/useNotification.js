import { ref } from 'vue'

let nextId = 0
const notifications = ref([])

let permission = typeof Notification !== 'undefined' ? Notification.permission : 'denied'

export const useNotification = () => {

  const requestPermission = async () => {
    if (typeof Notification === 'undefined') return
    if (Notification.permission === 'default') {
      permission = await Notification.requestPermission()
    }
  }

  const notify = (message, type = 'info') => {
    if (permission === 'granted') {
      new Notification(message)
      return
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

  return { notifications, notify, remove, requestPermission }
}
