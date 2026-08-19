<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api/client'
import { useI18n } from '../i18n'
import { useAuthStore } from '../stores/auth'
import { formatDateShanghai, parseApiDate } from '../utils/time'
import { avatarSrc, compressImageFile } from '../utils/compressImage'
import { formatApiError } from '../utils/apiError'
import { useCopyToast } from '../composables/useCopyToast'

interface AdminUser {
  id: number
  nickname: string
  email: string | null
  role: string
  is_active: boolean
  is_muted: boolean
  muted_until: string | null
  mute_reason: string
  mute_remaining_days: number | null
  created_at: string | null
  last_login_at: string | null
  avatar_url?: string | null
  bio: string
  bot_preset?: string
  bot_rounds_limit?: number
  bot_rounds_used?: number
  bot_rounds_remaining?: number
  bot_msgs_per_round?: number
  bot_msgs_this_round?: number
  bot_msgs_remaining?: number
  is_bot?: boolean
}

interface AdminUserDetail extends AdminUser {
  registered_invite_code: string
  inviter_nickname: string | null
  inviter_id: number | null
  message_count: number
  password_note: string
  previous_email?: string | null
  previous_nickname?: string | null
}

interface AdminThread {
  thread_id: number
  peer_id: number
  peer_nickname: string
  peer_active: boolean
  message_count: number
  hidden_count: number
  status: string
}

interface BotDoc {
  name: string
  content: string
}

interface BotAdminState {
  id: number
  nickname: string
  bio: string
  avatar_url: string | null
  system_prompt: string
  docs: BotDoc[]
}

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const { t } = useI18n()
const users = ref<AdminUser[]>([])
const detail = ref<AdminUserDetail | null>(null)
const tip = ref('')
const error = ref('')
const { toast, showToast, copyText } = useCopyToast()

const notifyTitleEl = ref<HTMLInputElement | null>(null)
const loadingDetail = ref(false)

const muteReason = ref('content_violation')
const muteDetail = ref('')
const muteHours = ref<string>('24')
const muteModalOpen = ref(false)
const muteBusy = ref(false)

const notifyChannel = ref<'email' | 'inApp'>('email')
const notifyTarget = ref<'all' | string>('')
const notifyTitle = ref('')
const notifyBody = ref('')
const notifyBusy = ref(false)
const notifyAlsoInApp = ref(true)

const restoreEmail = ref('')
const restoreNickname = ref('')
const restorePassword = ref('')
const restoreBusy = ref(false)
const userThreads = ref<AdminThread[]>([])
const restoreChatBusyId = ref<number | null>(null)

const homeLeads = ref<Record<string, string>>({
  'zh-CN': '',
  'zh-TW': '',
  en: '',
  ja: '',
})
const homeLeadBusy = ref(false)
const homeLeadDirty = ref(false)
const homeLeadTab = ref<'zh-CN' | 'zh-TW' | 'en' | 'ja'>('zh-CN')

const homeLeadTabs: { code: 'zh-CN' | 'zh-TW' | 'en' | 'ja'; label: string }[] = [
  { code: 'zh-CN', label: '简体' },
  { code: 'zh-TW', label: '繁中' },
  { code: 'en', label: 'EN' },
  { code: 'ja', label: '日本語' },
]

interface BatchInvite {
  id: number
  code: string
  max_uses: number
  use_count: number
  note: string
  is_active: boolean
  remaining: number
}
interface MyInvite {
  id: number
  code: string
  max_uses: number
  use_count: number
  is_active: boolean
  created_at: string
  invite_url: string
  share_text: string
}
interface InviteQuota {
  used: number
  limit: number
  remaining: number
  unlock_30_in_days: number
}

const batchInvites = ref<BatchInvite[]>([])
const batchCreated = ref<BatchInvite[]>([])
const batchCount = ref(10)
const batchMaxUses = ref(1)
const batchNote = ref('')
const batchExpiresDays = ref(30)
const batchBusy = ref(false)

const myInvites = ref<MyInvite[]>([])
const myQuota = ref<InviteQuota | null>(null)
const myLatest = ref<MyInvite | null>(null)
const myBusy = ref(false)

const botState = ref<BotAdminState | null>(null)
const botNick = ref('')
const botBio = ref('')
const botPrompt = ref('')
const botAppendText = ref('')
const botBusy = ref(false)
const botAvatarBusy = ref(false)
const botDocBusy = ref(false)
const botPresetDraft = ref('normal')
const botPermBusy = ref(false)

const botPresets = [
  { value: 'normal', key: 'admin.botPresetNormal' },
  { value: 'limited', key: 'admin.botPresetLimited' },
  { value: 'none', key: 'admin.botPresetNone' },
]

type AdminPanel = 'menu' | 'homeLead' | 'notify' | 'users' | 'batchInvites' | 'myInvites' | 'zeejBot'
const panel = ref<AdminPanel>('menu')

const origin = computed(() => (typeof window !== 'undefined' ? window.location.origin : ''))

const activeRecipients = computed(() =>
  users.value.filter((u) => u.is_active && u.role !== 'admin'),
)
const emailRecipients = computed(() =>
  activeRecipients.value.filter((u) => !u.is_bot && Boolean(u.email)),
)
const selectedNotifyUser = computed(() =>
  activeRecipients.value.find((u) => String(u.id) === notifyTarget.value) || null,
)
const notifyBodyLimit = computed(() => (notifyChannel.value === 'email' ? 5000 : 500))

function setNotifyChannel(channel: 'email' | 'inApp') {
  notifyChannel.value = channel
  notifyTarget.value = channel === 'email' ? '' : 'all'
  error.value = ''
  tip.value = ''
}

const reasons = [
  { value: 'content_violation', key: 'admin.reasonContent' },
  { value: 'spam', key: 'admin.reasonSpam' },
  { value: 'harassment', key: 'admin.reasonHarassment' },
  { value: 'other', key: 'admin.reasonOther' },
]

const durations = [
  { value: '1', key: 'admin.dur1h' },
  { value: '24', key: 'admin.dur1d' },
  { value: '168', key: 'admin.dur7d' },
  { value: '720', key: 'admin.dur30d' },
  { value: 'perm', key: 'admin.durPerm' },
]

function shanghaiParts(d: Date) {
  const fmt = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
  })
  const bag: Record<string, string> = {}
  for (const p of fmt.formatToParts(d)) {
    if (p.type !== 'literal') bag[p.type] = p.value
  }
  return {
    year: Number(bag.year),
    month: Number(bag.month),
    day: Number(bag.day),
  }
}

function releaseDateText(d: Date | null, permanent = false) {
  if (permanent || !d) return t('admin.releasePerm')
  const p = shanghaiParts(d)
  return t('admin.releaseOn', { year: p.year, month: p.month, day: p.day })
}

function remainingDaysFrom(until: Date | null, permanent = false) {
  if (permanent) return null
  if (!until) return 0
  const now = Date.now()
  const ms = until.getTime() - now
  if (ms <= 0) return 0
  return Math.max(1, Math.ceil(ms / 86400000))
}

function computeUntilDate(extendFromMuted: boolean): { until: Date | null; permanent: boolean } {
  if (!detail.value) return { until: null, permanent: false }
  const hours = muteHours.value === 'perm' ? null : Number(muteHours.value)
  const now = new Date()
  const base =
    extendFromMuted && detail.value.muted_until
      ? parseApiDate(detail.value.muted_until) || now
      : now
  if (hours == null || !Number.isFinite(hours) || hours <= 0) {
    return { until: null, permanent: true }
  }
  return { until: new Date(base.getTime() + hours * 3600 * 1000), permanent: false }
}

const modalPreview = computed(() => {
  if (!detail.value || !muteModalOpen.value) {
    return { remaining: '', release: '' }
  }
  const extending = detail.value.is_muted
  const { until, permanent } = computeUntilDate(extending)
  if (permanent) {
    return {
      remaining: t('admin.remainingPerm'),
      release: t('admin.releasePerm'),
    }
  }
  const days = remainingDaysFrom(until, false)
  return {
    remaining: t('admin.remainingDays', { days: days ?? 0 }),
    release: releaseDateText(until, false),
  }
})

function openMuteModal() {
  muteReason.value = 'content_violation'
  muteDetail.value = ''
  muteHours.value = '24'
  muteModalOpen.value = true
}

function closeMuteModal() {
  muteModalOpen.value = false
}

async function load() {
  const { data } = await api.get<AdminUser[]>('/api/admin/users')
  users.value = data
}

