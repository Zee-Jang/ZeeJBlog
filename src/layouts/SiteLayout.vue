<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import api from '../api/client'
import { useI18n } from '../i18n'
import { useAuthStore } from '../stores/auth'
import type { AppLocale } from '../stores/locale'
import type { ChatRequest, ChatThread, NotificationItem } from '../types'
import { shanghaiYear } from '../utils/time'
import { avatarSrc } from '../utils/compressImage'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const { t, locale, setLocale } = useI18n()
const notifUnread = ref(0)
const socialBadge = ref(0)
const menuOpen = ref(false)
const langOpen = ref(false)
const isSocial = computed(() => route.name === 'social' || route.path === '/social')
const extraViewportLock = ref(false)
const isLocked = computed(() => isSocial.value || extraViewportLock.value)
const myAvatar = computed(() => avatarSrc(auth.user?.avatar_url))
let timer: number | undefined

function onViewportLock(e: Event) {
  const detail = (e as CustomEvent).detail
  extraViewportLock.value = detail === true || detail === 'on'
}

const langOptions: { code: AppLocale; name: string }[] = [
  { code: 'zh-CN', name: '简体中文' },
  { code: 'zh-TW', name: '繁體中文' },
  { code: 'en', name: 'English' },
  { code: 'ja', name: '日本語' },
]

async function loadBadges() {
  try {
    const [notifs, threads, received] = await Promise.all([
      api.get<NotificationItem[]>('/api/notifications'),
      api.get<ChatThread[]>('/api/chat/threads'),
      api.get<ChatRequest[]>('/api/chat-requests/received'),
    ])
    notifUnread.value = notifs.data.filter(
      (n) =>
        !n.is_read &&
        !['chat_request', 'chat_accepted', 'chat_rejected', 'new_message'].includes(n.type),
    ).length
    const pending = received.data.filter((r) => r.status === 'pending').length
    const unreadMsg = threads.data.reduce((n, t) => n + (t.unread_count || 0), 0)
    socialBadge.value = pending + unreadMsg
  } catch {
    notifUnread.value = 0
    socialBadge.value = 0
  }
}

function toggleMenu() {
  langOpen.value = false
  menuOpen.value = !menuOpen.value
  if (menuOpen.value) {
    void nextTick(() => {
      refreshOpenMenus()
      requestAnimationFrame(() => refreshOpenMenus())
    })
  }
}
function toggleLang() {
  menuOpen.value = false
  langOpen.value = !langOpen.value
  if (langOpen.value) {
    void nextTick(() => {
      refreshOpenMenus()
      requestAnimationFrame(() => refreshOpenMenus())
    })
  }
}

function logout() {
  menuOpen.value = false
  auth.logout()
  router.push('/login')
}

function pickLang(code: AppLocale) {
  setLocale(code)
  langOpen.value = false
}

function onDocClick(e: MouseEvent) {
  const el = e.target as HTMLElement | null
  if (!el?.closest('.account') && !el?.closest('.account-drop')) menuOpen.value = false
  if (!el?.closest('.lang') && !el?.closest('.lang-drop')) langOpen.value = false
}

const welcomeOpen = ref(false)
const welcomeVisible = ref(false)
const chatImmersive = ref(false)
const langBtnEl = ref<HTMLElement | null>(null)
const accountBtnEl = ref<HTMLElement | null>(null)
const langMenuStyle = ref<Record<string, string>>({})
const accountMenuStyle = ref<Record<string, string>>({})

function placeMenu(
  el: HTMLElement | null,
  align: 'left' | 'right',
  menuEl?: HTMLElement | null,
): Record<string, string> {
  if (!el) return { visibility: 'hidden' }
  const r = el.getBoundingClientRect()
  const vv = window.visualViewport
  const vvLeft = vv?.offsetLeft ?? 0
  const vw = vv?.width ?? window.innerWidth
  const margin = 10
  const top = Math.round(r.bottom + 6)
  const maxW = Math.min(17.5 * 16, vw - margin * 2)
  const menuW = Math.min(maxW, Math.max(menuEl?.offsetWidth || 0, 9.5 * 16))

  let left: number
  if (align === 'right') {
    left = r.right - menuW
  } else {
    left = r.left
  }
  left = Math.max(vvLeft + margin, Math.min(left, vvLeft + vw - menuW - margin))

  return {
    position: 'fixed',
    top: `${top}px`,
    left: `${Math.round(left)}px`,
    right: 'auto',
    zIndex: '200',
    width: 'max-content',
    maxWidth: `${Math.round(maxW)}px`,
    visibility: 'visible',
  }
}

