<script setup>
import { computed } from 'vue'
import TableQueryBar from '@/components/common/TableQueryBar.vue'
import { useFuzzySearchPagination } from '@/composables/useFuzzySearchPagination'

const props = defineProps({
  data: { type: Array, default: () => [] },
  fields: { type: Array, default: () => ['name', 'sku', 'label'] },
  placeholder: { type: String, default: '模糊搜索' },
  emptyText: { type: String, default: '暂无数据' },
  pageSize: { type: Number, default: 20 },
  pageSizes: { type: Array, default: () => [10, 20, 50, 100] },
  showToolbar: { type: Boolean, default: true },
})

const sourceList = computed(() => (Array.isArray(props.data) ? props.data : []))

const { keyword, page, pageSize, total, paged } = useFuzzySearchPagination(sourceList, {
  fields: props.fields,
  pageSize: props.pageSize,
})
</script>

<template>
  <div class="searchable-table">
    <TableQueryBar
      v-if="showToolbar"
      v-model:keyword="keyword"
      v-model:page="page"
      v-model:page-size="pageSize"
      :total="total"
      :placeholder="placeholder"
      :page-sizes="pageSizes"
    >
      <el-empty v-if="!total" :description="emptyText" :image-size="64" />
      <el-table v-else :data="paged" v-bind="$attrs">
        <slot />
      </el-table>
    </TableQueryBar>

    <template v-else>
      <el-empty v-if="!total" :description="emptyText" :image-size="64" />
      <el-table v-else :data="paged" v-bind="$attrs">
        <slot />
      </el-table>
    </template>
  </div>
</template>

<style scoped>
.searchable-table {
  width: 100%;
}
</style>
