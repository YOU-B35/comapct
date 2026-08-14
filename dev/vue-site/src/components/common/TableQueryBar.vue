<script setup>
import { computed, useSlots } from 'vue'

const keyword = defineModel('keyword', { type: String, default: '' })
const page = defineModel('page', { type: Number, default: 1 })
const pageSize = defineModel('pageSize', { type: Number, default: 10 })

const props = defineProps({
  total: { type: Number, default: 0 },
  placeholder: { type: String, default: '搜索 SKU / 商品名称 / 店铺' },
  pageSizes: { type: Array, default: () => [10, 20, 50, 100] },
  /** 是否显示每页条数切换；固定 10 条时建议关闭 */
  showSizes: { type: Boolean, default: true },
  /** 是否显示搜索框 */
  showSearch: { type: Boolean, default: true },
})

const slots = useSlots()
const hasBody = computed(() => Boolean(slots.default))

const pagerLayout = computed(() =>
  props.showSizes ? 'sizes, prev, pager, next, jumper' : 'prev, pager, next, jumper',
)
</script>

<template>
  <div class="table-query-bar" :class="{ 'table-query-bar--with-body': hasBody }">
    <template v-if="hasBody">
      <div v-if="showSearch" class="table-query-bar__top">
        <el-input
          v-model="keyword"
          clearable
          :placeholder="placeholder"
          class="table-query-bar__search"
        />
      </div>

      <div class="table-query-bar__body">
        <slot />
      </div>

      <div class="table-query-bar__footer">
        <el-text type="info" class="table-query-bar__total">共 {{ total }} 条</el-text>
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="pageSizes"
          :layout="pagerLayout"
          background
          small
          class="table-query-bar__pager"
        />
      </div>
    </template>

    <template v-else>
      <div class="table-query-bar__inline">
        <el-input
          v-if="showSearch"
          v-model="keyword"
          clearable
          :placeholder="placeholder"
          class="table-query-bar__search"
        />
        <el-text type="info" class="table-query-bar__total">共 {{ total }} 条</el-text>
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="pageSizes"
          :layout="pagerLayout"
          background
          small
          class="table-query-bar__pager"
        />
      </div>
    </template>
  </div>
</template>

<style scoped>
.table-query-bar {
  display: grid;
  gap: 12px;
  width: 100%;
}

.table-query-bar__top,
.table-query-bar__inline {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}

.table-query-bar__search {
  width: min(320px, 100%);
}

.table-query-bar__body {
  min-width: 0;
}

.table-query-bar__footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
}

.table-query-bar__total {
  flex: 1;
  min-width: 72px;
}

.table-query-bar__footer .table-query-bar__total {
  margin-right: auto;
  flex: 0 1 auto;
}

.table-query-bar__pager {
  margin-left: auto;
}
</style>
