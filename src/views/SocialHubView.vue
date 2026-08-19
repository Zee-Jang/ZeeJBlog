<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api/client'
import { useI18n } from '../i18n'
import { useAuthStore } from '../stores/auth'
import type { ChatMessage, ChatRequest, ChatThread, PublicUser } from '../types'
import { formatDateShanghai, parseApiDate } from '../utils/time'
import { avatarSrc } from '../utils/compressImage'
import { formatApiError } from '../utils/apiError'

type Mode = 'empty' | 'request' | 'pending_sent' | 'pending_recv' | 'chat' | 'blocked' | 'rejected' | 'inactive'

interface PeerItem {
  userId: number
  name: string
  bio: string
  avatarUrl: string | null
  threadId: number | null
  unread: number
  lastPreview: string
  pendingRecv: ChatRequest | null
  pendingSent: ChatRequest | null
  rejected: ChatRequest | null
  blocked: boolean
  peerActive: boolean
  isBot: boolean
  isAdmin: boolean
  updatedAt: string
}

const auth = useAuthStore()
const route = useRoute()
const { t: tr, locale } = useI18n()
const mobilePane = ref<'list' | 'detail'>('list')
const botOpening = ref(false)
const botClearing = ref(false)
const botThinking = ref(false)
const adminOpening = ref(false)
const chatMenuOpen = ref(false)
const searchOpen = ref(false)
const searchQ = ref('')
const searchDate = ref('')
const searchHits = ref<ChatMessage[]>([])
const highlightId = ref<number | null>(null)
const clearingChat = ref(false)


const threads = ref<ChatThread[]>([])
const contacts = ref<PublicUser[]>([])
const received = ref<ChatRequest[]>([])
const sent = ref<ChatRequest[]>([])
const blockedIds = ref<number[]>([])
const messages = ref<ChatMessage[]>([])
const q = ref('')
const selectedId = ref<number | null>(null)
const requestDraft = ref(tr('social.requestDefault'))
let requestDraftDefault = tr('social.requestDefault')
const draft = ref('')

watch(locale, () => {
  const nextDefault = tr('social.requestDefault')
  if (!requestDraft.value.trim() || requestDraft.value === requestDraftDefault) {
    requestDraft.value = nextDefault
  }
  requestDraftDefault = nextDefault
})
const showEmoji = ref(false)
const tip = ref('')
const error = ref('')
const listEl = ref<HTMLElement | null>(null)
const hubEl = ref<HTMLElement | null>(null)
const SIDE_W_KEY = 'zeej-social-side-w'
const sideWidth = ref(clampSideWidth(Number(localStorage.getItem(SIDE_W_KEY)) || 320))
const resizing = ref(false)
let timer: number | undefined

function clampSideWidth(w: number, hubWidth = 0) {
  const min = 240
  const maxHard = 480
  const maxByHub = hubWidth > 0 ? Math.max(min, hubWidth - 360) : maxHard
  return Math.round(Math.min(Math.max(w, min), Math.min(maxHard, maxByHub)))
}

function onSplitterPointerDown(e: PointerEvent) {
  if (window.matchMedia('(max-width: 800px)').matches) return
  e.preventDefault()
  const handle = e.currentTarget as HTMLElement
  handle.setPointerCapture(e.pointerId)
  resizing.value = true
  const startX = e.clientX
  const startW = sideWidth.value
  const hubW = hubEl.value?.clientWidth || 0

  const onMove = (ev: PointerEvent) => {
    sideWidth.value = clampSideWidth(startW + (ev.clientX - startX), hubW)
  }
  const onUp = (ev: PointerEvent) => {
    resizing.value = false
    try {
      handle.releasePointerCapture(ev.pointerId)
    } catch {
      /* ignore */
    }
    localStorage.setItem(SIDE_W_KEY, String(sideWidth.value))
    handle.removeEventListener('pointermove', onMove)
    handle.removeEventListener('pointerup', onUp)
    handle.removeEventListener('pointercancel', onUp)
  }
  handle.addEventListener('pointermove', onMove)
  handle.addEventListener('pointerup', onUp)
  handle.addEventListener('pointercancel', onUp)
}

function listTime(p: PeerItem) {
  // 仅有会话/申请动态时显示，避免用注册时间冒充消息时间
  if (!p.threadId && !p.pendingRecv && !p.pendingSent && !p.rejected) return ''
  if (!p.updatedAt) return ''
  return formatTime(p.updatedAt)
}

const emojis = [
  '😊', '🥰', '😍', '😘', '😉', '🤗', '🤭', '🥺', '😌', '😇',
  '🥳', '🤩', '😋', '😜', '🤪', '😝', '😏', '😳', '😅', '😂',
  '🥹', '😢', '😭', '😤', '😴', '🤔', '🫡', '👍', '👎', '👏',
  '🙌', '🙏', '💪', '✌️', '🤞', '🤟', '👋', '🫶', '❤️', '💕',
  '💗', '💖', '💘', '💝', '✨', '🌟', '💫', '🌈', '🌸', '🍀',
  '🐱', '🐰', '🐻', '🐼', '🦊', '🐥', '🦄', '☕', '🧋', '🍰',
  '🧁', '🍪', '🍩', '🍓', '🍑', '🎉', '🎁', '💌', '🔥', '💤',
]

const peers = computed(() => {
  const map = new Map<number, PeerItem>()
  for (const c of contacts.value) {
    map.set(c.id, {
      userId: c.id,
      name: c.nickname,
      bio: c.bio || '',
      avatarUrl: c.avatar_url,
      threadId: null,
      unread: 0,
      lastPreview: c.bio || tr('social.previewStart'),
      pendingRecv: null,
      pendingSent: null,
      rejected: null,
      blocked: blockedIds.value.includes(c.id),
      peerActive: true,
      isBot: Boolean(c.is_bot),
      isAdmin: Boolean(c.is_admin),
      updatedAt: c.created_at || '',
    })
  }
  for (const thread of threads.value) {
    const item = map.get(thread.peer_id) || {
      userId: thread.peer_id,
      name: thread.peer_name,
      bio: '',
      avatarUrl: null,
      threadId: null,
      unread: 0,
      lastPreview: '',
      pendingRecv: null,
      pendingSent: null,
      rejected: null,
      blocked: blockedIds.value.includes(thread.peer_id),
      peerActive: thread.peer_active !== false,
      isBot: Boolean(thread.peer_is_bot),
      isAdmin: Boolean(thread.peer_is_admin),
      updatedAt: thread.updated_at,
    }
    item.threadId = thread.id
    item.unread = thread.unread_count
    item.lastPreview = thread.last_message || tr('social.previewThread')
    item.name = thread.peer_name
    item.updatedAt = thread.updated_at
    item.peerActive = thread.peer_active !== false
    if (thread.peer_is_bot) item.isBot = true
    if (thread.peer_is_admin) item.isAdmin = true
    map.set(thread.peer_id, item)
  }
  for (const r of received.value) {
    if (r.status !== 'pending' && r.status !== 'rejected') continue
    const item = map.get(r.sender_id) || {
      userId: r.sender_id,
      name: r.sender_name || tr('social.unknownUser'),
      bio: '',
      avatarUrl: null,
      threadId: null,
      unread: 0,
      lastPreview: '',
      pendingRecv: null,
      pendingSent: null,
      rejected: null,
      blocked: blockedIds.value.includes(r.sender_id),
      peerActive: true,
      isBot: false,
      isAdmin: false,
      updatedAt: r.created_at,
    }
    if (r.status === 'pending') {
      item.pendingRecv = r
      item.lastPreview = tr('social.previewRecv')
      item.updatedAt = r.created_at
    } else item.rejected = r
    if (!item.name && r.sender_name) item.name = r.sender_name
    map.set(r.sender_id, item)
  }
  for (const r of sent.value) {
    if (r.status !== 'pending' && r.status !== 'rejected') continue
    const item = map.get(r.receiver_id) || {
      userId: r.receiver_id,
      name: r.receiver_name || tr('social.unknownUser'),
      bio: '',
      avatarUrl: null,
      threadId: null,
      unread: 0,
      lastPreview: '',
      pendingRecv: null,
      pendingSent: null,
      rejected: null,
      blocked: blockedIds.value.includes(r.receiver_id),
      peerActive: true,
      isBot: false,
      isAdmin: false,
      updatedAt: r.created_at,
    }
    if (r.status === 'pending') {
      item.pendingSent = r
      item.lastPreview = tr('social.previewSent')
      item.updatedAt = r.created_at
    } else if (!item.pendingRecv) item.rejected = r
    if (!item.name && r.receiver_name) item.name = r.receiver_name
    map.set(r.receiver_id, item)
  }
  let list = [...map.values()].filter((p) => p.peerActive !== false)
  const key = q.value.trim().toLowerCase()
  if (key) list = list.filter((p) => p.name.toLowerCase().includes(key))
  list.sort((a, b) => {
    if (a.isBot !== b.isBot) return a.isBot ? -1 : 1
    if (a.isAdmin !== b.isAdmin) return a.isAdmin ? -1 : 1
    const score = (p: PeerItem) =>
      (p.unread ? 1000 : 0) + (p.pendingRecv ? 800 : 0) + (p.threadId ? 500 : 0) + (p.pendingSent ? 300 : 0)
    const d = score(b) - score(a)
    if (d !== 0) return d
    return (b.updatedAt || '').localeCompare(a.updatedAt || '')
  })
  return list
})

