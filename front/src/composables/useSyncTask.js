import { ref, computed } from 'vue'

// Synchros suivies, dans leur ordre d'exécution : une seule pour une démarche,
// plusieurs pour « Tout synchroniser ». Chacune : { taskId, demarcheNumber }.
const _tasks = ref([])
const _currentIndex = ref(0)
const _finished = ref(true)
// Dernier état connu de chaque synchro suivie, logs cumulés (le serveur les envoie en delta)
const _states = ref({})

export const useSyncTask = () => {
  const currentTask = computed(() => _tasks.value[_currentIndex.value] ?? null)
  const currentTaskId = computed(() => (_finished.value ? null : currentTask.value?.taskId ?? null))
  const demarcheNumber = computed(() => currentTask.value?.demarcheNumber ?? null)
  const demarcheIndex = computed(() => _currentIndex.value + 1)
  const totalDemarches = computed(() => _tasks.value.length)

  const seriesTasks = computed(() =>
    _tasks.value.map(task => ({ ...task, ..._states.value[task.taskId] }))
  )

  const setTasks = (tasks) => {
    _tasks.value = tasks
    _currentIndex.value = 0
    _finished.value = tasks.length === 0
    _states.value = Object.fromEntries(tasks.map(task => [
      task.taskId,
      // Lancées depuis la page : toujours manuelles
      { status: 'queued', message: '', result: null, syncReason: null, endTime: null, auto: false, logs: [] }
    ]))
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

  // Enregistre un événement task_update ; ignoré si la synchro n'est pas suivie
  const recordTaskUpdate = (taskId, task) => {
    const previous = _states.value[taskId]
    if (!previous) return

    _states.value = {
      ..._states.value,
      [taskId]: {
        ...previous,
        status: task.status,
        message: task.message ?? '',
        result: task.result ?? null,
        syncReason: task.sync_reason ?? null,
        endTime: task.end_time ? new Date(task.end_time * 1000) : null,
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
