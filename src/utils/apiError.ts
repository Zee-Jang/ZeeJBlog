import { translate } from '../i18n/messages'
import type { AppLocale } from '../stores/locale'

const STORAGE_KEY = 'zeej_locale'
const SUPPORTED: AppLocale[] = ['zh-CN', 'zh-TW', 'en', 'ja']

function currentLocale(): AppLocale {
  try {
    const saved = localStorage.getItem(STORAGE_KEY) as AppLocale | null
    if (saved && SUPPORTED.includes(saved)) return saved
  } catch {
    /* ignore */
  }
  return 'zh-CN'
}

/** Normalize FastAPI / axios errors into a short user-facing string. */
export function formatApiError(err: unknown, fallback?: string): string {
  const locale = currentLocale()
  const fb = fallback ?? translate(locale, 'common.fail')
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0]
    if (typeof first === 'string') return first
    if (first && typeof first === 'object' && 'msg' in first) {
      const msg = (first as { msg?: unknown }).msg
      if (typeof msg === 'string') return msg
    }
    return fb
  }
  const message = (err as { message?: string })?.message
  if (message === 'Network Error') return translate(locale, 'common.network')
  return fb
}