watch(
  peers,
  (list) => {
    if (selectedId.value && !list.some((p) => p.userId === selectedId.value)) {
      selectedId.value = null
      mobilePane.value = 'list'
      messages.value = []
    }
  },
  { flush: 'post' },
)

const badgeCount = computed(
  () =>
    received.value.filter((r) => r.status === 'pending').length +
    threads.value.reduce((n, t) => n + (t.unread_count || 0), 0),
)

const selected = computed(() => peers.value.find((p) => p.userId === selectedId.value) || null)

const mode = computed<Mode>(() => {
  const p = selected.value
  if (!p) return 'empty'
  if (p.blocked) return 'blocked'
  if (!p.peerActive) return 'inactive'
  if (p.threadId) return 'chat'
  if (p.isBot) return 'request' // 将用「开始对话」直开，不走申请
  if (p.pendingRecv) return 'pending_recv'
  if (p.pendingSent) return 'pending_sent'
  if (p.rejected) return 'rejected'
  return 'request'
})

const sending = ref(false)
const canSend = computed(
  () =>
    mode.value === 'chat' &&
    !sending.value &&
    !auth.user?.is_muted &&
    selected.value?.peerActive !== false &&
    !botThinking.value &&
    draft.value.trim().length > 0,
)
const amMuted = computed(() => Boolean(auth.user?.is_muted))

function statusLabel(msg: ChatMessage) {
  if (msg.recalled) return ''
  if (msg.localStatus === 'sending') return tr('social.sending')
  if (msg.localStatus === 'failed') return tr('social.failed')
  if (!msg.is_mine) return ''
  if (msg.status === 'read') {
    const when = msg.read_at ? formatTime(msg.read_at) : ''
    return when ? `${tr('social.read')} ${when}` : tr('social.read')
  }
  return tr('social.sent')
}

function recallNotice(msg: ChatMessage) {
  if (msg.is_mine) return tr('social.recalledYou')
  const name = selected.value?.name || msg.sender_name || tr('social.sys')
  return tr('social.recalledPeer', { name })
}

function formatTime(iso: string) {
  return formatDateShanghai(iso, 'chat', { yesterday: tr('time.yesterday') })
}

function clipText(s: string, n = 80) {
  const t = (s || '').trim().replace(/\s+/g, ' ')
  if (t.length <= n) return t
  return `${t.slice(0, n)}…`
}

function showTimeDivider(curr: ChatMessage, prev?: ChatMessage) {
  if (!prev) return true
  const a = parseApiDate(curr.created_at)
  const b = parseApiDate(prev.created_at)
  if (!a || !b) return true
  return Math.abs(a.getTime() - b.getTime()) > 5 * 60 * 1000
}

async function scrollBottom() {
  await nextTick()
  if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight
}

function dedupeMessages(list: ChatMessage[]): ChatMessage[] {
  const seen = new Set<number>()
  const out: ChatMessage[] = []
  for (const m of list) {
    if (seen.has(m.id)) continue
    seen.add(m.id)
    out.push(m)
  }
  return out
}

async function loadAll() {
  const [t, c, r, s, b] = await Promise.all([
    api.get<ChatThread[]>('/api/chat/threads'),
    api.get<PublicUser[]>('/api/users', { params: { page_size: 50 } }),
    api.get<ChatRequest[]>('/api/chat-requests/received'),
    api.get<ChatRequest[]>('/api/chat-requests/sent'),
    api.get<number[]>('/api/blocks'),
  ])
  threads.value = t.data
  contacts.value = c.data
  received.value = r.data
  sent.value = s.data
  blockedIds.value = b.data
}

async function loadMessages(threadId: number, scroll: 'bottom' | 'preserve' = 'bottom') {
  const el = listEl.value
  const distFromBottom = el ? el.scrollHeight - el.scrollTop - el.clientHeight : 0
  const nearBottom = distFromBottom < 80
  const locals = messages.value.filter((m) => m.id < 0)
  const { data } = await api.get<ChatMessage[]>(`/api/chat/threads/${threadId}/messages`)
  // 服务端已有同内容自己的消息时，丢掉对应临时气泡，避免双份
  const serverMine = new Set(
    data.filter((m) => m.is_mine).map((m) => `${m.content.trim()}\0${m.sender_id}`),
  )
  const keptLocals = locals.filter(
    (m) => !serverMine.has(`${m.content.trim()}\0${m.sender_id}`),
  )
  messages.value = dedupeMessages([...data, ...keptLocals])
  await nextTick()
  if (highlightId.value) return
  if (scroll === 'bottom' || nearBottom) await scrollBottom()
}

async function refresh() {
  await Promise.all([loadAll(), auth.refreshMe()])
  const p = selected.value
  if (p?.threadId && mode.value === 'chat') await loadMessages(p.threadId, 'preserve')
}

function selectPeer(p: PeerItem) {
  selectedId.value = p.userId
  mobilePane.value = 'detail'
  tip.value = ''
  error.value = ''
  chatMenuOpen.value = false
  searchOpen.value = false
  highlightId.value = null
  quoteTarget.value = null
  showSideTimes.value = false
  blankMenu.value = null
  closeMsgMenu()
  if (p.isBot && !p.threadId && !p.blocked) {
    void openBotChat()
    return
  }
  // 掌柜对普通用户：无需申请，点选即开聊
  if (
    auth.isAdmin &&
    !p.isBot &&
    !p.blocked &&
    p.peerActive !== false &&
    !p.threadId &&
    !p.pendingRecv
  ) {
    void adminOpenChat()
    return
  }
  if (p.threadId && !p.blocked) void loadMessages(p.threadId)
  else messages.value = []
}

async function openBotChat() {
  if (botOpening.value) return
  botOpening.value = true
  error.value = ''
  try {
    const { data } = await api.post<ChatThread>('/api/chat/open-bot')
    await loadAll()
    selectedId.value = data.peer_id
    mobilePane.value = 'detail'
    await loadMessages(data.id)
  } catch (e: unknown) {
    error.value = formatApiError(e, tr('social.errSend'))
  } finally {
    botOpening.value = false
  }
}

async function clearChat() {
  const p = selected.value
  if (!p?.threadId) return
  if (p.isBot && (auth.user?.bot_rounds_limit ?? 0) <= 0) {
    error.value = tr('social.botNoAccess')
    chatMenuOpen.value = false
    return
  }
  const ok = confirm(p.isBot ? tr('social.botClearConfirm') : tr('social.clearConfirm'))
  if (!ok) return
  clearingChat.value = true
  botClearing.value = true
  chatMenuOpen.value = false
  error.value = ''
  tip.value = ''
  try {
    await api.post(`/api/chat/threads/${p.threadId}/clear`)
    messages.value = []
    tip.value = p.isBot ? tr('social.botCleared') : tr('social.cleared')
    await loadAll()
    await auth.refreshMe()
  } catch (e: unknown) {
    error.value = formatApiError(e, tr('social.errSend'))
  } finally {
    clearingChat.value = false
    botClearing.value = false
  }
}

function openChatMenu() {
  chatMenuOpen.value = true
}

function closeChatMenu() {
  chatMenuOpen.value = false
}

function openSearchPanel() {
  chatMenuOpen.value = false
  searchOpen.value = true
  searchQ.value = ''
  searchDate.value = ''
  searchHits.value = []
}

function closeSearchPanel() {
  searchOpen.value = false
  searchHits.value = []
  highlightId.value = null
}

function runKeywordSearch() {
  const q = searchQ.value.trim().toLowerCase()
  if (!q) {
    searchHits.value = []
    return
  }
  searchHits.value = messages.value.filter(
    (m) => !m.recalled && (m.content || '').toLowerCase().includes(q),
  )
}

function runDateSearch() {
  const day = searchDate.value.trim()
  if (!day) {
    searchHits.value = []
    return
  }
  searchHits.value = messages.value.filter(
    (m) => !m.recalled && formatDateShanghai(m.created_at, 'date') === day,
  )
}

async function jumpToHit(msg: ChatMessage) {
  searchOpen.value = false
  highlightId.value = msg.id
  await nextTick()
  const el = listEl.value?.querySelector(`[data-msg-id="${msg.id}"]`) as HTMLElement | null
  el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  window.setTimeout(() => {
    if (highlightId.value === msg.id) highlightId.value = null
  }, 2800)
}

