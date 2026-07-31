import { computed, ref, unref, watch } from 'vue'
import { fuzzyMatchRow } from '@/utils/fuzzyMatch'

function resolveSourceList(source) {
  const raw = typeof source === 'function' ? source() : unref(source)
  return Array.isArray(raw) ? raw : []
}

export function useFuzzySearchPagination(source, options = {}) {
  const keyword = ref('')
  const page = ref(1)
  const pageSize = ref(options.pageSize ?? 20)
  const fields = options.fields ?? ['sku', 'name', 'storeName']

  const filtered = computed(() => {
    const list = resolveSourceList(source)
    if (!String(keyword.value || '').trim()) return list
    if (typeof options.matchRow === 'function') {
      return list.filter((row) => options.matchRow(row, keyword.value))
    }
    return list.filter((row) => fuzzyMatchRow(row, keyword.value, fields))
  })

  const total = computed(() => filtered.value.length)

  const paged = computed(() => {
    const start = (page.value - 1) * pageSize.value
    return filtered.value.slice(start, start + pageSize.value)
  })

  watch([keyword, () => resolveSourceList(source), pageSize], () => {
    page.value = 1
  })

  watch(total, (count) => {
    const maxPage = Math.max(1, Math.ceil(count / pageSize.value) || 1)
    if (page.value > maxPage) page.value = maxPage
  })

  return {
    keyword,
    page,
    pageSize,
    filtered,
    total,
    paged,
  }
}
