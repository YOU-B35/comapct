import { service } from './request'

function mapTask(row) {
  if (!row) return row
  return {
    id: row.id,
    assigneeType: row.assigneeType || row.assignee_type || 'employee',
    assigneeId: row.assigneeId || row.assignee_id || row.employeeId,
    employeeId: row.employeeId || row.assignee_id || row.assigneeId,
    assignee: row.assignee || row.assignee_name || '',
    title: row.title,
    description: row.description || '',
    platformKey: row.platformKey || row.platform_key || 'temu',
    category: row.category || '',
    priority: row.priority || 'medium',
    status: row.status || '待处理',
    progress: row.progress ?? 0,
    due: row.due || row.due_text || '',
    warehouseName: row.warehouseName || row.warehouse_name || '',
    assignedBy: row.assignedBy || row.assigned_by || '',
    assignedAt: row.assignedAt || row.assigned_at || '',
    updatedAt: row.updatedAt || row.updated_at || '',
    lastOutcome: row.lastOutcome || row.last_outcome || '',
    lastFeedback: row.lastFeedback || row.last_feedback || '',
    lastFeedbackAt: row.lastFeedbackAt || row.last_feedback_at || '',
    lastFeedbackBy: row.lastFeedbackBy || row.last_feedback_by || '',
    nudgedAt: row.nudgedAt || row.nudged_at || '',
    nudgedBy: row.nudgedBy || row.nudged_by || '',
  }
}

export async function fetchBackendAssignedTasks(filters = {}) {
  const params = {}
  if (filters.status) params.status = filters.status
  if (filters.platformKey) params.platform_key = filters.platformKey
  if (filters.activeOnly) params.active_only = true
  const res = await service.get('/api/tasks', { params, skipGlobalErrorToast: true })
  return (res?.data || []).map(mapTask)
}

export async function fetchBackendAssignedTask(id) {
  const res = await service.get(`/api/tasks/${id}`, { skipGlobalErrorToast: true })
  return mapTask(res?.data)
}

export async function createBackendAssignedTask(payload) {
  const res = await service.post('/api/tasks', payload)
  return mapTask(res?.data)
}

export async function createBackendAssignedTasksBatch(payload) {
  const res = await service.post('/api/tasks/batch', payload)
  const data = res?.data || {}
  return {
    created: (data.created || []).map(mapTask),
    failed: data.failed || [],
    successCount: data.successCount ?? (data.created || []).length,
    failCount: data.failCount ?? (data.failed || []).length,
  }
}

export async function nudgeBackendAssignedTask(id) {
  const res = await service.post(`/api/tasks/${id}/nudge`)
  return mapTask(res?.data)
}

export async function updateBackendAssignedTask(id, payload) {
  const res = await service.patch(`/api/tasks/${id}`, payload)
  return mapTask(res?.data)
}

export async function updateBackendAssignedTaskStatus(id, status, extra = {}) {
  const res = await service.patch(`/api/tasks/${id}`, { status, ...extra })
  return mapTask(res?.data)
}

export async function deleteBackendAssignedTask(id) {
  await service.delete(`/api/tasks/${id}`)
}