async function menuBlock() {
  chatMenuOpen.value = false
  if (mode.value === 'blocked') await unblockPeer()
  else {
    if (!confirm(tr('social.blockConfirm', { name: selected.value?.name || '' }))) return
    await blockPeer({ skipConfirm: true })
  }
}

async function sendRequest() {
  if (!selected.value) return
  if (amMuted.value) {
    error.value = tr('social.mutedBlock')
    return
  }
  error.value = ''
  try {
    await api.post('/api/chat-requests', {
      receiver_id: selected.value.userId,
      message: requestDraft.value.trim(),
    })
    tip.value = tr('social.tipSent')
    await loadAll()
  } catch (e: unknown) {
    error.value = formatApiError(e, tr('social.errSend'))
  }
}

async function adminOpenChat() {
  if (!selected.value || !auth.isAdmin || adminOpening.value) return
  adminOpening.value = true
  error.value = ''
  tip.value = ''
  try {
    const { data } = await api.post<ChatThread>(`/api/chat/open/${selected.value.userId}`)
    await loadAll()
    selectedId.value = data.peer_id
    mobilePane.value = 'detail'
    await loadMessages(data.id)
    tip.value = tr('social.adminOpened')
  } catch (e: unknown) {
    error.value = formatApiError(e, tr('social.errSend'))
  } finally {
    adminOpening.value = false
  }
}

async function accept() {
  const req = selected.value?.pendingRecv
  if (!req) return
  error.value = ''
  try {
    await api.post(`/api/chat-requests/${req.id}/accept`)
    tip.value = tr('social.tipAccepted')
    await refresh()
  } catch (e: unknown) {
    error.value = formatApiError(e, tr('social.errSend'))
  }
}

async function reject() {
  const req = selected.value?.pendingRecv
  if (!req) return
  error.value = ''
  try {
    await api.post(`/api/chat-requests/${req.id}/reject`)
    await loadAll()
  } catch (e: unknown) {
    error.value = formatApiError(e, tr('social.errSend'))
  }
}

async function cancel() {
  const req = selected.value?.pendingSent
  if (!req) return
  error.value = ''
  try {
    await api.post(`/api/chat-requests/${req.id}/cancel`)
    await loadAll()
  } catch (e: unknown) {
    error.value = formatApiError(e, tr('social.errSend'))
  }
}

async function blockPeer(opts?: { skipConfirm?: boolean }) {
  if (!selected.value) return
  if (!opts?.skipConfirm && !confirm(tr('social.confirmBlock'))) return
  error.value = ''
  try {
    await api.post(`/api/blocks/${selected.value.userId}`)
    await loadAll()
  } catch (e: unknown) {
    error.value = formatApiError(e, tr('social.errSend'))
  }
}

async function unblockPeer() {
  if (!selected.value) return
  const peerId = selected.value.userId
  error.value = ''
  try {
    await api.delete(`/api/blocks/${peerId}`)
    await loadAll()
    const p = peers.value.find((x) => x.userId === peerId)
    if (p?.threadId) await loadMessages(p.threadId, 'bottom')
  } catch (e: unknown) {
    error.value = formatApiError(e, tr('social.errSend'))
  }
}

async function send() {
  const p = selected.value
  // 同步锁：防止 Enter + 表单 submit、或连点导致同内容打两次 API
  if (!p?.threadId || sending.value || !canSend.value) return
  const content = draft.value.trim()
  if (!content) return
  sending.value = true
  const reply = quoteTarget.value
  const replyPayload =
    reply && reply.id > 0
      ? {
          id: reply.id,
          sender_name: reply.sender_name,
          content: reply.recalled ? '' : reply.content,
          recalled: Boolean(reply.recalled),
        }
      : null
  const tempId = -Date.now()
  messages.value = [
    ...messages.value,
    {
      id: tempId,
      thread_id: p.threadId,
      sender_id: auth.user?.id || 0,
      sender_name: auth.displayName || tr('social.me'),
      sender_avatar_url: auth.user?.avatar_url || null,
      content,
      status: 'sent',
      created_at: new Date().toISOString(),
      read_at: null,
      is_mine: true,
      recalled: false,
      reply_to: replyPayload,
      localStatus: 'sending',
    },
  ]
  draft.value = ''
  quoteTarget.value = null
  showEmoji.value = false
  await scrollBottom()
  const talkingBot = Boolean(p.isBot)
  if (talkingBot) botThinking.value = true
  try {
    const body: { content: string; reply_to_id?: number } = { content }
    if (reply && reply.id > 0) body.reply_to_id = reply.id
    const { data } = await api.post<ChatMessage>(
      `/api/chat/threads/${p.threadId}/messages`,
      body,
      { timeout: 90000 },
    )
    // 先去掉临时气泡，再写入正式消息并去重（避免轮询已插入同 id）
    messages.value = dedupeMessages([
      ...messages.value.filter((m) => m.id !== tempId && m.id !== data.id),
      data,
    ])
    await loadAll()
    // 不立刻全量重拉消息，减少和轮询打架；下一次 refresh 会对齐
  } catch (e: unknown) {
    messages.value = messages.value.filter((m) => m.id !== tempId)
    draft.value = content
    if (reply) quoteTarget.value = reply
    error.value = formatApiError(e, tr('social.errSend'))
  } finally {
    sending.value = false
    botThinking.value = false
    await scrollBottom()
  }
}

const recallingId = ref<number | null>(null)
const msgMenuId = ref<number | null>(null)
const quoteTarget = ref<ChatMessage | null>(null)
const showSideTimes = ref(false)
const blankMenu = ref<{ x: number; y: number } | null>(null)

function showAllSideTimes() {
  showSideTimes.value = true
  blankMenu.value = null
  closeMsgMenu()
}

function hideAllSideTimes() {
  showSideTimes.value = false
  blankMenu.value = null
  closeMsgMenu()
}

function onMessagesContextMenu(e: MouseEvent) {
  const t = e.target as HTMLElement | null
  if (!t) return
  // 气泡上的右键留给引用/撤回，不在这里处理
  if (t.closest('.bubble, .msg-menu, .blank-menu')) return
  e.preventDefault()
  e.stopPropagation()
  closeMsgMenu()
  blankMenu.value = { x: e.clientX, y: e.clientY }
}

function closeBlankMenu() {
  blankMenu.value = null
}

function onMessagesClick() {
  closeBlankMenu()
  closeMsgMenu()
}

function sideTimeLabel(iso: string) {
  return formatDateShanghai(iso, 'chat', { yesterday: tr('time.yesterday') })
}

function openMsgMenu(msg: ChatMessage, e?: Event) {
  e?.preventDefault()
  e?.stopPropagation()
  if (msg.recalled || msg.id < 0 || msg.localStatus === 'sending') return
  blankMenu.value = null
  msgMenuId.value = msgMenuId.value === msg.id ? null : msg.id
}

function closeMsgMenu() {
  msgMenuId.value = null
}

let longPressTimer = 0
function onBubblePressStart(msg: ChatMessage, e: TouchEvent | MouseEvent) {
  if ('button' in e && e.button !== 0) return
  if (longPressTimer) window.clearTimeout(longPressTimer)
  longPressTimer = window.setTimeout(() => {
    longPressTimer = 0
    openMsgMenu(msg, e)
  }, 480)
}
function onBubblePressEnd() {
  if (longPressTimer) {
    window.clearTimeout(longPressTimer)
    longPressTimer = 0
  }
}

function setQuote(msg: ChatMessage) {
  if (msg.recalled || msg.id < 0) return
  quoteTarget.value = msg
  closeMsgMenu()
  void nextTick(() => {
    const ta = composerEl.value?.querySelector('textarea') as HTMLTextAreaElement | null
    ta?.focus()
  })
}

function clearQuote() {
  quoteTarget.value = null
}

async function jumpToQuoted(id: number) {
  highlightId.value = id
  await nextTick()
  const el = listEl.value?.querySelector(`[data-msg-id="${id}"]`) as HTMLElement | null
  el?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  window.setTimeout(() => {
    if (highlightId.value === id) highlightId.value = null
  }, 1600)
}

async function recallMessage(msg: ChatMessage) {
  if (!msg.is_mine || msg.recalled || msg.id < 0 || recallingId.value) return
  closeMsgMenu()
  recallingId.value = msg.id
  error.value = ''
  try {
    const { data } = await api.post<ChatMessage>(`/api/chat/messages/${msg.id}/recall`)
    messages.value = messages.value.map((m) => (m.id === msg.id ? { ...m, ...data } : m))
    if (quoteTarget.value?.id === msg.id) quoteTarget.value = { ...quoteTarget.value, recalled: true, content: '' }
    await loadAll()
  } catch (e: unknown) {
    error.value = formatApiError(e, tr('social.errRecall'))
  } finally {
    recallingId.value = null
  }
}

