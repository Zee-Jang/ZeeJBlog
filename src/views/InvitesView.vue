<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import api from '../api/client'
import { useI18n } from '../i18n'
import { useAuthStore } from '../stores/auth'
import { formatDateShanghai } from '../utils/time'
import { formatApiError } from '../utils/apiError'
import { useCopyToast } from '../composables/useCopyToast'

interface Invite {
  id: number
  code: string
  max_uses: number
  use_count: number
  note: string
  is_active: boolean
  created_at: string
  expires_at: string | null
  remaining: number
  invite_url: string
  share_text: string
}

interface Quota {
  used: number
  limit: number
  remaining: number
  account_age_days: number
  unlock_30_in_days: number
}

const auth = useAuthStore()
const { t } = useI18n()
const invites = ref<Invite[]>([])
const quota = ref<Quota | null>(null)
const latest = ref<Invite | null>(null)
const error = ref('')
const tip = ref('')
const loading = ref(false)
const { toast, copyText } = useCopyToast()

const origin = computed(() => (typeof window !== 'undefined' ? window.location.origin : ''))

function withOrigin(inv: Invite): Invite {
  const path = `/register?invite=${encodeURIComponent(inv.code)}`
  const url = `${origin.value}${path}`
  const share = t('invite.shareBody', { url, code: inv.code })
  return { ...inv, invite_url: url, share_text: share }
}

async function load() {
  const [q, list] = await Promise.all([
    api.get<Quota>('/api/invites/quota'),
    api.get<Invite[]>('/api/invites/mine'),
  ])
  quota.value = q.data
  invites.value = list.data.map(withOrigin)
}

async function createOne() {
  error.value = ''
  tip.value = ''
  loading.value = true
  try {
    const { data } = await api.post<Invite>('/api/invites/one', {
      expires_days: 30,
    })
    latest.value = withOrigin(data)
    tip.value = t('invite.created')
    await load()
  } catch (e: unknown) {
    error.value = formatApiError(e, t('invite.fail'))
  } finally {
    loading.value = false
  }
}

async function revoke(id: number) {
  if (!confirm(t('invite.revokeConfirm'))) return
  error.value = ''
  try {
    await api.post(`/api/invites/${id}/revoke`)
    await load()
  } catch (e: unknown) {
    error.value = formatApiError(e, t('invite.fail'))
  }
}

async function copy(text: string, kind: 'msg' | 'link' | 'code') {
  const ok =
    kind === 'msg'
      ? t('invite.copiedMsg')
      : kind === 'link'
        ? t('invite.copiedLink')
        : t('invite.copiedCode')
  await copyText(text, ok, t('invite.copyFailed'))
}

onMounted(load)
</script>

