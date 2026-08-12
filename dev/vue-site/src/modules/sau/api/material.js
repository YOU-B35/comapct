import { buildApiUrl } from '@sau/utils/apiBase'
import { http } from '@sau/utils/request'

/** SAU 素材 API（对齐线上 automedia 契约） */
export const materialApi = {
  getAllMaterials() {
    return http.get('/getFiles')
  },
  uploadMaterial(formData, onUploadProgress) {
    return http.upload('/uploadSave', formData, onUploadProgress)
  },
  deleteMaterial(id) {
    return http.get(`/deleteFile?id=${id}`)
  },
  downloadMaterial(filePath) {
    return buildApiUrl(`/download/${filePath}`)
  },
  getMaterialPreviewUrl(filename) {
    return buildApiUrl(`/getFile?filename=${filename}`)
  },
}