defineExpose({ badgeCount })

const composerEl = ref<HTMLElement | null>(null)
const composerPad = ref(0)
let composerFocusPoll = 0

function syncChatImmersive() {
  const on =
    mobilePane.value === 'detail' && window.matchMedia('(max-width: 800px)').matches
  window.dispatchEvent(new CustomEvent('zeej:chat-immersive', { detail: on }))
  placeComposerDock()
}

function clearHubDock() {
  const hub = hubEl.value
  if (!hub) return
  hub.style.position = ''
  hub.style.top = ''
  hub.style.left = ''
  hub.style.right = ''
  hub.style.width = ''
  hub.style.height = ''
  hub.style.zIndex = ''
  hub.style.borderRadius = ''
  hub.style.maxHeight = ''
}

/**
 * 聚焦时把整个对话面板钉在 visualViewport 内：
 * 输入栏在面板底部（文档流），贴齐可视区底边，避免 bottom inset 算大留下白缝。
 * 齿轮/Done 栏是系统输入法或浏览器控件，网页无法去除。
 */
function placeComposerDock() {
  const hub = hubEl.value
  const el = composerEl.value
  const mobile = window.matchMedia('(max-width: 800px)').matches
  const shouldDock = mobile && mobilePane.value === 'detail' && !!hub
  if (!shouldDock) {
    clearHubDock()
    if (el) {
      el.style.position = ''
      el.style.left = ''
      el.style.right = ''
      el.style.bottom = ''
      el.style.top = ''
      el.style.width = ''
      el.style.zIndex = ''
    }
    composerPad.value = 0
    return
  }

  const vv = window.visualViewport
  const focused = !!el && !!document.activeElement && el.contains(document.activeElement)

  // 输入栏保持文档流，不单独 fixed
  if (el) {
    el.style.position = ''
    el.style.left = ''
    el.style.right = ''
    el.style.bottom = ''
    el.style.top = ''
    el.style.width = ''
    el.style.zIndex = ''
  }
  composerPad.value = 0

  if (focused && vv) {
    const top = Math.max(0, Math.round(vv.offsetTop))
    const height = Math.max(200, Math.round(vv.height))
    hub.style.position = 'fixed'
    hub.style.left = '0'
    hub.style.right = '0'
    hub.style.width = '100%'
    hub.style.top = `${top}px`
    hub.style.height = `${height}px`
    hub.style.maxHeight = `${height}px`
    hub.style.zIndex = '60'
    hub.style.borderRadius = '0'
  } else {
    clearHubDock()
  }
}

function onComposerFocus() {
  placeComposerDock()
  window.setTimeout(() => {
    placeComposerDock()
    void scrollBottom()
  }, 50)
  window.setTimeout(() => {
    placeComposerDock()
    void scrollBottom()
  }, 300)
  if (composerFocusPoll) window.clearInterval(composerFocusPoll)
  composerFocusPoll = window.setInterval(() => placeComposerDock(), 100)
}

function onComposerBlur() {
  window.setTimeout(() => {
    const a = document.activeElement
    if (a && composerEl.value?.contains(a)) return
    if (composerFocusPoll) {
      window.clearInterval(composerFocusPoll)
      composerFocusPoll = 0
    }
    clearHubDock()
    window.scrollTo(0, 0)
    placeComposerDock()
  }, 0)
  window.setTimeout(() => {
    clearHubDock()
    window.scrollTo(0, 0)
    placeComposerDock()
  }, 350)
}

function backToList() {
  mobilePane.value = 'list'
  if (composerFocusPoll) {
    window.clearInterval(composerFocusPoll)
    composerFocusPoll = 0
  }
  clearHubDock()
  window.scrollTo(0, 0)
  document.documentElement.scrollTop = 0
  document.body.scrollTop = 0
  window.dispatchEvent(new CustomEvent('zeej:viewport-reset'))
  syncChatImmersive()
  window.setTimeout(() => {
    window.scrollTo(0, 0)
    window.dispatchEvent(new CustomEvent('zeej:viewport-reset'))
  }, 50)
  window.setTimeout(() => {
    window.scrollTo(0, 0)
    window.dispatchEvent(new CustomEvent('zeej:viewport-reset'))
  }, 320)
}

watch(mobilePane, () => syncChatImmersive())

onMounted(async () => {
  await loadAll()
  timer = window.setInterval(() => void refresh(), 4000)
  await maybeOpenFromQuery()
  syncChatImmersive()
  window.addEventListener('resize', syncChatImmersive)
  window.visualViewport?.addEventListener('resize', placeComposerDock)
  window.visualViewport?.addEventListener('scroll', placeComposerDock)
})
onUnmounted(() => {
  if (timer) window.clearInterval(timer)
  if (composerFocusPoll) window.clearInterval(composerFocusPoll)
  if (longPressTimer) window.clearTimeout(longPressTimer)
  window.removeEventListener('resize', syncChatImmersive)
  window.visualViewport?.removeEventListener('resize', placeComposerDock)
  window.visualViewport?.removeEventListener('scroll', placeComposerDock)
  window.dispatchEvent(new CustomEvent('zeej:chat-immersive', { detail: false }))
})

async function maybeOpenFromQuery() {
  const wantBot = route.query.bot === '1' || route.query.bot === 'true'
  const peerQ = Number(route.query.peer || 0)
  if (wantBot) {
    if (selected.value?.isBot && selected.value.threadId) return
    await openBotChat()
    return
  }
  if (peerQ && selectedId.value !== peerQ) {
    const p = peers.value.find((x) => x.userId === peerQ)
    if (p) selectPeer(p)
  }
}

watch(
  () => route.fullPath,
  () => {
    void maybeOpenFromQuery()
  },
)
</script>

