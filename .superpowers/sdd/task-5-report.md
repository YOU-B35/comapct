# Task 5 Report: 联调验收 + 文案清理

## Status

**DONE**

## Commits

none (per task instruction)

## Spec §5 checklist (static walk of `DouyinModuleView.vue` + `douyinFullSync`)

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | 驾驶舱同盒（罗盘概况 + 概览汇总） | **PASS** | `PageSection title="经营驾驶舱"` → `.cockpit__compass` + `.cockpit__overview`（Boss） |
| 2 | 经营明细三级 Tab | **PASS** | 大 Tab `detailTab`: 商品榜 / 商机中心 / 商品信息；子 Tab `activeTab`: 商品 / 订单 / 预警 |
| 3 | 榜/商机子选项保留 | **PASS** | 榜：board / dateWindow / trackFilter / sort；商机：pool / sort / category + drawer |
| 4 | 刷新全部 6 步进度 + partial | **PASS** | `syncDouyinFull` + `FULL_SYNC_STEP_IDS`×6；UI `n/6 label…`；`out.partial` → warning。单测 `douyinFullSync.test.mjs` pass |
| 5 | 高级同步分模块可用 | **PASS** | collapse「高级同步」含商品/订单/罗盘/榜/商机×2/内容预警 |
| 6 | 切 Tab 不自动 sync | **PASS** | 无 `watch(detailTab)` / `watch(activeTab)` 调 sync；仅 store/filter/`onMounted` load |
| 7 | Java（若仅前端） | **N/A** | 本期前端编排，未改 Java |

Live Helper 点击「刷新全部」跑通 6 agent job：**未在本会话执行**（需在线 Helper + 已登录抖店）；编排与 UI 接线以源码+单测验收。

## Fixes applied

1. **Boss 跳转预警/订单** — `handleOverviewNavigate` 对 `orders` / `issues*` 设 `detailTab='catalog'`，再交 `navigateOverview` 设 `activeTab`（issues/orders）与 filter。
2. **`operationalDemoOnly`** — 仅隐藏罗盘段（`.cockpit__compass`）与榜/商机 Tab；Boss 概览仍可见；demo 时强制 `detailTab='catalog'`。同步助手 / Helper bar 仍整段隐藏。
3. **助手提示文案** — 改为含「刷新全部」串行六源 +「高级同步」分模块说明。
4. **Polish** — `advancedSyncOpen = ref([])`（Element Plus collapse 兼容）。

## Tests

```
cd dev/vue-site
node --test src/api/douyinFullSync.test.mjs
# pass 1 / fail 0
```

## Concerns

- E2E「刷新全部」仍依赖本机 Sync Helper + 抖店登录，未做点击冒烟。
- Demo-only 非 Boss 用户不显示驾驶舱（无罗盘且无概览），仅「经营明细 → 商品信息」。

## FIX (final-review Important)

1. **Gate「刷新全部」when Helper offline** — Primary button `:disabled="!session.agent_online || fullSyncing"`; `handleFullSync` early-returns with `ElMessage.warning('本机同步助手未在线，请先启动 CrossHub-Sync-Helper')` when `!session.agent_online`.
2. **Dedupe 商机 advanced-sync** — Removed duplicate「同步为你推荐 Top100」(same `handleSyncOpportunity`); kept single「同步商机当前榜」(current pool/sort).

**Verified:** grep `DouyinModuleView.vue` — one `handleFullSync` button with `agent_online || fullSyncing` disable + offline early-return; one advanced `handleSyncOpportunity` label「同步商机当前榜」; no「同步为你推荐 Top100」.

## Files touched

- `dev/vue-site/src/views/douyin/DouyinModuleView.vue`
- `.superpowers/sdd/task-5-report.md`（this report）
