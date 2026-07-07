import { ref, computed } from 'vue'

const _demarchesCount = ref(0)
const _demarcheIndex = ref(1)

export const useDemarcheContext = () => {
  const totalDemarches = computed(() => _demarchesCount.value)
  const demarcheIndex = computed(() => _demarcheIndex.value)

  const setDemarcheCount = (count) => {
    _demarchesCount.value = count
  }

  return { totalDemarches, demarcheIndex, setDemarcheCount }
}
