# Amazon 模块 UI 对齐拼多多实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Amazon 模块主页面与全部子面板视觉对齐拼多多（PDD）模块 UI，功能与数据流零改动。

**Architecture:** 页面骨架重构（`AmazonModuleView.vue`）为 PDD 的标准结构：常显 `PageHeader` + `HelperStatusBar` + 「店铺」工具栏卡片 + 「店铺经营驾驶舱」+ 标签页分区；`AmazonPanelHeader.vue` 改为包装公共 `PanelHeader`（PDD 同款「同步于」时间戳样式）；8 个面板的 `el-segmented` 过滤控件改为 PDD 风格 `el-radio-button` 工具栏。所有改动均为纯模板/样式层。

**Tech Stack:** Vue 3 + Element Plus + Vite（`dev/vue-site`）。项目无前端组件测试框架，唯一前端编译门禁为 `npm run build`。

## Global Constraints

- 只修改 Amazon 相关文件：`dev/vue-site/src/views/amazon/AmazonModuleView.vue`、`dev/vue-site/src/components/amazon/*.vue`（8 个面板 + `AmazonPanelHeader.vue`）以及本文档。
- 禁止修改公共组件（`src/components/common/*`）、PDD / 淘宝 / 1688 等其它平台文件、接口层（`@/api/*`、`src/utils/amazon*`、`src/constants/amazon*`）。
- 保持所有现有 props / events / 数据流不变，仅做模板与样式调整。
- 工作区已有 PDD 相关未提交改动（`backend/python/agent/pdd_tasks.py` 等），不得触碰或纳入提交；每次提交只含 Amazon 文件。
- 每个 Task 完成后必须执行 `cd dev/vue-site && npm run build`，预期输出包含 `✓ built in` 且退出码 0，方可继续。
- `docs/` 被 `.gitignore` 忽略：新增/提交 docs 文件必须使用 `git add -f`（与仓库现有 19 份跟踪文档的约定一致）。
- 文案规范：沿用 Amazon 现有中文文案；仅 `PageHeader` 描述按设计统一为一句概括。

---

### Task 1: 统一 `AmazonPanelHeader` 为 PDD 风格

**Files:**
- Modify: `dev/vue-site/src/components/amazon/AmazonPanelHeader.vue`（整文件重写）

**Interfaces:**
- Consumes: 公共 `PanelHeader`（`@/components/common/PanelHeader.vue`，props：`title/description/syncedAt/syncedPrefix/actionLabel/secondaryActionLabel/loading/secondaryLoading/showActionIcon`，events：`action/secondaryAction`）、`SyncSummaryLine`（`@/components/common/SyncSummaryLine.vue`，props：`summaryText`，event：`open-history`）
- Produces: 对外接口与旧版完全一致（props：`title/description/syncedAt/summaryText/actionLabel/secondaryActionLabel/loading/secondaryLoading`；events：`action/secondaryAction/open-history`；`#actions` 插槽透传），供 9 个 Amazon 面板直接使用，面板自身零改动。

> 说明：本项目无前端测试框架，本任务及后续任务以 `npm run build` 作为编译门禁，并以浏览器目检作为视觉验证（见 Task 4）。

- [ ] **Step 1: 重写 `AmazonPanelHeader.vue`**

将整个文件内容替换为：

