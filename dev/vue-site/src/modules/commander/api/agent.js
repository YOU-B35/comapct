import { commanderService } from './request'

const V1 = '/api/commander/v1'

export async function getAgentList(config = {}) {
  return commanderService.post(`${V1}/agent/list`, null, config)
}

export async function getShopList(agentId, platform) {
  return commanderService.post(
    `${V1}/agent/shop_list`,
    { agent_id: agentId, platform },
    { skipGlobalErrorToast: true },
  )
}

export async function getCategoryList(agentId, platform) {
  return commanderService.post(
    `${V1}/agent/category_list`,
    { agent_id: agentId, platform },
    { skipGlobalErrorToast: true },
  )
}

export async function productIssuePrecheck(agentId, shopId, platform) {
  return commanderService.post(
    `${V1}/agent/product_issue_precheck`,
    { agent_id: agentId, shop_id: shopId, platform },
    { skipGlobalErrorToast: true },
  )
}

export async function productIssue(formData) {
  return commanderService.post(`${V1}/agent/product_issue`, formData, {
    skipGlobalErrorToast: true,
    headers: { 'Content-Type': undefined },
  })
}

export async function getAgentTaskList(params = {}, config = {}) {
  const body = {
    agent_id: params.agent_id ?? params.agentId ?? '',
    platform: params.platform ?? 'temu',
    page: Number(params.page ?? 1),
    page_size: Number(params.page_size ?? params.pageSize ?? 10),
    list_scope: params.list_scope ?? params.listScope ?? 'active',
  }
  return commanderService.post(`${V1}/agent/task_list`, body, config)
}

export async function taskRetry(taskId) {
  return commanderService.post(`${V1}/agent/retask`, { taskId })
}
