import { ref, computed } from 'vue'

// Synchros suivies, dans leur ordre d'exécution : une seule pour une démarche,
// plusieurs pour « Tout synchroniser ». Chacune : { taskId, demarcheNumber }.
const _tasks = ref([])
const _currentIndex = ref(0)
const _finished = ref(true)
// Dernier état connu de chaque synchro suivie, logs cumulés (le serveur les envoie en delta)
const _states = ref({})

const FINISHED_STATUSES = ['completed', 'error']

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

  // Reprend les synchros en cours renvoyées par le serveur (message sync_state),
  // chacune { task_id, task } avec tous ses logs : la page rouverte suit la
  // première non terminée
  const restoreTasks = (syncs) => {
    _tasks.value = syncs.map(sync => ({
      taskId: sync.task_id,
      demarcheNumber: sync.task.demarche_number ?? null
    }))
    _states.value = Object.fromEntries(syncs.map(sync => [
      sync.task_id,
      // Seules les synchros manuelles ont un état sur le serveur
      { ...stateFromTask(sync.task), auto: false, logs: sync.task.logs ?? [] }
    ]))

    const currentIndex = syncs.findIndex(sync => !FINISHED_STATUSES.includes(sync.task.status))
    _currentIndex.value = currentIndex === -1 ? Math.max(syncs.length - 1, 0) : currentIndex
    _finished.value = currentIndex === -1
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
        ...stateFromTask(task),
        logs: [...previous.logs, ...newLogs(previous.logs, task.logs ?? [])]
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
    recordTaskUpdate,
    restoreTasks
  }
}

// --- Fonctions privées ---

// Champs d'affichage d'une synchro, depuis une tâche du serveur
const stateFromTask = (task) => ({
  status: task.status,
  message: task.message ?? '',
  result: task.result ?? null,
  syncReason: task.sync_reason ?? null,
  endTime: task.end_time ? new Date(task.end_time * 1000) : null
})

// Logs reçus qui ne sont pas encore connus : un état complet (restoreTasks) et
// les envois en delta peuvent se recouvrir, la position (index) les départage.
// Un log sans position est toujours ajouté.
const newLogs = (knownLogs, receivedLogs) => {
  const lastIndex = knownLogs.at(-1)?.index ?? -1

  return receivedLogs.filter(log => !(log.index <= lastIndex))
}