async function loadSite() {
  try {
    const { data } = await api.get<{ home_lead: string; home_leads?: Record<string, string> }>(
      '/api/admin/site',
    )
    const leads = data.home_leads || {
      'zh-CN': data.home_lead || '',
      'zh-TW': '',
      en: '',
      ja: '',
    }
    homeLeads.value = {
      'zh-CN': leads['zh-CN'] || '',
      'zh-TW': leads['zh-TW'] || '',
      en: leads.en || '',
      ja: leads.ja || '',
    }
    homeLeadDirty.value = false
  } catch (e: unknown) {
    error.value = formatApiError(e, t('admin.loadFail'))
  }
}

function openPanel(next: AdminPanel) {
  tip.value = ''
  error.value = ''
  detail.value = null
  muteModalOpen.value = false
  panel.value = next
  if (next === 'homeLead') void loadSite()
  if (next === 'users' || next === 'notify') void load()
  if (next === 'batchInvites') void loadBatchInvites()
  if (next === 'myInvites') void loadMyInvites()
  if (next === 'zeejBot') void loadBotAdmin()
}

function backToMenu() {
  if (
    notifyBusy.value ||
    homeLeadBusy.value ||
    batchBusy.value ||
    myBusy.value ||
    botBusy.value ||
    botAvatarBusy.value ||
    botDocBusy.value
  ) {
    return
  }
  tip.value = ''
  error.value = ''
  detail.value = null
  muteModalOpen.value = false
  panel.value = 'menu'
}

async function loadBotAdmin() {
  error.value = ''
  try {
    const { data } = await api.get<BotAdminState>('/api/admin/bot')
    botState.value = data
    botNick.value = data.nickname || ''
    botBio.value = data.bio || ''
    botPrompt.value = data.system_prompt || ''
    botAppendText.value = ''
  } catch (e: unknown) {
    error.value = formatApiError(e, t('admin.loadFail'))
  }
}

async function saveBotProfile() {
  error.value = ''
  tip.value = ''
  botBusy.value = true
  try {
    await api.put('/api/admin/bot/profile', {
      nickname: botNick.value.trim(),
      bio: botBio.value.trim(),
    })
    tip.value = t('admin.botProfileOk')
    await loadBotAdmin()
  } catch (e: unknown) {
    error.value = formatApiError(e, t('admin.botSaveFail'))
  } finally {
    botBusy.value = false
  }
}

