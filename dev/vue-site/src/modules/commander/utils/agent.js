/** 心跳新鲜窗口（与线上 AutoUpload 一致） */
const HEARTBEAT_FRESH_MS = 90 * 1000

function text(value) {
  return value == null ? '' : String(value).trim()
}

function parseHeartbeatMs(raw) {
  const s = text(raw)
  if (!s) return NaN
  if (s.includes('T')) return Date.parse(s)
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})$/)
  if (!m) return Date.parse(s)
  const [, y, mo, d, h, mi, se] = m
  return new Date(Number(y), Number(mo) - 1, Number(d), Number(h), Number(mi), Number(se)).getTime()
}

function heartbeatRaw(row) {
  return (
    text(row?.last_heartbeat_at)
    || text(row?.lastHeartbeatAt)
    || text(row?.heartbeat_at)
    || text(row?.heartbeatAt)
    || text(row?.last_online_at)
    || text(row?.lastOnlineAt)
    || text(row?.updated_at)
    || text(row?.updatedAt)
  )
}

function isHeartbeatFresh(row, now = Date.now()) {
  const raw = heartbeatRaw(row)
  if (!raw) return false
  const ts = parseHeartbeatMs(raw)
  if (Number.isNaN(ts)) return false
  return now - ts <= HEARTBEAT_FRESH_MS
}

/** Commander Agent 主键：线上列表字段为 uuid */
export function agentIdOf(row) {
  return text(row?.uuid || row?.agent_id || row?.agentId || row?.id)
}

/**
 * 在线判定对齐线上 AutoUpload：
 * - status/online 可为 boolean / 0|1 / 字符串
 * - 若仅有心跳时间，则 90s 内视为在线
 */
export function isAgentOnline(row, now = Date.now()) {
  if (!row) return false

  const flag = row.online ?? row.is_online ?? row.isOnline ?? row.connected ?? row.is_connected ?? row.isConnected
  if (flag === false || flag === 0 || flag === '0') return false
  if (flag === true || flag === 1 || flag === '1') return true

  const status = row.status ?? row.state ?? row.connection_status ?? row.connectionStatus
  if (status === false || status === 0 || status === '0') return false
  if (typeof status === 'string') {
    const n = status.trim().toLowerCase()
    if (['offline', 'inactive', 'disabled', 'disconnected', 'closed'].includes(n)) return false
    if (['online', 'active', 'connected', 'open', 'ready'].includes(n)) {
      return heartbeatRaw(row) ? isHeartbeatFresh(row, now) : true
    }
  }
  return !!(status === true || status === 1 || isHeartbeatFresh(row, now))
}

function unwrapAgentArray(raw) {
  if (Array.isArray(raw)) return raw
  if (!raw || typeof raw !== 'object') return []
  const candidates = [
    raw.agents,
    raw.agent_list,
    raw.agentList,
    raw.list,
    raw.items,
    raw.data,
    raw.result,
    raw.rows,
  ]
  for (const c of candidates) {
    if (Array.isArray(c)) return c
  }
  if (raw.data && typeof raw.data === 'object') {
    const nested = [
      raw.data.agents,
      raw.data.agent_list,
      raw.data.agentList,
      raw.data.list,
      raw.data.rows,
      raw.data.items,
    ]
    for (const c of nested) {
      if (Array.isArray(c)) return c
    }
  }
  return []
}

export function normalizeAgentList(raw) {
  const list = unwrapAgentArray(raw)
  return list.map((row) => ({
    ...row,
    id: agentIdOf(row),
    online: isAgentOnline(row),
  }))
}
