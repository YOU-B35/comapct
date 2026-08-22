<script setup>
import { formatUtc8 } from '@/utils/time'
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { formatOrderAmount } from '@/utils/operationsOverview'
import { formatMoneyDecimal } from '@/utils/format'
import { Right } from '@element-plus/icons-vue'
import AssigneeTableColumn from '@/components/common/AssigneeTableColumn.vue'

const props = defineProps({
  overview: { type: Object, default: null },
})

const router = useRouter()
const auth = useAuthStore()
const activePlatform = ref('temu')
const expandedStores = ref([])

const platforms = computed(() => props.overview?.platforms || [])

const platformRouteMap = {
  temu: 'temu',
  aliexpress: 'aliexpress',
  walmart: 'walmart',
  pdd: 'pdd',
  douyin: 'douyin',
  channels: 'channels',
  amazon: 'amazon',
  '1688': '1688',
  dtc: 'dtc',
}

function goPlatform(platformId) {
  const segment = platformRouteMap[platformId]
  if (!segment) return
  const prefix = auth.isBoss ? '/boss' : '/employee'
  router.push(`${prefix}/${segment}`)
}

function temuSections(store) {
  const sections = []
  if (store.restockItems?.length) {
    sections.push({
      key: 'restock',
      title: `备货跟进（${store.restockItems.length}）`,
      type: 'warning',
      rows: store.restockItems,
    })
  }
  if (store.lossItems?.length) {
    sections.push({
      key: 'loss',
      title: `亏损链接（${store.lossItems.length}）`,
      type: 'danger',
      rows: store.lossItems,
    })
  }
  return sections
}

function aliexpressSections(store) {
  const sections = []
  const jit = [...(store.jitUnshipped || []), ...(store.jitShipped || [])]
  if (jit.length) {
    sections.push({
      key: 'jit',
      title: `JIT 发货（未发 ${store.jitUnshipped?.length || 0}）`,
      type: store.jitUnshipped?.length ? 'danger' : 'success',
      rows: jit,
    })
  }
  const wh = [...(store.warehousePending || []), ...(store.warehouseShipped || [])]
  if (wh.length) {
    sections.push({
      key: 'warehouse',
      title: `仓发今日发货（待出 ${store.warehousePending?.length || 0}）`,
      type: store.warehousePending?.length ? 'warning' : 'success',
      rows: wh,
    })
  }
  if (store.todayViolations?.length) {
    sections.push({
      key: 'violations',
      title: `当日违规申诉（${store.todayViolations.length}）`,
      type: 'danger',
      rows: store.todayViolations,
    })
  }
  return sections
}

function walmartSections(store) {
  const sections = []
  const wfs = [...(store.wfsPending || []), ...(store.wfsShipped || [])]
  if (wfs.length) {
    sections.push({
      key: 'wfs',
      title: `WFS 发货（待处理 ${store.wfsPending?.length || 0}）`,
      type: store.wfsPending?.length ? 'danger' : 'success',
      rows: wfs,
    })
  }
  const seller = [...(store.sellerPending || []), ...(store.sellerShipped || [])]
  if (seller.length) {
    sections.push({
      key: 'seller',
      title: `自发货（待处理 ${store.sellerPending?.length || 0}）`,
      type: store.sellerPending?.length ? 'warning' : 'success',
      rows: seller,
    })
  }
  if (store.openListingIssues?.length) {
    sections.push({
      key: 'listings',
      title: `Listing 问题（${store.openListingIssues.length}）`,
      type: 'danger',
      rows: store.openListingIssues,
    })
  }
  return sections
}

function amazonSections(store) {
  const sections = []
  if (store.pendingMessages?.length) {
    sections.push({
      key: 'messages',
      title: `买家消息（待回复 ${store.pendingMessages.length}）`,
      type: 'danger',
      rows: store.pendingMessages,
    })
  }
  if (store.alertMetrics?.length) {
    sections.push({
      key: 'account',
      title: `账户爆红/预警（${store.alertMetrics.length}）`,
      type: 'danger',
      rows: store.alertMetrics,
    })
  }
  if (store.pendingReviews?.length) {
    sections.push({
      key: 'reviews',
      title: `差评待处理（${store.pendingReviews.length}）`,
      type: 'warning',
      rows: store.pendingReviews,
    })
  }
  if (store.alertCoupons?.length) {
    sections.push({
      key: 'coupons',
      title: `优惠券异常（${store.alertCoupons.length}）`,
      type: 'warning',
      rows: store.alertCoupons,
    })
  }
  if (store.alertShipments?.length) {
    sections.push({
      key: 'shipments',
      title: `货件预警（${store.alertShipments.length}）`,
      type: 'danger',
      rows: store.alertShipments,
    })
  }
  if (store.newCaseReplies?.length) {
    sections.push({
      key: 'cases',
      title: `Case 新回复（${store.newCaseReplies.length}）`,
      type: 'primary',
      rows: store.newCaseReplies,
    })
  }
  return sections
}

