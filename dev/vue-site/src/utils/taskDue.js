/** 任务截止时间：新格式 yyyy-MM-dd HH:mm；兼容旧中文文案 */

const PAD = (n) => String(n).padStart(2, '0')

export function formatDueDateTime(date) {
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) return ''
  return `${date.getFullYear()}-${PAD(date.getMonth() + 1)}-${PAD(date.getDate())} ${PAD(date.getHours())}:${PAD(date.getMinutes())}`
}

export function parseTaskDue(due) {
  const text = String(due || '').trim()
  if (!text) return null
  // 2026-08-08 18:00 or 2026-08-08 18:00:00
  const m = text.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?$/)
  if (m) {
    const d = new Date(
      Number(m[1]),
      Number(m[2]) - 1,
      Number(m[3]),
      Number(m[4]),
      Number(m[5]),
      Number(m[6] || 0),
    )
    return Number.isNaN(d.getTime()) ? null : d
  }
  return null
}

export function isTaskOverdue(task, now = new Date()) {
  if (!task) return false
  const status = String(task.status || '')
  if (status === '已完成' || status === '已取消') return false
  const dueAt = parseTaskDue(task.due)
  if (!dueAt) return false
  return dueAt.getTime() < now.getTime()
}

/** 快捷截止：写成具体日期时间 */
export function dueShortcut(kind) {
  const now = new Date()
  const at = (h, m = 0) => {
    const d = new Date(now)
    d.setHours(h, m, 0, 0)
    return d
  }
  if (kind === 'today18') return formatDueDateTime(at(18))
  if (kind === 'today20') return formatDueDateTime(at(20))
  if (kind === 'today2359') return formatDueDateTime(at(23, 59))
  if (kind === 'tomorrow12') {
    const d = at(12)
    d.setDate(d.getDate() + 1)
    return formatDueDateTime(d)
  }
  if (kind === 'tomorrow18') {
    const d = at(18)
    d.setDate(d.getDate() + 1)
    return formatDueDateTime(d)
  }
  if (kind === 'friday18') {
    const d = at(18)
    const day = d.getDay() // 0 Sun … 5 Fri
    const add = (5 - day + 7) % 7 // 今天周五则为 0
    d.setDate(d.getDate() + add)
    return formatDueDateTime(d)
  }
  return formatDueDateTime(at(18))
}

export const DUE_SHORTCUTS = [
  { key: 'today18', label: '今天 18:00' },
  { key: 'today20', label: '今天 20:00' },
  { key: 'tomorrow18', label: '明天 18:00' },
  { key: 'friday18', label: '本周五 18:00' },
]
