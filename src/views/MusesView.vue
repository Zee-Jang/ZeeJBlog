<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api/client'
import { useI18n } from '../i18n'
import { useAuthStore } from '../stores/auth'
import type { Post, PostKind } from '../types'
import { formatDateShanghai } from '../utils/time'
import { formatApiError } from '../utils/apiError'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const posts = ref<Post[]>([])
const loading = ref(true)

type FocusMode = 'create' | 'edit' | 'append' | 'view' | null
const focusMode = ref<FocusMode>(null)
const focusPostId = ref<number | null>(null)

const title = ref('')
const body = ref('')
const kind = ref<PostKind>('muse')
const error = ref('')

const editTitle = ref('')
const editBody = ref('')
const editKind = ref<PostKind>('muse')
const editError = ref('')
const appendBody = ref('')
const appendError = ref('')
const creating = ref(false)
const savingEdit = ref(false)
const savingAppend = ref(false)
const deletingId = ref<number | null>(null)

function routeOpenId(): number {
  const fromParam = Number(route.params.id)
  const fromQuery = Number(route.query.open)
  if (Number.isFinite(fromParam) && fromParam > 0) return fromParam
  if (Number.isFinite(fromQuery) && fromQuery > 0) return fromQuery
  return 0
}

// 首屏直接进详情，避免先闪列表再跳一次
const bootOpenId = routeOpenId()
if (bootOpenId > 0) {
  focusMode.value = 'view'
  focusPostId.value = bootOpenId
}

const focusPost = computed(() => posts.value.find((p) => p.id === focusPostId.value) || null)
const isFocused = computed(() => {
  if (focusMode.value === 'create') return true
  if (focusMode.value === 'edit' || focusMode.value === 'append' || focusMode.value === 'view') {
    return focusPostId.value != null
  }
  return false
})

const focusHeading = computed(() => {
  if (focusMode.value === 'create') return t('muses.publish')
  if (focusMode.value === 'edit') return t('muses.edit')
  if (focusMode.value === 'append') return t('muses.append')
  if (focusMode.value === 'view') return t('muses.detail')
  return ''
})

function setViewportLock(on: boolean) {
  window.dispatchEvent(new CustomEvent('zeej:viewport-lock', { detail: on }))
}

watch(isFocused, (on) => setViewportLock(on), { immediate: true })

onUnmounted(() => setViewportLock(false))

async function load() {
  loading.value = true
  try {
    const { data } = await api.get<Post[]>('/api/posts')
    posts.value = data
  } finally {
    loading.value = false
  }
}

function resetCreateDraft() {
  title.value = ''
  body.value = ''
  kind.value = 'muse'
  error.value = ''
}

async function enterCreate() {
  focusMode.value = 'create'
  focusPostId.value = null
  resetCreateDraft()
  setViewportLock(true)
  await nextTick()
}

async function enterView(post: Post) {
  focusMode.value = 'view'
  focusPostId.value = post.id
  setViewportLock(true)
  if (route.name !== 'muse-detail' || String(route.params.id) !== String(post.id)) {
    await router.replace({ name: 'muse-detail', params: { id: String(post.id) } })
  }
  await nextTick()
}

async function enterFocus(mode: 'edit' | 'append', post: Post) {
  focusMode.value = mode
  focusPostId.value = post.id
  editError.value = ''
  appendError.value = ''
  if (mode === 'edit') {
    editTitle.value = post.title
    editBody.value = post.body
    editKind.value = post.kind
  } else {
    appendBody.value = ''
  }
  setViewportLock(true)
  await nextTick()
}

function leaveFocus() {
  setViewportLock(false)
  focusMode.value = null
  focusPostId.value = null
  editError.value = ''
  appendError.value = ''
  appendBody.value = ''
  resetCreateDraft()
  if (route.name === 'muse-detail' || route.query.open) {
    void router.replace({ name: 'muses' })
  }
}

function onCardKey(e: KeyboardEvent, post: Post) {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault()
    enterView(post)
  }
}

async function createPost() {
  if (creating.value) return
  error.value = ''
  creating.value = true
  try {
    await api.post('/api/posts', {
      kind: kind.value,
      title: title.value.trim(),
      body: body.value.trim(),
    })
    leaveFocus()
    await load()
  } catch (e: any) {
    error.value = formatApiError(e, t('common.publishFail'))
  } finally {
    creating.value = false
  }
}