```vue
<script setup>
import PanelHeader from '@/components/common/PanelHeader.vue'
import SyncSummaryLine from '@/components/common/SyncSummaryLine.vue'

defineProps({
  title: { type: String, required: true },
  description: { type: String, default: '' },
  syncedAt: { type: String, default: '' },
  summaryText: { type: String, default: '' },
  actionLabel: { type: String, default: '' },
  secondaryActionLabel: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  secondaryLoading: { type: Boolean, default: false },
})

defineEmits(['action', 'secondaryAction', 'open-history'])
</script>

<template>
  <PanelHeader
    :title="title"
    :description="description"
    :synced-at="syncedAt"
    synced-prefix="同步于"
    :action-label="actionLabel"
    :secondary-action-label="secondaryActionLabel"
    :loading="loading"
    :secondary-loading="secondaryLoading"
    :show-action-icon="false"
    @action="$emit('action')"
    @secondary-action="$emit('secondaryAction')"
  >
    <template #actions>
      <SyncSummaryLine
        v-if="summaryText"
        :summary-text="summaryText"
        @open-history="$emit('open-history')"
      />
      <el-button
        v-if="secondaryActionLabel"
        size="small"
        :loading="secondaryLoading"
        @click="$emit('secondaryAction')"
      >
        {{ secondaryActionLabel }}
      </el-button>
      <el-button
        v-if="actionLabel"
        size="small"
        type="primary"
        :loading="loading"
        @click="$emit('action')"
      >
        {{ actionLabel }}
      </el-button>
      <slot name="actions" />
    </template>
  </PanelHeader>
</template>
```

要点：`PanelHeader` 自带「同步于 xx:xx」绿色时间戳胶囊（`syncedPrefix`），`show-action-icon=false` 去掉刷新图标；`#actions` 插槽中放 `SyncSummaryLine` + 两个按钮 + 透传旧插槽（`AmazonAccountHealthPanel` 自定义的「刷新数据」按钮经此继续生效）。

- [ ] **Step 2: 编译验证**

运行：

```bash
cd dev/vue-site && npm run build
```

预期：构建成功，输出包含 `✓ built in`，退出码 0。

- [ ] **Step 3: 提交**

```bash
git add dev/vue-site/src/components/amazon/AmazonPanelHeader.vue
git commit -m "style(amazon): 面板头部统一为拼多多同步于样式"
```

---

### Task 2: 重构 `AmazonModuleView` 页面骨架

**Files:**
- Modify: `dev/vue-site/src/views/amazon/AmazonModuleView.vue`

**Interfaces:**
- Consumes: 既有组件与 API（`PageHeader`、`PageScroll`、`PageSection`、`HelperStatusBar`、`SyncSummaryLine`、`SyncHistoryDrawer`、`AmazonBossOverview`、`AmazonDailyOverview`、9 个 Amazon 面板、`AmazonIntegrationGuide`）——仅调整模板组织，接口不变。
- Produces: PDD 同构页面骨架；删除「今日工作台」tab；老板默认 tab `products`、员工默认 tab `outbound`；`handleNavigate('dashboard')` 改跳 `outbound`。

- [ ] **Step 1: 修改 script 三处**

1a. 默认 tab（员工从 `dashboard` 改为 `outbound`）：

```js
// 原：const activeTab = ref(auth.isBoss ? 'products' : 'dashboard')
const activeTab = ref(auth.isBoss ? 'products' : 'outbound')
```

1b. `tabBadges` 中删除 `dashboard` 键（保留其它键）：

```js
  return {
    products: bossProductSummary.value.highAcosCount,
    outbound: outboundSummary.value.actionRequired,
    messages: map.messages || 0,
    account: map.account || 0,
    reviews: map.reviews || 0,
    coupons: map.coupons || 0,
    news: map.news || 0,
    shipments: map.shipments || 0,
    cases: map.cases || 0,
  }
```

1c. `handleNavigate` 增加 dashboard 兜底分支（插到 `if (target.startsWith('outbound'))` 分支之后、`activeTab.value = target` 之前）：

```js
  if (target === 'dashboard') {
    activeTab.value = 'outbound'
    return
  }
```

- [ ] **Step 2: 整体替换 `<template>` 块**

删除旧的 `<template>#header` 自定义工具栏与 `el-empty` 直出结构，将整个 `<template>` 替换为：

