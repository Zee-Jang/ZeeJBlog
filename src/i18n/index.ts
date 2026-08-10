import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useLocaleStore, type AppLocale } from '../stores/locale'
import { translate } from './messages'

export function useI18n() {
  const store = useLocaleStore()
  const { locale, label } = storeToRefs(store)

  function t(key: string, params?: Record<string, string | number>) {
    return translate(locale.value, key, params)
  }

  const localeOptions = computed(() =>
    (['zh-CN', 'zh-TW', 'en', 'ja'] as AppLocale[]).map((code) => ({
      code,
      name: translate(code, 'nav.lang') === 'nav.lang'
        ? code
        : {
            'zh-CN': '简体中文',
            'zh-TW': '繁體中文',
            en: 'English',
            ja: '日本語',
          }[code],
    })),
  )

  return {
    t,
    locale,
    label,
    setLocale: store.setLocale,
    localeOptions,
  }
}