function dtcSections(store) {
  if (!store.todayOrders?.length) return []
  return [{
    key: 'orders',
    title: `今日订单（待发货 ${store.pendingShipCount ?? store.issueCount}）`,
    type: store.issueCount ? 'warning' : 'success',
    rows: store.todayOrders,
  }]
}

function alibaba1688Sections(store) {
  const sections = []
  if (store.pendingPayment?.length) {
    sections.push({
      key: 'pending_payment',
      title: `待付款（${store.pendingPayment.length}）`,
      type: 'warning',
      rows: store.pendingPayment,
    })
  }
  if (store.pendingShipment?.length) {
    sections.push({
      key: 'pending_shipment',
      title: `待发货（${store.pendingShipment.length}）`,
      type: 'danger',
      rows: store.pendingShipment,
    })
  }
  if (store.pendingReceive?.length) {
    sections.push({
      key: 'pending_receive',
      title: `待收货（${store.pendingReceive.length}）`,
      type: 'primary',
      rows: store.pendingReceive,
    })
  }
  if (store.supplierAlerts?.length) {
    sections.push({
      key: 'supplier_alerts',
      title: `供应商预警（${store.supplierAlerts.length}）`,
      type: 'danger',
      rows: store.supplierAlerts,
    })
  }
  return sections
}

function domesticSections(store) {
  const sections = []
  const orders = [...(store.pendingOrders || []), ...(store.shippedOrders || [])]
  if (orders.length) {
    sections.push({
      key: 'orders',
      title: `今日订单（待处理 ${store.pendingOrders?.length || 0}）`,
      type: store.pendingOrders?.length ? 'warning' : 'success',
      rows: orders,
    })
  }
  if (store.openIssues?.length) {
    sections.push({
      key: 'issues',
      title: `运营预警（${store.openIssues.length}）`,
      type: 'danger',
      rows: store.openIssues,
    })
  }
  return sections
}

function storeSections(platform, store) {
  if (platform.id === 'temu') return temuSections(store)
  if (platform.id === 'aliexpress') return aliexpressSections(store)
  if (platform.id === 'walmart') return walmartSections(store)
  if (['pdd', 'douyin', 'channels'].includes(platform.id)) return domesticSections(store)
  if (platform.id === 'amazon') return amazonSections(store)
  if (platform.id === '1688') return alibaba1688Sections(store)
  if (platform.id === 'dtc') return dtcSections(store)
  return []
}

function storeStatusType(store) {
  return store.issueCount ? 'danger' : 'success'
}

function storeStatusLabel(store, platform) {
  if (!store.issueCount) {
    if (platform.id === 'dtc') return '已全部发货'
    if (platform.id === '1688') return '采购正常'
    return '正常'
  }
  if (platform.id === 'dtc') return `${store.issueCount} 单待发货`
  if (platform.id === '1688') return `${store.issueCount} 项待跟进`
  return `${store.issueCount} 项待处理`
}

function initFromOverview(val) {
  if (!val?.platforms?.length) return

  const firstWithIssues = val.platforms.find((p) => p.issueCount)
  activePlatform.value = firstWithIssues?.id || val.platforms[0].id

  const ids = []
  for (const platform of val.platforms) {
    for (const store of platform.storeGroups || []) {
      if (store.issueCount) ids.push(store.storeId)
    }
  }
  expandedStores.value = ids.length
    ? ids
    : val.platforms[0]?.storeGroups?.[0]
      ? [val.platforms[0].storeGroups[0].storeId]
      : []
}

watch(() => props.overview, initFromOverview, { immediate: true })
</script>

