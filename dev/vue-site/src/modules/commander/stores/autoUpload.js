import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  getAgentList,
  getAgentTaskList,
  getShopList,
  productIssue,
  productIssuePrecheck,
  taskRetry,
} from '../api/agent'
import { getCommanderUsername } from '../api/request'
import { agentIdOf, isAgentOnline, normalizeAgentList } from '../utils/agent'

export const useCommanderAutoUploadStore = defineStore('commanderAutoUpload', () => {
  const agents = ref([])
  const agentLoading = ref(false)
  const agentListError = ref('')
  const selectedAgent = ref(null)
  const selectedPlatform = ref('temu')
  const platformOptions = [
    { value: 'temu', label: 'TEMU' },
    { value: 'aliexpress', label: 'AliExpress' },
    { value: 'ozon', label: 'Ozon' },
    // Commander 抖店/抖音 Excel 上货平台 id 为 douyin（与线上 /douyin-auto-upload 一致）
    { value: 'douyin', label: '抖店' },
    { value: '1688', label: '1688' },
  ]

  const shopList = ref([])
  const shopLoading = ref(false)
  const shopLoadError = ref('')
  const excelFile = ref(null)
  const shopId = ref('')
  const submitting = ref(false)
  const statusMessage = ref(null)

  const taskList = ref([])
  const taskTotal = ref(0)
  const taskPage = ref(1)
  const taskPageSize = ref(10)
  const taskLoading = ref(false)
  const taskError = ref('')

  const onlineAgents = computed(() => agents.value.filter((a) => isAgentOnline(a)))

  async function fetchAgents() {
    agentLoading.value = true
    agentListError.value = ''
    try {
      const res = await getAgentList({ skipGlobalErrorToast: true })
      const raw = res?.data ?? res?.list ?? res
      agents.value = normalizeAgentList(raw)
      if (!agents.value.length) agentListError.value = '暂无 Agent，请确认 Commander Agent 已在线'
    } catch (e) {
      agents.value = []
      agentListError.value = e.message || '加载 Agent 失败'
    } finally {
      agentLoading.value = false
    }
  }

  async function fetchShops() {
    const id = agentIdOf(selectedAgent.value)
    const platform = selectedPlatform.value
    if (!id || !platform) {
      shopList.value = []
      shopId.value = ''
      return
    }
    shopLoading.value = true
    shopLoadError.value = ''
    try {
      const res = await getShopList(id, platform)
      const raw = Array.isArray(res?.data) ? res.data : Array.isArray(res) ? res : []
      shopList.value = raw
      if (raw.length === 1) {
        shopId.value = String(raw[0]?.id ?? raw[0]?.shop_id ?? raw[0]?.shopId ?? '')
      }
    } catch (e) {
      shopList.value = []
      const raw = e.message || '加载店铺失败'
      // 抖店需桌面 Agent 开启「抖店」模块；离线/未开启时接口常返回泛化失败文案
      if (platform === 'douyin') {
        shopLoadError.value =
          /店铺|Agent|agent|离线|offline|失败|读取/i.test(raw)
            ? '没有读取到抖店 Agent，请确认桌面 Agent 已开启「抖店」并保持在线后重试'
            : raw
      } else {
        shopLoadError.value = raw
      }
    } finally {
      shopLoading.value = false
    }
  }

  function selectAgent(agent) {
    if (!isAgentOnline(agent)) return
    const nextId = agentIdOf(agent)
    const curId = agentIdOf(selectedAgent.value)
    if (curId && nextId && curId === nextId) {
      selectedAgent.value = null
      shopList.value = []
      shopId.value = ''
      return
    }
    selectedAgent.value = agent
    statusMessage.value = null
    fetchShops()
    fetchTasks()
  }

  async function fetchTasks(page = taskPage.value) {
    taskLoading.value = true
    taskError.value = ''
    taskPage.value = page
    try {
      const res = await getAgentTaskList(
        {
          agent_id: agentIdOf(selectedAgent.value),
          platform: selectedPlatform.value,
          page: taskPage.value,
          page_size: taskPageSize.value,
          list_scope: 'active',
        },
        { skipGlobalErrorToast: true },
      )
      const payload = res?.data ?? res
      const list = Array.isArray(payload?.list)
        ? payload.list
        : Array.isArray(payload?.data)
          ? payload.data
          : Array.isArray(payload)
            ? payload
            : []
      taskList.value = list
      taskTotal.value = Number(payload?.total ?? list.length ?? 0)
    } catch (e) {
      taskList.value = []
      taskTotal.value = 0
      taskError.value = e.message || '加载任务失败'
    } finally {
      taskLoading.value = false
    }
  }

  async function submitExcel() {
    if (submitting.value) return
    const agentId = agentIdOf(selectedAgent.value)
    if (!agentId) {
      statusMessage.value = { type: 'error', text: '请先选择在线 Agent' }
      return
    }
    if (!shopId.value) {
      statusMessage.value = { type: 'error', text: '请选择店铺' }
      return
    }
    if (!excelFile.value) {
      statusMessage.value = { type: 'error', text: '请选择 Excel 文件' }
      return
    }
    submitting.value = true
    statusMessage.value = null
    try {
      const platform = selectedPlatform.value || 'temu'
      if (platform === 'temu' || platform === 'douyin' || platform === '1688') {
        statusMessage.value = {
          type: 'info',
          text:
            platform === 'douyin'
              ? '正在预检抖店登录与店铺…'
              : platform === '1688'
                ? '正在预检1688登录与店铺…'
                : '正在预检…',
        }
        await productIssuePrecheck(agentId, shopId.value, platform)
      }
      const data = new FormData()
      data.append('agent', agentId)
      data.append('shop_id', shopId.value)
      data.append('platform', platform)
      data.append('file', excelFile.value)
      const operator = getCommanderUsername()
      if (operator) data.append('operator', operator)
      const res = await productIssue(data)
      statusMessage.value = {
        type: 'success',
        text: res?.data ?? res?.msg ?? '任务已提交',
      }
      excelFile.value = null
      await fetchTasks(1)
    } catch (e) {
      statusMessage.value = { type: 'error', text: e.message || '上传失败' }
    } finally {
      submitting.value = false
    }
  }

  async function retryTask(row) {
    const id = row?.taskId || row?.id || row?.uuid
    if (!id) return
    await taskRetry(id)
    await fetchTasks()
  }

  return {
    agents,
    agentLoading,
    agentListError,
    selectedAgent,
    selectedPlatform,
    platformOptions,
    onlineAgents,
    shopList,
    shopLoading,
    shopLoadError,
    excelFile,
    shopId,
    submitting,
    statusMessage,
    taskList,
    taskTotal,
    taskPage,
    taskPageSize,
    taskLoading,
    taskError,
    isAgentOnline,
    agentIdOf,
    fetchAgents,
    fetchShops,
    selectAgent,
    fetchTasks,
    submitExcel,
    retryTask,
  }
})