<template>
  <main
    ref="hubEl"
    class="hub"
    :class="{ detailOn: mobilePane === 'detail', resizing }"
    :style="{ '--side-w': `${sideWidth}px` }"
  >
    <aside class="side">
      <header class="side-head">
        <h1>{{ tr('social.title') }}</h1>
        <span v-if="badgeCount" class="badge">{{ badgeCount }}</span>
      </header>
      <input v-model="q" class="search" :placeholder="tr('social.search')" />
      <div class="list">
        <button
          v-for="p in peers"
          :key="p.userId"
          type="button"
          class="item"
          :class="{ on: selectedId === p.userId }"
          @click="selectPeer(p)"
        >
          <div class="avatar">
            <img v-if="avatarSrc(p.avatarUrl)" :src="avatarSrc(p.avatarUrl)!" alt="" />
            <template v-else>{{ p.name.slice(0, 1) }}</template>
          </div>
          <div class="body">
            <div class="row1">
              <strong>
                {{ p.name }}
                <em v-if="p.isBot" class="bot-tag">{{ tr('social.botTag') }}</em>
                <em v-else-if="p.isAdmin" class="bot-tag host-tag">{{ tr('social.hostTag') }}</em>
              </strong>
              <time v-if="listTime(p)">{{ listTime(p) }}</time>
            </div>
            <div class="row2">
              <span>{{ p.lastPreview }}</span>
              <i v-if="p.unread || p.pendingRecv">{{ p.unread || '!' }}</i>
            </div>
          </div>
        </button>
        <p v-if="!peers.length" class="empty">{{ tr('social.emptyList') }}</p>
      </div>
    </aside>

    <div
      class="splitter"
      role="separator"
      aria-orientation="vertical"
      :aria-valuenow="sideWidth"
      aria-valuemin="240"
      aria-valuemax="480"
      :aria-label="tr('social.resizePane')"
      tabindex="0"
      @pointerdown="onSplitterPointerDown"
    />

    <section class="panel">
      <header class="panel-head">
        <button class="back" type="button" @click="backToList">←</button>
        <strong>
          {{ selected?.name || tr('social.pick') }}
          <em v-if="selected?.isBot" class="bot-tag">{{ tr('social.botTag') }}</em>
          <em v-else-if="selected?.isAdmin" class="bot-tag host-tag">{{ tr('social.hostTag') }}</em>
        </strong>
        <div v-if="selected && (mode === 'chat' || mode === 'blocked')" class="head-actions">
          <button
            class="menu-btn"
            type="button"
            :aria-label="tr('social.chatMenu')"
            :aria-expanded="chatMenuOpen"
            @click="openChatMenu"
          >
            <span /><span /><span />
          </button>
        </div>
      </header>

      <div v-if="mode === 'empty'" class="empty center">{{ tr('social.pickHint') }}</div>

      <div v-else-if="mode === 'request'" class="sys">
        <div class="sys-card">
          <p class="sys-title">{{ tr('social.sys') }}</p>
          <template v-if="selected?.isBot">
            <p>{{ tr('social.botIntro', { name: selected?.name || '' }) }}</p>
            <button
              class="btn primary"
              type="button"
              :disabled="botOpening"
              @click="openBotChat"
            >
              {{ botOpening ? tr('social.botOpening') : tr('social.botStart') }}
            </button>
          </template>
          <template v-else-if="auth.isAdmin">
            <p>{{ tr('social.adminDirect', { name: selected?.name || '' }) }}</p>
            <button
              class="btn primary"
              type="button"
              :disabled="adminOpening"
              @click="adminOpenChat"
            >
              {{ adminOpening ? tr('social.adminOpening') : tr('social.startChat') }}
            </button>
          </template>
          <template v-else>
            <p>{{ tr('social.needRequest', { name: selected?.name || '' }) }}</p>
            <p v-if="amMuted" class="mute-banner">{{ tr('social.mutedBlock') }}</p>
            <textarea
              v-model="requestDraft"
              rows="3"
              maxlength="500"
              :placeholder="tr('social.requestPh')"
              :disabled="amMuted"
            />
            <p class="time">{{ tr('social.now') }}</p>
            <button class="btn primary" type="button" :disabled="amMuted" @click="sendRequest">
              {{ tr('social.sendRequest') }}
            </button>
          </template>
        </div>
      </div>

      <div v-else-if="mode === 'pending_sent'" class="sys">
        <div class="sys-card">
          <p class="sys-title">{{ tr('social.sys') }}</p>
          <p>{{ tr('social.pendingSent', { name: selected?.name || '' }) }}</p>
          <p class="quote">{{ selected?.pendingSent?.message || tr('social.noNote') }}</p>
          <p class="time">{{ formatTime(selected?.pendingSent?.created_at || '') }} · {{ tr('social.delivered') }}</p>
          <button class="btn ghost" type="button" @click="cancel">{{ tr('social.cancel') }}</button>
        </div>
      </div>

      <div v-else-if="mode === 'pending_recv'" class="sys">
        <div class="sys-card">
          <p class="sys-title">{{ tr('social.sys') }}</p>
          <p>{{ tr('social.pendingRecv', { name: selected?.name || '' }) }}</p>
          <p class="quote">{{ selected?.pendingRecv?.message || tr('social.noNote') }}</p>
          <p class="time">{{ formatTime(selected?.pendingRecv?.created_at || '') }}</p>
          <div class="row">
            <button class="btn primary" type="button" @click="accept">{{ tr('social.accept') }}</button>
            <button class="btn ghost" type="button" @click="reject">{{ tr('social.reject') }}</button>
          </div>
        </div>
      </div>

      <div v-else-if="mode === 'rejected'" class="sys">
        <div class="sys-card">
          <p class="sys-title">{{ tr('social.sys') }}</p>
          <p>{{ tr('social.rejected') }}</p>
          <p v-if="amMuted" class="mute-banner">{{ tr('social.mutedBlock') }}</p>
          <textarea v-model="requestDraft" rows="3" maxlength="500" :disabled="amMuted" />
          <button class="btn primary" type="button" :disabled="amMuted" @click="sendRequest">
            {{ tr('social.reapply') }}
          </button>
        </div>
      </div>

      <div v-else-if="mode === 'inactive'" class="sys">
        <div class="sys-card">
          <p class="sys-title">{{ tr('social.sys') }}</p>
          <p>{{ tr('social.peerInactive', { name: selected?.name || '' }) }}</p>
        </div>
      </div>

      <div v-else-if="mode === 'blocked'" class="sys">
        <div class="sys-card">
          <p class="sys-title">{{ tr('social.sys') }}</p>
          <p>{{ tr('social.blocked', { name: selected?.name || '' }) }}</p>
          <button class="btn primary" type="button" @click="unblockPeer">{{ tr('social.restore') }}</button>
        </div>
      </div>

      <template v-else>
        <div
          ref="listEl"
          class="messages"
          @click="onMessagesClick"
          @contextmenu="onMessagesContextMenu"
        >
          <div class="sys-inline">
            {{ selected?.isBot ? tr('social.botCanChat') : tr('social.canChat') }}
          </div>
          <p v-if="showSideTimes" class="times-hint">{{ tr('social.showTimesHint') }}</p>
          <Teleport to="body">
            <div
              v-if="blankMenu"
              class="blank-menu"
              :style="{ left: `${blankMenu.x}px`, top: `${blankMenu.y}px` }"
              @click.stop
              @contextmenu.prevent
            >
              <button
                v-if="!showSideTimes"
                type="button"
                @click="showAllSideTimes"
              >
                {{ tr('social.showTimesPrompt') }}
              </button>
              <button v-else type="button" @click="hideAllSideTimes">
                {{ tr('social.hideTimesPrompt') }}
              </button>
            </div>
          </Teleport>
          <template v-for="(msg, idx) in messages" :key="msg.id">
            <div
              v-if="!showSideTimes && showTimeDivider(msg, messages[idx - 1])"
              class="time-divider"
            >
              {{ formatTime(msg.created_at) }}
            </div>
            <div v-if="msg.recalled" class="recall-notice">{{ recallNotice(msg) }}</div>
            <div
              v-else
              class="bubble-row"
              :class="{ mine: msg.is_mine, hit: highlightId === msg.id, timed: showSideTimes }"
              :data-msg-id="msg.id"
            >
              <span v-if="showSideTimes && !msg.is_mine" class="side-time left">
                {{ sideTimeLabel(msg.created_at) }}
              </span>
              <div class="msg-stack">
                <div class="msg-line">
                  <div class="msg-avatar" aria-hidden="true">
                    <img
                      v-if="avatarSrc(msg.sender_avatar_url || (msg.is_mine ? auth.user?.avatar_url : selected?.avatarUrl))"
                      :src="avatarSrc(msg.sender_avatar_url || (msg.is_mine ? auth.user?.avatar_url : selected?.avatarUrl))!"
                      alt=""
                    />
                    <span v-else>{{
                      (msg.is_mine
                        ? auth.displayName || msg.sender_name
                        : selected?.name || msg.sender_name || '?'
                      ).slice(0, 1)
                    }}</span>
                  </div>
                  <div
                    class="bubble"
                    :class="{ menuOn: msgMenuId === msg.id }"
                    @contextmenu.prevent="openMsgMenu(msg, $event)"
                    @touchstart.passive="onBubblePressStart(msg, $event)"
                    @touchend="onBubblePressEnd"
                    @touchmove="onBubblePressEnd"
                    @touchcancel="onBubblePressEnd"
                  >
                    <button
                      v-if="msg.reply_to"
                      type="button"
                      class="quote-card"
                      @click.stop="jumpToQuoted(msg.reply_to.id)"
                    >
                      <strong>{{ msg.reply_to.sender_name }}</strong>
                      <span>{{
                        msg.reply_to.recalled
                          ? tr('social.quoteRecalled')
                          : clipText(msg.reply_to.content)
                      }}</span>
                    </button>
                    <p class="text">{{ msg.content }}</p>
                    <div v-if="msgMenuId === msg.id" class="msg-menu" @click.stop>
                      <button type="button" @click="setQuote(msg)">{{ tr('social.quote') }}</button>
                      <button
                        v-if="msg.is_mine"
                        type="button"
                        :disabled="recallingId === msg.id"
                        @click="recallMessage(msg)"
                      >
                        {{
                          recallingId === msg.id ? tr('social.recalling') : tr('social.recall')
                        }}
                      </button>
                    </div>
                  </div>
                </div>
                <p v-if="msg.is_mine" class="status">{{ statusLabel(msg) }}</p>
              </div>
              <span v-if="showSideTimes && msg.is_mine" class="side-time right">
                {{ sideTimeLabel(msg.created_at) }}
              </span>
            </div>
          </template>
          <p v-if="botThinking" class="bot-thinking">{{ tr('social.botThinking') }}</p>
        </div>
        <p v-if="amMuted" class="mute-banner">{{ tr('social.mutedBlock') }}</p>
        <div v-if="quoteTarget && !amMuted" class="quote-bar">
          <div class="quote-bar-body">
            <strong>{{ quoteTarget.sender_name }}</strong>
            <span>{{
              quoteTarget.recalled
                ? tr('social.quoteRecalled')
                : clipText(quoteTarget.content, 120)
            }}</span>
          </div>
          <button type="button" class="quote-bar-close" :aria-label="tr('social.quoteCancel')" @click="clearQuote">
            ×
          </button>
        </div>
        <form ref="composerEl" class="composer" @submit.prevent="send">
          <textarea
            v-model="draft"
            rows="1"
            enterkeyhint="send"
            :placeholder="amMuted ? tr('social.mutedPh') : tr('social.say')"
            :disabled="amMuted || sending"
            @focus="onComposerFocus"
            @blur="onComposerBlur"
            @keydown.enter.exact.prevent="send"
          />
          <div class="composer-actions">
            <div class="tools">
              <button
                type="button"
                class="composer-btn ghost"
                :disabled="amMuted"
                @click="showEmoji = !showEmoji"
              >
                {{ tr('social.emoji') }}
              </button>
              <div v-if="showEmoji && !amMuted" class="emoji-panel">
                <button
                  v-for="e in emojis"
                  :key="e"
                  type="button"
                  @click="draft += e"
                >
                  {{ e }}
                </button>
              </div>
            </div>
            <button class="composer-btn primary" type="submit" :disabled="!canSend">
              {{ tr('social.send') }}
            </button>
          </div>
        </form>
      </template>

      <p v-if="tip" class="tip">{{ tip }}</p>
      <p v-if="error" class="error">{{ error }}</p>
    </section>

    <Teleport to="body">
      <div v-if="chatMenuOpen" class="sheet-mask" @click.self="closeChatMenu">
        <div class="chat-sheet" role="dialog" :aria-label="tr('social.chatMenu')">
          <header class="sheet-head">
            <div class="sheet-peer">
              <strong>{{ selected?.name }}</strong>
              <em v-if="selected?.isBot" class="bot-tag">{{ tr('social.botTag') }}</em>
              <em v-else-if="selected?.isAdmin" class="bot-tag host-tag">{{ tr('social.hostTag') }}</em>
            </div>
            <button type="button" class="sheet-close" @click="closeChatMenu">×</button>
          </header>
          <nav class="sheet-list">
            <button
              v-if="mode === 'chat' && selected?.threadId"
              type="button"
              class="sheet-item"
              @click="openSearchPanel"
            >
              <span>{{ tr('social.searchChat') }}</span>
              <i>›</i>
            </button>
            <button
              v-if="mode === 'chat' && selected?.threadId"
              type="button"
              class="sheet-item danger"
              :disabled="clearingChat || botClearing"
              @click="clearChat"
            >
              <span>{{
                selected?.isBot
                  ? clearingChat || botClearing
                    ? tr('social.botClearing')
                    : tr('social.clearChat')
                  : clearingChat
                    ? tr('social.clearing')
                    : tr('social.clearChat')
              }}</span>
            </button>
            <button
              v-if="!selected?.isBot"
              type="button"
              class="sheet-item"
              :class="{ danger: mode !== 'blocked' }"
              @click="menuBlock"
            >
              <span>{{ mode === 'blocked' ? tr('social.unblock') : tr('social.block') }}</span>
            </button>
          </nav>
          <p v-if="selected?.isBot && mode === 'chat'" class="sheet-hint">{{ tr('social.clearBotHint') }}</p>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="searchOpen" class="sheet-mask search-mask" @click.self="closeSearchPanel">
        <div class="search-sheet" role="dialog" :aria-label="tr('social.searchChat')">
          <header class="sheet-head">
            <strong>{{ tr('social.searchChat') }}</strong>
            <button type="button" class="sheet-close" @click="closeSearchPanel">×</button>
          </header>

          <section class="search-block">
            <h3>{{ tr('social.searchByKeyword') }}</h3>
            <p class="search-desc">{{ tr('social.searchByKeywordHint') }}</p>
            <div class="search-row">
              <input
                v-model="searchQ"
                type="search"
                maxlength="80"
                :placeholder="tr('social.searchKeywordPh')"
                @keydown.enter.prevent="runKeywordSearch"
              />
              <button class="btn primary" type="button" @click="runKeywordSearch">
                {{ tr('social.searchGo') }}
              </button>
            </div>
          </section>

          <section class="search-block">
            <h3>{{ tr('social.searchByDate') }}</h3>
            <p class="search-desc">{{ tr('social.searchByDateHint') }}</p>
            <div class="search-row">
              <input v-model="searchDate" type="date" @change="runDateSearch" />
              <button class="btn ghost" type="button" @click="runDateSearch">
                {{ tr('social.searchGo') }}
              </button>
            </div>
          </section>

          <section class="search-hits">
            <p v-if="!searchHits.length" class="search-empty">{{ tr('social.searchEmpty') }}</p>
            <button
              v-for="hit in searchHits"
              :key="hit.id"
              type="button"
              class="hit-item"
              @click="jumpToHit(hit)"
            >
              <span class="hit-time">{{ formatDateShanghai(hit.created_at, 'datetime') }}</span>
              <span class="hit-who">{{ hit.is_mine ? tr('social.me') : selected?.name }}</span>
              <span class="hit-text">{{ hit.content }}</span>
            </button>
          </section>
        </div>
      </div>
    </Teleport>
  </main>
