import { createDomesticOrdersLocal, createDomesticIssuesLocal } from './domesticPlatformLocal'
import { PDD_ORDERS_SEED, PDD_ISSUES_SEED } from '@/constants/pddDemo'
import { DOUYIN_ORDERS_SEED, DOUYIN_ISSUES_SEED } from '@/constants/douyinDemo'
import { CHANNELS_ORDERS_SEED, CHANNELS_ISSUES_SEED } from '@/constants/channelsDemo'
import { TAOBAO_ORDERS_SEED, TAOBAO_ISSUES_SEED } from '@/constants/taobaoDemo'

const pddOrders = createDomesticOrdersLocal({
  storageKey: 'crosshub_pdd_orders',
  seedOrders: PDD_ORDERS_SEED,
  orderPrefix: 'PDD',
  refreshMessage: '已刷新拼多多今日订单',
  channels: ['商城', '百亿补贴'],
})

const pddIssues = createDomesticIssuesLocal({
  storageKey: 'crosshub_pdd_issues',
  seedIssues: PDD_ISSUES_SEED,
  refreshMessage: '已刷新拼多多运营预警',
})

const douyinOrders = createDomesticOrdersLocal({
  storageKey: 'crosshub_douyin_orders',
  seedOrders: DOUYIN_ORDERS_SEED,
  orderPrefix: 'DY',
  refreshMessage: '已刷新抖音今日订单',
  channels: ['直播', '短视频', '商城'],
})

const douyinIssues = createDomesticIssuesLocal({
  storageKey: 'crosshub_douyin_issues',
  seedIssues: DOUYIN_ISSUES_SEED,
  refreshMessage: '已刷新抖音运营预警',
})

const channelsOrders = createDomesticOrdersLocal({
  storageKey: 'crosshub_channels_orders',
  seedOrders: CHANNELS_ORDERS_SEED,
  orderPrefix: 'SPH',
  refreshMessage: '已刷新视频号今日订单',
  channels: ['直播', '短视频', '橱窗'],
})

const channelsIssues = createDomesticIssuesLocal({
  storageKey: 'crosshub_channels_issues',
  seedIssues: CHANNELS_ISSUES_SEED,
  refreshMessage: '已刷新视频号运营预警',
})

const taobaoOrders = createDomesticOrdersLocal({
  storageKey: 'crosshub_taobao_orders',
  seedOrders: TAOBAO_ORDERS_SEED,
  orderPrefix: 'TB',
  refreshMessage: '已刷新淘宝今日订单',
  channels: ['天猫', '淘宝', '聚划算'],
})

const taobaoIssues = createDomesticIssuesLocal({
  storageKey: 'crosshub_taobao_issues',
  seedIssues: TAOBAO_ISSUES_SEED,
  refreshMessage: '已刷新淘宝运营预警',
})

export const pddOrdersLocal = pddOrders
export const pddIssuesLocal = pddIssues
export const douyinOrdersLocal = douyinOrders
export const douyinIssuesLocal = douyinIssues
export const channelsOrdersLocal = channelsOrders
export const channelsIssuesLocal = channelsIssues
export const taobaoOrdersLocal = taobaoOrders
export const taobaoIssuesLocal = taobaoIssues
