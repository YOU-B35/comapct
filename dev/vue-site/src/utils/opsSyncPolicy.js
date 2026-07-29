/**
 * 运营网页同步策略（产品强制口径）
 *
 * - 任何成员（Boss / 员工）只看运营数据，不操作同步、不下载/启动助手
 * - 同步由一台运维肉机常驻 CrossHub-Sync-Helper.exe + 服务端日批（默认 09:30）完成
 * - 运维排障仍可用 API / 肉机本机工具；网页不再暴露同步入口
 */

/** 是否允许运营网页触发手动同步 / 打开登录窗 / 下载助手 */
export const OPS_MANUAL_SYNC_ENABLED = false

export function canUseOpsManualSync() {
  return OPS_MANUAL_SYNC_ENABLED === true
}

export const OPS_SYNC_READONLY_HINT =
  '店铺数据由运维机定时自动同步（默认每天 09:30），本页仅展示结果，无需手动同步或安装助手。'
