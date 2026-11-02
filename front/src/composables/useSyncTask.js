import { ref, computed } from 'vue'

// Synchros suivies, dans leur ordre d'exécution : une seule pour une démarche,
// plusieurs pour « Tout synchroniser ». Chacune : { taskId, demarcheNumber, demarcheTitle }.
const _tasks = ref([])
const _currentIndex = ref(0)
const _finished = ref(true)
// Vrai pour « Tout synchroniser », même avec une seule démarche
const _isSeries = ref(false)
// Dernier état connu de chaque synchro suivie, logs cumulés (le serveur les envoie en delta)
const _states = ref({})

export const useSyncTask = () => {
  const currentTask = computed(() => _tasks.value[_currentIndex.value] ?? null)
  const currentTaskId = computed(() => (_finished.value ? null : currentTask.value?.taskId ?? null))
  const demarcheNumber = computed(() => currentTask.value?.demarcheNumber ?? null)
  const demarcheIndex = computed(() => _currentIndex.value + 1)
  const totalDemarches = computed(() => _tasks.value.length)

  const seriesTasks = computed(() => (_isSeries.value
    ? _tasks.value.map(task => ({ ...task, ..._states.value[task.taskId] }))
    : []
  ))

  const setTasks = (tasks, isSeries = true) => {
    _tasks.value = tasks
    _currentIndex.value = 0
    _finished.value = tasks.length === 0
    _isSeries.value = isSeries && tasks.length > 0
    _states.value = Object.fromEntries(tasks.map(task => [
      task.taskId,
      { status: 'queued', message: '', result: null, syncReason: null, logs: [] }
    ]))
  }

  const setCurrentTaskId = (id, demarcheNumber = null) => {
    setTasks(id ? [{ taskId: id, demarcheNumber }] : [], false)
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

  // Enregistre un événement task_update ; ignoré si la synchro n'est pas suivie
  const recordTaskUpdate = (taskId, task) => {
    const previous = _states.value[taskId]
    if (!previous) return

    _states.value = {
      ..._states.value,
      [taskId]: {
        status: task.status,
        message: task.message ?? '',
        result: task.result ?? null,
        syncReason: task.sync_reason ?? null,
        logs: [...previous.logs, ...(task.logs ?? [])]
      }
    }
  }

  return {
    currentTaskId,
    demarcheNumber,
    demarcheIndex,
    totalDemarches,
    seriesTasks,
    setTasks,
    setCurrentTaskId,
    finishCurrentTask,
    recordTaskUpdate
  }
}
