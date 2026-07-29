<script setup>
import { computed, ref } from 'vue'
import { SLOW_MOVING_THRESHOLDS } from '@/constants/temu'
import AssigneeTableColumn from '@/components/common/AssigneeTableColumn.vue'
import TableQueryBar from '@/components/common/TableQueryBar.vue'
import { useFuzzySearchPagination } from '@/composables/useFuzzySearchPagination'

const props = defineProps({
  products: { type: Array, required: true },
  showStoreColumn: { type: Boolean, default: false },
})

const activeTier = ref('all')

const tierCounts = computed(() => ({
  all: props.products.filter((p) => p.daysWithoutSale >= 15).length,
  15: props.products.filter((p) => p.daysWithoutSale >= 15 && p.daysWithoutSale < 30).length,
  30: props.products.filter((p) => p.daysWithoutSale >= 30 && p.daysWithoutSale < 45).length,
  45: props.products.filter((p) => p.daysWithoutSale >= 45).length,
}))

const tierFiltered = computed(() => {
  const list = props.products.filter((p) => p.slowMoving)
  if (activeTier.value === 'all') return list.sort((a, b) => b.daysWithoutSale - a.daysWithoutSale)
  const min = Number(activeTier.value)
  const max = min === 15 ? 30 : min === 30 ? 45 : Infinity
  return list
    .filter((p) => p.daysWithoutSale >= min && p.daysWithoutSale < max)
    .sort((a, b) => b.daysWithoutSale - a.daysWithoutSale)
})

const { keyword, page, pageSize, total, paged } = useFuzzySearchPagination(tierFiltered, {
  fields: ['sku', 'name', 'storeName', 'category'],
})

function tierTagType(row) {
  if (row.daysWithoutSale >= 45) return 'danger'
  if (row.daysWithoutSale >= 30) return 'warning'
  return 'info'
}
</script>

<template>
  <div>
    <el-row :gutter="16" style="margin-bottom: 16px">
      <el-col v-for="tier in SLOW_MOVING_THRESHOLDS" :key="tier.days" :xs="24" :sm="8">
        <el-card shadow="never" :class="['tier-card', tier.level]">
          <el-statistic :title="tier.label" :value="tierCounts[tier.days]" />
          <el-text size="small" type="info">
            {{ tier.days === 15 ? '动销放缓，关注促销' : tier.days === 30 ? '需制定清仓方案' : '严重积压，建议下架' }}
          </el-text>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never">
      <template #header>
        <el-space wrap>
          <span>全托管官方仓滞销清单</span>
          <el-radio-group v-model="activeTier" size="small">
            <el-radio-button value="all">全部 ({{ tierCounts.all }})</el-radio-button>
            <el-radio-button value="15">15 日 ({{ tierCounts[15] }})</el-radio-button>
            <el-radio-button value="30">30 日 ({{ tierCounts[30] }})</el-radio-button>
            <el-radio-button value="45">45 日+ ({{ tierCounts[45] }})</el-radio-button>
          </el-radio-group>
        </el-space>
      </template>

      <TableQueryBar
        v-model:keyword="keyword"
        v-model:page="page"
        v-model:page-size="pageSize"
        :total="total"
      />

      <el-empty v-if="!total" description="当前阈值下无滞销 SKU" />

      <el-table v-else :data="paged" stripe>
        <el-table-column v-if="showStoreColumn" prop="storeName" label="所属店铺" width="130" show-overflow-tooltip />
        <AssigneeTableColumn />
        <el-table-column prop="sku" label="SKU" width="110" />
        <el-table-column prop="name" label="商品名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="category" label="类目" width="90" />
        <el-table-column label="未动销天数" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="tierTagType(row)" effect="dark">{{ row.daysWithoutSale }} 天</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="预警级别" width="120">
          <template #default="{ row }">
            <el-tag :type="row.slowMoving.tagType">{{ row.slowMoving.alertTitle }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="officialStock" label="官方仓库存" width="110" align="right" />
        <el-table-column label="7 日总销量" width="110" align="right">
          <template #default="{ row }">
            {{ Number.isFinite(Number(row.sales7Total)) ? row.sales7Total : (row.salesLast7Days || []).reduce((s, n) => s + n, 0) }}
          </template>
        </el-table-column>
        <el-table-column label="30 日总销量" width="110" align="right">
          <template #default="{ row }">
            {{ row.sales30Total ?? '—' }}
          </template>
        </el-table-column>
        <el-table-column label="处理建议" min-width="160">
          <template #default="{ row }">
            <el-text v-if="row.daysWithoutSale >= 45" type="danger" size="small">紧急清仓 / 下架</el-text>
            <el-text v-else-if="row.daysWithoutSale >= 30" type="warning" size="small">降价促销 / 捆绑销售</el-text>
            <el-text v-else type="info" size="small">加大曝光 / 优惠券</el-text>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.tier-card.caution {
  border-left: 3px solid var(--el-color-warning);
}

.tier-card.warning {
  border-left: 3px solid var(--el-color-danger-light-3);
}

.tier-card.critical {
  border-left: 3px solid var(--el-color-danger);
}
</style>
