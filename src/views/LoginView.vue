<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useI18n } from '../i18n'
import { useAuthStore } from '../stores/auth'
import type { AppLocale } from '../stores/locale'
import { formatApiError } from '../utils/apiError'
import {
  clearRememberedLogin,
  loadRememberedLogin,
  saveRememberedLogin,
} from '../utils/rememberLogin'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const { t, locale, setLocale } = useI18n()

const email = ref(typeof route.query.email === 'string' ? route.query.email : '')
const password = ref('')
const remember = ref(false)
const error = ref('')
const tip = ref('')
const loading = ref(false)

const langs: { code: AppLocale; name: string }[] = [
  { code: 'zh-CN', name: '简体中文' },
  { code: 'zh-TW', name: '繁體中文' },
  { code: 'en', name: 'English' },
  { code: 'ja', name: '日本語' },
]

onMounted(() => {
  if (route.query.reset === '1') tip.value = t('gate.resetOk')
  const queryEmail = typeof route.query.email === 'string' ? route.query.email.trim() : ''
  const saved = loadRememberedLogin()
  if (route.query.reset === '1') {
    // 刚重置密码：清掉旧密码，只保留邮箱
    clearRememberedLogin()
    if (queryEmail) email.value = queryEmail
    remember.value = false
    password.value = ''
  } else if (saved) {
    remember.value = true
    email.value = queryEmail || saved.email
    // 仅当邮箱与记住的一致时才回填密码，避免串号
    password.value = !queryEmail || queryEmail === saved.email ? saved.password : ''
  } else if (queryEmail) {
    email.value = queryEmail
  }
})

async function onSubmit() {
  error.value = ''
  loading.value = true
  try {
    const mail = email.value.trim()
    await auth.login(mail, password.value)
    if (remember.value) saveRememberedLogin(mail, password.value)
    else clearRememberedLogin()
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    router.push(redirect)
  } catch (e: unknown) {
    error.value = formatApiError(e, t('gate.loginFail'))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="gate">
    <div class="lang-bar">
      <button
        v-for="opt in langs"
        :key="opt.code"
        type="button"
        :class="{ on: locale === opt.code }"
        @click="setLocale(opt.code)"
      >
        {{ opt.name }}
      </button>
    </div>
    <form class="card" @submit.prevent="onSubmit">
      <p class="eyebrow">{{ t('gate.loginEyebrow') }}</p>
      <h1>{{ t('gate.loginTitle') }}</h1>
      <p class="sub">{{ t('gate.loginSub') }}</p>
      <p v-if="tip" class="banner ok">{{ tip }}</p>
      <div class="field">
        <label>{{ t('gate.email') }}</label>
        <input
          v-model="email"
          type="email"
          name="username"
          required
          autocomplete="username"
        />
      </div>
      <div class="field">
        <label>{{ t('gate.password') }}</label>
        <input
          v-model="password"
          type="password"
          name="password"
          required
          autocomplete="current-password"
        />
      </div>
      <label class="remember">
        <input v-model="remember" type="checkbox" />
        <span>{{ t('gate.remember') }}</span>
      </label>
      <p v-if="error" class="banner err">{{ error }}</p>
      <button class="btn primary" type="submit" :disabled="loading">
        {{ loading ? t('gate.loggingIn') : t('gate.login') }}
      </button>
      <p class="foot">
        <RouterLink to="/register">{{ t('gate.registerLink') }}</RouterLink>
        ·
        <RouterLink to="/forgot-password">{{ t('gate.forgotLink') }}</RouterLink>
      </p>
    </form>
  </div>
</template>

<style scoped>
.gate {
  min-height: 100dvh;
  display: grid;
  place-items: center;
  padding: calc(1.5rem + env(safe-area-inset-top, 0px)) 1.5rem
    calc(1.5rem + env(safe-area-inset-bottom, 0px));
  position: relative;
}
.lang-bar {
  position: absolute;
  top: calc(1rem + env(safe-area-inset-top, 0px));
  right: max(1rem, env(safe-area-inset-right, 0px));
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  justify-content: flex-end;
}
.lang-bar button {
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.75);
  border-radius: 999px;
  padding: 0.3rem 0.65rem;
  font: inherit;
  font-size: 0.8rem;
  cursor: pointer;
  color: rgba(20, 32, 27, 0.7);
}
.lang-bar button.on {
  background: rgba(47, 111, 94, 0.14);
  color: var(--moss-deep);
}
.card {
  width: min(440px, 100%);
  display: grid;
  gap: 0.85rem;
  padding: 1.6rem;
  border: 1px solid var(--line);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.72);
}
.eyebrow {
  margin: 0;
  color: var(--moss-deep);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-size: 0.75rem;
}
h1 {
  margin: 0;
  font-family: var(--font-display);
  font-weight: 500;
}
.sub,
.foot {
  margin: 0;
  color: rgba(20, 32, 27, 0.65);
}
.remember {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  margin: 0;
  font-size: 0.9rem;
  color: rgba(20, 32, 27, 0.72);
  cursor: pointer;
  user-select: none;
}
.remember input {
  width: 1rem;
  height: 1rem;
  accent-color: var(--moss-deep);
  cursor: pointer;
}
.banner {
  margin: 0;
  padding: 0.65rem 0.75rem;
  border-radius: 10px;
  font-size: 0.9rem;
  line-height: 1.4;
}
.banner.ok {
  background: rgba(47, 111, 94, 0.12);
  border: 1px solid rgba(47, 111, 94, 0.28);
  color: var(--moss-deep);
  font-weight: 600;
}
.banner.err {
  background: rgba(180, 60, 50, 0.08);
  border: 1px solid rgba(180, 60, 50, 0.22);
  color: #9a3b32;
}
.foot a {
  color: var(--moss-deep);
  font-weight: 600;
}
</style>