```vue
<template>
  <PageScroll>
    <PageHeader
      title="Amazon 运营中心"
      description="销售、广告、账户健康与买家沟通的一站式运营数据"
    />

    <HelperStatusBar
      platform="amazon"
      :store-id="selectedStoreId"
      @update:online="onHelperOnline"
    />

    <AmazonIntegrationGuide v-if="showIntegrationGuide" />

    <el-alert
      v-if="operationalDemoOnly && operationalHint"
      :title="operationalHint"
      type="info"
      show-icon
      :closable="false"
      class="operational-hint"
    />

    <PageSection v-if="amazonStores.length" title="店铺" tone="toolbar">
      <div class="toolbar-row">
        <el-radio-group v-model="selectedStoreId" size="small">
          <el-radio-button value="all">全部店铺</el-radio-button>
          <el-radio-button v-for="store in amazonStores" :key="store.id" :value="store.id">
            {{ store.storeName }}
          </el-radio-button>
        </el-radio-group>
        <div class="toolbar-actions">
          <el-button
            v-if="showManualSyncControls"
            type="primary"
            :loading="loadingAll"
            :disabled="!helperOnline"
            @click="syncAllAmazon"
          >
            一键刷新全部数据
          </el-button>
          <el-button size="small" @click="syncHistoryOpen = true">同步日志</el-button>
        </div>
      </div>
    </PageSection>

    <PageSection v-if="!loadingStores && !amazonStores.length" flush>
      <el-empty description="暂无可看的 Amazon 店铺" :image-size="96">
        <el-text type="info" size="small">
          {{
            auth.isBoss
              ? '请先在「账号绑定」中绑定 Amazon 店铺；本机可先下载并绑定 Sync Helper'
              : '请联系企业管理员分配负责店铺；本机可先下载并绑定 Sync Helper'
          }}
        </el-text>
        <el-button v-if="auth.isBoss" type="primary" style="margin-top: 16px" @click="goToAccountBinding">
          前往账号绑定
        </el-button>
      </el-empty>
    </PageSection>

    <PageSection v-else-if="amazonStores.length" title="店铺经营驾驶舱">
      <template #actions>
        <SyncSummaryLine
          v-if="syncSummaryText"
          :summary-text="syncSummaryText"
          @open-history="syncHistoryOpen = true"
        />
      </template>

      <AmazonBossOverview
        v-if="auth.isBoss"
        :products="filteredProducts"
        :outbound-orders="filteredOutbound"
        :account-metrics="filtered.accountMetrics"
        :stores="overviewStores"
        :assignee-map="assigneeMap"
        :show-store-list="showStoreList"
        @navigate="handleNavigate"
      />

      <AmazonDailyOverview
        v-else
        :workflow="filtered"
        :stores="overviewStores"
        :assignee-map="assigneeMap"
        :show-store-list="showStoreList"
        @navigate="handleNavigate"
      />
    </PageSection>

    <PageSection v-if="!loadingStores && amazonStores.length" title="运营管理">
      <el-tabs v-model="activeTab" class="module-tabs">
        <el-tab-pane v-if="auth.isBoss" name="products">
          <template #label>
            <span>产品 TOP20</span>
            <el-badge v-if="tabBadges.products" :value="tabBadges.products" class="tab-badge" />
          </template>
          <div class="tab-panel">
            <AmazonProductsPanel
              ref="productsPanel"
              :products="filteredProducts"
              :synced-at="bossSyncedAt"
              :summary-text="syncSummaryText"
              :sync-issue="productSyncIssue"
              :data-quality="productDataQuality"
              :loading="loadingBoss"
              :reports-loading="loadingReports"
              :show-store-column="showStoreColumn"
              :store-name-map="storeNameMap"
              :initial-filter="productsFilter"
              @refresh="syncBossInsights(true)"
              @refresh-reports="syncBossReports(true)"
              @open-history="syncHistoryOpen = true"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane name="outbound">
          <template #label>
            <span>订单发货</span>
            <el-badge v-if="tabBadges.outbound" :value="tabBadges.outbound" class="tab-badge" />
          </template>
          <div class="tab-panel">
            <AmazonOutboundPanel
              ref="outboundPanel"
              :orders="filteredOutbound"
              :synced-at="bossSyncedAt"
              :summary-text="syncSummaryText"
              :loading="loadingBoss"
              :show-store-column="showStoreColumn"
              :store-name-map="storeNameMap"
              :initial-filter="outboundFilter"
              @refresh="syncBossInsights(true)"
              @ship="onShipOutbound"
              @open-history="syncHistoryOpen = true"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane name="messages">
          <template #label>
            <span>买家消息</span>
            <el-badge v-if="tabBadges.messages" :value="tabBadges.messages" class="tab-badge" />
          </template>
          <div class="tab-panel">
            <AmazonBuyerMessagesPanel
              ref="messagesPanel"
              :messages="filtered.buyerMessages"
              :synced-at="syncedAt"
              :summary-text="syncSummaryText"
              :loading="loading"
              :show-store-column="showStoreColumn"
              :store-name-map="storeNameMap"
              @reply="onReplyMessage"
              @open-history="syncHistoryOpen = true"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane name="account">
          <template #label>
            <span>账号状况</span>
            <el-badge v-if="tabBadges.account" :value="tabBadges.account" class="tab-badge" />
          </template>
          <div class="tab-panel">
            <AmazonAccountHealthPanel
              :metrics="filtered.accountMetrics"
              :synced-at="syncedAt"
              :summary-text="syncSummaryText"
              :loading="loading"
              :show-store-column="showStoreColumn"
              :store-name-map="storeNameMap"
              @refresh="syncAccountHealth(true)"
              @open-history="syncHistoryOpen = true"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane name="reviews">
          <template #label>
            <span>差评预警</span>
            <el-badge v-if="tabBadges.reviews" :value="tabBadges.reviews" class="tab-badge" />
          </template>
          <div class="tab-panel">
            <AmazonReviewsPanel
              ref="reviewsPanel"
              :reviews="filtered.reviews"
              :synced-at="syncedAt"
              :summary-text="syncSummaryText"
              :loading="loading"
              :show-store-column="showStoreColumn"
              :store-name-map="storeNameMap"
              @handle="onHandleReview"
              @open-history="syncHistoryOpen = true"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane name="coupons">
          <template #label>
            <span>优惠券</span>
            <el-badge v-if="tabBadges.coupons" :value="tabBadges.coupons" class="tab-badge" />
          </template>
          <div class="tab-panel">
            <AmazonCouponsPanel
              :coupons="filtered.coupons"
              :synced-at="syncedAt"
              :summary-text="syncSummaryText"
              :loading="loading"
              :show-store-column="showStoreColumn"
              :store-name-map="storeNameMap"
              @refresh="syncWorkflow(true)"
              @open-history="syncHistoryOpen = true"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane name="news">
          <template #label>
            <span>卖家新闻</span>
            <el-badge v-if="tabBadges.news" :value="tabBadges.news" class="tab-badge" />
          </template>
          <div class="tab-panel">
            <AmazonSellerNewsPanel
              :news="filtered.sellerNews"
              :synced-at="syncedAt"
              :summary-text="syncSummaryText"
              :loading="loading"
              :show-store-column="showStoreColumn"
              :store-name-map="storeNameMap"
              @open-history="syncHistoryOpen = true"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane name="shipments">
          <template #label>
            <span>货件到货</span>
            <el-badge v-if="tabBadges.shipments" :value="tabBadges.shipments" class="tab-badge" />
          </template>
          <div class="tab-panel">
            <AmazonShipmentsPanel
              :shipments="filtered.shipments"
              :synced-at="syncedAt"
              :summary-text="syncSummaryText"
              :loading="loading"
              :show-store-column="showStoreColumn"
              :store-name-map="storeNameMap"
              @refresh="syncWorkflow(true)"
              @open-history="syncHistoryOpen = true"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane name="cases">
          <template #label>
            <span>Case 回复</span>
            <el-badge v-if="tabBadges.cases" :value="tabBadges.cases" class="tab-badge" />
          </template>
          <div class="tab-panel">
            <AmazonCasesPanel
              ref="casesPanel"
              :cases="filtered.cases"
              :synced-at="syncedAt"
              :summary-text="syncSummaryText"
              :loading="loading"
              :show-store-column="showStoreColumn"
              :store-name-map="storeNameMap"
              @acknowledge="onAcknowledgeCase"
              @open-history="syncHistoryOpen = true"
            />
          </div>
        </el-tab-pane>
      </el-tabs>
    </PageSection>

    <SyncHistoryDrawer
      v-model="syncHistoryOpen"
      platform="amazon"
      :fetcher="() => fetchAmazonSyncJobs({ limit: 20 })"
    />
  </PageScroll>
</template>
```

