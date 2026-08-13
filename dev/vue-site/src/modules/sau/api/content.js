import { http } from '@sau/utils/request'

/** 本地开发勿开 mock；线上 ContentWorks 同为 false */
export function useContentMock() {
  return false
}

/** SAU 作品 / 同步 API（对齐线上 automedia 契约） */
export const contentApi = {
  sync(accountId, limit = 20) {
    return http.post('/content/sync', { account_id: accountId, limit })
  },
  getJob(jobId) {
    return http.get(`/content/sync/${jobId}`)
  },
  listWorks(params = {}) {
    return http.get('/content/works', params)
  },
  getDashboard(params = {}) {
    return http.get('/content/dashboard', params)
  },
  getWork(id) {
    return http.get(`/content/works/${id}`)
  },
  getWorkSnapshots(id, params = {}) {
    return http.get(`/content/works/${id}/snapshots`, params)
  },
}
