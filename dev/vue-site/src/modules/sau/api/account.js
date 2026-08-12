import { http } from '@sau/utils/request'

/** SAU 账号 API（对齐线上 automedia 契约） */
export const accountApi = {
  getValidAccounts(validate = true) {
    return http.get('/getValidAccounts', { validate: +!!validate })
  },
  checkAccount(id) {
    return http.post('/checkAccount', { id })
  },
  getAccounts() {
    return http.get('/getAccounts')
  },
  addAccount(payload) {
    return http.post('/account', payload)
  },
  updateAccount(payload) {
    return http.post('/updateUserinfo', payload)
  },
  deleteAccount(id) {
    return http.get(`/deleteAccount?id=${id}`)
  },
}
