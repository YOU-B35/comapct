import {
  ASSIGNED_TASKS_SEED,
  PLATFORM_LABELS,
  TASK_STATUS_OPTIONS,
} from '@/constants/assignedTasks'
import { loadScoped, resolveTenantId, saveScoped, isDemoTemplateEnabled } from '@/utils/tenantStorage'

const STORAGE_KEY = 'crosshub_assigned_tasks'
const SEED_FLAG_KEY = 'crosshub_assigned_tasks_seeded'

function nowText() {
  return new Date().toISOString().replace('T', ' ').slice(0, 19)
}

function loadAll(tenantId = resolveTenantId()) {
  return loadScoped(tenantId, STORAGE_KEY, []) || []
}

function saveAll(items, tenantId = resolveTenantId()) {
  saveScoped(tenantId, STORAGE_KEY, items)
}

function ensureSeedTasks(tenantId = resolveTenantId()) {
  if (!isDemoTemplateEnabled(tenantId)) return
  const existing = loadAll(tenantId)
  const demoById = Object.fromEntries(ASSIGNED_TASKS_SEED.map((item) => [item.id, item]))
  const custom = existing.filter((item) => !demoById[item.id])
  const mergedDemos = ASSIGNED_TASKS_SEED.map((item) => {
    const current = existing.find((row) => row.id === item.id)
    if (!current) return { ...item }
    return { ...item, ...current }
  })
  saveAll([...custom, ...mergedDemos], tenantId)
  saveScoped(tenantId, SEED_FLAG_KEY, '1')
}

function normalizeStatus(status) {
  return TASK_STATUS_OPTIONS.includes(status) ? status : '待处理'
}

function taskAssigneeType(task) {
  return task?.assigneeType || 'employee'
}

function taskAssigneeId(task) {
  return task?.assigneeId || task?.employeeId || ''
}

export function fetchLocalAssignedTasks(filters = {}) {
  ensureSeedTasks()
  let items = loadAll()

  if (filters.assigneeType) {
    items = items.filter((item) => taskAssigneeType(item) === filters.assigneeType)
  }
  if (filters.assigneeId) {
    items = items.filter((item) => taskAssigneeId(item) === filters.assigneeId)
  }
  if (filters.employeeId) {
    items = items.filter((item) => taskAssigneeId(item) === filters.employeeId)
  }
  if (filters.status) {
    items = items.filter((item) => item.status === filters.status)
  }
  if (filters.platformKey) {
    items = items.filter((item) => item.platformKey === filters.platformKey)
  }
  if (filters.activeOnly) {
    items = items.filter((item) => item.status !== '已完成' && item.status !== '已取消')
  }

  return items.sort((a, b) => String(b.assignedAt).localeCompare(String(a.assignedAt)))
}

export function fetchLocalAssignedTaskById(id) {
  ensureSeedTasks()
  return loadAll().find((item) => item.id === id) || null
}

export function createLocalAssignedTask(payload, context = {}) {
  ensureSeedTasks()
  const items = loadAll()
  const { employees = [], warehouseStaff = [] } = context
  const assigneeType = payload.assigneeType || 'employee'
  const assigneeId = payload.assigneeId || payload.employeeId

  let assignee
  if (assigneeType === 'warehouse') {
    assignee = warehouseStaff.find((item) => item.id === assigneeId)
    if (!assignee) throw new Error('请选择有效仓库管理员')
  } else {
    assignee = employees.find((item) => item.id === assigneeId)
    if (!assignee) throw new Error('请选择有效运营人员')
  }
  if (!payload.title?.trim()) {
    throw new Error('请填写任务标题')
  }

  const row = {
    id: `assign_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
    assigneeType,
    assigneeId: assignee.id,
    employeeId: assignee.id,
    assignee: assignee.name,
    title: payload.title.trim(),
    description: (payload.description || '').trim(),
    platformKey: assigneeType === 'warehouse'
      ? 'warehouse'
      : (payload.platformKey || assignee.platforms?.[0] || 'temu'),
    category: payload.category || (assigneeType === 'warehouse' ? '出库' : '运营'),
    priority: payload.priority || 'medium',
    status: '待处理',
    progress: 0,
    due: payload.due || '今天 18:00',
    warehouseName: assigneeType === 'warehouse' ? (payload.warehouseName || '').trim() : '',
    assignedBy: payload.assignedBy || '企业管理员',
    assignedAt: nowText(),
    updatedAt: nowText(),
    lastOutcome: '',
    lastFeedback: '',
    lastFeedbackAt: '',
    lastFeedbackBy: '',
  }

  items.unshift(row)
  saveAll(items)
  return row
}

export function updateLocalAssignedTask(id, payload) {
  ensureSeedTasks()
  const items = loadAll()
  const index = items.findIndex((item) => item.id === id)
  if (index === -1) throw new Error('任务不存在')

  items[index] = {
    ...items[index],
    ...payload,
    updatedAt: nowText(),
  }
  saveAll(items)
  return items[index]
}

export function updateLocalAssignedTaskStatus(id, status, extra = {}) {
  const normalized = normalizeStatus(status)
  return updateLocalAssignedTask(id, { status: normalized, ...extra })
}

export function deleteLocalAssignedTask(id) {
  ensureSeedTasks()
  const items = loadAll()
  const index = items.findIndex((item) => item.id === id)
  if (index === -1) throw new Error('任务不存在')
  const [removed] = items.splice(index, 1)
  saveAll(items)
  return removed
}

export function mapAssignedTaskToCenterTask(task) {
  const platformKey = task.platformKey || 'temu'
  const assigneeType = taskAssigneeType(task)
  const routes = {
    temu: '/employee/temu',
    aliexpress: '/employee/aliexpress',
    amazon: '/employee/amazon',
    walmart: '/employee/walmart',
    pdd: '/employee/pdd',
    douyin: '/employee/douyin',
    channels: '/employee/channels',
    '1688': '/employee/1688',
    dtc: '/employee/dtc',
    warehouse: '/warehouse/pending-review',
  }
  return {
    id: task.id,
    source: 'assigned',
    assigneeType,
    assigneeId: taskAssigneeId(task),
    employeeId: task.employeeId,
    assignee: task.assignee,
    title: task.title,
    detail: task.description || '',
    platform: PLATFORM_LABELS[platformKey] || platformKey,
    platformKey,
    category: task.category || '运营',
    priority: task.priority || 'medium',
    status: task.status || '待处理',
    progress: task.progress ?? 0,
    due: task.due || '今天 18:00',
    storeName: task.warehouseName || task.storeName || '—',
    route: routes[platformKey] || '',
    assignedBy: task.assignedBy,
    assignedAt: task.assignedAt,
    updatedAt: task.updatedAt,
    lastOutcome: task.lastOutcome,
    lastFeedback: task.lastFeedback,
    lastFeedbackAt: task.lastFeedbackAt,
    nudgedAt: task.nudgedAt || '',
    nudgedBy: task.nudgedBy || '',
  }
}
