<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import api from '../api/client'
import { useI18n } from '../i18n'
import { useAuthStore } from '../stores/auth'
import type { User } from '../types'
import { avatarSrc, compressImageFile } from '../utils/compressImage'
import { formatApiError } from '../utils/apiError'

const auth = useAuthStore()
const router = useRouter()
const { t } = useI18n()

const editingProfile = ref(false)
const editingPassword = ref(false)

const nickname = ref('')
const bio = ref('')
const allowRequests = ref(true)
const showEmail = ref(false)
const showJoinDate = ref(true)
const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const msg = ref('')
const err = ref('')
const avatarBusy = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

const preview = computed(() => avatarSrc(auth.user?.avatar_url))
const displayName = computed(() => auth.user?.nickname || auth.user?.name || '')
const displayBio = computed(() => (auth.user?.bio || '').trim())
const displayEmail = computed(() => auth.user?.email || '')

function syncFromUser() {
  if (!auth.user) return
  nickname.value = auth.user.nickname || auth.user.name
  bio.value = auth.user.bio || ''
  allowRequests.value = auth.user.allow_message_requests ?? true
  showEmail.value = auth.user.show_email ?? false
  showJoinDate.value = auth.user.show_join_date ?? true
}

onMounted(syncFromUser)

function startEditProfile() {
  syncFromUser()
  msg.value = ''
  err.value = ''
  editingPassword.value = false
  editingProfile.value = true
}

function cancelEditProfile() {
  syncFromUser()
  editingProfile.value = false
  msg.value = ''
  err.value = ''
}

function startEditPassword() {
  oldPassword.value = ''
  newPassword.value = ''
  confirmPassword.value = ''
  msg.value = ''
  err.value = ''
  editingProfile.value = false
  editingPassword.value = true
}

function cancelEditPassword() {
  oldPassword.value = ''
  newPassword.value = ''
  confirmPassword.value = ''
  editingPassword.value = false
  msg.value = ''
  err.value = ''
}

function yn(v: boolean) {
  return v ? t('profile.yes') : t('profile.no')
}

async function saveProfile() {
  msg.value = ''
  err.value = ''
  try {
    const { data } = await api.patch<User>('/api/users/me', {
      nickname: nickname.value.trim(),
      bio: bio.value.trim(),
      allow_message_requests: allowRequests.value,
      show_email: showEmail.value,
      show_join_date: showJoinDate.value,
    })
    auth.setUser(data)
    msg.value = t('profile.saved')
    editingProfile.value = false
  } catch (e: any) {
    err.value = formatApiError(e, t('common.saveFail'))
  }
}

async function changePassword() {
  msg.value = ''
  err.value = ''
  try {
    await api.post('/api/auth/change-password', {
      old_password: oldPassword.value,
      new_password: newPassword.value,
      confirm_password: confirmPassword.value,
    })
    msg.value = t('profile.pwChanged')
    auth.logout()
    router.push('/login')
  } catch (e: any) {
    err.value = formatApiError(e, t('common.fail'))
  }
}

