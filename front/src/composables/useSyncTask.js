import { ref, computed } from 'vue'

// Synchros suivies, dans leur ordre d'exécution : une seule pour une démarche,
// plusieurs pour « Tout synchroniser ». Chacune : { taskId, demarcheNumber }.
const _tasks = ref([])
const _currentIndex = ref(0)
const _finished = ref(true)

export const useSyncTask = () => {
  const currentTask = computed(() => _tasks.value[_currentIndex.value] ?? null)
  const currentTaskId = computed(() => (_finished.value ? null : currentTask.value?.taskId ?? null))
  const demarcheNumber = computed(() => currentTask.value?.demarcheNumber ?? null)
  const demarcheIndex = computed(() => _currentIndex.value + 1)
  const totalDemarches = computed(() => _tasks.value.length)

  const setTasks = (tasks) => {
    _tasks.value = tasks
    _currentIndex.value = 0
    _finished.value = tasks.length === 0
  }

  const setCurrentTaskId = (id, demarcheNumber = null) => {
    setTasks(id ? [{ taskId: id, demarcheNumber }] : [])
  }

  // Passe à la synchro suivante ; retourne false quand la dernière est terminée
  const finishCurrentTask = () => {
    if (_currentIndex.value < _tasks.value.length - 1) {
      _currentIndex.value += 1
      return true
    }

    _finished.value = true
    return false
  }

  return {
    currentTaskId,
    demarcheNumber,
    demarcheIndex,
    totalDemarches,
    setTasks,
    setCurrentTaskId,
    finishCurrentTask
  }
}
