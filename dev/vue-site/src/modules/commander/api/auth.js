/**
 * 历史 Commander 模块登录 API（已废弃）。
 * 自动上货改为 CrossHub JWT + Java BFF，不再直连 /api/v1/user/login。
 */
import { clearCommanderLocalState } from './request'

export async function commanderLogin() {
  throw new Error('已改为 CrossHub 代登，请直接使用自动上货页面')
}

export async function commanderRefresh() {
  return { code: 0, data: null }
}

export function commanderLogoutLocal() {
  clearCommanderLocalState()
}
