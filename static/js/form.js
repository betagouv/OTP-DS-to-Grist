const updateDSTokenStatus = (config) => {
  const dsTokenElement = document.getElementById('ds_api_token')
  const dsTokenElementvalue = dsTokenElement.value

  if (dsTokenElementvalue || config.ds_api_token) {
    dsTokenElement.placeholder = '************************************************************************************'
  } else {
    dsTokenElement.placeholder = ''
  }
}

const updateGristKeyStatus = (config) => {
  const gristKeyElement = document.getElementById('grist_api_key');
  const gristKeyElementValue = gristKeyElement.value;

  if (gristKeyElementValue || config.grist_api_key) {
    gristKeyElement.placeholder = '****************************************'
  } else {
    gristKeyElement.placeholder = ''
  }
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { updateDSTokenStatus, updateGristKeyStatus }
}
