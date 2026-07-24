export const sortConfigs = (configs) => {
  const unsaved = configs.filter(config => !config)
  const saved = configs.filter(config => config)
    .sort((a, b) => a.otp_config_id - b.otp_config_id)
  return [...saved, ...unsaved]
}

export const canDeleteConfig = (config) => !!config?.otp_config_id

export const canSyncConfig = (config, syncRunning) => !!config?.otp_config_id && !syncRunning
