/** 本机记住登录邮箱。出于安全考虑不再存储密码；仅存当前浏览器。 */

const STORAGE_KEY = 'zeej_remember_login'

export interface RememberedLogin {
  email: string
}

function encode(text: string): string {
  try {
    return btoa(unescape(encodeURIComponent(text)))
  } catch {
    return ''
  }
}

function decode(text: string): string {
  try {
    return decodeURIComponent(escape(atob(text)))
  } catch {
    return ''
  }
}

export function loadRememberedLogin(): RememberedLogin | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const data = JSON.parse(raw) as { e?: string; p?: string }
    const email = decode(data.e || '')
    if (!email) return null
    if (data.p !== undefined) {
      // 旧版本曾存储过密码：改写为仅邮箱，清掉历史残留
      saveRememberedLogin(email)
    }
    return { email }
  } catch {
    return null
  }
}

export function saveRememberedLogin(email: string): void {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      e: encode(email.trim()),
    }),
  )
}

export function clearRememberedLogin(): void {
  localStorage.removeItem(STORAGE_KEY)
}
