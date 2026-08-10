<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import api from '../api/client'
import { useI18n } from '../i18n'
import { useAuthStore } from '../stores/auth'
import type { AppLocale } from '../stores/locale'
import { formatApiError } from '../utils/apiError'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const { t, locale, setLocale } = useI18n()

const nickname = ref('')
const email = ref('')
const password = ref('')
const confirm = ref('')
const invite = ref(typeof route.query.invite === 'string' ? route.query.invite : '')
const emailCode = ref('')
const error = ref('')
const tip = ref('')
const loading = ref(false)
const sending = ref(false)
const cooldown = ref(0)
let timer: number | undefined

const langs: { code: AppLocale; name: string }[] = [
  { code: 'zh-CN', name: '简体中文' },
  { code: 'zh-TW', name: '繁體中文' },
  { code: 'en', name: 'English' },
  { code: 'ja', name: '日本語' },
]

onMounted(() => {
  if (typeof route.query.invite === 'string' && route.query.invite) {
    invite.value = route.query.invite
  }
})

onUnmounted(() => {
  if (timer) window.clearInterval(timer)
})

const passwordHint = computed(() => {
  if (!password.value) return t('gate.pwHint')
  if (!/^(?=.*[A-Za-z])(?=.*\d).{8,}$/.test(password.value)) return t('gate.pwBad')
  if (confirm.value && confirm.value !== password.value) return t('gate.pwMismatch')
  return t('gate.pwOk')
})

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
  tip.value = ''
  if (!email.value.includes('@')) {
    error.value = t('gate.emailNeed')
    return
  }
  sending.value = true
  try {
    const { data } = await api.post<{ detail: string }>('/api/auth/send-register-code', {
      email: email.value.trim(),
    })
    tip.value = data.detail || t('gate.sendCode')
    const m = /开发模式）[：:]\s*(\d{4,8})/.exec(data.detail || '')
    if (m) emailCode.value = m[1]
    startCooldown()
  } catch (e: unknown) {
    error.value = formatApiError(e, t('gate.sendFail'))
  } finally {
    sending.value = false
  }
}

async function onSubmit() {
  error.value = ''
  tip.value = ''
  loading.value = true
  try {
    await auth.register({
      nickname: nickname.value.trim(),
      email: email.value.trim(),
      password: password.value,
      confirm_password: confirm.value,
      email_code: emailCode.value.trim(),
      invite_code: invite.value.trim(),
    })
    router.push('/')
  } catch (e: unknown) {
    error.value = formatApiError(e, t('gate.regFail'))
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
      <p class="eyebrow">{{ t('gate.regEyebrow') }}</p>
      <h1>{{ t('gate.regTitle') }}</h1>
      <p class="sub">{{ t('gate.regSub') }}</p>

      <div class="field">
        <label>{{ t('gate.invite') }}</label>
        <input v-model="invite" required :placeholder="t('gate.invitePh')" />
      </div>
      <div class="field">
        <label>{{ t('gate.email') }}</label>
        <div class="row">
          <input v-model="email" type="email" required autocomplete="email" />
          <button class="btn ghost" type="button" :disabled="sending || cooldown > 0" @click="sendCode">
            {{ cooldown > 0 ? `${cooldown}s` : sending ? t('gate.sending') : t('gate.sendCode') }}
          </button>
        </div>
      </div>
      <div class="field">
        <label>{{ t('gate.emailCode') }}</label>
        <input v-model="emailCode" required maxlength="10" :placeholder="t('gate.codePh')" />
      </div>
      <div class="field">
        <label>{{ t('gate.nickname') }}</label>
        <input v-model="nickname" required maxlength="30" />
      </div>
      <div class="field">
        <label>{{ t('gate.password') }}</label>
        <input v-model="password" type="password" required autocomplete="new-password" />
      </div>
      <div class="field">
        <label>{{ t('gate.confirmPassword') }}</label>
        <input v-model="confirm" type="password" required autocomplete="new-password" />
        <small :class="{ ok: passwordHint === t('gate.pwOk') }">{{ passwordHint }}</small>
      </div>

      <p v-if="tip" class="ok">{{ tip }}</p>
      <p v-if="error" class="error">{{ error }}</p>
      <button class="btn primary" type="submit" :disabled="loading">
        {{ loading ? t('gate.registering') : t('gate.register') }}
      </button>
      <p class="foot">
        {{ t('gate.hasAccount') }}
        <RouterLink to="/login">{{ t('gate.goLogin') }}</RouterLink>
      </p>
      <p class="tip">{{ t('gate.devTip') }}</p>
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
  width: min(480px, 100%);
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
.foot,
.tip,
small {
  margin: 0;
  color: rgba(20, 32, 27, 0.65);
}
.tip {
  font-size: 0.85rem;
}
small.ok {
  color: var(--moss-deep);
}
.ok {
  margin: 0;
  color: var(--moss-deep);
  font-size: 0.9rem;
}
.error {
  margin: 0;
  color: #9a3b32;
  font-size: 0.9rem;
}
.row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0.5rem;
}
.foot a {
  color: var(--moss-deep);
  font-weight: 600;
}
</style>
