<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import api from '../api/client'
import { useI18n } from '../i18n'
import { useAuthStore } from '../stores/auth'
import type { Post } from '../types'
import { formatDateShanghai } from '../utils/time'

const auth = useAuthStore()
const router = useRouter()
const { t, locale } = useI18n()
const show = ref(false)
const posts = ref<Post[]>([])
const loading = ref(true)
const homeLead = ref('')

async function loadHomeLead() {
  try {
    const { data } = await api.get<{ home_lead: string }>('/api/site/home', {
      params: { locale: locale.value },
    })
    homeLead.value = (data.home_lead || '').trim() || t('home.lead')
  } catch {
    homeLead.value = t('home.lead')
  }
}

onMounted(async () => {
  requestAnimationFrame(() => {
    show.value = true
  })
  try {
    const [postsRes] = await Promise.all([
      api.get<Post[]>('/api/posts', { params: { on_home: true } }),
      loadHomeLead(),
    ])
    posts.value = postsRes.data.slice(0, 12)
  } catch {
    if (!homeLead.value) homeLead.value = t('home.lead')
  } finally {
    loading.value = false
  }
})

watch(locale, () => {
  void loadHomeLead()
})

function kindLabel(k: string) {
  return k === 'diary' ? t('muses.diary') : t('muses.muse')
}

/** 列表预览：压成单行，避免换行导致高度不齐或文字叠在一起 */
function previewText(s: string, max = 72) {
  const one = (s || '').replace(/\s+/g, ' ').trim()
  if (one.length <= max) return one
  return `${one.slice(0, max)}…`
}

function openPost(id: number) {
  router.push(`/muses/${id}`)
}
</script>

<template>
  <main>
    <section class="hero" :class="{ show }">
      <div class="hero-plane" aria-hidden="true" />
      <div class="container hero-copy">
        <p class="brand-line">Zeej</p>
        <h1>{{ t('home.welcome') }}</h1>
        <p class="lead">{{ homeLead }}</p>
        <div class="cta">
          <RouterLink
            v-if="(auth.user?.bot_rounds_limit ?? 0) > 0"
            class="btn primary"
            to="/social?bot=1"
          >
            {{ t('home.botCta') }}
          </RouterLink>
          <RouterLink class="btn ghost" to="/social">{{ t('home.zoneSocial') }}</RouterLink>
          <RouterLink class="btn ghost" to="/projects">{{ t('home.zoneProjects') }}</RouterLink>
          <RouterLink v-if="auth.isAdmin" class="btn ghost" to="/muses">{{ t('home.musesCta') }}</RouterLink>
        </div>
      </div>
    </section>

    <section class="container feed">
      <header class="feed-head">
        <h2>{{ t('home.partialMuses') }}</h2>
        <RouterLink class="more" to="/muses">{{ t('home.viewAll') }}</RouterLink>
      </header>
      <p v-if="loading" class="muted">{{ t('muses.loading') }}</p>
      <ul v-else class="posts">
        <li
          v-for="post in posts"
          :key="post.id"
          class="card"
          role="button"
          tabindex="0"
          :title="t('muses.openHint')"
          @click="openPost(post.id)"
          @keydown.enter="openPost(post.id)"
        >
          <div class="meta">
            <time>{{ formatDateShanghai(post.created_at, 'datetime') }}</time>
            <span class="tag">{{ kindLabel(post.kind) }}</span>
          </div>
          <h3 class="clip">{{ previewText(post.title) }}</h3>
          <p class="clip">{{ previewText(post.body) }}</p>
        </li>
        <li v-if="!posts.length" class="muted empty">{{ t('home.noPosts') }}</li>
      </ul>
    </section>
  </main>
</template>

<style scoped>
.hero {
  position: relative;
  overflow: hidden;
  opacity: 0;
  transform: translateY(10px);
  transition: opacity 0.65s ease, transform 0.65s ease;
}
.hero.show {
  opacity: 1;
  transform: none;
}
.hero-plane {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    linear-gradient(
      180deg,
      rgba(244, 247, 245, 0.12) 0%,
      rgba(244, 247, 245, 0.4) 40%,
      rgba(244, 247, 245, 0.78) 70%,
      var(--paper) 100%
    ),
    radial-gradient(ellipse 70% 55% at 78% 28%, rgba(47, 111, 94, 0.28), transparent 68%),
    radial-gradient(ellipse 55% 50% at 18% 62%, rgba(20, 32, 27, 0.12), transparent 70%),
    linear-gradient(145deg, rgba(185, 207, 196, 0.9) 0%, rgba(127, 168, 148, 0.75) 45%, rgba(53, 95, 82, 0.55) 100%);
  mask-image: linear-gradient(180deg, #000 0%, #000 52%, transparent 100%);
  -webkit-mask-image: linear-gradient(180deg, #000 0%, #000 52%, transparent 100%);
}
.hero-copy {
  position: relative;
  z-index: 1;
  padding: 1.05rem 0 0.75rem;
  max-width: none;
}
.brand-line {
  margin: 0 0 0.3rem;
  font-family: var(--font-display);
  font-size: clamp(1.55rem, 3.5vw, 2rem);
  font-weight: 600;
  letter-spacing: -0.02em;
  line-height: 1.15;
  color: var(--ink);
}
h1 {
  margin: 0 0 0.65rem;
  font-family: var(--font-display);
  font-weight: 500;
  font-size: clamp(1.2rem, 2.6vw, 1.5rem);
}
.lead {
  margin: 0 0 1.05rem;
  line-height: 1.65;
  color: rgba(20, 32, 27, 0.72);
  font-size: 0.95rem;
  max-width: 36rem;
}
.cta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
}
.feed {
  padding: 0.85rem 0 3rem;
}
.feed-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}
.feed-head h2 {
  margin: 0;
  font-family: var(--font-display);
  font-weight: 500;
  font-size: 1.6rem;
}
.more {
  color: var(--moss-deep);
  font-size: 0.9rem;
}
.posts {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.85rem;
}
.posts li.card {
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 1rem 1.1rem;
  background: rgba(255, 255, 255, 0.62);
  cursor: pointer;
}
.posts li.card:hover {
  border-color: rgba(47, 111, 94, 0.35);
}
.meta {
  display: flex;
  gap: 0.55rem;
  align-items: center;
  margin-bottom: 0.35rem;
  font-size: 0.8rem;
  color: rgba(20, 32, 27, 0.5);
}
.tag {
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 0.1rem 0.45rem;
}
.posts h3 {
  margin: 0 0 0.35rem;
  font-family: var(--font-display);
  font-weight: 500;
  font-size: 1.15rem;
}
.posts p {
  margin: 0;
  line-height: 1.65;
  color: rgba(20, 32, 27, 0.78);
}
.clip {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.muted {
  color: rgba(20, 32, 27, 0.5);
}
.empty {
  list-style: none;
  padding: 0.5rem 0;
}
</style>