async function onBotAvatar(ev: Event) {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  error.value = ''
  tip.value = ''
  botAvatarBusy.value = true
  try {
    const blob = await compressImageFile(file)
    const form = new FormData()
    form.append('file', blob, 'avatar.jpg')
    await api.post('/api/admin/bot/avatar', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    tip.value = t('admin.botAvatarOk')
    await loadBotAdmin()
  } catch (e: unknown) {
    error.value = formatApiError(e, t('admin.botAvatarFail'))
  } finally {
    botAvatarBusy.value = false
  }
}

async function saveBotPrompt(mode: 'replace' | 'append') {
  error.value = ''
  tip.value = ''
  const text = mode === 'append' ? botAppendText.value.trim() : botPrompt.value.trim()
  if (!text) {
    error.value = t('admin.botPromptEmpty')
    return
  }
  botBusy.value = true
  try {
    await api.put('/api/admin/bot/prompt', { system_prompt: text, mode })
    tip.value = mode === 'append' ? t('admin.botPromptAppendOk') : t('admin.botPromptOk')
    botAppendText.value = ''
    await loadBotAdmin()
  } catch (e: unknown) {
    error.value = formatApiError(e, t('admin.botSaveFail'))
  } finally {
    botBusy.value = false
  }
}

async function onBotDocFile(ev: Event) {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  error.value = ''
  tip.value = ''
  botDocBusy.value = true
  try {
    const content = await file.text()
    if (!content.trim()) {
      error.value = t('admin.botDocEmpty')
      return
    }
    await api.post('/api/admin/bot/docs', {
      name: file.name || 'notes.txt',
      content,
    })
    tip.value = t('admin.botDocOk')
    await loadBotAdmin()
  } catch (e: unknown) {
    error.value = formatApiError(e, t('admin.botSaveFail'))
  } finally {
    botDocBusy.value = false
  }
}

async function removeBotDoc(index: number) {
  if (!confirm(t('admin.botDocRemoveConfirm'))) return
  error.value = ''
  tip.value = ''
  botDocBusy.value = true
  try {
    await api.delete(`/api/admin/bot/docs/${index}`)
    tip.value = t('admin.botDocRemoved')
    await loadBotAdmin()
  } catch (e: unknown) {
    error.value = formatApiError(e, t('admin.botSaveFail'))
  } finally {
    botDocBusy.value = false
  }
}

async function saveUserBotPermission() {
  if (!detail.value || detail.value.is_bot || detail.value.role === 'admin') return
  error.value = ''
  tip.value = ''
  botPermBusy.value = true
  try {
    const { data } = await api.post<{ detail: string }>(
      `/api/admin/users/${detail.value.id}/bot-permission`,
      { preset: botPresetDraft.value },
    )
    tip.value = data.detail || t('admin.botPermOk')
    await openUserKeepTip(detail.value.id)
    await load()
  } catch (e: unknown) {
    error.value = formatApiError(e, t('admin.botPermFail'))
  } finally {
    botPermBusy.value = false
  }
}

function botQuotaLabel(u: AdminUser) {
  if (u.is_bot) return t('admin.botAccount')
  const preset = u.bot_preset || 'normal'
  if (preset === 'none') return t('admin.botPresetNone')
  if (preset === 'limited') return t('admin.botPresetLimited')
  return t('admin.botPresetNormal')
}

function withInviteOrigin(inv: { code: string } & Partial<MyInvite>): MyInvite {
  const path = `/register?invite=${encodeURIComponent(inv.code)}`
  const url = `${origin.value}${path}`
  return {
    id: inv.id || 0,
    code: inv.code,
    max_uses: inv.max_uses || 1,
    use_count: inv.use_count || 0,
    is_active: inv.is_active ?? true,
    created_at: inv.created_at || '',
    invite_url: url,
    share_text: t('invite.shareBody', { url, code: inv.code }),
  }
}

async function loadBatchInvites() {
  error.value = ''
  try {
    const { data } = await api.get<BatchInvite[]>('/api/invites')
    batchInvites.value = data
  } catch (e: unknown) {
    error.value = formatApiError(e, t('common.loadFail'))
  }
}

async function generateBatchInvites() {
  error.value = ''
  tip.value = ''
  batchBusy.value = true
  try {
    const { data } = await api.post<{ codes: BatchInvite[] }>('/api/invites', {
      count: batchCount.value,
      max_uses: batchMaxUses.value,
      note: batchNote.value,
      expires_days: batchExpiresDays.value || null,
    })
    batchCreated.value = data.codes
    tip.value = t('adminInvites.fresh')
    await loadBatchInvites()
  } catch (e: unknown) {
    error.value = formatApiError(e, t('adminInvites.fail'))
  } finally {
    batchBusy.value = false
  }
}

async function revokeBatchInvite(id: number) {
  if (!confirm(t('invite.revokeConfirm'))) return
  error.value = ''
  try {
    await api.post(`/api/invites/${id}/revoke`)
    await loadBatchInvites()
  } catch (e: unknown) {
    error.value = formatApiError(e, t('adminInvites.fail'))
  }
}

async function loadMyInvites() {
  error.value = ''
  try {
    const [q, list] = await Promise.all([
      api.get<InviteQuota>('/api/invites/quota'),
      api.get<MyInvite[]>('/api/invites/mine'),
    ])
    myQuota.value = q.data
    myInvites.value = list.data.map((inv) => withInviteOrigin(inv))
  } catch (e: unknown) {
    error.value = formatApiError(e, t('invite.fail'))
  }
}

async function createMyInvite() {
  error.value = ''
  tip.value = ''
  myBusy.value = true
  try {
    const { data } = await api.post<MyInvite>('/api/invites/one', { expires_days: 30 })
    myLatest.value = withInviteOrigin(data)
    tip.value = t('invite.created')
    await loadMyInvites()
  } catch (e: unknown) {
    error.value = formatApiError(e, t('invite.fail'))
  } finally {
    myBusy.value = false
  }
}

async function revokeMyInvite(id: number) {
  if (!confirm(t('invite.revokeConfirm'))) return
  error.value = ''
  try {
    await api.post(`/api/invites/${id}/revoke`)
    await loadMyInvites()
  } catch (e: unknown) {
    error.value = formatApiError(e, t('invite.fail'))
  }
}

async function copyInvite(text: string, kind: 'msg' | 'link' | 'code' = 'code') {
  const ok =
    kind === 'msg'
      ? t('invite.copiedMsg')
      : kind === 'link'
        ? t('invite.copiedLink')
        : t('invite.copiedCode')
  await copyText(text, ok, t('invite.copyFailed'))
}

async function saveHomeLead() {
  error.value = ''
  tip.value = ''
  homeLeadBusy.value = true
  try {
    const { data } = await api.put<{ home_lead: string; home_leads: Record<string, string> }>(
      '/api/admin/site',
      { home_leads: { ...homeLeads.value } },
    )
    const leads = data.home_leads || homeLeads.value
    homeLeads.value = {
      'zh-CN': leads['zh-CN'] || '',
      'zh-TW': leads['zh-TW'] || '',
      en: leads.en || '',
      ja: leads.ja || '',
    }
    homeLeadDirty.value = false
    tip.value = t('admin.homeLeadOk')
  } catch (e: unknown) {
    error.value = formatApiError(e, t('admin.homeLeadFail'))
  } finally {
    homeLeadBusy.value = false
  }
}

async function openUser(id: number) {
  tip.value = ''
  error.value = ''
  muteModalOpen.value = false
  loadingDetail.value = true
  userThreads.value = []
  try {
    const { data } = await api.get<AdminUserDetail>(`/api/admin/users/${id}`)
    detail.value = data
    botPresetDraft.value = data.bot_preset || 'normal'
    fillRestoreDraft(data)
    panel.value = 'users'
    await loadUserThreads(id)
  } catch (e: unknown) {
    error.value = formatApiError(e, t('admin.loadFail'))
    detail.value = null
  } finally {
    loadingDetail.value = false
  }
}

async function openUserKeepTip(id: number) {
  error.value = ''
  muteModalOpen.value = false
  loadingDetail.value = true
  try {
    const { data } = await api.get<AdminUserDetail>(`/api/admin/users/${id}`)
    detail.value = data
    botPresetDraft.value = data.bot_preset || 'normal'
    fillRestoreDraft(data)
    panel.value = 'users'
    await loadUserThreads(id)
  } catch (e: unknown) {
    error.value = formatApiError(e, t('admin.loadFail'))
    detail.value = null
  } finally {
    loadingDetail.value = false
  }
}

function closeDetail() {
  muteModalOpen.value = false
  detail.value = null
  userThreads.value = []
  panel.value = 'users'
}

async function confirmMuteModal() {
  if (!detail.value) return
  const id = detail.value.id
  error.value = ''
  muteBusy.value = true
  try {
    const { data } = await api.post<{ detail: string }>(`/api/admin/users/${id}/mute`, {
      reason: muteReason.value,
      reason_detail: muteDetail.value,
      duration_hours: muteHours.value === 'perm' ? null : Number(muteHours.value),
    })
    tip.value = data.detail || t('admin.mutedOk')
    muteModalOpen.value = false
    await load()
    await openUserKeepTip(id)
  } catch (e: any) {
    error.value = formatApiError(e, t('admin.opFail'))
  } finally {
    muteBusy.value = false
  }
}

async function unmute() {
  if (!detail.value) return
  const id = detail.value.id
  error.value = ''
  try {
    await api.post(`/api/admin/users/${id}/unmute`)
    tip.value = t('admin.unmutedOk')
    await load()
    await openUserKeepTip(id)
  } catch (e: unknown) {
    error.value = formatApiError(e, t('admin.opFail'))
  }
}

async function removeUser() {
  if (!detail.value) return
  if (!confirm(t('admin.deleteConfirm', { name: detail.value.nickname }))) return
  error.value = ''
  try {
    await api.delete(`/api/admin/users/${detail.value.id}`)
    tip.value = t('admin.deletedOk')
    detail.value = null
    panel.value = 'users'
    await load()
  } catch (e: unknown) {
    error.value = formatApiError(e, t('admin.opFail'))
  }
}

async function loadUserThreads(userId: number) {
  try {
    const { data } = await api.get<AdminThread[]>(`/api/admin/users/${userId}/threads`)
    userThreads.value = data
  } catch {
    userThreads.value = []
  }
}

function fillRestoreDraft(d: AdminUserDetail) {
  restoreEmail.value = d.previous_email || ''
  restoreNickname.value = d.previous_nickname || ''
  restorePassword.value = ''
}

async function restoreUser() {
  if (!detail.value) return
  const id = detail.value.id
  error.value = ''
  if (!restorePassword.value || restorePassword.value.length < 6) {
    error.value = t('admin.restorePwdNeed')
    return
  }
  if (!confirm(t('admin.restoreConfirm', { name: detail.value.nickname }))) return
  restoreBusy.value = true
  try {
    const { data } = await api.post<{ detail: string }>(`/api/admin/users/${id}/restore`, {
      email: restoreEmail.value.trim() || undefined,
      nickname: restoreNickname.value.trim() || undefined,
      password: restorePassword.value,
    })
    tip.value = data.detail || t('admin.restoredOk')
    restorePassword.value = ''
    await load()
    await openUserKeepTip(id)
  } catch (e: unknown) {
    error.value = formatApiError(e, t('admin.opFail'))
  } finally {
    restoreBusy.value = false
  }
}

async function restoreChatWithPeer(peerId: number) {
  if (!detail.value) return
  const peer = userThreads.value.find((x) => x.peer_id === peerId)
  const label = peer?.peer_nickname || String(peerId)
  if (
    !confirm(
      t('admin.restoreChatConfirm', {
        a: detail.value.nickname,
        b: label,
      }),
    )
  ) {
    return
  }
  error.value = ''
  restoreChatBusyId.value = peerId
  try {
    const { data } = await api.post<{ detail: string; restored: number }>(
      '/api/admin/chat/restore-messages',
      { user_a_id: detail.value.id, user_b_id: peerId },
    )
    tip.value = data.detail || t('admin.restoreChatOk', { n: data.restored })
    await loadUserThreads(detail.value.id)
  } catch (e: unknown) {
    error.value = formatApiError(e, t('admin.opFail'))
  } finally {
    restoreChatBusyId.value = null
  }
}

async function exportMessages() {
  if (!detail.value) return
  try {
    const res = await api.get(`/api/admin/users/${detail.value.id}/messages/export`, {
      responseType: 'blob',
    })
    const blob = new Blob([res.data], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `messages-${detail.value.id}-${detail.value.nickname}.txt`
    a.click()
    URL.revokeObjectURL(url)
    tip.value = t('admin.exported')
  } catch (e: any) {
    error.value = formatApiError(e, t('admin.exportFail'))
  }
}

async function sendNotify() {
  const title = notifyTitle.value.trim()
  const content = notifyBody.value.trim()
  if (!title) {
    error.value = t('admin.notifyNeedTitle')
    tip.value = ''
    notifyTitleEl.value?.focus()
    return
  }
  if (!content) {
    error.value = t('admin.notifyNeedBody')
    tip.value = ''
    return
  }
  if (notifyChannel.value === 'email' && !selectedNotifyUser.value) {
    error.value = t('admin.emailNeedTarget')
    tip.value = ''
    return
  }
  error.value = ''
  tip.value = ''
  notifyBusy.value = true
  try {
    if (notifyChannel.value === 'email') {
      const { data } = await api.post<{ detail: string }>('/api/admin/email-notifications', {
        user_id: Number(notifyTarget.value),
        subject: title,
        content,
        also_in_app: notifyAlsoInApp.value,
      })
      const ok = data.detail || t('admin.emailOk')
      tip.value = ok
      showToast(ok)
      notifyTitle.value = ''
      notifyBody.value = ''
      notifyTarget.value = ''
      return
    }
    const payload: { title: string; content: string; user_id?: number } = {
      title,
      content,
    }
    if (notifyTarget.value !== 'all') {
      payload.user_id = Number(notifyTarget.value)
    }
    const { data } = await api.post<{ detail: string }>('/api/admin/notifications', payload)
    const ok = data.detail || t('admin.notifyOk')
    tip.value = ok
    showToast(ok)
    notifyTitle.value = ''
    notifyBody.value = ''
    notifyTarget.value = 'all'
  } catch (e: unknown) {
    error.value = formatApiError(
      e,
      notifyChannel.value === 'email' ? t('admin.emailFail') : t('admin.notifyFail'),
    )
  } finally {
    notifyBusy.value = false
  }
}

function muteLabel(u: AdminUser) {
  if (!u.is_muted) return ''
  const days = u.mute_remaining_days
  const reason = u.mute_reason || t('admin.muted')
  if (days == null) return reason
  if (days >= 3000) return `${reason}（${t('admin.remainingPerm')}）`
  return `${reason}（${t('admin.remainingDays', { days })}）`
}

function currentReleaseText(u: AdminUser) {
  if (!u.is_muted || !u.muted_until) return ''
  const days = u.mute_remaining_days
  if (days != null && days >= 3000) return t('admin.releasePerm')
  const d = parseApiDate(u.muted_until)
  return d ? releaseDateText(d, false) : ''
}

onMounted(async () => {
  if (!auth.isAdmin) {
    router.replace('/')
    return
  }
  await Promise.all([load(), loadSite()])
  const q = String(route.query.panel || '')
  if (
    q === 'homeLead' ||
    q === 'notify' ||
    q === 'users' ||
    q === 'batchInvites' ||
    q === 'myInvites' ||
    q === 'zeejBot'
  ) {
    openPanel(q)
  }
})
</script>

<template>
  <main class="container page">
    <header class="head">
      <div>
        <h1>{{ t('admin.title') }}</h1>
        <p>{{ t('admin.desc') }}</p>
      </div>
    </header>

    <p v-if="tip && panel !== 'notify' && panel !== 'myInvites'" class="ok">{{ tip }}</p>
    <p
      v-if="
        error &&
        !detail &&
        panel !== 'notify' &&
        panel !== 'batchInvites' &&
        panel !== 'myInvites' &&
        panel !== 'zeejBot'
      "
      class="error"
    >
      {{ error }}
    </p>

    <!-- 功能目录 -->
    <nav v-if="panel === 'menu' && !detail" class="menu" aria-label="admin">
      <button type="button" class="menu-item" @click="openPanel('homeLead')">
        <span>
          <strong>{{ t('admin.homeLeadTitle') }}</strong>
          <em>{{ t('admin.menuHomeLeadHint') }}</em>
        </span>
        <span class="chev">→</span>
      </button>
      <button type="button" class="menu-item" @click="openPanel('notify')">
        <span>
          <strong>{{ t('admin.notifyTitle') }}</strong>
          <em>{{ t('admin.menuNotifyHint') }}</em>
        </span>
        <span class="chev">→</span>
      </button>
      <button type="button" class="menu-item" @click="openPanel('users')">
        <span>
          <strong>{{ t('admin.userList') }}</strong>
          <em>{{ t('admin.menuUsersHint') }}</em>
        </span>
        <span class="chev">→</span>
      </button>
      <button type="button" class="menu-item" @click="openPanel('zeejBot')">
        <span>
          <strong>{{ t('admin.botTitle') }}</strong>
          <em>{{ t('admin.menuBotHint') }}</em>
        </span>
        <span class="chev">→</span>
      </button>
      <button type="button" class="menu-item" @click="openPanel('batchInvites')">
        <span>
          <strong>{{ t('nav.adminInvites') }}</strong>
          <em>{{ t('admin.menuInvitesHint') }}</em>
        </span>
        <span class="chev">→</span>
      </button>
      <button type="button" class="menu-item" @click="openPanel('myInvites')">
        <span>
          <strong>{{ t('nav.myInvites') }}</strong>
          <em>{{ t('admin.menuMyInvitesHint') }}</em>
        </span>
        <span class="chev">→</span>
      </button>
    </nav>

    <!-- 主页导语 -->
    <section v-if="panel === 'homeLead' && !detail" class="panel-box">
      <header class="panel-head">
        <button type="button" class="back" @click="backToMenu">← {{ t('admin.backMenu') }}</button>
        <h2>{{ t('admin.homeLeadTitle') }}</h2>
        <p>{{ t('admin.homeLeadDesc') }}</p>
      </header>
      <div class="lead-tabs" role="tablist">
        <button
          v-for="tab in homeLeadTabs"
          :key="tab.code"
          type="button"
          role="tab"
          :class="{ on: homeLeadTab === tab.code }"
          @click="homeLeadTab = tab.code"
        >
          {{ tab.label }}
        </button>
      </div>
      <div class="field">
        <label>{{ t('admin.homeLeadLabel') }} · {{ homeLeadTab }}</label>
        <textarea
          v-model="homeLeads[homeLeadTab]"
          rows="6"
          maxlength="800"
          :placeholder="t('admin.homeLeadPh')"
          @input="homeLeadDirty = true"
        />
        <span class="count">{{ (homeLeads[homeLeadTab] || '').length }}/800</span>
      </div>
      <p class="hint">{{ t('admin.homeLeadI18nHint') }}</p>
      <button
        class="btn primary"
        type="button"
        :disabled="homeLeadBusy || !homeLeadDirty"
        @click="saveHomeLead"
      >
        {{ homeLeadBusy ? t('admin.homeLeadSaving') : t('admin.homeLeadSave') }}
      </button>
    </section>

    <!-- 发布通知 -->
    <section v-if="panel === 'notify' && !detail" class="panel-box">
      <header class="panel-head">
        <button type="button" class="back" @click="backToMenu">← {{ t('admin.backMenu') }}</button>
        <h2>{{ t('admin.notifyTitle') }}</h2>
        <p>{{ notifyChannel === 'email' ? t('admin.emailDesc') : t('admin.notifyDesc') }}</p>
      </header>
      <div class="notify-mode" role="tablist" :aria-label="t('admin.notifyChannel')">
        <button
          type="button"
          :class="{ on: notifyChannel === 'email' }"
          @click="setNotifyChannel('email')"
        >
          <span aria-hidden="true">✉</span> {{ t('admin.notifyModeEmail') }}
        </button>
        <button
          type="button"
          :class="{ on: notifyChannel === 'inApp' }"
          @click="setNotifyChannel('inApp')"
        >
          <span aria-hidden="true">●</span> {{ t('admin.notifyModeInApp') }}
        </button>
      </div>
      <div class="field">
        <label>{{ t('admin.notifyTarget') }}</label>
        <select v-model="notifyTarget">
          <option v-if="notifyChannel === 'email'" value="" disabled>{{ t('admin.emailChoose') }}</option>
          <option v-else value="all">{{ t('admin.notifyAll') }}</option>
          <option
            v-for="u in notifyChannel === 'email' ? emailRecipients : activeRecipients"
            :key="u.id"
            :value="String(u.id)"
          >
            {{ u.nickname }}{{ u.email ? ` · ${u.email}` : '' }}
          </option>
        </select>
      </div>
      <div v-if="notifyChannel === 'email' && selectedNotifyUser" class="recipient-card">
        <span class="recipient-avatar">{{ selectedNotifyUser.nickname.slice(0, 1).toUpperCase() }}</span>
        <span class="recipient-meta">
          <small>{{ t('admin.emailRecipient') }}</small>
          <strong>{{ selectedNotifyUser.nickname }}</strong>
          <em>{{ selectedNotifyUser.email }}</em>
        </span>
        <span class="recipient-ready" aria-hidden="true">✓</span>
      </div>
      <div class="field">
        <label>{{ t('admin.notifySubject') }}</label>
        <input
          ref="notifyTitleEl"
          v-model="notifyTitle"
          :maxlength="notifyChannel === 'email' ? 160 : 120"
          :placeholder="t('admin.notifySubjectPh')"
          @input="error = ''"
        />
      </div>
      <div class="field">
        <label>{{ t('admin.notifyBody') }}</label>
        <textarea
          v-model="notifyBody"
          rows="8"
          :maxlength="notifyBodyLimit"
          :placeholder="t('admin.notifyBodyPh')"
          @input="error = ''"
        />
        <span class="count">{{ notifyBody.length }}/{{ notifyBodyLimit }}</span>
      </div>
      <label v-if="notifyChannel === 'email'" class="check-row">
        <input v-model="notifyAlsoInApp" type="checkbox" />
        <span>
          <strong>{{ t('admin.emailAlsoInApp') }}</strong>
          <small>{{ t('admin.emailAlsoInAppHint') }}</small>
        </span>
      </label>
      <section v-if="notifyChannel === 'email'" class="mail-preview" aria-live="polite">
        <div class="mail-preview-label">{{ t('admin.emailPreview') }}</div>
        <div class="mail-preview-paper">
          <header>
            <small>A NOTE FROM ZEEJ</small>
            <h3>{{ notifyTitle || t('admin.notifySubjectPh') }}</h3>
          </header>
          <div class="mail-preview-body">
            <p>{{ t('admin.emailGreeting', { name: selectedNotifyUser?.nickname || '朋友' }) }}</p>
            <div class="mail-copy">{{ notifyBody || t('admin.notifyBodyPh') }}</div>
            <footer>{{ t('admin.emailFooter') }}<br /><b>zeej.me →</b></footer>
          </div>
        </div>
      </section>
      <p v-if="error" class="error panel-msg">{{ error }}</p>
      <p v-else-if="tip" class="ok panel-msg">{{ tip }}</p>
      <div class="panel-actions">
        <button
          class="btn primary"
          type="button"
          :disabled="notifyBusy"
          @click="sendNotify"
        >
          {{ notifyBusy
            ? (notifyChannel === 'email' ? t('admin.emailSending') : t('admin.notifySending'))
            : (notifyChannel === 'email' ? t('admin.emailSend') : t('admin.notifySend')) }}
        </button>
        <button class="btn ghost" type="button" :disabled="notifyBusy" @click="backToMenu">
          {{ t('admin.cancel') }}
        </button>
      </div>
    </section>

    <!-- 用户列表 -->
    <section v-if="panel === 'users' && !detail" class="panel-box">
      <header class="panel-head">
        <button type="button" class="back" @click="backToMenu">← {{ t('admin.backMenu') }}</button>
        <h2>{{ t('admin.userList') }}</h2>
        <p>{{ t('admin.menuUsersHint') }}</p>
      </header>
      <ul class="list">
        <li
          v-for="u in users"
          :key="u.id"
          class="card"
          role="button"
          tabindex="0"
          @click="openUser(u.id)"
          @keydown.enter="openUser(u.id)"
        >
          <div class="card-main">
            <strong>{{ u.nickname }}</strong>
            <span class="email">{{ u.email }}</span>
            <span class="role">{{ u.role }}</span>
            <span v-if="u.is_bot" class="role">Bot</span>
            <span v-else-if="!u.is_bot" class="role soft">{{ botQuotaLabel(u) }}</span>
            <span v-if="!u.is_active" class="bad">{{ t('admin.inactive') }}</span>
            <span v-else-if="u.is_muted" class="warn">{{ muteLabel(u) }}</span>
          </div>
          <span class="action">{{ t('admin.operate') }} →</span>
        </li>
        <li v-if="loadingDetail" class="empty">{{ t('admin.loading') }}</li>
        <li v-else-if="!users.length" class="empty">{{ t('admin.userEmpty') }}</li>
      </ul>
    </section>

    <!-- 批量邀请 -->
    <section v-if="panel === 'batchInvites' && !detail" class="panel-box">
      <header class="panel-head">
        <button type="button" class="back" @click="backToMenu">← {{ t('admin.backMenu') }}</button>
        <h2>{{ t('adminInvites.title') }}</h2>
        <p>{{ t('adminInvites.desc') }}</p>
      </header>
      <form class="invite-form" @submit.prevent="generateBatchInvites">
        <div class="invite-grid">
          <div class="field">
            <label>{{ t('adminInvites.count') }}</label>
            <input v-model.number="batchCount" type="number" min="1" max="100" />
          </div>
          <div class="field">
            <label>{{ t('adminInvites.maxUses') }}</label>
            <input v-model.number="batchMaxUses" type="number" min="1" max="1000" />
          </div>
          <div class="field">
            <label>{{ t('adminInvites.expires') }}</label>
            <input v-model.number="batchExpiresDays" type="number" min="1" max="365" />
          </div>
        </div>
        <div class="field">
          <label>{{ t('invite.note') }}</label>
          <input v-model="batchNote" maxlength="200" :placeholder="t('adminInvites.notePh')" />
        </div>
        <p v-if="error" class="error panel-msg">{{ error }}</p>
        <button class="btn primary" type="submit" :disabled="batchBusy">
          {{ batchBusy ? t('adminInvites.generating') : t('adminInvites.generate') }}
        </button>
      </form>
      <div v-if="batchCreated.length" class="invite-block">
        <h3>{{ t('adminInvites.fresh') }}</h3>
        <ul class="code-list">
          <li v-for="item in batchCreated" :key="item.id">
            <code>{{ item.code }}</code>
            <button type="button" class="btn ghost" @click="copyInvite(item.code)">
              {{ t('invite.copyCode') }}
            </button>
          </li>
        </ul>
      </div>
      <div class="invite-block">
        <h3>{{ t('adminInvites.all') }}</h3>
        <table class="invite-table">
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
            <tr v-for="item in batchInvites" :key="item.id">
              <td>
                <code>{{ item.code }}</code>
                <button type="button" class="mini" @click="copyInvite(item.code)">
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
                  @click="revokeBatchInvite(item.id)"
                >
                  {{ t('invite.revoke') }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- 我的邀请 -->
    <section v-if="panel === 'myInvites' && !detail" class="panel-box">
      <header class="panel-head">
        <button type="button" class="back" @click="backToMenu">← {{ t('admin.backMenu') }}</button>
        <h2>{{ t('invite.title') }}</h2>
        <p>{{ t('invite.desc') }}</p>
        <p v-if="myQuota" class="quota">
          {{
            t('invite.quota', {
              used: myQuota.used,
              limit: myQuota.limit,
              left: myQuota.remaining,
            })
          }}
          <span v-if="myQuota.unlock_30_in_days > 0">
            · {{ t('invite.unlockIn', { days: myQuota.unlock_30_in_days }) }}
          </span>
        </p>
      </header>
      <button
        class="btn primary"
        type="button"
        :disabled="myBusy || (myQuota !== null && myQuota.remaining <= 0)"
        @click="createMyInvite"
      >
        {{ t('invite.generateOne') }}
      </button>
      <p class="hint">{{ t('invite.oneOnly') }}</p>
      <p v-if="error" class="error panel-msg">{{ error }}</p>
      <p v-else-if="tip" class="ok panel-msg">{{ tip }}</p>

      <div v-if="myLatest" class="invite-block">
        <h3>{{ t('invite.latest') }}</h3>
        <p class="invite-code">{{ myLatest.code }}</p>
        <textarea readonly rows="6" :value="myLatest.share_text" />
        <div class="panel-actions">
          <button class="btn primary" type="button" @click="copyInvite(myLatest!.share_text, 'msg')">
            {{ t('invite.copyMsg') }}
          </button>
          <button class="btn ghost" type="button" @click="copyInvite(myLatest!.invite_url, 'link')">
            {{ t('invite.copyLink') }}
          </button>
          <button class="btn ghost" type="button" @click="copyInvite(myLatest!.code, 'code')">
            {{ t('invite.copyCode') }}
          </button>
        </div>
      </div>

      <div class="invite-block">
        <h3>{{ t('invite.mine') }}</h3>
        <ul class="my-invite-list">
          <li v-for="inv in myInvites" :key="inv.id">
            <div class="meta">
              <strong>{{ inv.code }}</strong>
              <span>{{ formatDateShanghai(inv.created_at, 'datetime') }}</span>
              <span>{{ inv.is_active ? t('invite.active') : t('invite.revoked') }}</span>
              <span>{{ inv.use_count }}/{{ inv.max_uses }}</span>
            </div>
            <div class="panel-actions start">
              <button
                class="btn ghost"
                type="button"
                @click="copyInvite(withInviteOrigin(inv).share_text, 'msg')"
              >
                {{ t('invite.copyMsg') }}
              </button>
              <button
                v-if="inv.is_active"
                class="btn ghost"
                type="button"
                @click="revokeMyInvite(inv.id)"
              >
                {{ t('invite.revoke') }}
              </button>
            </div>
          </li>
          <li v-if="!myInvites.length" class="empty">{{ t('invite.empty') }}</li>
        </ul>
      </div>
    </section>

    <!-- 用户详情 / 操作用户 -->
    <section v-if="detail" class="detail">
      <header class="detail-head">
        <button type="button" class="back" @click="closeDetail">← {{ t('admin.backList') }}</button>
        <h2>{{ t('admin.operate') }} · {{ detail.nickname }}</h2>
      </header>

      <p v-if="error" class="error">{{ error }}</p>

      <div class="profile">
        <div class="avatar">
          <img v-if="avatarSrc(detail.avatar_url)" :src="avatarSrc(detail.avatar_url)!" alt="" />
          <span v-else>{{ detail.nickname.slice(0, 1) }}</span>
        </div>
        <dl class="facts">
          <div>
            <dt>{{ t('admin.fieldNick') }}</dt>
            <dd>{{ detail.nickname }}</dd>
          </div>
          <div>
            <dt>{{ t('admin.fieldEmail') }}</dt>
            <dd>{{ detail.email || '—' }}</dd>
          </div>
          <div>
            <dt>{{ t('admin.fieldPassword') }}</dt>
            <dd class="muted">{{ t('admin.passwordNote') }}</dd>
          </div>
          <div>
            <dt>{{ t('admin.fieldRole') }}</dt>
            <dd>{{ detail.role }}</dd>
          </div>
          <div>
            <dt>{{ t('admin.fieldActive') }}</dt>
            <dd :class="{ bad: !detail.is_active }">
              {{ detail.is_active ? t('admin.active') : t('admin.inactive') }}
            </dd>
          </div>
          <div>
            <dt>{{ t('admin.fieldLogin') }}</dt>
            <dd>
              {{
                detail.last_login_at
                  ? formatDateShanghai(detail.last_login_at, 'datetime')
                  : t('admin.neverLogin')
              }}
            </dd>
          </div>
          <div>
            <dt>{{ t('admin.fieldJoined') }}</dt>
            <dd>
              {{
                detail.created_at ? formatDateShanghai(detail.created_at, 'datetime') : '—'
              }}
            </dd>
          </div>
          <div>
            <dt>{{ t('admin.fieldInvite') }}</dt>
            <dd>
              <template v-if="detail.registered_invite_code">
                {{ detail.registered_invite_code }}
                <span v-if="detail.inviter_nickname">
                  · {{ t('admin.invitedBy', { name: detail.inviter_nickname }) }}
                </span>
              </template>
              <template v-else>{{ t('admin.inviteUnknown') }}</template>
            </dd>
          </div>
          <div>
            <dt>{{ t('admin.fieldMute') }}</dt>
            <dd>
              <template v-if="detail.is_muted">
                <span class="warn">{{ muteLabel(detail) }}</span>
                <span v-if="currentReleaseText(detail)" class="until">
                  · {{ currentReleaseText(detail) }}
                </span>
              </template>
              <template v-else>{{ t('admin.notMuted') }}</template>
            </dd>
          </div>
          <div>
            <dt>{{ t('admin.fieldMsgs') }}</dt>
            <dd>{{ detail.message_count }}</dd>
          </div>
          <div v-if="!detail.is_bot">
            <dt>{{ t('admin.fieldBot') }}</dt>
            <dd>
              {{ botQuotaLabel(detail) }}
              <span class="muted">
                · {{ t('admin.botRemain', {
                  rounds: detail.bot_rounds_remaining ?? 0,
                  msgs: detail.bot_msgs_remaining ?? 0,
                }) }}
              </span>
            </dd>
          </div>
        </dl>
      </div>

      <div
        v-if="detail.role !== 'admin' && !detail.is_active && !detail.is_bot"
        class="ops restore-box"
      >
        <h3 class="ops-title">{{ t('admin.restoreTitle') }}</h3>
        <p class="hint">{{ t('admin.restoreHint') }}</p>
        <div class="field">
          <label>{{ t('admin.fieldEmail') }}</label>
          <input
            v-model="restoreEmail"
            type="email"
            maxlength="255"
            :placeholder="t('admin.restoreEmailPh')"
          />
        </div>
        <div class="field">
          <label>{{ t('admin.fieldNick') }}</label>
          <input
            v-model="restoreNickname"
            type="text"
            maxlength="30"
            :placeholder="t('admin.restoreNickPh')"
          />
        </div>
        <div class="field">
          <label>{{ t('admin.restorePwd') }}</label>
          <input
            v-model="restorePassword"
            type="text"
            maxlength="128"
            autocomplete="new-password"
            :placeholder="t('admin.restorePwdPh')"
          />
        </div>
        <button
          class="btn primary"
          type="button"
          :disabled="restoreBusy"
          @click="restoreUser"
        >
          {{ restoreBusy ? t('admin.restoring') : t('admin.restore') }}
        </button>
      </div>

      <div
        v-if="detail.role !== 'admin' && !detail.is_bot"
        class="ops restore-chat-box"
      >
        <h3 class="ops-title">{{ t('admin.restoreChatTitle') }}</h3>
        <p class="hint">{{ t('admin.restoreChatHint') }}</p>
        <ul v-if="userThreads.length" class="thread-restore-list">
          <li v-for="th in userThreads" :key="th.thread_id">
            <div class="thread-meta">
              <strong>{{ th.peer_nickname }}</strong>
              <span class="muted">
                {{ t('admin.restoreChatStats', { total: th.message_count, hidden: th.hidden_count }) }}
              </span>
              <span v-if="!th.peer_active" class="bad">{{ t('admin.inactive') }}</span>
            </div>
            <button
              class="btn ghost"
              type="button"
              :disabled="restoreChatBusyId === th.peer_id || th.hidden_count === 0"
              @click="restoreChatWithPeer(th.peer_id)"
            >
              {{
                restoreChatBusyId === th.peer_id
                  ? t('admin.restoringChat')
                  : th.hidden_count === 0
                    ? t('admin.restoreChatNone')
                    : t('admin.restoreChat')
              }}
            </button>
          </li>
        </ul>
        <p v-else class="hint">{{ t('admin.restoreChatEmpty') }}</p>
      </div>

      <div
        v-if="detail.role !== 'admin' && detail.is_active && !detail.is_bot"
        class="ops bot-perm"
      >
        <h3 class="ops-title">{{ t('admin.botPermTitle') }}</h3>
        <p class="hint">{{ t('admin.botPermHint') }}</p>
        <div class="field">
          <label>{{ t('admin.botPermLabel') }}</label>
          <select v-model="botPresetDraft">
            <option v-for="p in botPresets" :key="p.value" :value="p.value">
              {{ t(p.key) }}
            </option>
          </select>
        </div>
        <p v-if="error" class="error panel-msg">{{ error }}</p>
        <button
          class="btn primary"
          type="button"
          :disabled="botPermBusy"
          @click="saveUserBotPermission"
        >
          {{ botPermBusy ? t('admin.botPermSaving') : t('admin.botPermSave') }}
        </button>
      </div>

      <div v-if="detail.role !== 'admin' && detail.is_active && !detail.is_bot" class="ops">
        <div class="row">
          <button class="btn primary" type="button" @click="openMuteModal">
            {{ detail.is_muted ? t('admin.extendTitle') : t('admin.muteTitle') }}
          </button>
          <button v-if="detail.is_muted" class="btn ghost" type="button" @click="unmute">
            {{ t('admin.unmute') }}
          </button>
          <button class="btn ghost" type="button" @click="exportMessages">
            {{ t('admin.exportMsgs') }}
          </button>
          <button class="btn ghost danger" type="button" @click="removeUser">
            {{ t('admin.delete') }}
          </button>
        </div>
      </div>
      <div v-else class="ops">
        <button class="btn ghost" type="button" @click="exportMessages">
          {{ t('admin.exportMsgs') }}
        </button>
      </div>
    </section>

    <!-- Zeej Bot 管理 -->
    <section v-if="panel === 'zeejBot' && !detail" class="panel-box">
      <header class="panel-head">
        <button type="button" class="back" @click="backToMenu">← {{ t('admin.backMenu') }}</button>
        <h2>{{ t('admin.botTitle') }}</h2>
        <p>{{ t('admin.botDesc') }}</p>
      </header>

      <p v-if="error" class="error panel-msg">{{ error }}</p>

      <div class="bot-profile">
        <div class="avatar bot-av">
          <img
            v-if="avatarSrc(botState?.avatar_url)"
            :src="avatarSrc(botState?.avatar_url)!"
            alt=""
          />
        </div>
        <div class="bot-av-actions">
          <label class="btn ghost file-btn">
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              hidden
              :disabled="botAvatarBusy"
              @change="onBotAvatar"
            />
            {{ botAvatarBusy ? t('profile.avatarUploading') : t('admin.botAvatarUpload') }}
          </label>
        </div>
      </div>

      <div class="field">
        <label>{{ t('admin.botName') }}</label>
        <input v-model="botNick" maxlength="30" :placeholder="t('admin.botNamePh')" />
      </div>
      <div class="field">
        <label>{{ t('admin.botBio') }}</label>
        <textarea v-model="botBio" rows="3" maxlength="500" :placeholder="t('admin.botBioPh')" />
      </div>
      <div class="panel-actions">
        <button class="btn primary" type="button" :disabled="botBusy" @click="saveBotProfile">
          {{ botBusy ? t('admin.botSaving') : t('admin.botSaveProfile') }}
        </button>
      </div>

      <h3 class="subhead">{{ t('admin.botPromptTitle') }}</h3>
      <p class="hint">{{ t('admin.botPromptHint') }}</p>
      <div class="field">
        <label>{{ t('admin.botPromptLabel') }}</label>
        <textarea v-model="botPrompt" rows="14" class="prompt-area" />
        <span class="count">{{ botPrompt.length }} {{ t('admin.botChars') }}</span>
      </div>
      <div class="panel-actions">
        <button class="btn primary" type="button" :disabled="botBusy" @click="saveBotPrompt('replace')">
          {{ botBusy ? t('admin.botSaving') : t('admin.botPromptReplace') }}
        </button>
      </div>

      <div class="field">
        <label>{{ t('admin.botPromptAppend') }}</label>
        <textarea
          v-model="botAppendText"
          rows="4"
          :placeholder="t('admin.botPromptAppendPh')"
        />
      </div>
      <div class="panel-actions">
        <button class="btn ghost" type="button" :disabled="botBusy" @click="saveBotPrompt('append')">
          {{ t('admin.botPromptAppendBtn') }}
        </button>
      </div>

      <h3 class="subhead">{{ t('admin.botDocsTitle') }}</h3>
      <p class="hint">{{ t('admin.botDocsHint') }}</p>
      <label class="btn ghost file-btn">
        <input
          type="file"
          accept=".txt,text/plain"
          hidden
          :disabled="botDocBusy"
          @change="onBotDocFile"
        />
        {{ botDocBusy ? t('admin.botSaving') : t('admin.botDocUpload') }}
      </label>
      <ul v-if="botState?.docs?.length" class="doc-list">
        <li v-for="(doc, i) in botState.docs" :key="`${doc.name}-${i}`" class="doc-item">
          <div>
            <strong>{{ doc.name }}</strong>
            <span class="muted">{{ doc.content.length }} {{ t('admin.botChars') }}</span>
          </div>
          <button class="btn ghost danger" type="button" :disabled="botDocBusy" @click="removeBotDoc(i)">
            {{ t('admin.botDocRemove') }}
          </button>
        </li>
      </ul>
      <p v-else class="empty soft">{{ t('admin.botDocsEmpty') }}</p>
    </section>

    <!-- 禁言 / 禁言加时弹窗 -->
    <Teleport to="body">
      <div v-if="muteModalOpen && detail" class="modal-mask" @click.self="closeMuteModal">
        <div class="modal" role="dialog" :aria-label="detail.is_muted ? t('admin.extendTitle') : t('admin.muteTitle')">
          <h3>{{ detail.is_muted ? t('admin.extendTitle') : t('admin.muteTitle') }}</h3>
          <p class="modal-user">{{ detail.nickname }}</p>

          <div class="field">
            <label>{{ t('admin.reason') }}</label>
            <select v-model="muteReason">
              <option v-for="r in reasons" :key="r.value" :value="r.value">{{ t(r.key) }}</option>
            </select>
          </div>
          <div class="field">
            <label>{{ detail.is_muted ? t('admin.extendDuration') : t('admin.duration') }}</label>
            <select v-model="muteHours">
              <option v-for="d in durations" :key="String(d.value)" :value="d.value">{{ t(d.key) }}</option>
            </select>
          </div>
          <div class="field">
            <label>{{ t('admin.detail') }}</label>
            <input v-model="muteDetail" maxlength="300" :placeholder="t('admin.detailPh')" />
          </div>

          <div class="preview-box">
            <p>{{ t('admin.afterRemain', { text: modalPreview.remaining }) }}</p>
            <p class="release">{{ modalPreview.release }}</p>
          </div>

          <p v-if="error" class="error modal-error">{{ error }}</p>

          <div class="row">
            <button class="btn primary" type="button" :disabled="muteBusy" @click="confirmMuteModal">
              {{ detail.is_muted ? t('admin.confirmExtend') : t('admin.confirmMute') }}
            </button>
            <button class="btn ghost" type="button" :disabled="muteBusy" @click="closeMuteModal">
              {{ t('admin.cancel') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

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
.menu {
  display: grid;
  gap: 0.55rem;
}
.menu-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  width: 100%;
  text-align: left;
  padding: 0.95rem 1.05rem;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.72);
  color: var(--ink);
  font: inherit;
  cursor: pointer;
  text-decoration: none;
  transition: border-color 0.15s ease, background 0.15s ease;
}
.menu-item:hover {
  border-color: rgba(47, 111, 94, 0.35);
  background: rgba(255, 255, 255, 0.92);
}
.menu-item strong {
  display: block;
  font-size: 1.05rem;
  font-weight: 650;
}
.menu-item em {
  display: block;
  margin-top: 0.25rem;
  font-style: normal;
  font-size: 0.88rem;
  color: rgba(20, 32, 27, 0.55);
  line-height: 1.4;
}
.menu-item .chev {
  flex-shrink: 0;
  color: rgba(20, 32, 27, 0.4);
  font-size: 1.05rem;
}
.panel-box {
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 1.05rem 1.1rem;
  background: rgba(255, 255, 255, 0.62);
  display: grid;
  gap: 0.8rem;
}
.panel-head .back,
.detail-head .back {
  border: 0;
  background: transparent;
  color: var(--moss-deep);
  font: inherit;
  cursor: pointer;
  padding: 0;
  margin-bottom: 0.45rem;
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
.panel-box textarea {
  min-height: 8rem;
  resize: vertical;
  line-height: 1.6;
  max-width: 100%;
}
.panel-box .count {
  justify-self: end;
  font-size: 0.78rem;
  color: rgba(20, 32, 27, 0.45);
}
.panel-box .field {
  display: grid;
  gap: 0.35rem;
}
.panel-box .row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
}
.panel-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.55rem;
  padding-top: 0.25rem;
}
.panel-actions.start {
  justify-content: flex-start;
}
.panel-msg {
  margin: 0;
  text-align: center;
  font-size: 0.92rem;
}
.notify-mode {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.45rem;
  padding: 0.3rem;
  border-radius: 13px;
  background: rgba(31, 71, 57, 0.07);
}
.notify-mode button {
  border: 0;
  border-radius: 10px;
  padding: 0.68rem 0.8rem;
  background: transparent;
  color: rgba(20, 32, 27, 0.58);
  font: inherit;
  font-weight: 600;
  cursor: pointer;
  transition: 0.18s ease;
}
.notify-mode button.on {
  color: var(--moss-deep);
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 3px 14px rgba(28, 61, 50, 0.09);
}
.notify-mode button span {
  margin-right: 0.25rem;
  font-size: 0.78rem;
}
.recipient-card {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.78rem;
  border: 1px solid rgba(47, 111, 94, 0.2);
  border-radius: 13px;
  background: linear-gradient(135deg, rgba(230, 241, 235, 0.75), rgba(255, 255, 255, 0.8));
}
.recipient-avatar {
  display: grid;
  place-items: center;
  width: 2.5rem;
  height: 2.5rem;
  flex: 0 0 auto;
  border-radius: 50%;
  background: var(--moss-deep);
  color: white;
  font-family: var(--font-display);
  font-size: 1.1rem;
}
.recipient-meta {
  display: grid;
  min-width: 0;
  line-height: 1.25;
}
.recipient-meta small {
  color: rgba(20, 32, 27, 0.48);
  font-size: 0.7rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.recipient-meta strong {
  margin-top: 0.12rem;
}
.recipient-meta em {
  overflow: hidden;
  color: rgba(20, 32, 27, 0.58);
  font-size: 0.82rem;
  font-style: normal;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.recipient-ready {
  display: grid;
  place-items: center;
  width: 1.55rem;
  height: 1.55rem;
  margin-left: auto;
  border-radius: 50%;
  background: rgba(47, 111, 94, 0.14);
  color: var(--moss-deep);
  font-weight: 700;
}
.check-row {
  display: flex;
  align-items: flex-start;
  gap: 0.65rem;
  padding: 0.78rem;
  border: 1px solid var(--line);
  border-radius: 12px;
  cursor: pointer;
}
.check-row input {
  width: 1rem;
  height: 1rem;
  margin-top: 0.15rem;
  accent-color: var(--moss-deep);
}
.check-row span {
  display: grid;
  gap: 0.18rem;
}
.check-row strong {
  font-size: 0.9rem;
}
.check-row small {
  color: rgba(20, 32, 27, 0.52);
  line-height: 1.4;
}
.mail-preview {
  display: grid;
  gap: 0.45rem;
}
.mail-preview-label {
  color: rgba(20, 32, 27, 0.48);
  font-size: 0.72rem;
  font-weight: 650;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}
.mail-preview-paper {
  overflow: hidden;
  border: 1px solid #dce6e0;
  border-radius: 17px;
  background: #fff;
  box-shadow: 0 13px 34px rgba(22, 56, 44, 0.08);
}
.mail-preview-paper > header {
  padding: 1.3rem 1.45rem;
  background: #173e32;
  color: #fff;
}
.mail-preview-paper > header small {
  font-size: 0.62rem;
  letter-spacing: 0.18em;
  opacity: 0.7;
}
.mail-preview-paper > header h3 {
  margin: 0.55rem 0 0;
  font-family: var(--font-display);
  font-size: 1.4rem;
  font-weight: 500;
  line-height: 1.35;
}
.mail-preview-body {
  padding: 1.35rem 1.45rem;
  color: #34443d;
}
.mail-preview-body > p {
  margin: 0 0 1rem;
  color: #173e32;
}
.mail-copy {
  min-height: 3.5rem;
  color: #34443d;
  line-height: 1.75;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.mail-preview-body footer {
  margin-top: 1.35rem;
  padding-top: 1rem;
  border-top: 1px solid #e5ece8;
  color: #718078;
  font-size: 0.76rem;
  line-height: 1.7;
}
.mail-preview-body footer b {
  color: #246b55;
  font-weight: 500;
}
.lead-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}
.lead-tabs button {
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.7);
  border-radius: 999px;
  padding: 0.28rem 0.7rem;
  font: inherit;
  font-size: 0.82rem;
  cursor: pointer;
  color: rgba(20, 32, 27, 0.65);
}
.lead-tabs button.on {
  background: rgba(47, 111, 94, 0.14);
  color: var(--moss-deep);
  border-color: rgba(47, 111, 94, 0.3);
}
.hint {
  margin: 0;
  font-size: 0.85rem;
  color: rgba(20, 32, 27, 0.5);
}
.quota {
  color: var(--moss-deep) !important;
}
.invite-form {
  display: grid;
  gap: 0.75rem;
}
.invite-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.75rem;
}
.invite-block {
  display: grid;
  gap: 0.65rem;
  padding-top: 0.35rem;
  border-top: 1px solid var(--line);
}
.invite-block h3 {
  margin: 0;
  font-family: var(--font-display);
  font-weight: 500;
  font-size: 1.15rem;
}
.invite-code {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.35rem;
}
.invite-block textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 0.65rem 0.75rem;
  resize: vertical;
  background: #fff;
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
.invite-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.92rem;
}
.invite-table th,
.invite-table td {
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
.my-invite-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.65rem;
}
.my-invite-list li {
  display: grid;
  gap: 0.4rem;
  padding: 0.55rem 0;
  border-top: 1px solid var(--line);
}
.my-invite-list li:first-child {
  border-top: 0;
  padding-top: 0;
}
.my-invite-list .meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  font-size: 0.88rem;
  color: rgba(20, 32, 27, 0.65);
}
.head {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
}
.head h1 {
  margin: 0 0 0.35rem;
  font-family: var(--font-display);
  font-weight: 500;
}
.head p {
  margin: 0;
  color: rgba(20, 32, 27, 0.65);
}
.list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.45rem;
}
.card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.7rem 0.9rem;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--card);
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}
.card:hover,
.card:focus-visible {
  border-color: rgba(47, 111, 94, 0.35);
  background: var(--card-hover);
  outline: none;
}
.card-main {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem 0.65rem;
  align-items: baseline;
  min-width: 0;
  font-size: 0.88rem;
  color: rgba(20, 32, 27, 0.62);
}
.card-main strong {
  color: var(--ink);
  font-size: 0.95rem;
}
.action {
  flex-shrink: 0;
  color: var(--moss-deep);
  font-weight: 600;
  font-size: 0.88rem;
}
.detail {
  border: 1px solid var(--line);
  border-radius: 14px;
  background: var(--card);
  padding: 1rem 1.1rem 1.15rem;
  display: grid;
  gap: 1rem;
}
.detail-head .back {
  border: 0;
  background: transparent;
  padding: 0;
  color: var(--moss-deep);
  font-size: 0.9rem;
  margin-bottom: 0.35rem;
  cursor: pointer;
}
.detail-head h2 {
  margin: 0;
  font-family: var(--font-display);
  font-weight: 500;
  font-size: 1.35rem;
}
.profile {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 1rem;
  align-items: start;
}
.avatar {
  width: 4.2rem;
  height: 4.2rem;
  border-radius: 50%;
  overflow: hidden;
  display: grid;
  place-items: center;
  background: rgba(47, 111, 94, 0.14);
  color: var(--moss-deep);
  font-family: var(--font-display);
  font-size: 1.4rem;
}
.avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.facts {
  margin: 0;
  display: grid;
  gap: 0.45rem;
}
.facts > div {
  display: grid;
  grid-template-columns: 6.5rem 1fr;
  gap: 0.5rem;
  font-size: 0.9rem;
}
.facts dt {
  color: rgba(20, 32, 27, 0.45);
}
.facts dd {
  margin: 0;
  min-width: 0;
  word-break: break-word;
}
.ops {
  display: grid;
  gap: 0.55rem;
  padding-top: 0.35rem;
  border-top: 1px solid var(--line);
}
.restore-box .field,
.restore-chat-box .field {
  display: grid;
  gap: 0.3rem;
}
.thread-restore-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.55rem;
}
.thread-restore-list li {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.55rem 0.65rem;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: rgba(238, 243, 239, 0.55);
}
.thread-meta {
  display: grid;
  gap: 0.15rem;
  min-width: 0;
}
.thread-meta .muted {
  font-size: 0.85rem;
  color: rgba(20, 32, 27, 0.5);
}
.modal-mask {
  position: fixed;
  inset: 0;
  z-index: 90;
  display: grid;
  place-items: center;
  padding: 1.25rem;
  background: rgba(20, 32, 27, 0.38);
  backdrop-filter: blur(4px);
}
.modal {
  width: min(420px, 100%);
  border: 1px solid var(--line);
  border-radius: 14px;
  background: #f7faf8;
  padding: 1.15rem 1.2rem 1.2rem;
  display: grid;
  gap: 0.65rem;
  box-shadow: 0 16px 40px rgba(20, 32, 27, 0.16);
}
.modal h3 {
  margin: 0;
  font-family: var(--font-display);
  font-weight: 500;
  font-size: 1.25rem;
}
.modal-user {
  margin: 0;
  color: rgba(20, 32, 27, 0.55);
  font-size: 0.9rem;
}
.preview-box {
  border: 1px solid rgba(47, 111, 94, 0.2);
  border-radius: 10px;
  background: rgba(47, 111, 94, 0.06);
  padding: 0.7rem 0.8rem;
  display: grid;
  gap: 0.25rem;
}
.preview-box p {
  margin: 0;
  font-size: 0.9rem;
  color: rgba(20, 32, 27, 0.72);
}
.preview-box .release {
  color: var(--moss-deep);
  font-weight: 600;
  font-size: 1rem;
}
.field label {
  display: block;
  font-size: 0.82rem;
  color: rgba(20, 32, 27, 0.55);
  margin-bottom: 0.25rem;
}
select,
input {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 0.5rem 0.65rem;
  background: #fff;
}
.preview {
  margin: 0;
  font-size: 0.88rem;
  color: var(--moss-deep);
}
.row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}
.bad {
  color: var(--danger);
}
.warn {
  color: #9a5b2e;
}
.until,
.muted {
  color: rgba(20, 32, 27, 0.55);
}
.danger {
  color: var(--danger) !important;
}
.ok {
  color: var(--moss-deep);
  margin: 0;
}
.error {
  color: var(--danger);
  margin: 0;
}
.modal-error {
  margin: 0.35rem 0 0;
  font-size: 0.9rem;
}
.empty {
  color: rgba(20, 32, 27, 0.5);
  padding: 0.5rem 0;
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
@media (max-width: 640px) {
  .profile {
    grid-template-columns: 1fr;
  }
  .facts > div {
    grid-template-columns: 1fr;
    gap: 0.1rem;
  }
  .ops .row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.45rem;
  }
  .ops .row .btn {
    width: 100%;
  }
  .invite-grid {
    grid-template-columns: 1fr;
  }
  .invite-table {
    display: block;
    overflow-x: auto;
  }
  .modal {
    width: min(420px, calc(100vw - 1.25rem));
    max-height: calc(100dvh - 2rem - var(--tabbar-h, 0px));
    overflow: auto;
  }
}
.role.soft {
  opacity: 0.72;
  font-weight: 500;
}
.bot-perm {
  display: grid;
  gap: 0.55rem;
  padding: 0.85rem 0 0;
  border-top: 1px solid var(--line);
}
.ops-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 650;
}
.bot-profile {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  flex-wrap: wrap;
}
.bot-av {
  flex-shrink: 0;
}
.bot-av-actions {
  display: flex;
  gap: 0.5rem;
}
.file-btn {
  display: inline-flex;
  align-items: center;
  cursor: pointer;
}
.subhead {
  margin: 1.1rem 0 0.35rem;
  font-size: 1.05rem;
  font-weight: 650;
}
.prompt-area {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.82rem;
  line-height: 1.45;
}
.doc-list {
  list-style: none;
  margin: 0.75rem 0 0;
  padding: 0;
  display: grid;
  gap: 0.45rem;
}
.doc-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.65rem 0.75rem;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.55);
}
.doc-item strong {
  display: block;
}
.empty.soft {
  margin: 0.5rem 0 0;
  color: rgba(20, 32, 27, 0.45);
  font-size: 0.9rem;
}
</style>
