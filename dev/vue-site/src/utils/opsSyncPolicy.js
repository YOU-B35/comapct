/**
 * 运营网页同步策略
 *
 * - Temu / AliExpress / Amazon：用户本机 Sync Helper（Boss+员工可下载绑定、登录、手动刷新）
 * - 其它仍可能只读；旧开关 OPS_MANUAL_SYNC_ENABLED 仅留给尚未迁移的入口
 */

/** @deprecated 用户本机 Helper 平台请用 canUsePlatformUserHelper() */
export const OPS_MANUAL_SYNC_ENABLED = false

export function canUseOpsManualSync() {
  return OPS_MANUAL_SYNC_ENABLED === true
}

/** Temu / AE / Amazon 用户本机助手模式 */
export function canUsePlatformUserHelper(auth) {
  return Boolean(auth?.backendLinked) && !auth?.isWarehouse
}

export const OPS_SYNC_READONLY_HINT =
  '请先安装并绑定本机 CrossHub Sync Helper，再在本页登录与刷新数据。'
