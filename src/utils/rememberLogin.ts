/** 本机记住登录表单（邮箱 + 密码）。仅存当前浏览器，非服务端加密。 */

const STORAGE_KEY = 'zeej_remember_login'

export interface RememberedLogin {
  email: string
  password: string
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
    const password = decode(data.p || '')
    if (!email) return null
    return { email, password }
  } catch {
    return null
  }
}

export function saveRememberedLogin(email: string, password: string): void {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      e: encode(email.trim()),
      p: encode(password),
    }),
  )
}

export function clearRememberedLogin(): void {
  localStorage.removeItem(STORAGE_KEY)
}
