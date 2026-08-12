import { defineStore } from 'pinia'
import { ref } from 'vue'
import { clearSauAuth, getSauToken, SAU_USER_KEY, setSauAuth } from '@sau/utils/authStorage'

export const useSauUserStore = defineStore('sauUser', () => {
  const userInfo = ref({
    id: null,
    username: '',
  })

  const token = ref(getSauToken())
  const isLoggedIn = ref(!!token.value)

  const setAuth = (authToken, user) => {
    token.value = authToken
    userInfo.value = {
      id: user?.id ?? null,
      username: user?.username || '',
    }
    isLoggedIn.value = true
    setSauAuth(authToken, userInfo.value)
  }

  const setUserInfo = (info) => {
    userInfo.value = info
    isLoggedIn.value = true
    localStorage.setItem(SAU_USER_KEY, JSON.stringify(info))
  }

  const logout = () => {
    userInfo.value = {
      id: null,
      username: '',
    }
    token.value = ''
    isLoggedIn.value = false
    clearSauAuth()
  }

  const restoreFromStorage = () => {
    const savedToken = getSauToken()
    const savedUser = localStorage.getItem(SAU_USER_KEY)
    if (savedToken) {
      token.value = savedToken
      isLoggedIn.value = true
    }
    if (savedUser) {
      try {
        userInfo.value = JSON.parse(savedUser)
      } catch {
        userInfo.value = { id: null, username: '' }
      }
    }
  }

  return {
    userInfo,
    token,
    isLoggedIn,
    setAuth,
    setUserInfo,
    logout,
    restoreFromStorage,
  }
})

/** @deprecated prefer useSauUserStore — kept for copied SAU views */
export const useUserStore = useSauUserStore
