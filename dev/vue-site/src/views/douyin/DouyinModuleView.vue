<script setup>
import { fetchDouyinStores } from '@/api/platformAccounts'
import {
  crawlDouyinIssues,
  fetchTodayDouyinOrders,
  loadDouyinIssues,
  resolveDouyinIssue,
} from '@/api/domesticPlatforms'
import { DOUYIN_ISSUE_TYPES } from '@/constants/douyinDemo'
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
  platformKey: 'douyin',
  fetchStores: fetchDouyinStores,
  fetchOrders: fetchTodayDouyinOrders,
  loadIssues: loadDouyinIssues,
  crawlIssues: crawlDouyinIssues,
  resolveIssue: resolveDouyinIssue,
  issueTypeMap: DOUYIN_ISSUE_TYPES,
})
</script>

<template>
  <PageScroll>
    <template #header>
      <PageHeader
        title="抖音运营"
        eyebrow="平台"
        :description="
          auth.isBoss
            ? '直播带货与订单跟进'
            : `${auth.employee.name} · 直播带货与订单跟进`
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
        description="暂无可见的抖音店铺"
        :image-size="96"
      >
        <el-text type="info" size="small">
          {{ auth.isBoss ? '请先在「账户绑定」中绑定抖音店铺' : '请联系企业管理员在运营绑定中分配负责店铺' }}
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
          issues-label="内容预警"
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
                show-channel-column
                orders-description="直播、短视频与商城订单"
                @refresh="syncTodayOrders(true)"
                @ship-push="openShipDialog($event, 'push')"
                @ship-urge="openShipDialog($event, 'urge')"
              />
            </div>
          </el-tab-pane>

          <el-tab-pane name="issues">
            <template #label>
              <span>内容预警</span>
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
                issues-title="内容预警"
                issues-description="直播挂车、短视频带货与商品问题"
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
        platform-key="douyin"
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
