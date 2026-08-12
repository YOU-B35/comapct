export function agentIdOf(row) {
  return String(row?.agent_id || row?.agentId || row?.id || '').trim()
}

export function isAgentOnline(row) {
  const status = String(row?.status || row?.state || '').toLowerCase()
  return status === 'online' || status === 'ready' || row?.online === true
}

export function normalizeAgentList(raw) {
  const list = Array.isArray(raw) ? raw : raw?.agents || raw?.list || raw?.data || []
  return (list || []).map((row) => ({
    ...row,
    id: agentIdOf(row),
    online: isAgentOnline(row),
  }))
}
