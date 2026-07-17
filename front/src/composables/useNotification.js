export const useNotification = () => {
  const notify = (message, type = 'info') => {
    alert(`[${type.toUpperCase()}] ${message}`)
  }

  return { notify }
}