function refreshOpenMenus() {
  if (langOpen.value) {
    const menu = document.querySelector('.portal-menu.lang-drop') as HTMLElement | null
    langMenuStyle.value = placeMenu(langBtnEl.value, 'left', menu)
  }
  if (menuOpen.value) {
    const menu = document.querySelector('.portal-menu.account-drop') as HTMLElement | null
    accountMenuStyle.value = placeMenu(accountBtnEl.value, 'right', menu)
  }
}

function onChatImmersive(e: Event) {
  chatImmersive.value = (e as CustomEvent).detail === true || (e as CustomEvent).detail === 'on'
  if (chatImmersive.value) {
    menuOpen.value = false
    langOpen.value = false
  } else {
    // 退出会话全屏时强制复位，避免上方大块空白
    onViewportResume()
  }
  syncVisualViewport()
}

function onViewportReset() {
  onViewportResume()
}

function maybeShowWelcome() {
  if (!auth.user) return
  const id = auth.user.id
  try {
    const pending = localStorage.getItem(`zeej_need_welcome_${id}`) === '1'
    const once = sessionStorage.getItem('zeej_greet_once') === '1'
    if (!pending || !once) return
    sessionStorage.removeItem('zeej_greet_once')
  } catch {
    return
  }
  welcomeOpen.value = true
  requestAnimationFrame(() => {
    welcomeVisible.value = true
  })
}

function dismissWelcome() {
  const id = auth.user?.id
  if (id) {
    try {
      localStorage.removeItem(`zeej_need_welcome_${id}`)
    } catch {
      /* ignore */
    }
  }
  welcomeVisible.value = false
  window.setTimeout(() => {
    welcomeOpen.value = false
  }, 900)
}

function resetPageScroll() {
  window.scrollTo(0, 0)
  document.documentElement.scrollTop = 0
  document.body.scrollTop = 0
}

function syncVisualViewport() {
  const root = document.documentElement
  const vv = window.visualViewport
  const focused = root.classList.contains('input-focus')
  const vvHeight = Math.round(vv?.height ?? window.innerHeight)
  const vvTop = Math.round(vv?.offsetTop ?? 0)
  const layoutH = Math.max(
    window.innerHeight || 0,
    document.documentElement.clientHeight || 0,
  )
  const inset = Math.max(0, Math.round(layoutH - vvHeight - vvTop))
  const keyboardOpen = focused && inset > 80
  root.classList.toggle('keyboard-open', keyboardOpen)

  // 键盘弹出时不要把整页缩到 vvHeight（会在输入框和键盘之间留出大缝）
  // 只记录 inset，由输入栏 fixed bottom 贴住键盘
  if (!focused) resetPageScroll()
  root.style.setProperty('--app-height', `${layoutH || vvHeight}px`)
  root.style.setProperty('--keyboard-inset', keyboardOpen ? `${inset}px` : '0px')
  root.style.setProperty('--vv-top', '0px')
}

function onFocusIn(e: FocusEvent) {
  const t = e.target as HTMLElement | null
  if (!t) return
  const tag = t.tagName
  if (tag !== 'TEXTAREA' && tag !== 'INPUT' && !t.isContentEditable) return
  if (!window.matchMedia('(max-width: 800px)').matches) return
  document.documentElement.classList.add('input-focus')
  const bump = () => {
    resetPageScroll()
    syncVisualViewport()
  }
  window.setTimeout(bump, 40)
  window.setTimeout(bump, 280)
}

function onFocusOut() {
  window.setTimeout(() => {
    const a = document.activeElement as HTMLElement | null
    const still =
      !!a &&
      (a.tagName === 'TEXTAREA' || a.tagName === 'INPUT' || a.isContentEditable)
    if (!still) document.documentElement.classList.remove('input-focus')
    resetPageScroll()
    syncVisualViewport()
  }, 0)
  window.setTimeout(() => {
    if (!document.documentElement.classList.contains('input-focus')) {
      resetPageScroll()
      syncVisualViewport()
    }
  }, 350)
}