async function saveEdit() {
  if (focusPostId.value == null || savingEdit.value) return
  editError.value = ''
  savingEdit.value = true
  try {
    await api.patch(`/api/posts/${focusPostId.value}`, {
      kind: editKind.value,
      title: editTitle.value.trim(),
      body: editBody.value.trim(),
    })
    leaveFocus()
    await load()
  } catch (e: any) {
    editError.value = formatApiError(e, t('common.saveFail'))
  } finally {
    savingEdit.value = false
  }
}

async function saveAppend() {
  if (focusPostId.value == null || savingAppend.value) return
  appendError.value = ''
  savingAppend.value = true
  try {
    await api.post(`/api/posts/${focusPostId.value}/append`, {
      body: appendBody.value.trim(),
    })
    leaveFocus()
    await load()
  } catch (e: any) {
    appendError.value = formatApiError(e, t('common.saveFail'))
  } finally {
    savingAppend.value = false
  }
}

async function removePost(id: number) {
  if (deletingId.value != null) return
  if (!confirm(t('muses.deleteConfirm'))) return
  deletingId.value = id
  try {
    await api.delete(`/api/posts/${id}`)
    posts.value = posts.value.filter((p) => p.id !== id)
    if (focusPostId.value === id) leaveFocus()
    await load()
  } catch (e: any) {
    alert(formatApiError(e, t('common.deleteFail')))
  } finally {
    deletingId.value = null
  }
}

async function toggleHome(post: Post) {
  try {
    const { data } = await api.post<Post>(`/api/posts/${post.id}/home`)
    const idx = posts.value.findIndex((p) => p.id === post.id)
    if (idx >= 0) posts.value[idx] = data
  } catch (e: any) {
    alert(formatApiError(e, t('admin.opFail')))
  }
}

async function toggleHide(post: Post) {
  try {
    const { data } = await api.post<Post>(`/api/posts/${post.id}/hide`)
    const idx = posts.value.findIndex((p) => p.id === post.id)
    if (idx >= 0) posts.value[idx] = data
  } catch (e: any) {
    alert(formatApiError(e, t('admin.opFail')))
  }
}

function kindLabel(k: string) {
  return k === 'diary' ? t('muses.diary') : t('muses.muse')
}

function previewText(text: string) {
  return (text || '').replace(/\s+/g, ' ').trim()
}

onMounted(async () => {
  if (!posts.value.length) await load()
  await openFromRoute()
})

watch(
  () => [route.name, route.params.id, route.query.open] as const,
  () => {
    void openFromRoute()
  },
)

async function openFromRoute() {
  const openId = routeOpenId()
  if (!openId) {
    if (route.name === 'muses' && focusMode.value === 'view') {
      // 已在列表路由且无 open 参数
      return
    }
    return
  }
  focusMode.value = 'view'
  focusPostId.value = openId
  setViewportLock(true)
  if (!posts.value.length) await load()
  const post = posts.value.find((p) => p.id === openId)
  if (!post && !loading.value) leaveFocus()
}
</script>

