<script setup>
import { fetchPddStores } from '@/api/platformAccounts'
import {
  crawlPddIssues,
  fetchTodayPddOrders,
  loadPddIssues,
  resolvePddIssue,
} from '@/api/domesticPlatforms'
import { PDD_ISSUE_TYPES } from '@/constants/pddDemo'
import { useDomesticModule } from '@/composables/useDomesticModule'
import PageHeader from '@/components/common/PageHeader.vue'
import PageScroll from '@/components/common/PageScroll.vue'
import PageSection from '@/components/common/PageSection.vue'
import DomesticBossOverview from '@/components/domestic/DomesticBossOverview.vue'
import DomesticOrdersPanel from '@/components/domestic/DomesticOrdersPanel.vue'
import DomesticIssuesPanel from '@/components/domestic/DomesticIssuesPanel.vue'
import PlatformShipPushDialog from '@/components/domestic/PlatformShipPushDialog.vue'

const {
  auth,
  assigneeMap,
  activeTab,
  selectedStoreId,
  stores,
  ordersSyncedAt,
  issuesSyncedAt,
  loadingStores,
  loadingOrders,
  loadingIssues,
  issuesPanel,
  issuesFilter,
  storeNameMap,
  showStoreColumn,
  showStoreList,
  overviewStores,
  filteredOrders,
  filteredIssues,
  pendingOrderCount,
  pendingIssueCount,
  syncTodayOrders,
  syncIssues,
  handleResolveIssue,
  goToAccountBinding,
  handleOverviewNavigate,
  openShipDialog,
  submitShipPush,
  shipDialogVisible,
  shipDialogOrder,
  shipDialogType,
  shipSubmitting,
  platformLabel,
  operationalDemoOnly,
  operationalHint,
} = useDomesticModule({
  platformKey: 'pdd',
  fetchStores: fetchPddStores,
  fetchOrders: fetchTodayPddOrders,
  loadIssues: loadPddIssues,
  crawlIssues: crawlPddIssues,
  resolveIssue: resolvePddIssue,
  issueTypeMap: PDD_ISSUE_TYPES,
})
</script>

<template>
  <PageScroll>
    <template #header>
      <PageHeader
        title="拼多多运营"
        eyebrow="平台"
        :description="
          auth.isBoss
            ? '订单处理与活动跟进'
            : `${auth.employee.name} · 订单处理与活动跟进`
        "
      />
    </template>

    <PageSection v-if="stores.length" tone="toolbar" title="店铺">
      <el-radio-group v-model="selectedStoreId" size="small">
        <el-radio-button value="all">全部店铺</el-radio-button>
        <el-radio-button v-for="store in stores" :key="store.id" :value="store.id">
          {{ store.storeName }}
        </el-radio-button>
      </el-radio-group>
    </PageSection>

    <PageSection v-if="!loadingStores && !stores.length" flush>
      <el-empty
        description="暂无可见的拼多多店铺"
        :image-size="96"
      >
        <el-text type="info" size="small">
          {{ auth.isBoss ? '请先在「账户绑定」中绑定拼多多店铺' : '请联系企业管理员在运营绑定中分配负责店铺' }}
        </el-text>
        <el-button v-if="auth.isBoss" type="primary" style="margin-top: 16px" @click="goToAccountBinding">
          前往账户绑定
        </el-button>
      </el-empty>
    </PageSection>

    <template v-else-if="stores.length">
      <el-alert
        v-if="operationalDemoOnly && operationalHint"
        :title="operationalHint"
        type="info"
        show-icon
        :closable="false"
        class="operational-hint"
      />

      <PageSection title="经营概览与明细">
        <DomesticBossOverview
          v-if="auth.isBoss"
          :orders="filteredOrders"
          :issues="filteredIssues"
          :stores="overviewStores"
          :assignee-map="assigneeMap"
          :show-store-list="showStoreList"
          issues-label="活动预警"
          @navigate="handleOverviewNavigate"
        />

        <el-tabs v-model="activeTab" class="module-tabs">
          <el-tab-pane name="orders">
            <template #label>
              <span>今日订单</span>
              <el-badge v-if="pendingOrderCount" :value="pendingOrderCount" class="tab-badge" />
            </template>
            <div class="tab-panel">
              <DomesticOrdersPanel
                :orders="filteredOrders"
                :synced-at="ordersSyncedAt"
                :loading="loadingOrders"
                :show-store-column="showStoreColumn"
                :store-name-map="storeNameMap"
                orders-description="百亿补贴与商城订单"
                @refresh="syncTodayOrders(true)"
                @ship-push="openShipDialog($event, 'push')"
                @ship-urge="openShipDialog($event, 'urge')"
              />
            </div>
          </el-tab-pane>

          <el-tab-pane name="issues">
            <template #label>
              <span>活动预警</span>
              <el-badge v-if="pendingIssueCount" :value="pendingIssueCount" class="tab-badge" />
            </template>
            <div class="tab-panel">
              <DomesticIssuesPanel
                ref="issuesPanel"
                :issues="filteredIssues"
                :synced-at="issuesSyncedAt"
                :loading="loadingIssues"
                :show-store-column="showStoreColumn"
                :store-name-map="storeNameMap"
                :initial-filter="issuesFilter"
                issues-title="活动预警"
                issues-description="拼团、价格与库存相关待跟进事项"
                @refresh="syncIssues(true)"
                @resolve="handleResolveIssue"
              />
            </div>
          </el-tab-pane>
        </el-tabs>
      </PageSection>

      <PlatformShipPushDialog
        v-model="shipDialogVisible"
        :order="shipDialogOrder"
        platform-key="pdd"
        :platform-label="platformLabel"
        :store-name="shipDialogOrder ? storeNameMap[shipDialogOrder.storeId] : ''"
        :request-type="shipDialogType"
        :submitting="shipSubmitting"
        @submit="submitShipPush"
      />
    </template>
  </PageScroll>
</template>

<style scoped>
.page-toolbar {
  margin-bottom: 16px;
}

.module-tabs {
  margin-top: 20px;
}

.tab-panel {
  padding: 16px 0 4px;
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
