import { api } from '../utils/InternalApi'

export const useSyncHistory = () => {
  // Dernière synchro de chaque démarche, lue en base, en lignes du tableau
  const fetchHistory = async () => {
    const data = await api.getLatestSyncsByDemarche()

    return data.syncs.map(toRow)
  }

  return { fetchHistory }
}

// Même forme qu'une ligne de synchro suivie en direct (useSyncTask), sans logs
const toRow = (sync) => {
  const isSuccess = sync.status === 'success'
  const isUpToDate = isSuccess && !sync.success_count && !sync.error_count

  return {
    key: `history_${sync.otp_config_id}`,
    demarcheNumber: sync.demarche_number,
    status: isSuccess ? 'completed' : 'error',
    message: sync.message ?? '',
    result: { success_count: sync.success_count, error_count: sync.error_count },
    // Non enregistré en base : déduit comme le faisaient les bandeaux
    syncReason: isUpToDate ? 'already_up_to_date' : null,
    endTime: sync.timestamp ? new Date(sync.timestamp) : null,
    auto: sync.auto
  }
}
