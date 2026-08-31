# Amazon 模块 UI 对齐拼多多设计

**日期**: 2026-08-31
**范围**: 仅本地项目修改，不涉及部署

## 背景

拼多多（PDD）、淘宝、1688 已统一为新版平台模块 UI：
`PageHeader` → `HelperStatusBar` → 「店铺」工具栏卡片 → 「店铺经营驾驶舱」指标卡片区 → 标签页分区，面板头部带「同步于 xx:xx」绿色时间戳。Amazon 模块仍为旧版：页头条件显示、工具栏散落、面板头部样式不一致。

目标：Amazon 主页面骨架与全部子面板视觉对齐 PDD，**功能与数据流零改动**。

## 方案

已与用户确认采用「视觉对齐、功能全保留」方案（方案 A）。

## 第 1 节：主页面骨架（`src/views/amazon/AmazonModuleView.vue`）

页面结构调整为：

```
PageScroll
├─ PageHeader           「Amazon 运营中心」+ 描述（常显）
├─ HelperStatusBar       platform="amazon"（常显）
├─ PageSection(店铺/toolbar)
│    ├─ 店铺 radio 组（全部店铺 + 各店铺）
│    └─ toolbar-actions：一键刷新全部数据 · 同步日志
├─ PageSection(店铺经营驾驶舱)
│    └─ 老板 → AmazonBossOverview；员工 → AmazonDailyOverview
│       （actions 槽放 SyncSummaryLine）
├─ PageSection(运营管理)
│    └─ el-tabs：产品TOP20(老板) · 订单发货 · 买家消息 · 账号状况
│                差评预警 · 优惠券 · 卖家新闻 · 货件到货 · Case回复
└─ SyncHistoryDrawer（保留）
```

具体改动：

1. **页头常显**：移除 `page-toolbar` 自定义页头槽；`PageHeader` 始终渲染。
2. **HelperStatusBar 常显**：不再受 `showManualSyncControls` 控制；「一键刷新全部数据」按钮保留原有 `showManualSyncControls` + `helperOnline` 判断。
3. **空状态**：改用 `PageSection flush` + `el-empty`，保留「前往账号绑定」入口。
4. **删除「今日工作台」标签页**：`AmazonDailyOverview` 上移常驻于「店铺经营驾驶舱」；老板默认 tab 仍为 `products`，员工默认 tab 改为 `outbound`；`handleNavigate` 中 `dashboard` 目标改指 `outbound`。
5. **店铺工具栏**：同步按钮收入「店铺」卡片 `toolbar-actions`。
6. `operationalDemoOnly` 提示条保留（置于助手状态条与驾驶舱之间）。
7. 所有数据加载 / 同步 / 回复 / 发货 / 账号刷新逻辑原样保留。

## 第 2 节：面板头部与工具栏统一

### 2.1 面板头部（`src/components/amazon/AmazonPanelHeader.vue`）

重写为包装公共 `PanelHeader`（PDD 同款）：

- `synced-prefix="同步于"`，`show-action-icon=false`（绿色时间戳胶囊）；
- actions 区域保留 `SyncSummaryLine`（最近同步摘要，点击打开同步日志）+ 原有刷新按钮；
- 对外 props / events 接口不变（title、description、syncedAt、summaryText、actionLabel、secondaryActionLabel、loading、secondaryLoading、open-history），9 个面板头部一次全部生效，业务逻辑零改动。

### 2.2 面板内过滤工具栏（8 个含过滤控件的面板轻量调整）

- `el-segmented` 过滤控件统一改为 PDD 风格 `el-radio-button` 小组；
- 放入统一 `.toolbar` 容器（左控件 + 右 `toolbar-actions`，下边距 14px）；
- 仅调整模板结构，不碰数据 / 事件 / 弹窗逻辑。

涉及面板：`AmazonProductsPanel`、`AmazonOutboundPanel`、`AmazonBuyerMessagesPanel`、`AmazonAccountHealthPanel`、`AmazonReviewsPanel`、`AmazonCouponsPanel`、`AmazonShipmentsPanel`、`AmazonCasesPanel`。

`AmazonSellerNewsPanel` 无过滤控件（mini-stats + 新闻卡片），仅通过 `AmazonPanelHeader` 自动获得统一头部，正文不动。

### 2.3 明确不动的部分

- 公共组件（`PanelHeader`、`PageHeader`、`PageSection`、`HelperStatusBar` 等）不改，避免影响 PDD / 淘宝 / 1688；
- 接口层（`@/api/amazon`、`amazonApi`）与状态逻辑不改；
- 工作区中已有的 PDD 未提交改动不触碰，提交仅含 Amazon 相关文件与本文档。

## 第 3 节：验证与交付

1. `dev/vue-site` 下执行 `npm run build`，Vite 构建零报错。
2. 本地 `npm run dev:vue` 启动后浏览器目检 Amazon 模块页：骨架顺序、店铺切换、驾驶舱展示、面板头部时间戳与过滤控件观感与 PDD 一致。
3. 不新增自动化测试（纯 UI 层改动）。

交付物：

| 文件 | 改动 |
|------|------|
| `src/views/amazon/AmazonModuleView.vue` | 页面骨架重构 |
| `src/components/amazon/AmazonPanelHeader.vue` | 头部统一 PDD 风格 |
| 8 个 `src/components/amazon/*.vue` 面板 | 过滤工具栏微调（卖家新闻仅头部统一） |
| `docs/superpowers/specs/2026-08-31-amazon-ui-pdd-alignment-design.md` | 本文档 |

## 不做的事

- 不改 Amazon 数据接口、同步任务、仓库推送逻辑；
- 不新建统一驾驶舱组件（方案 B，留作后续迭代）；
- 不调整拼多多 / 淘宝 / 1688 等其它平台模块。
