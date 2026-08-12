<script setup>
import { computed, onActivated, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { loadDtcOperationalData } from '@/api/dtc'
import { fetchDtcStores } from '@/api/platformAccounts'
import { scopeStores } from '@/utils/scope'
import { useStoreAssignees } from '@/composables/useStoreAssignees'
import PageHeader from '@/components/common/PageHeader.vue'
import PageScroll from '@/components/common/PageScroll.vue'
import PageSection from '@/components/common/PageSection.vue'
import DtcBossOverview from '@/components/dtc/DtcBossOverview.vue'
import DtcProductTable from '@/components/dtc/DtcProductTable.vue'
import DtcTrafficPanel from '@/components/dtc/DtcTrafficPanel.vue'
import DtcCampaignPanel from '@/components/dtc/DtcCampaignPanel.vue'
import { aggregateDtcTraffic, normalizeDtcStore } from '@/utils/dtcStore'
import { isPlatformOperationalDemoOnly, platformOperationalHint } from '@/utils/platformOperationalMode'

const router = useRouter()
const auth = useAuthStore()
const { assigneeMap, loadAssignees, enrichItems } = useStoreAssignees()
const activeTab = ref('products')
const selectedStoreId = ref('all')
const dtcStores = ref([])
const dtcDemo = ref({ products: [], campaigns: [], traffic: {}, meta: {} })
const loadingStores = ref(false)

const operationalDemoOnly = computed(() => isPlatformOperationalDemoOnly('dtc'))
const operationalHint = computed(() => platformOperationalHint('dtc'))

const boundStoreIds = computed(() => dtcStores.value.map((store) => store.id))

const storeNameMap = computed(() =>
  Object.fromEntries(dtcStores.value.map((store) => [store.id, store.storeName])),
)

const overviewSites = computed(() => {
  const stores =
    selectedStoreId.value === 'all'
      ? dtcStores.value
      : dtcStores.value.filter((store) => store.id === selectedStoreId.value)
  return stores.map(normalizeDtcStore)
})

function withStoreMeta(list) {
  return enrichItems(
    list.map((product) => ({
      ...product,
      storeName: storeNameMap.value[product.storeId] || '未分配店铺',
    })),
  )
}

const allProducts = computed(() => withStoreMeta(dtcDemo.value.products))

const products = computed(() => {
  if (selectedStoreId.value === 'all') return allProducts.value
  return allProducts.value.filter((product) => product.storeId === selectedStoreId.value)
})

const overviewProducts = computed(() => {
  if (selectedStoreId.value === 'all') return allProducts.value
  return products.value
})

const campaigns = computed(() => {
  if (selectedStoreId.value === 'all') return dtcDemo.value.campaigns
  return dtcDemo.value.campaigns.filter((item) => item.storeId === selectedStoreId.value)
})

const trafficSources = computed(() => {
  if (selectedStoreId.value === 'all') {
    return aggregateDtcTraffic(dtcDemo.value.traffic, boundStoreIds.value)
  }
  return dtcDemo.value.traffic[selectedStoreId.value] || []
})

const showSiteList = computed(
  () => selectedStoreId.value === 'all' && overviewSites.value.length > 0,
)

const showStoreColumn = computed(() => selectedStoreId.value === 'all')

const alertCount = computed(() => {
  const p = products.value
  return {
    lowstock: p.filter((i) => i.stock < 200).length,
    slow: p.filter((i) => i.daysWithoutSale >= 15).length,
    hot: p.filter((i) => i.dailyOrders >= 20).length,
  }
})

async function loadDtcStores() {
  loadingStores.value = true
  try {
    const res = await fetchDtcStores()
    dtcStores.value = scopeStores(res.data || [], auth)
    if (dtcStores.value.length && !operationalDemoOnly.value) {
      const demoRes = loadDtcOperationalData(dtcStores.value)
      dtcDemo.value = demoRes.data
    } else if (!dtcStores.value.length) {
      dtcDemo.value = { products: [], campaigns: [], traffic: {}, meta: {} }
    }
  } catch {
    dtcStores.value = []
    dtcDemo.value = { products: [], campaigns: [], traffic: {}, meta: {} }
  } finally {
    loadingStores.value = false
  }
}

function goToAccountBinding() {
  router.push(auth.isBoss ? '/boss/accounts' : '/employee/dashboard')
}

watch(dtcStores, (stores) => {
  if (selectedStoreId.value === 'all') return
  if (!stores.some((store) => store.id === selectedStoreId.value)) {
    selectedStoreId.value = 'all'
  }
})

onMounted(async () => {
  await loadAssignees()
  await loadDtcStores()
})
onActivated(loadDtcStores)
</script>

<template>
  <PageScroll>
    <template #header>
      <PageHeader
        title="独立站运营"
        eyebrow="平台"
        :description="
          auth.isBoss
            ? '商品、流量与营销'
            : `${auth.employee.name} · 商品、流量与营销`
        "
      />
    </template>

    <PageSection v-if="dtcStores.length" tone="toolbar" title="店铺">
      <el-radio-group v-model="selectedStoreId" size="small">
        <el-radio-button value="all">全部店铺</el-radio-button>
        <el-radio-button
          v-for="store in dtcStores"
          :key="store.id"
          :value="store.id"
        >
          {{ store.storeName }}
        </el-radio-button>
      </el-radio-group>
    </PageSection>

    <PageSection v-if="!loadingStores && !dtcStores.length" flush>
      <el-empty
        description="暂无可见的独立站店铺"
        :image-size="96"
      >
        <el-text type="info" size="small">
          {{ auth.isBoss ? '请先在「账户绑定」中绑定 Shopify 或 WordPress 店铺' : '请联系企业管理员在运营绑定中分配负责店铺' }}
        </el-text>
        <el-button v-if="auth.isBoss" type="primary" style="margin-top: 16px" @click="goToAccountBinding">
          前往账户绑定
        </el-button>
      </el-empty>
    </PageSection>

    <template v-else-if="dtcStores.length">
      <el-alert
        v-if="operationalDemoOnly && operationalHint"
        :title="operationalHint"
        type="info"
        show-icon
        :closable="false"
        class="operational-hint"
      />

      <PageSection title="经营概览与明细">
        <DtcBossOverview
          v-if="auth.isBoss"
          :products="overviewProducts"
          :sites="overviewSites"
          :assignee-map="assigneeMap"
          :show-site-list="showSiteList"
          @navigate="activeTab = $event"
        />

        <el-tabs v-model="activeTab" class="dtc-tabs">
          <el-tab-pane name="products">
            <template #label>
              <span>商品管理</span>
              <el-badge
                v-if="alertCount.lowstock + alertCount.slow"
                :value="alertCount.lowstock + alertCount.slow"
                class="tab-badge"
              />
            </template>
            <DtcProductTable :products="products" :show-store-column="showStoreColumn" />
          </el-tab-pane>

          <el-tab-pane name="traffic">
            <template #label>
              <span>流量分析</span>
            </template>
            <el-card shadow="never">
              <template #header>流量来源</template>
              <DtcTrafficPanel :traffic-sources="trafficSources" />
            </el-card>
          </el-tab-pane>

          <el-tab-pane name="campaigns">
            <template #label>
              <span>营销活动</span>
            </template>
            <el-card shadow="never">
              <template #header>广告投放与促销</template>
              <DtcCampaignPanel :campaigns="campaigns" :store-name-map="storeNameMap" />
            </el-card>
          </el-tab-pane>
        </el-tabs>
      </PageSection>
    </template>
  </PageScroll>
</template>

<style scoped>
.page-toolbar {
  margin-bottom: 16px;
}

.dtc-tabs {
  margin-top: 20px;
}

.tab-badge {
  margin-left: 6px;
  vertical-align: middle;
}

.tab-badge :deep(.el-badge__content) {
  position: relative;
  transform: none;
  vertical-align: middle;
}
</style>
