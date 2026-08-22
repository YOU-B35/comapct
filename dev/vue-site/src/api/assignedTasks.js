import { nowUtc8DateString, nowUtc8String } from '@/utils/time'
import { hasBackendSession } from './backendSession'
import {
  createBackendAssignedTask,
  createBackendAssignedTasksBatch,
  deleteBackendAssignedTask,
  fetchBackendAssignedTask,
  fetchBackendAssignedTasks,
  nudgeBackendAssignedTask,
  updateBackendAssignedTask,
  updateBackendAssignedTaskStatus,
} from './assignedTasksApi'
import {
  createLocalAssignedTask,
  deleteLocalAssignedTask,
  fetchLocalAssignedTaskById,
  fetchLocalAssignedTasks,
  mapAssignedTaskToCenterTask,
  updateLocalAssignedTask,
  updateLocalAssignedTaskStatus,
} from './assignedTasksLocal'
import { fetchBackendTaskFeedbacks } from './opsFeedbackApi'
import { fetchFeedbacksByTaskId } from './opsFeedbackLocal'
import { buildAssignedTaskDetail, mapOutcomeToTaskStatus } from '@/utils/assignedTaskFlow'

function mapAssignedRows(rows) {
  return rows
    .filter((task) => task.status !== '已取消')
    .map((task) => mapAssignedTaskToCenterTask(task))
}

function resolveAssigneeId(auth, task) {
  if (!auth?.backendLinked) return task.assigneeId || task.employeeId
  if (auth.isEmployee) return String(auth.backendUserId || auth.employee?.id || '')
  if (auth.isWarehouse) return String(auth.backendUserId || auth.warehouse?.id || '')
  return String(task.assigneeId || task.employeeId || '')
}

export async function fetchAssignedTasks(filters = {}, auth = null) {
  if (hasBackendSession(auth)) {
    const data = await fetchBackendAssignedTasks(filters)
    return { success: true, data }
  }
  return {
    success: true,
    data: fetchLocalAssignedTasks(filters),
  }
}

export async function fetchAssignedTaskDetail(taskId, auth = null) {
  if (hasBackendSession(auth)) {
    const task = await fetchBackendAssignedTask(taskId)
    if (!task) throw new Error('任务不存在')
    const feedbacks = await fetchBackendTaskFeedbacks(taskId)
    return {
      success: true,
      data: buildAssignedTaskDetail(task, feedbacks),
    }
  }

  const task = fetchLocalAssignedTaskById(taskId)
  if (!task) throw new Error('任务不存在')
  const feedbacks = fetchFeedbacksByTaskId(taskId)
  return {
    success: true,
    data: buildAssignedTaskDetail(task, feedbacks),
  }
}

export async function fetchAssignedTasksForCenter(auth, employees = []) {
  const filters = {}
  if (auth?.isEmployee && auth.employee?.id) {
    filters.assigneeId = resolveAssigneeId(auth, { assigneeId: auth.employee.id })
    filters.activeOnly = true
  }
  if (auth?.isWarehouse && auth.warehouse?.id) {
    filters.assigneeId = resolveAssigneeId(auth, { assigneeId: auth.warehouse.id })
    filters.activeOnly = true
  }

  let rows = []
  if (hasBackendSession(auth)) {
    rows = await fetchBackendAssignedTasks(
      auth?.isBoss
        ? { activeOnly: true }
        : { activeOnly: true },
    )
    if (auth?.isEmployee) {
      rows = rows.filter((task) => (task.assigneeType || 'employee') === 'employee')
    }
    if (auth?.isWarehouse) {
      rows = rows.filter((task) => task.assigneeType === 'warehouse')
    }
  } else if (auth?.isBoss) {
    rows = fetchLocalAssignedTasks()
  } else if (auth?.isEmployee && auth.employee?.id) {
    rows = fetchLocalAssignedTasks({ assigneeId: auth.employee.id }).filter(
      (task) => (task.assigneeType || 'employee') === 'employee',
    )
  } else if (auth?.isWarehouse && auth.warehouse?.id) {
    rows = fetchLocalAssignedTasks({ assigneeId: auth.warehouse.id }).filter(
      (task) => task.assigneeType === 'warehouse',
    )
  }

  return mapAssignedRows(rows)
}

