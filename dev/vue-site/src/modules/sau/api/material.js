import { http } from '@sau/utils/request'

export const materialApi = {
  async list() {
    try {
      const data = await http.get('/material/list')
      return Array.isArray(data) ? data : data?.list || data?.data || []
    } catch {
      return []
    }
  },
  async upload(formData) {
    return http.post('/material/upload', formData)
  },
  async remove(id) {
    return http.post('/material/delete', { id })
  },
}
