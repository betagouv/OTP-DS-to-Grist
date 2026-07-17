import { ref } from 'vue'

let _nextId = 0
const notifications = ref([])

export const useNotification = () => {

  const notify = (message, type = 'info') => {
    const id = _nextId++
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