async function onPickAvatar(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  msg.value = ''
  err.value = ''
  avatarBusy.value = true
  try {
    const blob = await compressImageFile(file, { maxEdge: 512, maxBytes: 280 * 1024 })
    const form = new FormData()
    form.append('file', blob, 'avatar.jpg')
    const { data } = await api.post<User>('/api/users/me/avatar', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    auth.setUser(data)
    msg.value = t('profile.avatarSaved', {
      size: Math.max(1, Math.round(blob.size / 1024)),
    })
  } catch (e: any) {
    if (e?.message === 'NOT_IMAGE') err.value = t('profile.avatarNotImage')
    else err.value = formatApiError(e, t('profile.avatarFail'))
  } finally {
    avatarBusy.value = false
  }
}

async function clearAvatar() {
  msg.value = ''
  err.value = ''
  avatarBusy.value = true
  try {
    const { data } = await api.delete<User>('/api/users/me/avatar')
    auth.setUser(data)
    msg.value = t('profile.avatarRemoved')
  } catch (e: any) {
    err.value = formatApiError(e, t('profile.avatarFail'))
  } finally {
    avatarBusy.value = false
  }
}
</script>

<template>
  <main class="container page">
    <header class="top">
      <h1>{{ t('profile.title') }}</h1>
    </header>

    <!-- 只读资料 -->
    <section v-if="!editingProfile" class="box">
      <div class="avatar-row">
        <div class="avatar-preview">
          <img v-if="preview" :src="preview" alt="" />
          <span v-else>{{ (displayName || 'Z').slice(0, 1) }}</span>
        </div>
        <div class="avatar-actions">
          <p class="avatar-label">{{ t('profile.avatar') }}</p>
          <p class="hint">{{ preview ? t('profile.avatarSet') : t('profile.avatarEmpty') }}</p>
        </div>
      </div>

      <div class="read-item">
        <span class="k">{{ t('profile.nickname') }}</span>
        <span class="v">{{ displayName || '—' }}</span>
      </div>
      <div class="read-item">
        <span class="k">{{ t('profile.email') }}</span>
        <span class="v">{{ displayEmail || '—' }}</span>
      </div>
      <div class="read-item block">
        <span class="k">{{ t('profile.bio') }}</span>
        <p class="v bio">{{ displayBio || t('profile.bioEmpty') }}</p>
      </div>
      <div class="read-item">
        <span class="k">{{ t('profile.allowRequests') }}</span>
        <span class="v">{{ yn(!!auth.user?.allow_message_requests) }}</span>
      </div>
      <div class="read-item">
        <span class="k">{{ t('profile.showEmail') }}</span>
        <span class="v">{{ yn(!!auth.user?.show_email) }}</span>
      </div>
      <div class="read-item">
        <span class="k">{{ t('profile.showJoin') }}</span>
        <span class="v">{{ yn(auth.user?.show_join_date !== false) }}</span>
      </div>
      <button class="btn primary edit-profile" type="button" @click="startEditProfile">
        {{ t('profile.edit') }}
      </button>
    </section>

    <!-- 编辑资料 -->
    <section v-else class="box">
      <div class="avatar-row">
        <div class="avatar-preview">
          <img v-if="preview" :src="preview" alt="" />
          <span v-else>{{ (nickname || 'Z').slice(0, 1) }}</span>
        </div>
        <div class="avatar-actions">
          <p class="avatar-label">{{ t('profile.avatar') }}</p>
          <p class="hint">{{ t('profile.avatarHint') }}</p>
          <div class="row">
            <button
              class="btn primary"
              type="button"
              :disabled="avatarBusy"
              @click="fileInput?.click()"
            >
              {{
                avatarBusy
                  ? t('profile.avatarUploading')
                  : preview
                    ? t('profile.avatarChange')
                    : t('profile.avatarUpload')
              }}
            </button>
            <button
              v-if="preview"
              class="btn ghost"
              type="button"
              :disabled="avatarBusy"
              @click="clearAvatar"
            >
              {{ t('profile.avatarRemove') }}
            </button>
          </div>
          <input
            ref="fileInput"
            type="file"
            accept="image/jpeg,image/png,image/webp,image/gif"
            hidden
            @change="onPickAvatar"
          />
        </div>
      </div>

      <div class="field">
        <label>{{ t('profile.nickname') }}</label>
        <input v-model="nickname" maxlength="30" />
      </div>
      <div class="field">
        <label>{{ t('profile.bio') }}</label>
        <textarea v-model="bio" rows="3" maxlength="500" />
      </div>
      <label class="check"><input v-model="allowRequests" type="checkbox" /> {{ t('profile.allowRequests') }}</label>
      <label class="check"><input v-model="showEmail" type="checkbox" /> {{ t('profile.showEmail') }}</label>
      <label class="check"><input v-model="showJoinDate" type="checkbox" /> {{ t('profile.showJoin') }}</label>
      <div class="row">
        <button class="btn primary" type="button" @click="saveProfile">{{ t('profile.save') }}</button>
        <button class="btn ghost" type="button" @click="cancelEditProfile">{{ t('profile.cancel') }}</button>
      </div>
    </section>

    <!-- 密码：默认只读入口 -->
    <section class="box">
      <div class="pw-head">
        <h2>{{ t('profile.password') }}</h2>
        <button
          v-if="!editingPassword"
          class="btn ghost"
          type="button"
          @click="startEditPassword"
        >
          {{ t('profile.changePassword') }}
        </button>
      </div>

      <template v-if="!editingPassword">
        <p class="hint">{{ t('profile.passwordHint') }}</p>
        <p class="hint">
          {{ t('profile.forgotHint') }}
          <RouterLink class="link" :to="{ name: 'forgot', query: { email: displayEmail } }">
            {{ t('profile.forgotLink') }}
          </RouterLink>
        </p>
      </template>

      <template v-else>
        <div class="field">
          <label>{{ t('profile.oldPassword') }}</label>
          <input v-model="oldPassword" type="password" autocomplete="current-password" />
        </div>
        <div class="field">
          <label>{{ t('profile.newPassword') }}</label>
          <input v-model="newPassword" type="password" autocomplete="new-password" />
        </div>
        <div class="field">
          <label>{{ t('profile.confirmPassword') }}</label>
          <input v-model="confirmPassword" type="password" autocomplete="new-password" />
        </div>
        <div class="row">
          <button class="btn primary" type="button" @click="changePassword">{{ t('profile.changePassword') }}</button>
          <button class="btn ghost" type="button" @click="cancelEditPassword">{{ t('profile.cancel') }}</button>
        </div>
        <p class="hint">
          {{ t('profile.forgotHint') }}
          <RouterLink class="link" :to="{ name: 'forgot', query: { email: displayEmail } }">
            {{ t('profile.forgotLink') }}
          </RouterLink>
        </p>
      </template>
    </section>

    <p v-if="msg" class="ok">{{ msg }}</p>
    <p v-if="err" class="error">{{ err }}</p>
  </main>
</template>

<style scoped>
.page {
  padding: 2.4rem 0;
  max-width: 640px;
  display: grid;
  gap: 1rem;
}
.top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
}
h1,
h2 {
  margin: 0;
  font-family: var(--font-display);
  font-weight: 500;
}
.box {
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 1rem;
  background: var(--card);
  display: grid;
  gap: 0.7rem;
}
.avatar-row {
  display: flex;
  gap: 1rem;
  align-items: center;
  padding-bottom: 0.35rem;
  border-bottom: 1px solid var(--line);
  margin-bottom: 0.2rem;
}
.avatar-preview {
  width: 5.2rem;
  height: 5.2rem;
  border-radius: 50%;
  overflow: hidden;
  display: grid;
  place-items: center;
  background: rgba(47, 111, 94, 0.14);
  color: var(--moss-deep);
  font-family: var(--font-display);
  font-size: 1.6rem;
  flex-shrink: 0;
  border: 1px solid var(--line);
}
.avatar-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.avatar-actions {
  display: grid;
  gap: 0.35rem;
  min-width: 0;
}
.avatar-label {
  margin: 0;
  font-weight: 600;
}
.hint {
  margin: 0;
  font-size: 0.82rem;
  color: rgba(20, 32, 27, 0.55);
  line-height: 1.45;
}
.link {
  color: var(--moss-deep);
  font-weight: 600;
}
.row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}
.read-item {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: baseline;
  padding: 0.15rem 0;
}
.read-item.block {
  flex-direction: column;
  gap: 0.25rem;
}
.k {
  color: rgba(20, 32, 27, 0.55);
  font-size: 0.9rem;
  flex-shrink: 0;
}
.v {
  color: var(--ink);
  text-align: right;
  word-break: break-word;
}
.read-item.block .v {
  text-align: left;
}
.bio {
  margin: 0;
  white-space: pre-wrap;
  line-height: 1.6;
  color: rgba(20, 32, 27, 0.82);
}
.check {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  color: rgba(20, 32, 27, 0.75);
}
.pw-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
}
.ok {
  color: var(--moss-deep);
  margin: 0;
}
.error {
  color: var(--danger);
  margin: 0;
}
.edit-profile {
  margin-top: 0.35rem;
  justify-self: start;
}
@media (max-width: 800px) {
  .page {
    padding: 1.35rem 0 1.75rem;
    gap: 0.95rem;
  }
  h1 {
    font-size: 1.85rem;
  }
  h2 {
    font-size: 1.4rem;
  }
  .box {
    padding: 1.05rem;
    gap: 0.85rem;
  }
  .avatar-label {
    font-size: 1.08rem;
  }
  .hint {
    font-size: 0.95rem;
    line-height: 1.55;
  }
  .k {
    font-size: 1rem;
  }
  .v {
    font-size: 1.05rem;
  }
  .edit-profile {
    width: 100%;
    justify-self: stretch;
    margin-top: 0.55rem;
    font-size: 1rem;
  }
  .pw-head {
    flex-direction: column;
    align-items: stretch;
    gap: 0.65rem;
  }
  .pw-head .btn {
    width: 100%;
    font-size: 1rem;
  }
  .check {
    font-size: 1rem;
  }
}
@media (max-width: 560px) {
  .top {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