<template>
  <div class="muses-root" :class="{ locked: isFocused }">
    <!-- 发布 / 修改 / 追记：视口锁定 -->
    <main v-if="isFocused" class="muse-focus">
      <header class="focus-head">
        <button type="button" class="back" @click="leaveFocus">← {{ t('muses.back') }}</button>
        <h1>{{ focusHeading }}</h1>
      </header>

      <div class="focus-scroll">
        <article
          class="focus-card"
          :class="{ 'is-hidden-post': focusPost?.is_hidden }"
        >
          <!-- 发布 -->
          <template v-if="focusMode === 'create'">
            <div class="focus-form create">
              <div class="kind-switch" role="group" :aria-label="t('muses.publish')">
                <button
                  type="button"
                  :class="{ on: kind === 'muse' }"
                  @click="kind = 'muse'"
                >
                  {{ t('muses.muse') }}
                </button>
                <button
                  type="button"
                  :class="{ on: kind === 'diary' }"
                  @click="kind = 'diary'"
                >
                  {{ t('muses.diary') }}
                </button>
              </div>
              <input v-model="title" :placeholder="t('muses.titlePh')" required />
              <textarea v-model="body" class="grow" :placeholder="t('muses.bodyPh')" required />
              <p v-if="error" class="error">{{ error }}</p>
              <div class="edit-actions">
                <button class="btn primary" type="button" :disabled="creating" @click="createPost">
                  {{ creating ? t('muses.publishing') : t('muses.publish') }}
                </button>
                <button class="btn ghost" type="button" @click="leaveFocus">{{ t('muses.cancel') }}</button>
              </div>
            </div>
          </template>

          <p v-else-if="focusMode === 'view' && loading" class="muted">{{ t('muses.loading') }}</p>

          <!-- 修改 / 追记 / 全文 -->
          <template v-else-if="focusPost">
            <div class="meta">
              <time>{{ formatDateShanghai(focusPost.created_at, 'datetime') }}</time>
              <span class="tag">{{ kindLabel(focusPost.kind) }}</span>
              <div v-if="auth.isAdmin && focusMode === 'view'" class="actions">
                <button type="button" class="text-btn" @click="enterFocus('edit', focusPost)">
                  {{ t('muses.edit') }}
                </button>
                <button type="button" class="text-btn" @click="enterFocus('append', focusPost)">
                  {{ t('muses.append') }}
                </button>
                <button
                  type="button"
                  class="text-btn"
                  :class="{ on: focusPost.on_home }"
                  @click="toggleHome(focusPost)"
                >
                  {{ focusPost.on_home ? t('muses.unpushHome') : t('muses.pushHome') }}
                </button>
                <button
                  type="button"
                  class="text-btn"
                  :class="{ dim: focusPost.is_hidden }"
                  @click="toggleHide(focusPost)"
                >
                  {{ focusPost.is_hidden ? t('muses.unhide') : t('muses.hide') }}
                </button>
                <button type="button" class="text-btn danger" @click="removePost(focusPost.id)">
                  {{ t('muses.delete') }}
                </button>
              </div>
            </div>

            <template v-if="focusMode === 'view'">
              <h2>{{ focusPost.title }}</h2>
              <p class="body">{{ focusPost.body }}</p>
            </template>

            <template v-else-if="focusMode === 'edit'">
              <div class="focus-form">
                <div class="kind-switch" role="group" :aria-label="t('muses.edit')">
                  <button
                    type="button"
                    :class="{ on: editKind === 'muse' }"
                    @click="editKind = 'muse'"
                  >
                    {{ t('muses.muse') }}
                  </button>
                  <button
                    type="button"
                    :class="{ on: editKind === 'diary' }"
                    @click="editKind = 'diary'"
                  >
                    {{ t('muses.diary') }}
                  </button>
                </div>
                <input v-model="editTitle" :placeholder="t('muses.titlePh')" required />
                <textarea v-model="editBody" class="grow" :placeholder="t('muses.bodyPh')" required />
                <p v-if="editError" class="error">{{ editError }}</p>
                <div class="edit-actions">
                  <button class="btn primary" type="button" :disabled="savingEdit" @click="saveEdit">
                    {{ savingEdit ? t('muses.saving') : t('muses.save') }}
                  </button>
                  <button class="btn ghost" type="button" @click="leaveFocus">{{ t('muses.cancel') }}</button>
                </div>
              </div>
            </template>

            <template v-else>
              <h2>{{ focusPost.title }}</h2>
              <p class="body">{{ focusPost.body }}</p>
              <div class="focus-form">
                <textarea v-model="appendBody" class="grow append" :placeholder="t('muses.appendPh')" required />
                <p v-if="appendError" class="error">{{ appendError }}</p>
                <div class="edit-actions">
                  <button class="btn primary" type="button" :disabled="savingAppend" @click="saveAppend">
                    {{ savingAppend ? t('muses.saving') : t('muses.appendSubmit') }}
                  </button>
                  <button class="btn ghost" type="button" @click="leaveFocus">{{ t('muses.cancel') }}</button>
                </div>
              </div>
            </template>
          </template>
        </article>
      </div>
    </main>

    <!-- 列表主页 -->
    <main v-else class="container page">
      <header class="head">
        <div class="head-row">
          <div>
            <h1>{{ t('nav.musesGuest') }}</h1>
            <p v-if="auth.isAdmin">{{ t('muses.adminHint') }}</p>
            <p v-else>{{ t('muses.guestHint') }}</p>
          </div>
          <button v-if="auth.isAdmin" class="btn primary" type="button" @click="enterCreate">
            {{ t('muses.publish') }}
          </button>
        </div>
      </header>

      <p v-if="loading">{{ t('muses.loading') }}</p>
      <ul v-else class="list">
        <li
          v-for="post in posts"
          :key="post.id"
          class="card"
          :class="{ 'is-hidden-post': post.is_hidden }"
          role="button"
          tabindex="0"
          :title="t('muses.openHint')"
          @click="enterView(post)"
          @keydown="onCardKey($event, post)"
        >
          <div class="meta">
            <time>{{ formatDateShanghai(post.created_at, 'datetime') }}</time>
            <span class="tag">{{ kindLabel(post.kind) }}</span>
            <span v-if="post.is_hidden" class="tag hidden-tag">{{ t('muses.hiddenTag') }}</span>
            <div v-if="auth.isAdmin" class="actions" @click.stop>
              <button type="button" class="text-btn" @click="enterFocus('edit', post)">{{ t('muses.edit') }}</button>
              <button type="button" class="text-btn" @click="enterFocus('append', post)">{{ t('muses.append') }}</button>
              <button
                type="button"
                class="text-btn"
                :class="{ on: post.on_home }"
                @click="toggleHome(post)"
              >
                {{ post.on_home ? t('muses.unpushHome') : t('muses.pushHome') }}
              </button>
              <button
                type="button"
                class="text-btn"
                :class="{ dim: post.is_hidden }"
                @click="toggleHide(post)"
              >
                {{ post.is_hidden ? t('muses.unhide') : t('muses.hide') }}
              </button>
              <button type="button" class="text-btn danger" @click="removePost(post.id)">
                {{ t('muses.delete') }}
              </button>
            </div>
          </div>
          <h2 class="clip">{{ previewText(post.title) }}</h2>
          <p class="clip">{{ previewText(post.body) }}</p>
        </li>
      </ul>
    </main>
  </div>