- [ ] **Step 3: 替换 `<style scoped>` 块**

将整个 `<style scoped>` 替换为：

```css
<style scoped>
.toolbar-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.operational-hint {
  margin-bottom: 12px;
}

.module-tabs :deep(.el-tabs__header) {
  margin-bottom: 4px;
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
```

- [ ] **Step 4: 编译验证**

运行：

```bash
cd dev/vue-site && npm run build
```

预期：构建成功，输出包含 `✓ built in`，退出码 0。

- [ ] **Step 5: 提交**

```bash
git add dev/vue-site/src/views/amazon/AmazonModuleView.vue
git commit -m "refactor(amazon): 主页面骨架对齐拼多多模块布局"
```

---

### Task 3: 8 个面板过滤工具栏统一为 PDD 风格

**Files:**
- Modify: `dev/vue-site/src/components/amazon/AmazonProductsPanel.vue`
- Modify: `dev/vue-site/src/components/amazon/AmazonOutboundPanel.vue`
- Modify: `dev/vue-site/src/components/amazon/AmazonBuyerMessagesPanel.vue`
- Modify: `dev/vue-site/src/components/amazon/AmazonAccountHealthPanel.vue`
- Modify: `dev/vue-site/src/components/amazon/AmazonReviewsPanel.vue`
- Modify: `dev/vue-site/src/components/amazon/AmazonCouponsPanel.vue`
- Modify: `dev/vue-site/src/components/amazon/AmazonShipmentsPanel.vue`
- Modify: `dev/vue-site/src/components/amazon/AmazonCasesPanel.vue`