<template>
  <main class="container page">
    <section class="panel-box">
      <header class="panel-head">
        <RouterLink v-if="auth.isAdmin" class="back" to="/admin">← {{ t('admin.backMenu') }}</RouterLink>
        <h2>{{ t('invite.title') }}</h2>
        <p>{{ t('invite.desc') }}</p>
        <p v-if="quota" class="quota">
          {{ t('invite.quota', { used: quota.used, limit: quota.limit, left: quota.remaining }) }}
          <span v-if="quota.unlock_30_in_days > 0">
            · {{ t('invite.unlockIn', { days: quota.unlock_30_in_days }) }}
          </span>
        </p>
      </header>

      <button
        class="btn primary"
        type="button"
        :disabled="loading || (quota !== null && quota.remaining <= 0)"
        @click="createOne"
      >
        {{ t('invite.generateOne') }}
      </button>
      <p class="hint">{{ t('invite.oneOnly') }}</p>
      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="tip" class="ok">{{ tip }}</p>
    </section>

    <section v-if="latest" class="panel-box">
      <h2 class="list-title">{{ t('invite.latest') }}</h2>
      <p class="code">{{ latest.code }}</p>
      <textarea readonly rows="6" :value="latest.share_text" />
      <div class="actions">
        <button class="btn primary" type="button" @click="copy(latest!.share_text, 'msg')">
          {{ t('invite.copyMsg') }}
        </button>
        <button class="btn ghost" type="button" @click="copy(latest!.invite_url, 'link')">
          {{ t('invite.copyLink') }}
        </button>
        <button class="btn ghost" type="button" @click="copy(latest!.code, 'code')">
          {{ t('invite.copyCode') }}
        </button>
      </div>
    </section>

    <section class="panel-box">
      <h2 class="list-title">{{ t('invite.mine') }}</h2>
      <ul>
        <li v-for="inv in invites" :key="inv.id">
          <div>
            <strong>{{ inv.code }}</strong>
            <span>{{ formatDateShanghai(inv.created_at, 'datetime') }}</span>
            <span>{{ inv.is_active ? t('invite.active') : t('invite.revoked') }}</span>
            <span>{{ inv.use_count }}/{{ inv.max_uses }}</span>
          </div>
          <div class="actions">
            <button class="btn ghost" type="button" @click="copy(withOrigin(inv).share_text, 'msg')">
              {{ t('invite.copyMsg') }}
            </button>
            <button
              v-if="inv.is_active"
              class="btn ghost"
              type="button"
              @click="revoke(inv.id)"
            >
              {{ t('invite.revoke') }}
            </button>
          </div>
        </li>
        <li v-if="!invites.length" class="empty">{{ t('invite.empty') }}</li>
      </ul>
      <p v-if="auth.isAdmin" class="hint">{{ t('invite.adminHint') }}</p>
    </section>

    <Teleport to="body">
      <Transition name="toast">
        <div v-if="toast" class="copy-toast" role="status" aria-live="polite">
          {{ toast }}
        </div>
      </Transition>
    </Teleport>
  </main>
</template>

<style scoped>
.page {
  padding: 2rem 0 2.5rem;
  display: grid;
  gap: 0.85rem;
  max-width: 720px;
}
.panel-box {
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 1.05rem 1.1rem;
  background: rgba(255, 255, 255, 0.62);
  display: grid;
  gap: 0.8rem;
}
.panel-head .back {
  display: inline-block;
  margin-bottom: 0.45rem;
  color: var(--moss-deep);
  text-decoration: none;
  font: inherit;
}
.panel-head .back:hover {
  text-decoration: underline;
}
.panel-head h2,
.list-title {
  margin: 0;
  font-family: var(--font-display);
  font-weight: 500;
  font-size: 1.4rem;
}
.panel-head p {
  margin: 0.35rem 0 0;
  color: rgba(20, 32, 27, 0.62);
  line-height: 1.5;
  font-size: 0.92rem;
}
.quota {
  color: var(--moss-deep) !important;
}
.hint {
  margin: 0;
  font-size: 0.85rem;
  color: rgba(20, 32, 27, 0.5);
}
.ok {
  margin: 0;
  color: var(--moss-deep);
}
.error {
  margin: 0;
  color: var(--danger);
}
.code {
  font-family: var(--font-display);
  font-size: 1.35rem;
  margin: 0;
}
textarea {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 0.65rem 0.75rem;
  resize: vertical;
  background: #fff;
  box-sizing: border-box;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}
ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.65rem;
}
li {
  display: grid;
  gap: 0.4rem;
  padding: 0.65rem 0;
  border-top: 1px solid var(--line);
}
li:first-child {
  border-top: 0;
  padding-top: 0;
}
li > div:first-child {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  font-size: 0.88rem;
  color: rgba(20, 32, 27, 0.65);
}
.empty {
  color: rgba(20, 32, 27, 0.45);
  border: 0;
}
.copy-toast {
  position: fixed;
  left: 50%;
  bottom: calc(1.35rem + var(--tabbar-h, 0px) + env(safe-area-inset-bottom, 0px));
  z-index: 100;
  transform: translateX(-50%);
  max-width: min(22rem, calc(100vw - 2rem));
  padding: 0.7rem 1.15rem;
  border-radius: 999px;
  background: rgba(20, 32, 27, 0.92);
  color: #f4f7f5;
  font-size: 0.92rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  text-align: center;
  pointer-events: none;
}
.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(0.45rem);
}
</style>
