<script setup lang="ts">
import { computed, onActivated, onMounted, onUnmounted, ref } from 'vue'
import api from '../api/client'
import { useI18n } from '../i18n'
import type { NotificationItem } from '../types'
import { formatApiError } from '../utils/apiError'
import { formatDateShanghai } from '../utils/time'

const { t } = useI18n()
const items = ref<NotificationItem[]>([])
const error = ref('')
let timer: number | undefined

const unreadCount = computed(() => items.value.filter((n) => !n.is_read).length)

async function load() {
  try {
    const { data } = await api.get<NotificationItem[]>('/api/notifications')
    items.value = data
    error.value = ''
  } catch (e: unknown) {
    error.value = formatApiError(e, t('notif.loadFail'))
  }
}

async function readAll() {
  try {
    await api.post('/api/notifications/read-all')
    await load()
    window.dispatchEvent(new Event('zeej:notifs-changed'))
  } catch (e: unknown) {
    error.value = formatApiError(e, t('notif.loadFail'))
  }
}

async function readOne(n: NotificationItem) {
  if (n.is_read) return
  try {
    await api.post(`/api/notifications/${n.id}/read`)
    n.is_read = true
    window.dispatchEvent(new Event('zeej:notifs-changed'))
  } catch (e: unknown) {
    error.value = formatApiError(e, t('notif.loadFail'))
  }
}

onMounted(() => {
  void load()
  timer = window.setInterval(() => void load(), 8000)
})
onActivated(() => {
  void load()
})
onUnmounted(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<template>
  <main class="container page">
    <header class="head">
      <div class="titles">
        <h1>{{ t('notif.title') }}</h1>
        <span v-if="unreadCount" class="unread-pill">
          {{ t('notif.unreadCount', { n: unreadCount }) }}
        </span>
      </div>
      <button
        v-if="items.length"
        class="btn ghost"
        type="button"
        :disabled="!unreadCount"
        @click="readAll"
      >
        {{ t('notif.readAll') }}
      </button>
    </header>
    <p v-if="error" class="error">{{ error }}</p>
    <ul v-if="items.length" class="list">
      <li
        v-for="n in items"
        :key="n.id"
        :class="{ unread: !n.is_read, read: n.is_read }"
        @click="readOne(n)"
      >
        <span class="mark" aria-hidden="true">
          <i v-if="!n.is_read" class="bang">!</i>
          <i v-else class="dot-empty" />
        </span>
        <div class="body">
          <div class="row">
            <strong>{{ n.title }}</strong>
            <em v-if="!n.is_read" class="tag">{{ t('notif.unread') }}</em>
            <em v-else class="tag muted">{{ t('notif.read') }}</em>
          </div>
          <p v-if="n.content">{{ n.content }}</p>
          <time>{{ formatDateShanghai(n.created_at) }}</time>
        </div>
      </li>
    </ul>
    <p v-else-if="!error" class="empty">{{ t('notif.empty') }}</p>
  </main>
</template>

<style scoped>
.page {
  padding: 2rem 0 3rem;
}
.head {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: center;
  margin-bottom: 1rem;
}
.titles {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.55rem 0.75rem;
}
h1 {
  margin: 0;
  font-family: var(--font-display);
  font-weight: 500;
  font-size: clamp(1.8rem, 4vw, 2.4rem);
}
.unread-pill {
  display: inline-flex;
  align-items: center;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  background: rgba(181, 74, 58, 0.12);
  color: var(--danger);
  font-size: 0.82rem;
  font-weight: 600;
}
.list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.55rem;
}
li {
  display: grid;
  grid-template-columns: 1.4rem 1fr;
  gap: 0.55rem;
  padding: 0.9rem 0.95rem;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.55);
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
}
li.unread {
  background: rgba(255, 255, 255, 0.88);
  border-color: rgba(181, 74, 58, 0.28);
}
li.read {
  opacity: 0.78;
}
li.read:hover,
li.unread:hover {
  opacity: 1;
  border-color: rgba(47, 111, 94, 0.35);
}
.mark {
  display: grid;
  place-items: start center;
  padding-top: 0.2rem;
}
.bang {
  width: 1.15rem;
  height: 1.15rem;
  border-radius: 50%;
  background: var(--danger);
  color: #fff;
  font-style: normal;
  font-size: 0.78rem;
  font-weight: 800;
  display: grid;
  place-items: center;
  line-height: 1;
}
.dot-empty {
  width: 0.45rem;
  height: 0.45rem;
  margin-top: 0.35rem;
  border-radius: 999px;
  background: rgba(20, 32, 27, 0.18);
  font-style: normal;
}
.body {
  min-width: 0;
}
.row {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.4rem 0.55rem;
  margin-bottom: 0.2rem;
}
li strong {
  font-size: 1.02rem;
}
li.unread strong {
  font-weight: 700;
}
.tag {
  font-style: normal;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--danger);
}
.tag.muted {
  color: rgba(20, 32, 27, 0.4);
  font-weight: 500;
}
li p {
  margin: 0 0 0.35rem;
  color: rgba(20, 32, 27, 0.72);
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}
time {
  font-size: 0.8rem;
  color: rgba(20, 32, 27, 0.45);
}
.empty {
  color: rgba(20, 32, 27, 0.5);
}
.error {
  color: var(--danger);
  margin: 0 0 0.75rem;
}
@media (max-width: 640px) {
  .page {
    padding: 1.35rem 0 2rem;
  }
  .head {
    flex-direction: column;
    align-items: stretch;
  }
  .head .btn {
    width: 100%;
  }
  li {
    padding: 0.95rem;
  }
  li strong {
    font-size: 1.05rem;
  }
  li p {
    font-size: 0.98rem;
  }
}
</style>
