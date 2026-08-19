import axios from 'axios'

const api = axios.create({
  // Same-origin is the safe default. Local development can override this in .env.
  baseURL: import.meta.env.VITE_API_BASE || '/',
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('zeej_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export default api