**Interfaces:**
- Consumes: 各面板现有 `filter` ref 与 `summary` computed（`filter` 取值保持不变，避免影响 `filtered` computed 逻辑）。
- Produces: 统一 `.toolbar` 容器 + `el-radio-button` 小组；filter 值与过滤逻辑完全不变。

> 每个文件两处改动：① 把 `<el-segmented ... />` 替换为下方对应代码；② 在 `<style scoped>` 中 `.amz-panel` 规则后追加 `.toolbar` 样式。

- [ ] **Step 1: `AmazonProductsPanel.vue`**

将：

```vue
    <el-segmented v-model="filter" :options="filterOptions" size="small" />
```

替换为：

```vue
    <div class="toolbar">
      <el-radio-group v-model="filter" size="small">
        <el-radio-button v-for="opt in filterOptions" :key="opt.value" :value="opt.value">
          {{ opt.label }}
        </el-radio-button>
      </el-radio-group>
    </div>
```

样式追加：

```css
.toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-bottom: 14px; }
```

- [ ] **Step 2: `AmazonOutboundPanel.vue`**

将：

```vue
    <el-segmented v-model="filter" :options="filterOptions" size="small" />
```

替换为：

```vue
    <div class="toolbar">
      <el-radio-group v-model="filter" size="small">
        <el-radio-button value="pending">{{ summary.pending ? `待发货 (${summary.pending})` : '待发货' }}</el-radio-button>
        <el-radio-button value="packed">{{ summary.packed ? `待揽收 (${summary.packed})` : '待揽收' }}</el-radio-button>
        <el-radio-button value="shipped">已发货</el-radio-button>
        <el-radio-button value="all">全部</el-radio-button>
      </el-radio-group>
    </div>
```

