export const sortConfigs = (configs) => {
  const unsaved = configs.filter(config => !config?.otp_config_id)
  const saved = configs.filter(config => config?.otp_config_id)
    .sort((a, b) => b.otp_config_id - a.otp_config_id)
  return [...unsaved, ...saved]
}

export const canDeleteConfig = (config) => !!config?.otp_config_id

export const canSyncConfig = (config, syncRunning) => !!config?.otp_config_id && !syncRunning
