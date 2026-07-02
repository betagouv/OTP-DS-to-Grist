import { ref, computed } from 'vue'

const _count = ref(0)
const _index = ref(1)

export const useDemarcheContext = () => {
  const totalDemarches = computed(() => _count.value)
  const demarcheIndex = computed(() => _index.value)

  const setDemarcheCount = (count) => {
    _count.value = count
  }

  return { totalDemarches, demarcheIndex, setDemarcheCount }
}
