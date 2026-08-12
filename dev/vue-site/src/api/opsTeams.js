import { service } from './request'

function unwrap(res) {
  return res?.data?.data ?? res?.data ?? null
}

export async function fetchOpsTeams() {
  const res = await service.get('/api/tenant/ops-teams')
  return unwrap(res) || []
}

export async function fetchMyOpsTeam() {
  const res = await service.get('/api/tenant/ops-teams/mine')
  return unwrap(res)
}

export async function fetchUnassignedEmployees() {
  const res = await service.get('/api/tenant/ops-teams/unassigned-employees')
  return unwrap(res) || []
}

export async function createOpsTeam(payload) {
  const res = await service.post('/api/tenant/ops-teams', payload)
  return unwrap(res)
}

export async function updateOpsTeam(id, payload) {
  const res = await service.put(`/api/tenant/ops-teams/${id}`, payload)
  return unwrap(res)
}

export async function archiveOpsTeam(id) {
  const res = await service.post(`/api/tenant/ops-teams/${id}/archive`)
  return unwrap(res) ?? true
}

export async function fetchOpsTeamMembers(teamId) {
  const res = await service.get(`/api/tenant/ops-teams/${teamId}/members`)
  return unwrap(res) || []
}

export async function addOpsTeamMember(teamId, userId) {
  const res = await service.post(`/api/tenant/ops-teams/${teamId}/members`, { userId })
  return unwrap(res)
}

export async function removeOpsTeamMember(teamId, userId) {
  const res = await service.delete(`/api/tenant/ops-teams/${teamId}/members/${userId}`)
  return unwrap(res) ?? true
}