</template>

<style scoped>
.muses-root {
  width: 100%;
}
.muses-root.locked {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.page {
  padding: 2.8rem 0 1rem;
}
.head {
  margin-bottom: 1.5rem;
}
.head-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}
h1 {
  margin: 0 0 0.5rem;
  font-family: var(--font-display);
  font-size: clamp(2.2rem, 5vw, 3.2rem);
  font-weight: 500;
}
.head p {
  margin: 0;
  color: rgba(20, 32, 27, 0.65);
}
.kind-switch {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.35rem;
  padding: 0.28rem;
  border-radius: 999px;
  background: rgba(20, 32, 27, 0.06);
  border: 1px solid var(--line);
}
.kind-switch button {
  border: 0;
  border-radius: 999px;
  padding: 0.55rem 0.8rem;
  background: transparent;
  color: rgba(20, 32, 27, 0.62);
  font-size: 0.95rem;
  transition: background 0.18s ease, color 0.18s ease, box-shadow 0.18s ease;
}
.kind-switch button.on {
  background: #fff;
  color: var(--moss-deep);
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(20, 32, 27, 0.08);
}
.kind-switch button:hover:not(.on) {
  color: var(--ink);
}
.focus-form input,
.focus-form textarea {
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 0.7rem 0.8rem;
  background: #fff;
  width: 100%;
}
.list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: calc(1cm / 3);
  width: 100%;
  max-width: none;
}
.card {
  height: auto;
  min-height: 0;
  max-height: none;
  box-sizing: border-box;
  padding: calc(0.85rem + 0.5cm / 3) calc(1.05rem + 0.5cm / 3);
  border: 1px solid var(--line);
  border-radius: 14px;
  background: var(--card);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  overflow: hidden;
  min-width: 0;
  width: 100%;
  transition: border-color 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
}
.card:hover,
.card:focus-visible {
  border-color: rgba(47, 111, 94, 0.35);
  background: var(--card-hover);
  box-shadow: 0 6px 18px rgba(20, 32, 27, 0.06);
  outline: none;
}
.card.is-hidden-post,
.focus-card.is-hidden-post {
  opacity: 0.48;
  filter: grayscale(0.35);
  background: rgba(238, 243, 239, 0.55);
  border-color: rgba(20, 32, 27, 0.1);
  box-shadow: none;
}
.card.is-hidden-post:hover,
.card.is-hidden-post:focus-visible {
  opacity: 0.62;
  filter: grayscale(0.2);
  border-color: rgba(20, 32, 27, 0.18);
  box-shadow: none;
  background: rgba(238, 243, 239, 0.7);
}
.hidden-tag {
  opacity: 0.85;
  background: rgba(20, 32, 27, 0.08) !important;
  color: rgba(20, 32, 27, 0.55) !important;
}
.text-btn.dim {
  color: rgba(20, 32, 27, 0.45);
}
.meta {
  display: flex;
  gap: 0.6rem;
  align-items: center;
  flex-wrap: nowrap;
  flex: 0 0 auto;
  min-width: 0;
}
.actions {
  margin-left: auto;
  display: flex;
  gap: 0.35rem;
  flex-shrink: 0;
}
.text-btn {
  border: 0;
  background: transparent;
  padding: 0.15rem 0.35rem;
  color: var(--moss-deep);
  font-size: 0.85rem;
  cursor: pointer;
}
.text-btn.danger {
  color: var(--danger);
}
.text-btn.on {
  color: var(--moss-deep);
  font-weight: 600;
}
time {
  font-size: 0.85rem;
  color: rgba(20, 32, 27, 0.5);
  flex-shrink: 0;
}
.tag {
  font-size: 0.75rem;
  padding: 0.1rem 0.45rem;
  border-radius: 999px;
  background: rgba(47, 111, 94, 0.12);
  color: var(--moss-deep);
  flex-shrink: 0;
}
.card h2.clip {
  margin: 0;
  font-family: var(--font-display);
  font-weight: 500;
  font-size: 1.2rem;
  line-height: 1.35;
  color: var(--ink);
}
.card p.clip {
  margin: 0;
  font-size: 0.95rem;
  line-height: 1.5;
  color: rgba(20, 32, 27, 0.72);
}
.card .clip {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 1;
  line-clamp: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: normal;
  word-break: break-all;
  overflow-wrap: anywhere;
  min-width: 0;
  max-width: 100%;
  flex: 0 0 auto;
}
.body {
  margin: 0.5rem 0 0;
  line-height: 1.7;
  color: rgba(20, 32, 27, 0.8);
  white-space: pre-wrap;
}
.edit-actions {
  display: flex;
  gap: 0.6rem;
  flex-wrap: wrap;
}
.error {
  margin: 0;
  color: var(--danger);
  font-size: 0.9rem;
}

