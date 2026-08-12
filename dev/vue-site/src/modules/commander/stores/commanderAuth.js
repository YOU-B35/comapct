import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { getAccessToken } from '@/api/request'
import {
  clearCommanderLocalState,
  isCommanderAuthenticated,
  setCommanderUnauthorizedHandler,
} from '../api/request'

/**
 * 自动上货鉴权：复用 CrossHub JWT（Java BFF 代登 Commander）。
 * 不再维护独立 Commander 登录会话。
 */
export const useCommanderAuthStore = defineStore('commanderAuth', () => {
  const ready = ref(false)
  const username = ref('')

  const isAuthenticated = computed(() => isCommanderAuthenticated())

  setCommanderUnauthorizedHandler(() => {
    // CrossHub 全局 401 由主 request 处理；此处仅清遗留 Commander key
    clearCommanderLocalState()
  })

  async function bootstrap() {
    clearCommanderLocalState()
    username.value = ''
    ready.value = true
  }

  function logout() {
    clearCommanderLocalState()
    username.value = ''
  }

  return {
    token: computed(() => getAccessToken() || ''),
    username,
    ready,
    isAuthenticated,
    bootstrap,
    logout,
  }
})
