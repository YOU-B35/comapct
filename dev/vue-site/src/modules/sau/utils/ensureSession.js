import { getAccessToken, service } from '@/api/request'
import { useSauUserStore } from '@sau/stores/user'
import { clearSauAuth, getSauToken } from '@sau/utils/authStorage'
import { isSauTokenUsable } from '@sau/utils/sauToken'

export { isSauTokenUsable }

let inflight = null

/** Exchange CrossHub employee JWT for SAU API token (silent). */
export async function ensureSauSession({ force = false } = {}) {
  const store = useSauUserStore()
  store.restoreFromStorage()
  if (!force && store.token && isSauTokenUsable(store.token)) {
    return store.token
  }
  if (!getAccessToken()) {
    throw new Error('请先登录 CrossHub 账号')
  }
  if (!inflight) {
    inflight = service
      .post('/api/sau/token')
      .then((res) => {
        // axios interceptor unwraps to { code, data }
        const data = res?.data || {}
        const token = data.token
        if (!token) throw new Error('未取得自媒体会话')
        store.setAuth(token, {
          id: data.sau_user_id,
          username: data.sau_username || '',
        })
        return token
      })
      .catch((err) => {
        // Stale local token must not keep winning force:false after a failed refresh.
        clearSauAuth()
        store.logout()
        throw err
      })
      .finally(() => {
        inflight = null
      })
  }
  return inflight
}