function onViewportResume() {
  const a = document.activeElement as HTMLElement | null
  const typing =
    !!a && (a.tagName === 'TEXTAREA' || a.tagName === 'INPUT' || a.isContentEditable)
  if (!typing) {
    document.documentElement.classList.remove('input-focus', 'keyboard-open')
  }
  resetPageScroll()
  syncVisualViewport()
}

function onVisibilityChange() {
  if (document.visibilityState === 'visible') onViewportResume()
}

onMounted(() => {
  void loadBadges()
  timer = window.setInterval(() => void loadBadges(), 8000)
  document.addEventListener('click', onDocClick)
  window.addEventListener('zeej:notifs-changed', onNotifsChanged)
  window.addEventListener('zeej:viewport-lock', onViewportLock)
  window.addEventListener('zeej:chat-immersive', onChatImmersive)
  window.addEventListener('zeej:viewport-reset', onViewportReset)
  document.addEventListener('focusin', onFocusIn)
  document.addEventListener('focusout', onFocusOut)
  document.addEventListener('visibilitychange', onVisibilityChange)
  window.addEventListener('pageshow', onViewportResume)
  syncVisualViewport()
  window.visualViewport?.addEventListener('resize', syncVisualViewport)
  window.visualViewport?.addEventListener('scroll', syncVisualViewport)
  window.addEventListener('resize', syncVisualViewport)
  window.addEventListener('scroll', refreshOpenMenus, true)
  window.visualViewport?.addEventListener('resize', refreshOpenMenus)
  window.visualViewport?.addEventListener('scroll', refreshOpenMenus)
  window.setTimeout(maybeShowWelcome, 280)
})
onUnmounted(() => {
  if (timer) window.clearInterval(timer)
  document.removeEventListener('click', onDocClick)
  window.removeEventListener('zeej:notifs-changed', onNotifsChanged)
  window.removeEventListener('zeej:viewport-lock', onViewportLock)
  window.removeEventListener('zeej:chat-immersive', onChatImmersive)
  window.removeEventListener('zeej:viewport-reset', onViewportReset)
  document.removeEventListener('focusin', onFocusIn)
  document.removeEventListener('focusout', onFocusOut)
  document.removeEventListener('visibilitychange', onVisibilityChange)
  window.removeEventListener('pageshow', onViewportResume)
  window.visualViewport?.removeEventListener('resize', syncVisualViewport)
  window.visualViewport?.removeEventListener('scroll', syncVisualViewport)
  window.removeEventListener('resize', syncVisualViewport)
  window.removeEventListener('scroll', refreshOpenMenus, true)
  window.visualViewport?.removeEventListener('resize', refreshOpenMenus)
  window.visualViewport?.removeEventListener('scroll', refreshOpenMenus)
  document.documentElement.classList.remove('no-page-scroll', 'keyboard-open', 'input-focus')
  document.body.classList.remove('no-page-scroll')
  document.documentElement.style.removeProperty('--app-height')
  document.documentElement.style.removeProperty('--vv-top')
  document.documentElement.style.removeProperty('--keyboard-inset')
})

function onNotifsChanged() {
  void loadBadges()
}

watch(
  isLocked,
  (locked) => {
    document.documentElement.classList.toggle('no-page-scroll', locked)
    document.body.classList.toggle('no-page-scroll', locked)
    if (!locked) extraViewportLock.value = false
  },
  { immediate: true },
)

function isMusesRoute(name: unknown) {
  return name === 'muses' || name === 'muse-detail'
}

function clearStuckFocusUi() {
  const a = document.activeElement as HTMLElement | null
  if (a && (a.tagName === 'INPUT' || a.tagName === 'TEXTAREA' || a.isContentEditable)) {
    a.blur()
  }
  document.documentElement.classList.remove('input-focus', 'keyboard-open')
  syncVisualViewport()
}

function onTabbarNavigate() {
  clearStuckFocusUi()
  menuOpen.value = false
  langOpen.value = false
  chatImmersive.value = false
}

