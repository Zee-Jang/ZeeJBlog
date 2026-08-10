import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'

export type AppLocale = 'zh-CN' | 'zh-TW' | 'en' | 'ja'

const STORAGE_KEY = 'zeej_locale'
const SUPPORTED: AppLocale[] = ['zh-CN', 'zh-TW', 'en', 'ja']

function detectInitial(): AppLocale {
  try {
    const saved = localStorage.getItem(STORAGE_KEY) as AppLocale | null
    if (saved && SUPPORTED.includes(saved)) return saved
  } catch {
    /* ignore */
  }
  const nav = (navigator.language || '').toLowerCase()
  if (nav.startsWith('ja')) return 'ja'
  if (nav.startsWith('en')) return 'en'
  if (nav.includes('hant') || nav.startsWith('zh-tw') || nav.startsWith('zh-hk')) return 'zh-TW'
  return 'zh-CN'
}

export const useLocaleStore = defineStore('locale', () => {
  const locale = ref<AppLocale>(detectInitial())

  const label = computed(() => {
    const map: Record<AppLocale, string> = {
      'zh-CN': '简体中文',
      'zh-TW': '繁體中文',
      en: 'English',
      ja: '日本語',
    }
    return map[locale.value]
  })

  function setLocale(next: AppLocale) {
    if (!SUPPORTED.includes(next)) return
    locale.value = next
  }

  watch(
    locale,
    (v) => {
      try {
        localStorage.setItem(STORAGE_KEY, v)
      } catch {
        /* ignore */
      }
      document.documentElement.lang = v === 'zh-CN' ? 'zh-Hans' : v === 'zh-TW' ? 'zh-Hant' : v
    },
    { immediate: true },
  )

  return { locale, label, setLocale, supported: SUPPORTED }
})
