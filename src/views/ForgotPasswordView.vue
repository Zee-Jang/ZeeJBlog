<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import api from '../api/client'
import { useI18n } from '../i18n'
import type { AppLocale } from '../stores/locale'
import { formatApiError } from '../utils/apiError'

const router = useRouter()
const route = useRoute()
const { t, locale, setLocale } = useI18n()
const email = ref(typeof route.query.email === 'string' ? route.query.email : '')
const code = ref('')
const password = ref('')
const confirm = ref('')
const error = ref('')
const ok = ref('')
const done = ref(false)
const loading = ref(false)
const sending = ref(false)
const cooldown = ref(0)
let timer: number | undefined
let redirectTimer: number | undefined

const langs: { code: AppLocale; name: string }[] = [
  { code: 'zh-CN', name: '简体中文' },
  { code: 'zh-TW', name: '繁體中文' },
  { code: 'en', name: 'English' },
  { code: 'ja', name: '日本語' },
]

onMounted(() => {
  if (typeof route.query.email === 'string' && route.query.email) {
    email.value = route.query.email
  }
})

onUnmounted(() => {
  if (timer) window.clearInterval(timer)
  if (redirectTimer) window.clearTimeout(redirectTimer)
})

const canSubmit = computed(
  () =>
    !done.value &&
    email.value.includes('@') &&
    code.value &&
    password.value.length >= 8 &&
    password.value === confirm.value,
)

function startCooldown() {
  cooldown.value = 60
  timer = window.setInterval(() => {
    cooldown.value -= 1
    if (cooldown.value <= 0 && timer) {
      window.clearInterval(timer)
      timer = undefined
    }
  }, 1000)
}

async function sendCode() {
  error.value = ''
  ok.value = ''
  if (!email.value.includes('@')) {
    error.value = t('gate.emailNeed')
    return
  }
  sending.value = true
  try {
    const { data } = await api.post<{ detail: string }>('/api/auth/send-reset-code', {
      email: email.value.trim(),
    })
    ok.value = data.detail || t('gate.sendCode')
    const m = /开发模式）[：:]\s*(\d{4,8})/.exec(data.detail || '')
    if (m) code.value = m[1]
    startCooldown()
  } catch (e: unknown) {
    error.value = formatApiError(e, t('gate.sendFail'))
  } finally {
    sending.value = false
  }
}

async function onSubmit() {
  error.value = ''
  ok.value = ''
  loading.value = true
  try {
    const { data } = await api.post<{ detail: string }>('/api/auth/reset-password', {
      email: email.value.trim(),
      email_code: code.value.trim(),
      password: password.value,
      confirm_password: confirm.value,
    })
    done.value = true
    ok.value = data.detail || t('gate.resetOk')
    try {
      const { clearRememberedLogin } = await import('../utils/rememberLogin')
      clearRememberedLogin()
    } catch {
      /* ignore */
    }
    redirectTimer = window.setTimeout(() => {
      router.push({ path: '/login', query: { reset: '1', email: email.value.trim() } })
    }, 2200)
  } catch (e: unknown) {
    error.value = formatApiError(e, t('gate.resetFail'))
  } finally {
    loading.value = false
  }
}

function goLoginNow() {
  if (redirectTimer) window.clearTimeout(redirectTimer)
  router.push({ path: '/login', query: { reset: '1', email: email.value.trim() } })
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

    <form v-if="!done" class="card" @submit.prevent="onSubmit">
      <p class="eyebrow">{{ t('gate.forgotEyebrow') }}</p>
      <h1>{{ t('gate.forgotTitle') }}</h1>
      <p class="sub">{{ t('gate.forgotSub') }}</p>
      <div class="field">
        <label>{{ t('gate.regEmail') }}</label>
        <div class="row">
          <input v-model="email" type="email" required />
          <button class="btn ghost" type="button" :disabled="sending || cooldown > 0" @click="sendCode">
            {{ cooldown > 0 ? `${cooldown}s` : sending ? t('gate.sending') : t('gate.sendCode') }}
          </button>
        </div>
      </div>
      <div class="field">
        <label>{{ t('gate.code') }}</label>
        <input v-model="code" required maxlength="10" />
      </div>
      <div class="field">
        <label>{{ t('gate.newPassword') }}</label>
        <input v-model="password" type="password" required />
      </div>
      <div class="field">
        <label>{{ t('gate.confirmNewPassword') }}</label>
        <input v-model="confirm" type="password" required />
      </div>
      <p v-if="ok" class="banner ok">{{ ok }}</p>
      <p v-if="error" class="banner err">{{ error }}</p>
      <button class="btn primary" type="submit" :disabled="loading || !canSubmit">
        {{ loading ? t('gate.resetting') : t('gate.reset') }}
      </button>
      <p class="foot"><RouterLink to="/login">{{ t('gate.backLogin') }}</RouterLink></p>
    </form>

    <div v-else class="card success-card">
      <p class="eyebrow">{{ t('gate.resetDoneEyebrow') }}</p>
      <h1>{{ t('gate.resetDoneTitle') }}</h1>
      <p class="banner ok">{{ ok }}</p>
      <p class="sub">{{ t('gate.resetDoneSub') }}</p>
      <button class="btn primary" type="button" @click="goLoginNow">{{ t('gate.goLoginNow') }}</button>
    </div>
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
  width: min(460px, 100%);
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
.row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0.5rem;
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