样式追加同 Step 1 的 `.toolbar` 一行。

- [ ] **Step 3: `AmazonBuyerMessagesPanel.vue`**

将：

```vue
    <el-segmented v-model="filter" :options="filterOptions" />
```

替换为：

```vue
    <div class="toolbar">
      <el-radio-group v-model="filter" size="small">
        <el-radio-button value="pending">{{ summary.pending ? `待回复 (${summary.pending})` : '待回复' }}</el-radio-button>
        <el-radio-button value="replied">已回复</el-radio-button>
        <el-radio-button value="all">全部</el-radio-button>
      </el-radio-group>
    </div>
```

样式追加同 Step 1 的 `.toolbar` 一行。

- [ ] **Step 4: `AmazonAccountHealthPanel.vue`**

将：

```vue
    <el-segmented v-model="filter" :options="[
      { label: `待关注(${summary.critical + summary.warning})`, value: 'alert' },
      ...filterOptions,
    ]" />
```

替换为：

```vue
    <div class="toolbar">
      <el-radio-group v-model="filter" size="small">
        <el-radio-button value="alert">待关注 ({{ summary.critical + summary.warning }})</el-radio-button>
        <el-radio-button value="critical">{{ summary.critical ? `爆红 (${summary.critical})` : '爆红' }}</el-radio-button>
        <el-radio-button value="warning">{{ summary.warning ? `预警 (${summary.warning})` : '预警' }}</el-radio-button>
        <el-radio-button value="all">全部指标</el-radio-button>
      </el-radio-group>
    </div>
```

样式追加同 Step 1 的 `.toolbar` 一行。

- [ ] **Step 5: `AmazonReviewsPanel.vue`**

将：

```vue
    <el-segmented v-model="filter" :options="[
      { label: summary.pending ? `待处理(${summary.pending})` : '待处理', value: 'pending' },
      { label: '已处理', value: 'handled' },
      { label: '全部', value: 'all' },
    ]" />
```

替换为：

```vue
    <div class="toolbar">
      <el-radio-group v-model="filter" size="small">
        <el-radio-button value="pending">{{ summary.pending ? `待处理 (${summary.pending})` : '待处理' }}</el-radio-button>
        <el-radio-button value="handled">已处理</el-radio-button>
        <el-radio-button value="all">全部</el-radio-button>
      </el-radio-group>
    </div>
```

样式追加同 Step 1 的 `.toolbar` 一行。

- [ ] **Step 6: `AmazonCouponsPanel.vue`**

将：

```vue
    <el-segmented v-model="filter" :options="[
      { label: summary.alerts ? `待关注(${summary.alerts})` : '待关注', value: 'alert' },
      { label: '生效中', value: 'active' },
      { label: '全部', value: 'all' },
    ]" />
```

替换为：

```vue
    <div class="toolbar">
      <el-radio-group v-model="filter" size="small">
        <el-radio-button value="alert">{{ summary.alerts ? `待关注 (${summary.alerts})` : '待关注' }}</el-radio-button>
        <el-radio-button value="active">生效中</el-radio-button>
        <el-radio-button value="all">全部</el-radio-button>
      </el-radio-group>
    </div>
```

样式追加同 Step 1 的 `.toolbar` 一行。

- [ ] **Step 7: `AmazonShipmentsPanel.vue`**

将：

```vue
    <el-segmented v-model="filter" :options="[
      { label: summary.alerts ? `预警 (${summary.alerts})` : '预警', value: 'alert' },
      { label: '运输中', value: 'in_transit' },
      { label: '全部', value: 'all' },
    ]" />
```