<template>
  <el-card shadow="never" class="issues-panel">
    <template #header>
      <div class="panel-header">
        <div>
          <span class="panel-title">待处理问题</span>
          <el-text v-if="overview?.syncedAt" size="small" type="info">
            同步于 {{ formatUtc8(overview.syncedAt) }}
          </el-text>
        </div>
        <el-tag
          v-if="overview"
          :type="overview.totalIssues ? 'danger' : 'success'"
          effect="plain"
        >
          {{ overview.totalIssues ? `共 ${overview.totalIssues} 项` : '全部正常' }}
        </el-tag>
      </div>
    </template>

    <el-empty v-if="!overview" description="暂无运营数据" :image-size="72" />

    <el-tabs v-else v-model="activePlatform" class="platform-tabs">
      <el-tab-pane
        v-for="platform in platforms"
        :key="platform.id"
        :name="platform.id"
      >
        <template #label>
          <span class="tab-label">
            {{ platform.name }}
            <el-badge
              v-if="platform.issueCount"
              :value="platform.issueCount"
              class="tab-badge"
            />
          </span>
        </template>

        <div class="tab-toolbar">
          <el-text size="small" type="info">
            {{ platform.storeSummaries?.length || 0 }} 家店铺
          </el-text>
          <el-button
            v-if="platform.bound"
            type="primary"
            link
            size="small"
            :icon="Right"
            @click="goPlatform(platform.id)"
          >
            进入 {{ platform.name }} 运营
          </el-button>
        </div>

        <el-empty
          v-if="!platform.bound"
          description="暂无绑定店铺"
          :image-size="64"
        />

        <el-collapse v-else v-model="expandedStores" class="store-collapse">
          <el-collapse-item
            v-for="store in platform.storeGroups"
            :key="store.storeId"
            :name="store.storeId"
          >
            <template #title>
              <div class="store-title">
                <strong>{{ store.storeName }}</strong>
                <el-tag size="small" effect="plain">{{ store.assigneeName }}</el-tag>
                <el-tag :type="storeStatusType(store)" size="small">
                  {{ storeStatusLabel(store, platform) }}
                </el-tag>
              </div>
            </template>

            <template v-if="storeSections(platform, store).length">
              <div
                v-for="section in storeSections(platform, store)"
                :key="section.key"
                class="issue-block"
              >
                <div class="issue-block__title">
                  <el-tag :type="section.type" size="small" effect="plain">
                    {{ section.title }}
                  </el-tag>
                </div>

                <!-- Temu restock -->
                <el-table
                  v-if="platform.id === 'temu' && section.key === 'restock'"
                  :data="section.rows"
                  size="small"
                  stripe
                >
                  <el-table-column prop="name" label="商品" min-width="140" show-overflow-tooltip />
                  <AssigneeTableColumn width="90" />
                  <el-table-column prop="urgency" label="紧急度" width="90" />
                  <el-table-column prop="suggestedRestock" label="建议补货" width="90" align="right" />
                  <el-table-column label="备货状态" width="100" align="center">
                    <template #default="{ row }">
                      <el-tag :type="row.restockStatusType" size="small">{{ row.restockStatusLabel }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="note" label="说明" min-width="160" show-overflow-tooltip />
                </el-table>

                <!-- Temu loss -->
                <el-table
                  v-else-if="platform.id === 'temu' && section.key === 'loss'"
                  :data="section.rows"
                  size="small"
                  stripe
                >
                  <el-table-column prop="name" label="商品" min-width="130" show-overflow-tooltip />
                  <AssigneeTableColumn width="90" />
                  <el-table-column prop="spuId" label="SPU" min-width="110" />
                  <el-table-column prop="skcId" label="SKC" min-width="120" />
                  <el-table-column prop="skuId" label="SKU ID" min-width="130" />
                  <el-table-column label="单件利润" width="100" align="right">
                    <template #default="{ row }">
                      <el-text type="danger">{{ formatMoneyDecimal(row.unitProfit) }}</el-text>
                    </template>
                  </el-table-column>
                </el-table>

                <!-- AliExpress JIT -->
                <el-table
                  v-else-if="platform.id === 'aliexpress' && section.key === 'jit'"
                  :data="section.rows"
                  size="small"
                  stripe
                >
                  <el-table-column prop="orderNo" label="订单号" min-width="140" />
                  <AssigneeTableColumn width="90" />
                  <el-table-column prop="productName" label="商品" min-width="130" show-overflow-tooltip />
                  <el-table-column prop="shipDeadline" label="发货截止" width="150" />
                  <el-table-column label="发货" width="90" align="center">
                    <template #default="{ row }">
                      <el-tag :type="row.isShipped ? 'success' : 'danger'" size="small">
                        {{ row.isShipped ? '已发' : '未发' }}
                      </el-tag>
                    </template>
                  </el-table-column>
                </el-table>

                <!-- AliExpress warehouse -->
                <el-table
                  v-else-if="platform.id === 'aliexpress' && section.key === 'warehouse'"
                  :data="section.rows"
                  size="small"
                  stripe
                >
                  <el-table-column prop="orderNo" label="订单号" min-width="140" />
                  <AssigneeTableColumn width="90" />
                  <el-table-column prop="productName" label="商品" min-width="130" show-overflow-tooltip />
                  <el-table-column prop="warehouseName" label="发货仓" width="90" />
                  <el-table-column label="今日发货" width="100" align="center">
                    <template #default="{ row }">
                      <el-tag :type="row.isShippedToday ? 'success' : 'warning'" size="small">
                        {{ row.isShippedToday ? '已发' : '未发' }}
                      </el-tag>
                    </template>
                  </el-table-column>
                </el-table>

                <!-- AliExpress violations -->
                <el-table
                  v-else-if="platform.id === 'aliexpress' && section.key === 'violations'"
                  :data="section.rows"
                  size="small"
                  stripe
                >
                  <el-table-column prop="typeLabel" label="类型" width="100" />
                  <AssigneeTableColumn width="90" />
                  <el-table-column prop="orderNo" label="订单" min-width="130" />
                  <el-table-column label="罚款" width="100" align="right">
                    <template #default="{ row }">
                      <el-text type="danger">{{ formatMoneyDecimal(row.fineAmount) }}</el-text>
                    </template>
                  </el-table-column>
                  <el-table-column label="申诉" width="100" align="center">
                    <template #default="{ row }">
                      <el-tag :type="row.isAppealDone ? 'success' : 'warning'" size="small">
                        {{ row.appealStatusLabel }}
                      </el-tag>
                    </template>
                  </el-table-column>
                </el-table>

                <!-- Walmart WFS -->
                <el-table
                  v-else-if="platform.id === 'walmart' && section.key === 'wfs'"
                  :data="section.rows"
                  size="small"
                  stripe
                >
                  <el-table-column prop="orderNo" label="订单号" min-width="140" />
                  <AssigneeTableColumn width="90" />
                  <el-table-column prop="productName" label="商品" min-width="130" show-overflow-tooltip />
                  <el-table-column prop="shipDeadline" label="发货截止" width="150" />
                  <el-table-column label="发货" width="90" align="center">
                    <template #default="{ row }">
                      <el-tag :type="row.isShipped ? 'success' : 'danger'" size="small">
                        {{ row.isShipped ? '已发' : '未发' }}
                      </el-tag>
                    </template>
                  </el-table-column>
                </el-table>

                <!-- Walmart seller -->
                <el-table
                  v-else-if="platform.id === 'walmart' && section.key === 'seller'"
                  :data="section.rows"
                  size="small"
                  stripe
                >
                  <el-table-column prop="orderNo" label="订单号" min-width="140" />
                  <AssigneeTableColumn width="90" />
                  <el-table-column prop="productName" label="商品" min-width="130" show-overflow-tooltip />
                  <el-table-column prop="shipDeadline" label="发货截止" width="150" />
                  <el-table-column label="发货" width="90" align="center">
                    <template #default="{ row }">
                      <el-tag :type="row.isShipped ? 'success' : 'warning'" size="small">
                        {{ row.isShipped ? '已发' : '未发' }}
                      </el-tag>
                    </template>
                  </el-table-column>
                </el-table>

                <!-- Walmart listings -->
                <el-table
                  v-else-if="platform.id === 'walmart' && section.key === 'listings'"
                  :data="section.rows"
                  size="small"
                  stripe
                >
                  <el-table-column prop="typeLabel" label="类型" width="100" />
                  <AssigneeTableColumn width="90" />
                  <el-table-column prop="sku" label="SKU" width="100" />
                  <el-table-column prop="productName" label="商品" min-width="130" show-overflow-tooltip />
                  <el-table-column prop="detail" label="问题说明" min-width="180" show-overflow-tooltip />
                </el-table>

                <!-- Domestic platform orders -->
                <el-table
                  v-else-if="['pdd', 'douyin', 'channels'].includes(platform.id) && section.key === 'orders'"
                  :data="section.rows"
                  size="small"
                  stripe
                >
                  <el-table-column prop="orderNo" label="订单号" min-width="150" />
                  <AssigneeTableColumn width="90" />
                  <el-table-column prop="productName" label="商品" min-width="130" show-overflow-tooltip />
                  <el-table-column v-if="platform.id !== 'pdd'" prop="channel" label="来源" width="80" />
                  <el-table-column prop="shipDeadline" label="发货截止" width="150" />
                  <el-table-column label="状态" width="90" align="center">
                    <template #default="{ row }">
                      <el-tag :type="row.isShipped ? 'success' : 'warning'" size="small">
                        {{ row.isShipped ? '已发' : row.status }}
                      </el-tag>
                    </template>
                  </el-table-column>
                </el-table>

                <!-- Domestic platform issues -->
                <el-table
                  v-else-if="['pdd', 'douyin', 'channels'].includes(platform.id) && section.key === 'issues'"
                  :data="section.rows"
                  size="small"
                  stripe
                >
                  <el-table-column prop="typeLabel" label="类型" width="110" />
                  <AssigneeTableColumn width="90" />
                  <el-table-column prop="sku" label="SKU" width="100" />
                  <el-table-column prop="productName" label="商品" min-width="130" show-overflow-tooltip />
                  <el-table-column prop="detail" label="说明" min-width="180" show-overflow-tooltip />
                </el-table>

                <!-- Amazon buyer messages -->
                <el-table
                  v-else-if="platform.id === 'amazon' && section.key === 'messages'"
                  :data="section.rows"
                  size="small"
                  stripe
                >
                  <el-table-column prop="buyerName" label="买家" width="100" />
                  <AssigneeTableColumn width="90" />
                  <el-table-column prop="subject" label="主题" min-width="140" show-overflow-tooltip />
                  <el-table-column prop="preview" label="摘要" min-width="180" show-overflow-tooltip />
                  <el-table-column prop="receivedAt" label="收到时间" width="155" />
                </el-table>

                <!-- Amazon account metrics -->
                <el-table
                  v-else-if="platform.id === 'amazon' && section.key === 'account'"
                  :data="section.rows"
                  size="small"
                  stripe
                >
                  <el-table-column prop="label" label="指标" min-width="130" />
                  <AssigneeTableColumn width="90" />
                  <el-table-column prop="value" label="当前值" width="100" />
                  <el-table-column label="状态" width="90" align="center">
                    <template #default="{ row }">
                      <el-tag :type="row.isCritical ? 'danger' : 'warning'" size="small">
                        {{ row.isCritical ? '爆红' : '预警' }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="note" label="建议" min-width="180" show-overflow-tooltip />
                </el-table>

                <!-- Amazon reviews -->
                <el-table
                  v-else-if="platform.id === 'amazon' && section.key === 'reviews'"
                  :data="section.rows"
                  size="small"
                  stripe
                >
                  <el-table-column label="星级" width="80" align="center">
                    <template #default="{ row }">
                      <el-tag type="danger" size="small">{{ row.rating }} 星</el-tag>
                    </template>
                  </el-table-column>
                  <AssigneeTableColumn width="90" />
                  <el-table-column prop="productName" label="商品" min-width="140" show-overflow-tooltip />
                  <el-table-column prop="content" label="内容" min-width="180" show-overflow-tooltip />
                </el-table>

                <!-- Amazon coupons -->
                <el-table
                  v-else-if="platform.id === 'amazon' && section.key === 'coupons'"
                  :data="section.rows"
                  size="small"
                  stripe
                >
                  <el-table-column prop="name" label="优惠券" min-width="150" show-overflow-tooltip />
                  <AssigneeTableColumn width="90" />
                  <el-table-column prop="endAt" label="到期" width="110" />
                  <el-table-column prop="note" label="说明" min-width="180" show-overflow-tooltip />
                </el-table>

                <!-- Amazon shipments -->
                <el-table
                  v-else-if="platform.id === 'amazon' && section.key === 'shipments'"
                  :data="section.rows"
                  size="small"
                  stripe
                >
                  <el-table-column prop="shipmentId" label="货件号" min-width="130" />
                  <AssigneeTableColumn width="90" />
                  <el-table-column prop="productName" label="商品" min-width="140" show-overflow-tooltip />
                  <el-table-column label="实收/预期" width="100" align="center">
                    <template #default="{ row }">{{ row.unitsReceived }} / {{ row.unitsExpected }}</template>
                  </el-table-column>
                  <el-table-column prop="note" label="说明" min-width="180" show-overflow-tooltip />
                </el-table>

                <!-- Amazon cases -->
                <el-table
                  v-else-if="platform.id === 'amazon' && section.key === 'cases'"
                  :data="section.rows"
                  size="small"
                  stripe
                >
                  <el-table-column prop="caseId" label="Case" width="120" />
                  <AssigneeTableColumn width="90" />
                  <el-table-column prop="subject" label="主题" min-width="160" show-overflow-tooltip />
                  <el-table-column prop="preview" label="最新回复" min-width="180" show-overflow-tooltip />
                </el-table>

                <!-- DTC orders -->
                <el-table
                  v-else-if="platform.id === 'dtc'"
                  :data="section.rows"
                  size="small"
                  stripe
                >
                  <el-table-column prop="orderNo" label="订单号" min-width="150" />
                  <AssigneeTableColumn width="90" />
                  <el-table-column prop="productName" label="商品" min-width="130" show-overflow-tooltip />
                  <el-table-column prop="customerCountry" label="目的国" width="80" />
                  <el-table-column label="金额" width="100" align="right">
                    <template #default="{ row }">
                      {{ formatOrderAmount(row.amount, row.currency) }}
                    </template>
                  </el-table-column>
                  <el-table-column label="发货" width="90" align="center">
                    <template #default="{ row }">
                      <el-tag :type="row.statusType" size="small">{{ row.statusLabel }}</el-tag>
                    </template>
                  </el-table-column>
                </el-table>

                <!-- 1688 purchase -->
                <el-table
                  v-else-if="platform.id === '1688' && section.key !== 'supplier_alerts'"
                  :data="section.rows"
                  size="small"
                  stripe
                >
                  <el-table-column prop="orderNo" label="采购单号" min-width="130" />
                  <AssigneeTableColumn width="90" />
                  <el-table-column prop="productName" label="商品" min-width="130" show-overflow-tooltip />
                  <el-table-column prop="supplierName" label="供应商" min-width="130" show-overflow-tooltip />
                  <el-table-column prop="linkedPlatform" label="关联平台" width="100" />
                  <el-table-column label="状态" width="90" align="center">
                    <template #default="{ row }">
                      <el-tag :type="row.statusType" size="small">{{ row.statusLabel }}</el-tag>
                    </template>
                  </el-table-column>
                </el-table>

                <!-- 1688 supplier alerts -->
                <el-table
                  v-else-if="platform.id === '1688'"
                  :data="section.rows"
                  size="small"
                  stripe
                >
                  <el-table-column prop="typeLabel" label="类型" width="100" />
                  <AssigneeTableColumn width="90" />
                  <el-table-column prop="supplierName" label="供应商" min-width="130" show-overflow-tooltip />
                  <el-table-column prop="productName" label="商品" min-width="120" show-overflow-tooltip />
                  <el-table-column prop="detail" label="详情" min-width="180" show-overflow-tooltip />
                </el-table>
              </div>
            </template>

            <el-empty
              v-else
              description="该店铺暂无待跟进问题"
              :image-size="48"
            />
          </el-collapse-item>
        </el-collapse>
      </el-tab-pane>
    </el-tabs>
  </el-card>
</template>

<style scoped>
.issues-panel :deep(.el-card__header) {
  padding: 18px 20px;
}

.platform-tabs :deep(.el-tabs__header) {
  margin-bottom: 12px;
}

.tab-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.tab-badge :deep(.el-badge__content) {
  position: relative;
  top: 0;
  transform: none;
}

.tab-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.store-title {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.issue-block + .issue-block {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px dashed var(--ch-border);
}

.issue-block__title {
  margin-bottom: 10px;
}
</style>
