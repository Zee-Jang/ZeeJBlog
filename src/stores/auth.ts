import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import api from '../api/client'
import type { TokenResponse, User } from '../types'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const token = ref<string | null>(localStorage.getItem('zeej_token'))
  const ready = ref(false)

  const isAuthenticated = computed(() => Boolean(token.value && user.value))
  const isAdmin = computed(() => user.value?.role === 'admin')
  const displayName = computed(() => user.value?.nickname || user.value?.name || '用户')

  async function bootstrap() {
    if (!token.value) {
      ready.value = true
      return
    }
    try {
      const { data } = await api.get<User>('/api/auth/me')
      user.value = data
    } catch (e: unknown) {
      const status = (e as { response?: { status?: number } })?.response?.status
      // 仅凭证失效时清 token；网络/5xx 暂保留，避免误登出
      if (status === 401 || status === 403) {
        token.value = null
        user.value = null
        localStorage.removeItem('zeej_token')
      }
    } finally {
      ready.value = true
    }
  }

  async function refreshMe() {
    if (!token.value) return null
    try {
      const { data } = await api.get<User>('/api/auth/me')
      user.value = data
      return data
    } catch {
      return null
    }
  }

  function persist(data: TokenResponse) {
    token.value = data.access_token
    user.value = data.user
    localStorage.setItem('zeej_token', data.access_token)
  }

  async function register(payload: {
    email: string
    nickname: string
    password: string
    confirm_password: string
    email_code: string
    invite_code: string
  }) {
    const { data } = await api.post<TokenResponse>('/api/auth/register', payload)
    persist(data)
    try {
      sessionStorage.setItem('zeej_greet_once', '1')
      localStorage.setItem(`zeej_need_welcome_${data.user.id}`, '1')
    } catch {
      /* ignore */
    }
  }

  async function login(email: string, password: string) {
    const body = new URLSearchParams()
    body.set('username', email)
    body.set('password', password)
    const { data } = await api.post<TokenResponse>('/api/auth/login', body, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    persist(data)
    // 仅注册后尚未完成「首次激活」问候时，才在第一次成功登录弹出
    try {
      const uid = data.user.id
      if (localStorage.getItem(`zeej_need_welcome_${uid}`) === '1') {
        sessionStorage.setItem('zeej_greet_once', '1')
      }
    } catch {
      /* ignore */
    }
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('zeej_token')
    try {
      sessionStorage.removeItem('zeej_greet_once')
    } catch {
      /* ignore */
    }
  }

  function setUser(next: User) {
    user.value = next
  }

  return {
    user,
    token,
    ready,
    isAuthenticated,
    isAdmin,
    displayName,
    bootstrap,
    refreshMe,
    register,
    login,
    logout,
    setUser,
  }
})
