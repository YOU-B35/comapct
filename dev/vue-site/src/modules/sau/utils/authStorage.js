/** Isolated SAU auth keys — never reuse CrossHub token storage. */
export const SAU_TOKEN_KEY = 'sau_token'
export const SAU_USER_KEY = 'sau_userInfo'

export function getSauToken() {
  return localStorage.getItem(SAU_TOKEN_KEY) || ''
}

export function setSauAuth(token, user) {
  if (token) localStorage.setItem(SAU_TOKEN_KEY, token)
  if (user) localStorage.setItem(SAU_USER_KEY, JSON.stringify(user))
}

export function clearSauAuth() {
  localStorage.removeItem(SAU_TOKEN_KEY)
  localStorage.removeItem(SAU_USER_KEY)
}