watch(
  () => route.name,
  (name, prev) => {
    // 离开碎碎念（含详情）时清锁；列表↔详情切换保留锁定
    if (isMusesRoute(prev) && !isMusesRoute(name)) extraViewportLock.value = false
    clearStuckFocusUi()
  },
)
</script>

<template>
  <div
    class="app"
    :class="{ locked: isLocked, home: route.name === 'home', immersive: chatImmersive }"
  >
    <div class="atmosphere" aria-hidden="true" />
    <Teleport to="body">
      <div v-if="welcomeOpen" class="welcome-layer" :class="{ on: welcomeVisible }">
        <div class="welcome-card">
          <p class="welcome-brand">Zeej</p>
          <h2>{{ t('home.hello', { name: auth.displayName }) }}</h2>
          <p class="welcome-sub">{{ t('home.welcomeOnce') }}</p>
          <button class="btn primary" type="button" @click="dismissWelcome">
            {{ t('home.welcomeContinue') }}
          </button>
        </div>
      </div>
    </Teleport>

    <header class="site-header">
      <div class="container inner">
        <RouterLink class="brand" to="/">Zeej<span>.</span></RouterLink>
        <nav class="nav desktop-nav" aria-label="primary">
          <RouterLink to="/" :class="{ 'nav-current': route.name === 'home' }">
            {{ t('nav.home') }}
          </RouterLink>
          <RouterLink
            to="/muses"
            :class="{ 'nav-current': route.name === 'muses' }"
          >
            {{ t('nav.musesGuest') }}
          </RouterLink>
          <RouterLink
            to="/projects"
            :class="{ 'nav-current': route.name === 'projects' || route.name === 'project-detail' }"
          >
            {{ t('nav.projects') }}
          </RouterLink>
          <RouterLink to="/social" class="bell" :class="{ 'nav-current': route.name === 'social' }">
            {{ t('nav.social') }}
            <em v-if="socialBadge">{{ socialBadge }}</em>
          </RouterLink>
          <RouterLink
            v-if="auth.isAdmin"
            to="/admin"
            :class="{ 'nav-current': route.name === 'admin' }"
          >
            {{ t('nav.admin') }}
          </RouterLink>
        </nav>
        <div class="right">
          <div class="lang">
            <button ref="langBtnEl" type="button" class="lang-btn" @click.stop="toggleLang">
              {{ langOptions.find((o) => o.code === locale)?.name || t('nav.lang') }}
              <span class="caret">▾</span>
            </button>
          </div>

          <div class="account">
            <button ref="accountBtnEl" type="button" class="account-btn" @click.stop="toggleMenu">
              <span class="avatar">
                <img v-if="myAvatar" :src="myAvatar" alt="" />
                <template v-else>{{ (auth.displayName || 'Z').slice(0, 1) }}</template>
              </span>
              <span class="name">{{ auth.displayName }}</span>
              <em v-if="notifUnread" class="dot">{{ notifUnread }}</em>
              <span class="caret">▾</span>
            </button>
          </div>

          <button type="button" class="linkish logout-desktop" @click="logout">{{ t('nav.logout') }}</button>
        </div>
      </div>
    </header>

    <Teleport to="body">
      <div
        v-show="langOpen"
        class="dropdown-wrap lang-drop portal-menu"
        :style="langMenuStyle"
        @click.stop
      >
        <div class="dropdown">
          <button
            v-for="opt in langOptions"
            :key="opt.code"
            type="button"
            :class="{ on: locale === opt.code }"
            @click="pickLang(opt.code)"
          >
            {{ opt.name }}
          </button>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-show="menuOpen"
        class="dropdown-wrap account-drop portal-menu"
        :style="accountMenuStyle"
        @click.stop
      >
        <div class="dropdown">
          <p class="drop-label">{{ t('nav.menu') }}</p>
          <RouterLink to="/notifications" class="drop-item bell" @click="menuOpen = false">
            {{ t('nav.notifications') }}
            <em v-if="notifUnread">{{ notifUnread }}</em>
          </RouterLink>
          <RouterLink to="/profile" class="drop-item" @click="menuOpen = false">
            {{ t('nav.profile') }}
          </RouterLink>
          <RouterLink
            :to="auth.isAdmin ? '/admin?panel=myInvites' : '/invites'"
            class="drop-item"
            @click="menuOpen = false"
          >
            {{ t('nav.myInvites') }}
          </RouterLink>
          <RouterLink
            v-if="auth.isAdmin"
            to="/admin"
            class="drop-item"
            @click="menuOpen = false"
          >
            {{ t('nav.admin') }}
          </RouterLink>
          <RouterLink
            v-if="auth.isAdmin"
            to="/admin?panel=batchInvites"
            class="drop-item"
            @click="menuOpen = false"
          >
            {{ t('nav.adminInvites') }}
          </RouterLink>
          <button type="button" class="drop-item danger" @click="logout">
            {{ t('nav.logout') }}
          </button>
        </div>
      </div>
    </Teleport>

    <div class="main-slot">
      <div class="main-slot-inner" :class="{ locked: isLocked }">
        <RouterView v-slot="{ Component }">
          <Transition name="fade" mode="out-in">
            <component
              :is="Component"
              :key="route.name === 'muse-detail' || route.name === 'muses' ? 'muses-shell' : route.fullPath"
            />
          </Transition>
        </RouterView>
      </div>
    </div>

    <footer class="site-footer" :class="{ compact: isLocked }">
      <div class="container">© {{ shanghaiYear() }} Zeej · {{ t('footer.invite') }}</div>
    </footer>

    <!-- 手机底栏：电脑端隐藏，同一套路由 -->
    <nav class="tabbar" aria-label="mobile" @pointerdown.capture="onTabbarNavigate">
      <RouterLink to="/" :class="{ on: route.name === 'home' }">
        <span class="tab-label">{{ t('nav.home') }}</span>
      </RouterLink>
      <RouterLink
        to="/muses"
        :class="{ on: isMusesRoute(route.name) }"
      >
        <span class="tab-label">{{ t('nav.musesShort') }}</span>
      </RouterLink>
      <RouterLink
        to="/projects"
        :class="{ on: route.name === 'projects' || route.name === 'project-detail' }"
      >
        <span class="tab-label">{{ t('nav.projects') }}</span>
      </RouterLink>
      <RouterLink to="/social" class="bell" :class="{ on: route.name === 'social' }">
        <span class="tab-label">{{ t('nav.social') }}</span>
        <em v-if="socialBadge">{{ socialBadge > 99 ? '99+' : socialBadge }}</em>
      </RouterLink>
      <RouterLink
        to="/profile"
        class="bell"
        :class="{
          on:
            route.name === 'profile' ||
            route.name === 'notifications' ||
            route.name === 'invites' ||
            route.name === 'admin',
        }"
      >
        <span class="tab-label">{{ t('nav.me') }}</span>
        <em v-if="notifUnread">{{ notifUnread > 99 ? '99+' : notifUnread }}</em>
      </RouterLink>
    </nav>
  </div>