替换为：

```vue
    <div class="toolbar">
      <el-radio-group v-model="filter" size="small">
        <el-radio-button value="alert">{{ summary.alerts ? `预警 (${summary.alerts})` : '预警' }}</el-radio-button>
        <el-radio-button value="in_transit">运输中</el-radio-button>
        <el-radio-button value="all">全部</el-radio-button>
      </el-radio-group>
    </div>
```

样式追加同 Step 1 的 `.toolbar` 一行。

- [ ] **Step 8: `AmazonCasesPanel.vue`**

将：

```vue
    <el-segmented v-model="filter" :options="[
      { label: summary.newReplies ? `新回复(${summary.newReplies})` : '新回复', value: 'new' },
      { label: '待回复', value: 'pending' },
      { label: '全部', value: 'all' },
    ]" />
```

替换为：

```vue
    <div class="toolbar">
      <el-radio-group v-model="filter" size="small">
        <el-radio-button value="new">{{ summary.newReplies ? `新回复 (${summary.newReplies})` : '新回复' }}</el-radio-button>
        <el-radio-button value="pending">待回复</el-radio-button>
        <el-radio-button value="all">全部</el-radio-button>
      </el-radio-group>
    </div>
```

样式追加同 Step 1 的 `.toolbar` 一行。

- [ ] **Step 9: 编译验证**

运行：

```bash
cd dev/vue-site && npm run build
```

预期：构建成功，输出包含 `✓ built in`，退出码 0。

- [ ] **Step 10: 提交**

```bash
git add dev/vue-site/src/components/amazon/AmazonProductsPanel.vue dev/vue-site/src/components/amazon/AmazonOutboundPanel.vue dev/vue-site/src/components/amazon/AmazonBuyerMessagesPanel.vue dev/vue-site/src/components/amazon/AmazonAccountHealthPanel.vue dev/vue-site/src/components/amazon/AmazonReviewsPanel.vue dev/vue-site/src/components/amazon/AmazonCouponsPanel.vue dev/vue-site/src/components/amazon/AmazonShipmentsPanel.vue dev/vue-site/src/components/amazon/AmazonCasesPanel.vue
git commit -m "style(amazon): 8 个面板过滤工具栏统一为拼多多风格"
```

---

### Task 4: 端到端目检与收尾

**Files:**
- 无（如发现视觉问题，按 Task 1-3 对应文件修复）

- [ ] **Step 1: 启动本地前端并目检**

运行：

```bash
cd dev/vue-site && npm run dev
```

浏览器打开 Amazon 模块页（本地路由：`/amazon-module` 或导航进入），逐项检查：

1. 页面顶部顺序：`Amazon 运营中心` 标题 → 助手状态条 → 「店铺」工具栏卡片（店铺切换 + 一键刷新 + 同步日志）；
2. 无店铺时显示空状态卡片（含「前往账号绑定」入口，老板角色）；
3. 「店铺经营驾驶舱」卡片：老板看到指标条/图表，员工看到今日运营工作台清单；右上角有最近同步摘要；
4. 标签页：无「今日工作台」tab；老板默认「产品 TOP20」、员工默认「订单发货」；其余 8 个 tab 内容与过滤控件正常；
5. 面板头部显示绿色「同步于 xx:xx」胶囊；各面板过滤控件为按钮组且与旧 `el-segmented` 行为一致；
6. 与 PDD 模块页观感一致。

发现问题则修复对应文件并重新 `npm run build`，通过后单独提交修复：

```bash
git add <修改的文件>
git commit -m "fix(amazon): 目检问题修复"
```

- [ ] **Step 2: 确认提交范围**

运行：

```bash
git status --short
git log --oneline -5
```

预期：本次提交仅含 Amazon 相关文件与两份 docs（spec + plan）；工作区原有的 PDD 相关未提交改动仍以 `M` 状态保留、未被提交。
