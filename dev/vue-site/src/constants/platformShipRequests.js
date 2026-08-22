/** 平台订单 → 仓库发货推送 */

export const SHIP_REQUEST_TYPES = {
  push: { value: 'push', label: '推送发货', tag: 'primary' },
  urge: { value: 'urge', label: '催促发货', tag: 'warning' },
}

export const PLATFORM_ORDER_STORAGE_KEYS = {
  pdd: 'crosshub_pdd_orders',
  taobao: 'crosshub_taobao_orders',
  douyin: 'crosshub_douyin_orders',
  channels: 'crosshub_channels_orders',
}

export const PLATFORM_ORDER_LABELS = {
  pdd: '拼多多',
  taobao: '淘宝',
  douyin: '抖音',
  channels: '视频号',
  '1688': '1688',
}

/** 1688 采购单可推送至仓库的状态 */
export const ALIBABA1688_SHIPPABLE_STATUSES = new Set(['pending_shipment'])
