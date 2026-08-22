# 1688 模块列表排序 设计

- 日期：2026-08-22
- 状态：已确认（用户选择方案 A：商品分类、爆款/今日爆款/近期销量、爆款追踪、经营明细四个列表；纯前端）
- 范围：前端 `dev/vue-site` 内 1688 模块 4 个列表组件

## 1. 目标与交互

为 1688 模块的四个列表增加“点击表头标签排序”：

- 点击列头：升序 → 降序 → 取消排序（Element Plus `el-table` 原生行为）；
- 排序作用于当前已加载数据：
  - 全量列表（商品分类、爆款/今日爆款/近期销量）跨页生效；
  - 后端分页列表（订单、爆款追踪）仅当前页生效（本次不改成服务端排序）。

## 2. 涉及文件与排序列

### 2.1 `dev/vue-site/src/components/alibaba1688/Alibaba1688ProductPanel.vue`（商品分类）

表格数据源 `paged`（本地分页），可排序列：

| 列 | 字段 | 方式 |
| --- | --- | --- |
| 价格 | `price` | `sortable` + `:sort-method`（模板渲染列） |
| 库存 | `stock` | `sortable` |
| 今日销售额 | `gmv1d` | `sortable` |
| 30天销售额 | `gmv30d` | `sortable` |
| 同步时间 | `syncedAt` | `sortable` |

### 2.2 `dev/vue-site/src/components/alibaba1688/Alibaba1688ProductAnalyticsPanel.vue`（爆款/今日爆款/近期销量）

表格数据源 `pagedRows`（本地筛选+分页），可排序列：

| 列 | 字段 | 方式 |
| --- | --- | --- |
| 单价 | `price` | `sortable` + `:sort-method`（模板渲染列） |
| 销量 | `salesQty` | `sortable` + `:sort-method` |
| 销售额 | `salesAmount` | `sortable` + `:sort-method` |
| 上架时间 | `productUpdatedAt` | `sortable`（仅 `type === 'recent_sales'` 时渲染该列） |
| 库存 | `stock` | `sortable` |

### 2.3 `dev/vue-site/src/components/alibaba1688/Alibaba1688PeerBestsellersPanel.vue`（爆款追踪）

表格数据源 `rows`（后端分页，仅当前页排序），可排序列：

| 列 | 字段 | 方式 |
| --- | --- | --- |
| 单价 | `price` | `sortable` + `:sort-method`（模板渲染列） |
| 销量（平台已售） | `sales` | `sortable` + `:sort-method`（模板渲染列，`saleText` 仅为展示） |
| 商品质量分 | `qualityScore` | `sortable` + `:sort-method` |
| 抓取时间 | `syncedAt` | `sortable` |

### 2.4 `dev/vue-site/src/components/alibaba1688/Alibaba1688OrderDetailsPanel.vue`（经营明细·订单）

表格数据源 `rows`（后端分页，仅当前页排序），可排序列：

| 列 | 字段 | 方式 |
| --- | --- | --- |
| 数量 | `quantity` | `sortable` |
| 单价 | `unitPrice` | `sortable` + `:sort-method`（模板渲染列） |
| 行金额 | `itemAmount` | `sortable` + `:sort-method` |
| 订单实付 | `paidAmount` | `sortable` + `:sort-method` |
| 退款金额 | `refundedAmount` | `sortable` + `:sort-method` |
| 支付时间 | `paidAt` | `sortable` |
| 退款时间 | `refundedAt` | `sortable` |

### 2.5 `dev/vue-site/src/components/alibaba1688/Alibaba1688MonitorPanel.vue`（竞店监控·爆款榜商品列表）

表格数据源 `products`（本地全量快照，无分页），可排序列：

| 列 | 字段 | 方式 |
| --- | --- | --- |
| 排名 | `rank` | `sortable` |
| 价格 | `price` | `sortable` |
| 起订量 | `moq` | `sortable` |
| 好评率 | `good_rate` | `sortable` |
| 48h揽收 | `delivery_48h_rate` | `sortable` |
| 累计销量 | `total_sales` | `sortable` |
| 日增量 | `daily_sales` | `sortable` |
| 代发7天 | `dropship_7d` | `sortable` |
| 复购率 | `rebuy_rate` | `sortable` |

文本列（商品、店铺、状态）不加排序；本列表为本地全量数据，排序对整个商品列表生效。

## 3. 实现方式

- 数值型且直接绑定 `prop` 的列：加 `sortable` 即可。
- 模板渲染的数值列（价格/单价/销量/销售额/金额/质量分）：加 `sortable` 并配 `:sort-method="(a, b) => Number(a.字段 || 0) - Number(b.字段 || 0)"`，空值按 0 处理，避免按格式化文本排序。
- 时间列：格式统一为 `YYYY-MM-DD HH:mm:ss`，直接 `sortable`（字符串字典序即时间序）。
- 不新增依赖、不改 API、不改分页逻辑、不动其他模块。

## 4. 明确不做的事

- 不做服务端排序（后端分页列表仅当前页排序，后续如需跨页排序再单独评估）；
- 不给文本列（商品名称、订单号、SKU、买家、状态、追踪建议等）加排序；
- 不动经营看板、竞店监控列表（本次范围外，用户方案 A）。

## 5. 验证

- `cd dev/vue-site && npm run build` 通过；
- 本地 `npm run dev` 逐个点击四个列表的表头，确认升/降序、取消排序、空值表现正常；
- 回归检查：分页切换、筛选、刷新按钮行为不变。