export async function assignTask(payload, context = {}, auth = null) {
  if (hasBackendSession(auth)) {
    const data = await createBackendAssignedTask({
      title: payload.title,
      description: payload.description,
      assigneeType: payload.assigneeType || 'employee',
      assigneeId: payload.assigneeId || payload.employeeId,
      assignee: payload.assignee,
      assigneeName: payload.assignee,
      platformKey: payload.platformKey,
      category: payload.category,
      priority: payload.priority,
      due: payload.due,
      warehouseName: payload.warehouseName,
      assignedBy: payload.assignedBy || '企业管理员',
    })
    return {
      success: true,
      message: `已分配给 ${data.assignee}`,
      data,
    }
  }

  const data = createLocalAssignedTask(payload, context)
  return {
    success: true,
    message: `已分配给 ${data.assignee}`,
    data,
  }
}

export async function assignTaskToEmployee(payload, employees = [], auth = null) {
  return assignTask(payload, { employees, warehouseStaff: [] }, auth)
}

/** 批量分配：payload.assignees = [{ assigneeType, assigneeId, assignee }] */
export async function assignTasksBatch(payload, auth = null) {
  if (!hasBackendSession(auth)) {
    throw new Error('批量分配需登录后端账号')
  }
  const data = await createBackendAssignedTasksBatch({
    title: payload.title,
    description: payload.description,
    platformKey: payload.platformKey,
    category: payload.category,
    priority: payload.priority,
    due: payload.due,
    warehouseName: payload.warehouseName,
    assignedBy: payload.assignedBy,
    assigneeType: payload.assigneeType || 'employee',
    assignees: payload.assignees || [],
  })
  return { success: true, data }
}

export async function nudgeAssignedTask(id, auth = null) {
  if (!hasBackendSession(auth)) {
    throw new Error('催办需登录后端账号')
  }
  const data = await nudgeBackendAssignedTask(id)
  return { success: true, data }
}

export async function updateAssignedTask(id, payload, auth = null) {
  if (hasBackendSession(auth)) {
    const data = await updateBackendAssignedTask(id, payload)
    return { success: true, data }
  }
  const data = updateLocalAssignedTask(id, payload)
  return { success: true, data }
}

export async function updateAssignedTaskStatus(id, status, extra = {}, auth = null) {
  if (hasBackendSession(auth)) {
    const data = await updateBackendAssignedTaskStatus(id, status, extra)
    return { success: true, data }
  }
  const data = updateLocalAssignedTaskStatus(id, status, extra)
  return { success: true, data }
}

export async function syncAssignedTaskFeedback(taskId, payload, auth = null) {
  const { outcome, feedback, employeeName, assigneeName } = payload
  const status = mapOutcomeToTaskStatus(outcome)
  const name = assigneeName || employeeName || ''

  if (hasBackendSession(auth)) {
    return updateBackendAssignedTaskStatus(taskId, status, {
      lastOutcome: outcome,
      lastFeedback: (feedback || '').trim(),
      lastFeedbackAt: nowUtc8String(),
      lastFeedbackBy: name,
    })
  }

  const task = fetchLocalAssignedTaskById(taskId)
  if (!task) return null
  return updateLocalAssignedTaskStatus(taskId, status, {
    lastOutcome: outcome,
    lastFeedback: (feedback || '').trim(),
    lastFeedbackAt: nowUtc8String(),
    lastFeedbackBy: name || task.assignee,
  })
}

export async function removeAssignedTask(id, auth = null) {
  if (hasBackendSession(auth)) {
    await deleteBackendAssignedTask(id)
    return { success: true, message: '任务已删除' }
  }
  deleteLocalAssignedTask(id)
  return { success: true, message: '任务已删除' }
}

export async function cancelAssignedTask(id, auth = null) {
  if (hasBackendSession(auth)) {
    const data = await updateBackendAssignedTaskStatus(id, '已取消')
    return { success: true, message: '任务已取消', data }
  }
  const data = updateLocalAssignedTaskStatus(id, '已取消')
  return { success: true, message: '任务已取消', data }
}

/** 仓库端任务中心：仅展示分配给当前仓管的任务 */
export async function fetchWarehouseAssignedTasks(auth) {
  return fetchAssignedTasksForCenter(auth, [])
}