</template>

<style scoped>
.app {
  position: relative;
  isolation: isolate;
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
  width: 100%;
  max-width: 100%;
  overflow-x: clip;
}
/* 非主页：顶部淡绿氛围，与主页 hero 同色系、更克制 */
.atmosphere {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background:
    radial-gradient(ellipse 85% 42% at 18% -8%, rgba(47, 111, 94, 0.16), transparent 60%),
    radial-gradient(ellipse 55% 35% at 92% 12%, rgba(127, 168, 148, 0.14), transparent 55%),
    linear-gradient(180deg, rgba(221, 232, 226, 0.55) 0%, transparent 28%);
  opacity: 1;
  transition: opacity 0.35s ease;
}
.app.home .atmosphere {
  /* 主页交给 hero-plane，避免叠两层过重 */
  opacity: 0;
}
.site-header {
  position: relative;
  z-index: 30;
  flex-shrink: 0;
}
.main-slot {
  position: relative;
  z-index: 1;
  flex: 1 0 auto;
}
.site-footer {
  position: relative;
  z-index: 1;
  flex-shrink: 0;
  margin-top: auto;
}
.app.locked {
  /* 用 visualViewport 高度，避免 iOS 软键盘把 fixed 底栏顶飞 */
  height: var(--app-height, 100dvh);
  max-height: var(--app-height, 100dvh);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.app.locked .main-slot {
  flex: 1 1 auto;
  min-height: 0;
  height: auto;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  /* 与碎碎念类似：偏上适中；给约 800px 高度留出空间 */
  padding: clamp(1.1rem, 2.6vh, 1.75rem) 0.75rem 0.65rem;
}
.app.locked .main-slot-inner.locked {
  flex: 1 1 auto;
  min-height: 0;
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
}
.app.locked .main-slot-inner.locked :deep(.hub),
.app.locked .main-slot-inner.locked :deep(.muses-root.locked) {
  flex: 0 0 auto;
  width: min(980px, 100%);
  /* 目标高度约 800px；矮屏自动吃满剩余高度 */
  height: min(800px, calc(100% - 0.35rem));
  max-height: 100%;
  min-height: 0;
  margin: 0;
}
.app.locked .main-slot-inner.locked :deep(.muses-root.locked) {
  width: min(720px, 100%);
}
.app.locked .site-footer.compact {
  margin-top: 0;
  padding: 0.45rem 0 max(0.55rem, calc(env(safe-area-inset-bottom, 0px) + 0.3rem));
  border-top: 1px solid var(--line);
  flex-shrink: 0;
}
@media (max-height: 760px) {
  .app.locked .main-slot {
    padding-top: 0.7rem;
    padding-bottom: 0.45rem;
  }
  .app.locked .main-slot-inner.locked :deep(.hub),
  .app.locked .main-slot-inner.locked :deep(.muses-root.locked) {
    height: 100%;
  }
}
@media (min-height: 900px) {
  .app.locked .main-slot {
    padding-top: 1.75rem;
  }
  .app.locked .main-slot-inner.locked :deep(.hub),
  .app.locked .main-slot-inner.locked :deep(.muses-root.locked) {
    height: min(800px, calc(100% - 0.5rem));
  }
}
.tabbar {
  display: none;
}
@media (max-width: 800px) {
  .desktop-nav {
    display: none !important;
  }
  .site-header .inner {
    flex-wrap: nowrap;
  }
  .right {
    margin-left: auto;
  }
  .right .logout-desktop {
    display: none;
  }
  .name {
    display: none;
  }
  .account-btn {
    padding-inline: 0.35rem;
  }
  .tabbar {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 120;
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 0;
    min-height: var(--tabbar-h);
    padding: 0.2rem 0.15rem calc(0.2rem + env(safe-area-inset-bottom, 0px));
    border-top: 1px solid var(--line);
    background: rgba(238, 243, 239, 0.94);
    backdrop-filter: blur(14px);
    touch-action: manipulation;
  }
  /* 交流/碎碎念锁定页：整壳钉在可视区，底栏改为壳内绝对定位 */
  .app.locked {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    width: 100%;
  }
  .app.locked .tabbar {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
  }
  /* 交流详情：微信式全屏，隐藏站点顶栏/底栏 */
  .app.immersive .site-header,
  .app.immersive .tabbar {
    display: none !important;
  }
  .app.immersive.locked .main-slot {
    padding: 0 !important;
  }
  .app.immersive.locked .main-slot-inner.locked {
    justify-content: stretch;
  }
  .app.immersive.locked .main-slot-inner.locked :deep(.hub) {
    width: 100%;
    height: 100%;
    max-height: none;
    border-radius: 0;
    border: 0;
    box-shadow: none;
  }
  /* 仅键盘真正弹出时藏底栏；勿用 input-focus（易残留导致底栏点不动） */
  html.keyboard-open .tabbar {
    display: none !important;
  }
  html.keyboard-open .app.locked:not(.immersive) .site-header,
  html.input-focus .app.locked:not(.immersive) .site-header {
    display: none;
  }
  html.keyboard-open .app.locked:not(.immersive) .main-slot,
  html.input-focus .app.locked:not(.immersive) .main-slot {
    padding-top: 0.35rem;
    padding-bottom: 0.35rem;
  }
  html.keyboard-open .app.locked .main-slot-inner.locked :deep(.hub),
  html.input-focus .app.locked .main-slot-inner.locked :deep(.hub),
  html.keyboard-open .app.locked .main-slot-inner.locked :deep(.muses-root.locked),
  html.input-focus .app.locked .main-slot-inner.locked :deep(.muses-root.locked) {
    height: 100%;
    max-height: none;
  }
  .tabbar a {
    position: relative;
    display: grid;
    place-items: center;
    align-self: stretch;
    width: 100%;
    min-height: 3.1rem;
    height: 100%;
    padding: 0.35rem 0.1rem;
    color: rgba(20, 32, 27, 0.5);
    font-size: 0.84rem;
    font-weight: 500;
    text-align: center;
    line-height: 1.2;
    touch-action: manipulation;
    -webkit-tap-highlight-color: transparent;
  }
  .tabbar a.on {
    color: var(--moss-deep);
    font-weight: 700;
  }
  .tabbar a.on .tab-label {
    position: relative;
  }
  .tabbar a.on .tab-label::after {
    content: '';
    position: absolute;
    left: 50%;
    bottom: -0.28rem;
    width: 1rem;
    height: 2px;
    border-radius: 999px;
    background: var(--moss);
    transform: translateX(-50%);
  }
  .tabbar .bell em {
    position: absolute;
    top: 0.1rem;
    right: max(0.15rem, 12%);
    min-width: 0.95rem;
    height: 0.95rem;
    border-radius: 999px;
    background: var(--moss);
    color: #fff;
    font-style: normal;
    font-size: 0.62rem;
    display: grid;
    place-items: center;
    padding: 0 0.18rem;
  }
  .app.locked .main-slot {
    padding-top: 0.45rem;
    padding-inline: 0.4rem;
    /* 底栏 fixed，需给交流框留出高度，避免输入栏被挡住 */
    padding-bottom: calc(var(--tabbar-h) + env(safe-area-inset-bottom, 0px) + 0.35rem);
  }
  .app.locked .main-slot-inner.locked {
    justify-content: flex-start;
  }
  .app.locked .main-slot-inner.locked :deep(.hub),
  .app.locked .main-slot-inner.locked :deep(.muses-root.locked) {
    /* 相对主区域吃满，避免再用 100dvh 魔法偏移与底栏打架 */
    height: 100%;
    max-height: none;
    min-height: 0;
    width: 100%;
  }
  /* 手机有底栏，隐藏页脚版权条，避免叠在 tab 上方 */
  .site-footer {
    display: none !important;
  }
  .main-slot {
    padding-bottom: calc(var(--tabbar-h) + env(safe-area-inset-bottom, 0px) + 0.75rem);
  }
  .account-drop .dropdown {
    max-width: min(18rem, calc(100% - 1.25rem));
  }
  .lang-drop .dropdown {
    max-width: min(18rem, calc(100% - 1.25rem));
  }
  .site-header .inner,
  .right,
  .lang,
  .account {
    min-width: 0;
  }
  .lang-btn {
    max-width: 7.5rem;
    overflow: hidden;
  }
}
.right {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  margin-left: auto;
  min-width: 0;
}
.lang {
  position: relative;
  /* 与头像按钮间距约 1cm */
  margin-right: 0.75cm;
}
@media (max-width: 800px) {
  .lang {
    margin-right: 0.45rem;
  }
}
.account {
  position: relative;
}
.lang-btn,
.account-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.72);
  border-radius: 999px;
  padding: 0.35rem 0.7rem;
  cursor: pointer;
  color: var(--ink);
  font: inherit;
  font-size: 0.88rem;
}
.account-btn {
  padding-left: 0.35rem;
}
.avatar {
  width: 1.55rem;
  height: 1.55rem;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: rgba(47, 111, 94, 0.16);
  color: var(--moss-deep);
  font-family: var(--font-display);
  font-size: 0.85rem;
  overflow: hidden;
}
.avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.name {
  max-width: 7rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.caret {
  font-size: 0.7rem;
  opacity: 0.55;
}
.dot {
  min-width: 1rem;
  height: 1rem;
  border-radius: 999px;
  background: var(--moss);
  color: #fff;
  font-style: normal;
  font-size: 0.65rem;
  display: grid;
  place-items: center;
  padding: 0 0.2rem;
}
.dropdown-wrap {
  position: absolute;
  top: calc(100% + 6px);
  z-index: 50;
  width: max-content;
  max-width: min(18rem, calc(100vw - 1.25rem));
}
/* portal 菜单的 top/left 只由内联 style 控制，禁止写死 left:0 */
.dropdown-wrap.portal-menu {
  position: fixed;
  top: auto;
  left: auto;
  right: auto;
  z-index: 200;
}
.dropdown {
  width: max-content;
  min-width: 9.5rem;
  padding: 0.45rem 0.3rem 0.35rem;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 12px 28px rgba(20, 32, 27, 0.12);
  display: grid;
  gap: 0.1rem;
}
/* 非 portal 时：语言靠左展开；账户靠右展开 */
.lang-drop:not(.portal-menu) {
  left: 0;
  right: auto;
}
.account-drop:not(.portal-menu) {
  left: auto;
  right: 0;
}
.portal-menu.lang-drop,
.portal-menu.account-drop {
  left: auto;
  right: auto;
}
.drop-label {
  margin: 0.2rem 0.45rem 0.35rem;
  font-size: 0.72rem;
  letter-spacing: 0.06em;
  color: rgba(20, 32, 27, 0.45);
}
.drop-item,
.lang-drop button {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.65rem;
  border: 0;
  background: transparent;
  text-align: left;
  padding: 0.5rem 0.7rem;
  border-radius: 8px;
  cursor: pointer;
  color: var(--ink);
  font: inherit;
  font-size: 0.9rem;
  text-decoration: none;
  white-space: nowrap;
}
.drop-item:hover,
.lang-drop button:hover,
.lang-drop button.on {
  background: rgba(47, 111, 94, 0.1);
}
.drop-item.danger {
  color: var(--danger);
  margin-top: 0.25rem;
  border-top: 1px solid var(--line);
  border-radius: 0 0 8px 8px;
  width: 100%;
}
.linkish {
  border: 0;
  background: transparent;
  color: var(--moss-deep);
  cursor: pointer;
  font: inherit;
  font-size: 0.9rem;
  padding: 0.2rem 0.15rem;
}
.bell {
  position: relative;
}
.bell em,
.drop-item.bell em {
  min-width: 1rem;
  height: 1rem;
  border-radius: 999px;
  background: var(--moss);
  color: #fff;
  font-style: normal;
  font-size: 0.65rem;
  display: grid;
  place-items: center;
  padding: 0 0.2rem;
}
.nav .bell em {
  position: absolute;
  top: -0.45rem;
  right: -0.7rem;
}
@media (max-width: 900px) and (min-width: 801px) {
  .site-header .inner {
    flex-wrap: wrap;
  }
  .desktop-nav {
    order: 3;
    width: 100%;
  }
  .right {
    margin-left: 0;
  }
  .name {
    max-width: 4.5rem;
  }
}

.welcome-layer {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: grid;
  place-items: center;
  padding: 1.5rem;
  background: linear-gradient(160deg, #e8efea 0%, #f4f7f5 45%, #dfeae4 100%);
  opacity: 0;
  transition: opacity 0.9s ease;
}
.welcome-layer.on {
  opacity: 1;
}
.welcome-layer:not(.on) {
  pointer-events: none;
}
.welcome-card {
  width: min(380px, 100%);
  padding: 2.4rem 1.6rem 1.6rem;
  text-align: center;
  display: grid;
  gap: 0.85rem;
  transform: scale(0.96) translateY(18px);
  opacity: 0;
  transition:
    transform 1s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.9s ease;
}
.welcome-layer.on .welcome-card {
  transform: none;
  opacity: 1;
}
.welcome-brand {
  margin: 0;
  font-family: var(--font-display);
  font-size: 2.6rem;
  font-weight: 600;
  letter-spacing: -0.03em;
  color: var(--ink);
}
.welcome-card h2 {
  margin: 0;
  font-family: var(--font-display);
  font-weight: 500;
  font-size: 1.55rem;
}
.welcome-sub {
  margin: 0 0 0.5rem;
  color: rgba(20, 32, 27, 0.58);
  line-height: 1.6;
  font-size: 1rem;
}
</style>