</template>

<style scoped>
.hub {
  display: grid;
  grid-template-columns: var(--side-w, 320px) 7px minmax(0, 1fr);
  height: 100%;
  min-height: 0;
  width: 100%;
  border: 1px solid rgba(20, 32, 27, 0.18);
  border-radius: 16px;
  overflow: hidden;
  background: #fff;
  box-shadow:
    0 1px 2px rgba(20, 32, 27, 0.06),
    0 10px 28px rgba(20, 32, 27, 0.08);
}
.hub.resizing {
  cursor: col-resize;
  user-select: none;
}
.hub.resizing * {
  cursor: col-resize !important;
  user-select: none !important;
}
.splitter {
  position: relative;
  z-index: 2;
  width: 7px;
  margin-inline: -3px;
  cursor: col-resize;
  touch-action: none;
  background: transparent;
}
.splitter::before {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  left: 50%;
  width: 1px;
  transform: translateX(-50%);
  background: rgba(20, 32, 27, 0.14);
  transition: background 0.15s ease, width 0.15s ease;
}
.splitter:hover::before,
.hub.resizing .splitter::before {
  width: 2px;
  background: rgba(47, 111, 94, 0.55);
}
.side {
  display: grid;
  grid-template-rows: auto auto 1fr;
  background: #eef2ef;
  min-width: 0;
  min-height: 0;
}
.panel {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  background: #f7f9f7;
  overflow: hidden;
}
.side-head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 1rem 1rem 0.5rem;
}
.side-head h1 {
  margin: 0;
  font-family: var(--font-display);
  font-weight: 500;
  font-size: 1.55rem;
}
.badge {
  min-width: 1.15rem;
  height: 1.15rem;
  padding: 0 0.3rem;
  border-radius: 999px;
  background: #2f6f5e;
  color: #fff;
  font-size: 0.7rem;
  display: grid;
  place-items: center;
}
.search {
  margin: 0 0.75rem 0.5rem;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 0.55rem 0.85rem;
  background: #fff;
}
.list {
  overflow: auto;
  padding: 0.25rem 0.45rem 0.8rem;
}
.item {
  width: 100%;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 0.65rem;
  align-items: center;
  border: 0;
  background: transparent;
  text-align: left;
  padding: 0.7rem 0.5rem;
  border-radius: 12px;
  cursor: pointer;
}
.item.on,
.item:hover {
  background: rgba(47, 111, 94, 0.12);
}
.avatar {
  width: 2.45rem;
  height: 2.45rem;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: rgba(47, 111, 94, 0.15);
  color: var(--moss-deep);
  font-family: var(--font-display);
  overflow: hidden;
  flex-shrink: 0;
}
.avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.body {
  min-width: 0;
  display: grid;
  gap: 0.18rem;
}
.row1,
.row2 {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  min-width: 0;
}
.row1 {
  align-items: baseline;
  justify-content: space-between;
}
.body strong {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  min-width: 0;
  font-size: 0.95rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.row1 time {
  flex-shrink: 0;
  font-size: 0.72rem;
  color: rgba(20, 32, 27, 0.42);
  font-variant-numeric: tabular-nums;
}
.bot-tag {
  font-style: normal;
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  padding: 0.08rem 0.35rem;
  border-radius: 999px;
  background: rgba(47, 111, 94, 0.14);
  color: var(--moss-deep);
}
.host-tag {
  background: rgba(180, 120, 60, 0.16);
  color: #8a5a22;
  text-transform: none;
  letter-spacing: 0.02em;
}
.panel-head strong {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  min-width: 0;
}
.bot-thinking {
  margin: 0.35rem 0.75rem 0.6rem;
  font-size: 0.85rem;
  color: rgba(20, 32, 27, 0.55);
}
.body span {
  flex: 1 1 auto;
  min-width: 0;
  font-size: 0.78rem;
  color: rgba(20, 32, 27, 0.5);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.item i {
  flex-shrink: 0;
  font-style: normal;
  background: #2f6f5e;
  color: #fff;
  border-radius: 999px;
  min-width: 1.05rem;
  height: 1.05rem;
  display: grid;
  place-items: center;
  font-size: 0.68rem;
}
.panel-head {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.85rem 1rem;
  border-bottom: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.92);
}
.head-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
}
.menu-btn {
  width: 2.2rem;
  height: 2.2rem;
  border: 0;
  border-radius: 10px;
  background: transparent;
  display: grid;
  place-content: center;
  gap: 0.22rem;
  cursor: pointer;
  padding: 0.35rem;
}
.menu-btn span {
  display: block;
  width: 1.05rem;
  height: 2px;
  border-radius: 2px;
  background: var(--moss-deep);
}
.menu-btn:hover {
  background: rgba(47, 111, 94, 0.1);
}
.ghost-btn,
.back {
  border: 0;
  background: transparent;
  color: var(--moss-deep);
  cursor: pointer;
  font: inherit;
}
.back {
  display: none;
  font-size: 1.1rem;
}
.sys {
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
  padding: 1.5rem 1rem;
  display: grid;
  place-items: start center;
}
.sys-card {
  width: min(420px, 100%);
  border: 1px solid var(--line);
  border-radius: 14px;
  background: #fff;
  padding: 1rem;
  display: grid;
  gap: 0.7rem;
}
.sys-title {
  margin: 0;
  font-size: 0.75rem;
  letter-spacing: 0.08em;
  color: rgba(20, 32, 27, 0.45);
  text-transform: uppercase;
}
.sys-card p {
  margin: 0;
  line-height: 1.6;
  color: rgba(20, 32, 27, 0.78);
}
.quote {
  padding: 0.65rem 0.75rem;
  border-radius: 10px;
  background: rgba(47, 111, 94, 0.08);
  color: rgba(20, 32, 27, 0.7) !important;
}
.time {
  font-size: 0.72rem !important;
  color: rgba(20, 32, 27, 0.42) !important;
}
.row {
  display: flex;
  gap: 0.5rem;
}
.sys-card textarea {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 0.65rem 0.75rem;
  resize: vertical;
  background: #fff;
}
.messages {
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
  padding: 0.9rem 1rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  background: #fff;
}
.sys-inline,
.time-divider,
.recall-notice {
  align-self: center;
  font-size: 0.68rem;
  color: rgba(20, 32, 27, 0.4);
  background: rgba(20, 32, 27, 0.04);
  border-radius: 999px;
  padding: 0.18rem 0.55rem;
  margin: 0.25rem 0;
}
.recall-notice {
  max-width: 90%;
  text-align: center;
  line-height: 1.35;
}
.bubble-row {
  display: flex;
  align-items: flex-end;
  gap: 0.35rem;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
}
.bubble-row.timed {
  width: 100%;
  box-sizing: border-box;
  padding-inline: 0.15rem;
}
.bubble-row.timed.mine {
  justify-content: flex-end;
}
.bubble-row.timed:not(.mine) {
  justify-content: flex-start;
}
.side-time {
  flex: 0 0 auto;
  align-self: center;
  min-width: 2.6rem;
  font-size: 0.72rem;
  line-height: 1.2;
  color: rgba(20, 32, 27, 0.42);
  font-variant-numeric: tabular-nums;
  user-select: none;
  pointer-events: none;
  white-space: nowrap;
  animation: side-time-in 0.2s ease;
}
.side-time.left {
  text-align: left;
  margin-right: 0.1rem;
}
.side-time.right {
  text-align: right;
  margin-left: 0.1rem;
}
@keyframes side-time-in {
  from {
    opacity: 0;
    transform: translateY(2px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
.times-hint {
  align-self: center;
  margin: 0.15rem 0 0.35rem;
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
  font-size: 0.68rem;
  color: rgba(20, 32, 27, 0.45);
  background: rgba(20, 32, 27, 0.05);
}
.blank-menu {
  position: fixed;
  z-index: 400;
  min-width: 8.5rem;
  padding: 0.25rem;
  border-radius: 10px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 8px 24px rgba(20, 32, 27, 0.12);
  transform: translate(0, 0);
}
.blank-menu button {
  display: block;
  width: 100%;
  border: 0;
  background: transparent;
  padding: 0.5rem 0.75rem;
  font: inherit;
  font-size: 0.82rem;
  color: var(--moss-deep);
  cursor: pointer;
  border-radius: 8px;
  text-align: left;
  white-space: nowrap;
}
.blank-menu button:hover {
  background: rgba(47, 111, 94, 0.1);
}
.bubble-row.hit .bubble {
  outline: 2px solid rgba(47, 111, 94, 0.55);
  box-shadow: 0 0 0 4px rgba(47, 111, 94, 0.12);
}
.bubble-row.mine {
  justify-content: flex-end;
}
.msg-stack {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  max-width: min(78%, 420px);
  min-width: 0;
}
.bubble-row.mine .msg-stack {
  align-items: flex-end;
}
.msg-line {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  max-width: 100%;
}
.bubble-row.mine .msg-line {
  flex-direction: row-reverse;
}
.msg-avatar {
  width: 2.35rem;
  height: 2.35rem;
  border-radius: 0.35rem;
  overflow: hidden;
  flex-shrink: 0;
  display: grid;
  place-items: center;
  background: rgba(47, 111, 94, 0.16);
  color: var(--moss-deep);
  font-size: 0.95rem;
  font-weight: 600;
  border: 1px solid rgba(20, 32, 27, 0.1);
  margin-top: 0.12rem;
}
.msg-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.bubble {
  position: relative;
  padding: 0.55rem 0.75rem;
  border-radius: 16px;
  background: #fff;
  border: 1px solid var(--line);
  max-width: calc(100% - 2.85rem);
  min-width: 0;
  cursor: default;
}
.msg-menu {
  position: absolute;
  z-index: 5;
  top: calc(100% + 0.35rem);
  right: 0;
  display: grid;
  min-width: 5.5rem;
  padding: 0.25rem;
  border-radius: 10px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 8px 24px rgba(20, 32, 27, 0.12);
}
.bubble-row:not(.mine) .msg-menu {
  right: auto;
  left: 0;
}
.msg-menu button {
  border: 0;
  background: transparent;
  padding: 0.45rem 0.7rem;
  font: inherit;
  font-size: 0.82rem;
  color: var(--moss-deep);
  cursor: pointer;
  border-radius: 8px;
  white-space: nowrap;
  text-align: left;
}
.msg-menu button:hover:not(:disabled) {
  background: rgba(47, 111, 94, 0.1);
}
.msg-menu button:disabled {
  opacity: 0.55;
  cursor: default;
}
.quote-card {
  display: grid;
  gap: 0.12rem;
  width: 100%;
  margin: 0 0 0.4rem;
  padding: 0.35rem 0.5rem;
  border: 0;
  border-left: 2px solid rgba(47, 111, 94, 0.45);
  border-radius: 6px;
  background: rgba(20, 32, 27, 0.05);
  text-align: left;
  cursor: pointer;
  font: inherit;
  color: inherit;
}
.quote-card strong {
  font-size: 0.72rem;
  font-weight: 650;
  color: var(--moss-deep);
}
.quote-card span {
  font-size: 0.78rem;
  line-height: 1.35;
  color: rgba(20, 32, 27, 0.55);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.bubble-row.mine .quote-card {
  background: rgba(255, 255, 255, 0.35);
  border-left-color: rgba(255, 255, 255, 0.7);
}
.bubble-row.mine .quote-card strong {
  color: rgba(20, 32, 27, 0.72);
}
.quote-bar {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  margin: 0 0.85rem 0.35rem;
  padding: 0.45rem 0.55rem 0.45rem 0.65rem;
  border-radius: 10px;
  border-left: 3px solid var(--moss);
  background: rgba(47, 111, 94, 0.08);
}
.quote-bar-body {
  flex: 1;
  min-width: 0;
  display: grid;
  gap: 0.1rem;
}
.quote-bar-body strong {
  font-size: 0.75rem;
  color: var(--moss-deep);
}
.quote-bar-body span {
  font-size: 0.8rem;
  color: rgba(20, 32, 27, 0.58);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.quote-bar-close {
  border: 0;
  background: transparent;
  color: rgba(20, 32, 27, 0.45);
  font-size: 1.1rem;
  line-height: 1;
  cursor: pointer;
  padding: 0.1rem 0.25rem;
}
.bubble::after {
  content: '';
  position: absolute;
  bottom: 0.42rem;
  width: 0;
  height: 0;
  border-style: solid;
  pointer-events: none;
}
/* 对方：左下尖尖 */
.bubble-row:not(.mine) .bubble {
  border-bottom-left-radius: 5px;
}
.bubble-row:not(.mine) .bubble::after {
  left: -6px;
  border-width: 5px 7px 5px 0;
  border-color: transparent #fff transparent transparent;
  filter: drop-shadow(-1px 0 0 var(--line));
}
/* 自己：右下尖尖 */
.bubble-row.mine .bubble {
  background: #a8d0e0;
  color: #14201b;
  border-color: transparent;
  border-bottom-right-radius: 5px;
}
.bubble-row.mine .bubble::after {
  right: -6px;
  left: auto;
  border-width: 5px 0 5px 7px;
  border-color: transparent transparent transparent #a8d0e0;
  filter: none;
}
.text {
  margin: 0;
  white-space: pre-wrap;
  line-height: 1.45;
  font-size: 0.95rem;
}
.status {
  margin: 0.18rem 0 0;
  /* 避开头像，再往左约 2mm */
  padding-right: calc(2.35rem + 0.5rem + 2mm);
  font-size: 0.68rem;
  color: rgba(20, 32, 27, 0.42);
  line-height: 1;
}
.composer {
  --composer-h: 2.55rem;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 0.85rem;
  border-top: 1px solid rgba(20, 32, 27, 0.14);
  background: #f0f3f1;
  box-sizing: border-box;
}
.mute-banner {
  flex-shrink: 0;
  margin: 0;
  padding: 0.45rem 0.85rem;
  border-top: 1px solid rgba(180, 60, 50, 0.12);
  background: rgba(180, 60, 50, 0.07);
  color: #9a3b32;
  font-size: 0.82rem;
}
.sys-card .mute-banner {
  margin: 0.35rem 0;
  border: 1px solid rgba(180, 60, 50, 0.15);
  border-radius: 8px;
  padding: 0.4rem 0.55rem;
}
.composer textarea:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.composer textarea {
  flex: 1;
  min-width: 0;
  height: var(--composer-h);
  box-sizing: border-box;
  border: 1px solid rgba(20, 32, 27, 0.22);
  border-radius: 999px;
  padding: 0.55rem 0.95rem;
  resize: none;
  background: #fff;
  line-height: 1.25;
  overflow-y: auto;
}
.composer-actions {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-shrink: 0;
}
.tools {
  position: relative;
  display: flex;
  align-items: center;
}
.composer-btn {
  height: var(--composer-h);
  min-height: var(--composer-h);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  padding: 0 1rem;
  font-size: 0.9rem;
  border: 1px solid transparent;
  white-space: nowrap;
}
.composer-btn.ghost {
  border-color: rgba(20, 32, 27, 0.22);
  background: #fff;
  color: var(--ink);
}
.composer-btn.primary {
  background: var(--ink);
  color: var(--foam);
  border-color: var(--ink);
}
.composer-btn.primary:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.emoji-panel {
  position: absolute;
  right: 0;
  bottom: calc(100% + 0.4rem);
  width: min(320px, 70vw);
  max-height: 220px;
  overflow: auto;
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 0.15rem;
  padding: 0.45rem;
  background: #fff;
  border: 1px solid rgba(20, 32, 27, 0.16);
  border-radius: 12px;
  box-shadow: 0 10px 30px rgba(20, 32, 27, 0.12);
  z-index: 5;
}
.emoji-panel button {
  border: 0;
  background: transparent;
  font-size: 1.15rem;
  cursor: pointer;
  padding: 0.15rem;
}
.empty {
  color: rgba(20, 32, 27, 0.45);
  padding: 1rem;
}
.empty.center {
  display: grid;
  place-items: center;
}
.tip,
.error {
  flex-shrink: 0;
  margin: 0;
  padding: 0.4rem 0.9rem 0.7rem;
  font-size: 0.85rem;
}
.tip {
  color: var(--moss-deep);
}
.sheet-mask {
  position: fixed;
  inset: 0;
  z-index: 80;
  background: rgba(20, 32, 27, 0.38);
  display: grid;
  align-items: end;
  justify-items: center;
  padding: 0.75rem;
  padding-bottom: calc(0.75rem + env(safe-area-inset-bottom, 0px));
}
.chat-sheet,
.search-sheet {
  width: min(440px, 100%);
  max-height: min(78dvh, 640px);
  overflow: auto;
  background: #fff;
  border-radius: 16px 16px 14px 14px;
  border: 1px solid var(--line);
  box-shadow: 0 16px 40px rgba(20, 32, 27, 0.18);
  display: grid;
  gap: 0.35rem;
  padding-bottom: 0.75rem;
}
.search-mask {
  align-items: center;
}
.search-sheet {
  max-height: min(86dvh, 720px);
  border-radius: 16px;
  padding-bottom: 1rem;
}
.sheet-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.95rem 1rem 0.65rem;
  border-bottom: 1px solid var(--line);
  position: sticky;
  top: 0;
  background: #fff;
  z-index: 1;
}
.sheet-peer {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  min-width: 0;
}
.sheet-peer strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sheet-close {
  border: 0;
  background: transparent;
  font-size: 1.45rem;
  line-height: 1;
  color: rgba(20, 32, 27, 0.45);
  cursor: pointer;
  padding: 0.1rem 0.35rem;
}
.sheet-list {
  display: grid;
  padding: 0.25rem 0;
}
.sheet-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  width: 100%;
  border: 0;
  border-bottom: 1px solid rgba(20, 32, 27, 0.06);
  background: transparent;
  text-align: left;
  padding: 0.95rem 1.05rem;
  font: inherit;
  font-size: 0.98rem;
  color: var(--ink);
  cursor: pointer;
}
.sheet-item:last-child {
  border-bottom: 0;
}
.sheet-item i {
  font-style: normal;
  color: rgba(20, 32, 27, 0.35);
}
.sheet-item.danger {
  color: #b42318;
}
.sheet-item:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.sheet-hint {
  margin: 0;
  padding: 0.15rem 1.05rem 0.35rem;
  font-size: 0.8rem;
  color: rgba(20, 32, 27, 0.48);
  line-height: 1.45;
}
.search-block {
  display: grid;
  gap: 0.4rem;
  padding: 0.85rem 1rem 0.35rem;
}
.search-block h3 {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 650;
}
.search-desc {
  margin: 0;
  font-size: 0.82rem;
  color: rgba(20, 32, 27, 0.5);
}
.search-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0.45rem;
}
.search-row input {
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 0.55rem 0.7rem;
  font: inherit;
  background: #fff;
}
.search-hits {
  display: grid;
  gap: 0.35rem;
  padding: 0.55rem 0.85rem 0.25rem;
  max-height: 42dvh;
  overflow: auto;
}
.search-empty {
  margin: 0.35rem 0.2rem;
  font-size: 0.88rem;
  color: rgba(20, 32, 27, 0.45);
}
.hit-item {
  display: grid;
  gap: 0.15rem;
  text-align: left;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.9);
  padding: 0.55rem 0.65rem;
  font: inherit;
  cursor: pointer;
}
.hit-item:hover {
  border-color: rgba(47, 111, 94, 0.35);
  background: rgba(47, 111, 94, 0.06);
}
.hit-time {
  font-size: 0.72rem;
  color: rgba(20, 32, 27, 0.45);
}
.hit-who {
  font-size: 0.78rem;
  color: var(--moss-deep);
  font-weight: 600;
}
.hit-text {
  font-size: 0.9rem;
  color: rgba(20, 32, 27, 0.82);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
@media (max-width: 800px) {
  .hub {
    grid-template-columns: 1fr;
    border-radius: 12px;
  }
  .splitter {
    display: none;
  }
  .panel {
    display: none;
  }
  .hub.detailOn .side {
    display: none;
  }
  .hub.detailOn .panel {
    display: flex;
  }
  .hub.detailOn {
    border-radius: 0;
    border: 0;
    box-shadow: none;
  }
  /* 微信式顶栏：左返回，中对方名字，右菜单 */
  .hub.detailOn .panel-head {
    position: relative;
    justify-content: center;
    min-height: 2.85rem;
    padding: 0.55rem 3rem;
    background: #ededed;
    border-bottom: 1px solid rgba(20, 32, 27, 0.08);
  }
  .hub.detailOn .panel-head .back {
    position: absolute;
    left: 0.35rem;
    top: 50%;
    transform: translateY(-50%);
    display: inline-grid;
    place-items: center;
    width: 2.4rem;
    height: 2.4rem;
    font-size: 1.25rem;
    border: 0;
    background: transparent;
  }
  .hub.detailOn .panel-head strong {
    margin: 0;
    font-size: 1.05rem;
    font-weight: 600;
    text-align: center;
  }
  .hub.detailOn .head-actions {
    position: absolute;
    right: 0.35rem;
    top: 50%;
    transform: translateY(-50%);
    margin-left: 0;
  }
  .hub.detailOn .composer {
    padding: 0.55rem 0.65rem max(0.55rem, env(safe-area-inset-bottom, 0px));
    background: #f7f7f7;
  }
  html.keyboard-open .hub.detailOn .composer,
  html.input-focus .hub.detailOn .composer {
    padding-bottom: 0.45rem;
  }
  .back {
    display: inline-block;
  }
  .side {
    border-right: 0;
  }
  .composer {
    padding-bottom: 0.55rem;
  }
}
</style>
