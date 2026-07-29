<script setup>
import { computed, ref } from 'vue'
import { formatMoneyDecimal, formatPercent } from '@/utils/format'
import AssigneeTableColumn from '@/components/common/AssigneeTableColumn.vue'
import TableQueryBar from '@/components/common/TableQueryBar.vue'
import { useFuzzySearchPagination } from '@/composables/useFuzzySearchPagination'

const props = defineProps({
  products: { type: Array, required: true },
  showStoreColumn: { type: Boolean, default: false },
})

const filterLoss = ref('all')

const categoryFiltered = computed(() => {
  const withCost = props.products.filter((p) => p.hasCost)
  if (filterLoss.value === 'loss') return withCost.filter((p) => p.isLoss)
  if (filterLoss.value === 'profit') return withCost.filter((p) => !p.isLoss)
  return withCost
})

const costReadyCount = computed(() => props.products.filter((p) => p.hasCost).length)

const { keyword, page, pageSize, total, paged } = useFuzzySearchPagination(categoryFiltered, {
  fields: ['sku', 'name', 'storeName', 'spuId', 'skcId'],
})
</script>

<template>
  <div>
    <el-card shadow="never">
      <template #header>
        <el-space>
          <span>价格利润分析</span>
          <el-tag type="info" effect="plain">已录入成本 {{ costReadyCount }} / {{ products.length }}</el-tag>
          <el-radio-group v-model="filterLoss" size="small">
            <el-radio-button value="all">全部</el-radio-button>
            <el-radio-button value="loss">仅亏损</el-radio-button>
            <el-radio-button value="profit">仅盈利</el-radio-button>
          </el-radio-group>
        </el-space>
      </template>

      <TableQueryBar
        v-model:keyword="keyword"
        v-model:page="page"
        v-model:page-size="pageSize"
        :total="total"
      />

      <el-empty v-if="!total" description="暂无匹配 SKU" />

      <el-table v-else :data="paged" stripe>
        <el-table-column v-if="showStoreColumn" prop="storeName" label="所属店铺" width="130" show-overflow-tooltip />
        <AssigneeTableColumn />
        <el-table-column prop="sku" label="SKU" width="110" fixed />
        <el-table-column prop="spuId" label="SPU" width="120" show-overflow-tooltip />
        <el-table-column prop="skcId" label="SKC" width="120" show-overflow-tooltip />
        <el-table-column prop="name" label="商品名称" min-width="180" show-overflow-tooltip />
        <el-table-column label="售价" width="90" align="right">
          <template #default="{ row }">{{ formatMoneyDecimal(row.sellingPrice) }}</template>
        </el-table-column>
        <el-table-column label="成本" width="90" align="right">
          <template #default="{ row }">{{ formatMoneyDecimal(row.costPrice) }}</template>
        </el-table-column>
        <el-table-column label="平台费" width="90" align="right">
          <template #default="{ row }">{{ formatMoneyDecimal(row.platformFee) }}</template>
        </el-table-column>
        <el-table-column label="物流费" width="90" align="right">
          <template #default="{ row }">{{ formatMoneyDecimal(row.logisticsFee) }}</template>
        </el-table-column>
        <el-table-column label="单件利润" width="110" align="right">
          <template #default="{ row }">
            <el-text :type="row.isLoss ? 'danger' : 'success'">
              {{ formatMoneyDecimal(row.unitProfit) }}
            </el-text>
          </template>
        </el-table-column>
        <el-table-column label="利润率" width="100" align="right">
          <template #default="{ row }">
            <el-text :type="row.isLoss ? 'danger' : 'success'">
              {{ formatPercent(row.profitRate) }}
            </el-text>
          </template>
        </el-table-column>
        <el-table-column label="官方仓库存" width="110" align="right" prop="officialStock" />
        <el-table-column label="状态" width="100" fixed="right">
          <template #default="{ row }">
            <el-tag v-if="row.isLoss" type="danger" effect="dark">亏损</el-tag>
            <el-tag v-else type="success" effect="plain">盈利</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="建议" width="120" fixed="right">
          <template #default="{ row }">
            <el-text v-if="row.isLoss" type="danger" size="small">调价或下架</el-text>
            <el-text v-else type="info" size="small">维持</el-text>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>
