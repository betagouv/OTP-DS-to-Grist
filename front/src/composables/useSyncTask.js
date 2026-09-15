import { ref, computed } from 'vue'

const _currentTaskId = ref(null)

export const useSyncTask = () => {
  const currentTaskId = computed(() => _currentTaskId.value)

  const setCurrentTaskId = (id) => {
    _currentTaskId.value = id ?? null
  }

  return { currentTaskId, setCurrentTaskId }
}