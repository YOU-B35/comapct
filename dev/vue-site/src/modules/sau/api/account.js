import { http } from '@sau/utils/request'

export const accountApi = {
  async list() {
    try {
      const data = await http.get('/account/list')
      return Array.isArray(data) ? data : data?.list || data?.data || []
    } catch {
      return []
    }
  },
  async create(payload) {
    return http.post('/account/create', payload)
  },
  async update(payload) {
    return http.post('/account/update', payload)
  },
  async remove(id) {
    return http.post('/account/delete', { id })
  },
}
