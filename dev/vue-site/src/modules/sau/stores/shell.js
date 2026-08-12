import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

/** Secondary sidebar collapse for 自媒体运营 module. */
export const useSauShellStore = defineStore('sauShell', () => {
  const isCollapse = ref(false)

  const asideWidth = computed(() => (isCollapse.value ? '64px' : '200px'))

  function toggleCollapse() {
    isCollapse.value = !isCollapse.value
  }

  function setCollapse(value) {
    isCollapse.value = Boolean(value)
  }

  return {
    isCollapse,
    asideWidth,
    toggleCollapse,
    setCollapse,
  }
})
