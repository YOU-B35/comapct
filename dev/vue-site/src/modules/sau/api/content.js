import { http } from '@sau/utils/request'

export const useContentMock = false

export const contentApi = {
  async list() {
    try {
      const data = await http.get('/content/list')
      return Array.isArray(data) ? data : data?.list || data?.data || []
    } catch {
      return []
    }
  },
  async detail(id) {
    return http.get('/content/detail', { params: { id } })
  },
}
