import { ref, computed } from 'vue'

const _count = ref(0)
const _index = ref(1)

export function useDemarcheContext() {
  const totalDemarches = computed(() => _count.value)
  const demarcheIndex = computed(() => _index.value)

  function setDemarcheCount(n) {
    _count.value = n
  }

  return { totalDemarches, demarcheIndex, setDemarcheCount }
}
