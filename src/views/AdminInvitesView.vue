<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import api from '../api/client'
import { useI18n } from '../i18n'
import { formatApiError } from '../utils/apiError'
import { useAuthStore } from '../stores/auth'
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
}

const auth = useAuthStore()
const router = useRouter()
const { t } = useI18n()

const invites = ref<Invite[]>([])
const created = ref<Invite[]>([])
const count = ref(10)
const maxUses = ref(1)
const note = ref('')
const expiresDays = ref(30)
const error = ref('')
const loading = ref(false)
const { toast, copyText } = useCopyToast()

async function load() {
  error.value = ''
  try {
    const { data } = await api.get<Invite[]>('/api/invites')
    invites.value = data
  } catch (e: unknown) {
    error.value = formatApiError(e, t('common.loadFail'))
  }
}

async function generate() {
  error.value = ''
  loading.value = true
  try {
    const { data } = await api.post<{ codes: Invite[] }>('/api/invites', {
      count: count.value,
      max_uses: maxUses.value,
      note: note.value,
      expires_days: expiresDays.value || null,
    })
    created.value = data.codes
    await load()
  } catch (e: unknown) {
    error.value = formatApiError(e, t('adminInvites.fail'))
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
    error.value = formatApiError(e, t('adminInvites.fail'))
  }
}

async function copy(text: string) {
  await copyText(text, t('invite.copiedCode'), t('invite.copyFailed'))
}

onMounted(async () => {
  if (!auth.isAdmin) {
    router.replace('/')
    return
  }
  await load()
})
</script>

<template>
  <main class="container page">
    <section class="panel-box">
      <header class="panel-head">
        <RouterLink class="back" to="/admin">← {{ t('admin.backMenu') }}</RouterLink>
        <h2>{{ t('adminInvites.title') }}</h2>
        <p>{{ t('adminInvites.desc') }}</p>
      </header>

      <form class="composer" @submit.prevent="generate">
        <div class="row">
          <div class="field">
            <label>{{ t('adminInvites.count') }}</label>
            <input v-model.number="count" type="number" min="1" max="100" />
          </div>
          <div class="field">
            <label>{{ t('adminInvites.maxUses') }}</label>
            <input v-model.number="maxUses" type="number" min="1" max="1000" />
          </div>
          <div class="field">
            <label>{{ t('adminInvites.expires') }}</label>
            <input v-model.number="expiresDays" type="number" min="1" max="365" />
          </div>
        </div>
        <div class="field">
          <label>{{ t('invite.note') }}</label>
          <input v-model="note" maxlength="200" :placeholder="t('adminInvites.notePh')" />
        </div>
        <p v-if="error" class="error">{{ error }}</p>
        <button class="btn primary" type="submit" :disabled="loading">
          {{ loading ? t('adminInvites.generating') : t('adminInvites.generate') }}
        </button>
      </form>
    </section>

    <section v-if="created.length" class="panel-box">
      <h2 class="list-title">{{ t('adminInvites.fresh') }}</h2>
      <ul class="code-list">
        <li v-for="item in created" :key="item.id">
          <code>{{ item.code }}</code>
          <button type="button" class="btn ghost" @click="copy(item.code)">
            {{ t('invite.copyCode') }}
          </button>
        </li>
      </ul>
    </section>

    <section class="panel-box">
      <h2 class="list-title">{{ t('adminInvites.all') }}</h2>
      <table>
        <thead>
          <tr>
            <th>{{ t('adminInvites.colCode') }}</th>
            <th>{{ t('adminInvites.colUsage') }}</th>
            <th>{{ t('adminInvites.colRemain') }}</th>
            <th>{{ t('adminInvites.colStatus') }}</th>
            <th>{{ t('adminInvites.colNote') }}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in invites" :key="item.id">
            <td>
              <code>{{ item.code }}</code>
              <button type="button" class="mini" @click="copy(item.code)">
                {{ t('invite.copyCode') }}
              </button>
            </td>
            <td>{{ item.use_count }}/{{ item.max_uses }}</td>
            <td>{{ item.remaining }}</td>
            <td>{{ item.is_active ? t('invite.active') : t('invite.revoked') }}</td>
            <td>{{ item.note || '—' }}</td>
            <td>
              <button
                v-if="item.is_active"
                type="button"
                class="btn danger"
                @click="revoke(item.id)"
              >
                {{ t('invite.revoke') }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
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
.composer {
  display: grid;
  gap: 0.75rem;
}
.row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.75rem;
}
.code-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.45rem;
}
.code-list li {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}
code {
  font-size: 0.95rem;
  padding: 0.2rem 0.45rem;
  border-radius: 6px;
  background: rgba(47, 111, 94, 0.1);
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.92rem;
}
th,
td {
  text-align: left;
  padding: 0.55rem 0.35rem;
  border-bottom: 1px solid var(--line);
  vertical-align: middle;
}
.mini {
  margin-left: 0.35rem;
  border: 0;
  background: transparent;
  color: var(--moss-deep);
  cursor: pointer;
}
.btn.danger {
  background: transparent;
  border: 1px solid rgba(181, 74, 58, 0.35);
  color: var(--danger);
  padding: 0.35rem 0.7rem;
}
.error {
  color: var(--danger);
  margin: 0;
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
@media (max-width: 800px) {
  .row {
    grid-template-columns: 1fr;
  }
  table {
    display: block;
    overflow-x: auto;
  }
}
</style>
