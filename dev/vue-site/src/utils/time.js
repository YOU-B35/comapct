/** 全项目时间口径：Asia/Shanghai（UTC+8），无时区字符串一律视为北京时间 */
export const SHANGHAI_OFFSET_MS = 8 * 60 * 60 * 1000

function pad(n) {
  return String(n).padStart(2, '0')
}

export function toUtc8Date(value) {
  if (value == null || value === '') return null
  if (typeof value === 'number') {
    const ms = Math.abs(value) < 1e12 ? value * 1000 : value
    return Number.isFinite(ms) ? new Date(ms) : null
  }
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value
  }
  const s = String(value).trim()
  if (!s) return null
  if (/^\d+$/.test(s)) {
    const n = Number(s)
    const ms = n < 1e12 ? n * 1000 : n
    return Number.isFinite(ms) ? new Date(ms) : null
  }
  if (/[zZ]|[+-]\d{2}:?\d{2}$/.test(s)) {
    const d = new Date(s)
    return Number.isNaN(d.getTime()) ? null : d
  }
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?/)
  if (!m) return null
  const [, y, mo, d, h, mi, se = '0'] = m
  const utcMs = Date.UTC(Number(y), Number(mo) - 1, Number(d), Number(h), Number(mi), Number(se))
  return new Date(utcMs - SHANGHAI_OFFSET_MS)
}

export function formatUtc8(value, { seconds = true } = {}) {
  const d = toUtc8Date(value)
  if (!d) return value == null || value === '' ? '—' : String(value)
  const shifted = new Date(d.getTime() + SHANGHAI_OFFSET_MS)
  const base = `${shifted.getUTCFullYear()}-${pad(shifted.getUTCMonth() + 1)}-${pad(shifted.getUTCDate())} ${pad(shifted.getUTCHours())}:${pad(shifted.getUTCMinutes())}`
  return seconds ? `${base}:${pad(shifted.getUTCSeconds())}` : base
}

export function nowUtc8String() {
  return formatUtc8(new Date())
}

export function nowUtc8DateString() {
  return formatUtc8(new Date(), { seconds: false }).slice(0, 10)
}