.muse-focus {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  width: 100%;
  overflow: hidden;
  box-sizing: border-box;
  padding: 0.35rem 0.15rem 0.2rem;
  animation: focus-in 0.28s ease;
}
@keyframes focus-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
.focus-head {
  flex-shrink: 0;
  margin-bottom: 0.65rem;
}
.focus-head .back {
  border: 0;
  background: transparent;
  padding: 0;
  margin-bottom: 0.35rem;
  color: var(--moss-deep);
  font-size: 0.95rem;
}
.focus-head h1 {
  margin: 0;
  font-size: clamp(1.6rem, 3.5vw, 2.1rem);
}
.focus-scroll {
  flex: 1;
  min-height: 0;
  overflow: auto;
  overscroll-behavior: contain;
}
.focus-card {
  padding: 1rem 1.15rem 1.25rem;
  border: 1px solid var(--line);
  border-radius: 16px;
  background: var(--card);
}
.focus-form {
  display: grid;
  gap: 0.75rem;
  margin-top: 0.85rem;
}
.focus-form.create {
  margin-top: 0;
}
.focus-form textarea.grow {
  min-height: 12rem;
  resize: vertical;
}
.focus-form textarea.append {
  min-height: 8rem;
}
.focus-card h2 {
  margin: 0.45rem 0 0;
  font-family: var(--font-display);
  font-weight: 500;
  font-size: 1.5rem;
  white-space: normal;
  overflow: visible;
  text-overflow: unset;
}
.focus-card .body {
  margin-top: 0.5rem;
}
@media (max-width: 700px) {
  .head-row {
    flex-direction: column;
    align-items: stretch;
  }
  .card {
    min-height: 0;
  }
  .card .actions {
    display: none;
  }
  .composer,
  .editor {
    padding-inline: 0.15rem;
  }
  .focus-card {
    max-height: calc(100dvh - 7rem - var(--tabbar-h, 0px));
  }
}
</style>
