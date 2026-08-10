<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import api from '../api/client'
import { useI18n } from '../i18n'
import { formatApiError } from '../utils/apiError'
import type { Project } from '../types'

const route = useRoute()
const { t } = useI18n()
const project = ref<Project | null>(null)
const error = ref('')
const loading = ref(true)
const slug = computed(() => String(route.params.slug))

onMounted(async () => {
  try {
    const { data } = await api.get<Project>(`/api/projects/${slug.value}`)
    project.value = data
  } catch (e: any) {
    error.value = formatApiError(e, t('common.loadFail'))
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <main class="container page">
    <RouterLink class="back" to="/projects">← 返回项目列表</RouterLink>
    <p v-if="loading">加载中…</p>
    <p v-else-if="error" class="error">{{ error }}</p>
    <template v-else-if="project">
      <header class="head">
        <h1>{{ project.title }}</h1>
        <p class="summary">{{ project.summary }}</p>
        <p class="meta">
          <span v-if="project.owner_name">作者 {{ project.owner_name }}</span>
          <a
            v-if="project.github_url"
            :href="project.github_url"
            target="_blank"
            rel="noreferrer"
          >
            打开 GitHub
          </a>
          <a
            v-if="project.demo_url"
            :href="project.demo_url"
            target="_blank"
            rel="noreferrer"
          >
            打开 Demo
          </a>
        </p>
      </header>

      <article class="readme">
        <pre>{{ project.readme || '暂无 README' }}</pre>
      </article>
    </template>
  </main>
</template>

<style scoped>
.page {
  padding: 2rem 0 2rem;
  max-width: 860px;
}
.back {
  color: var(--moss-deep);
  font-weight: 600;
}
.head {
  margin: 1.2rem 0 1.4rem;
}
h1 {
  margin: 0 0 0.5rem;
  font-family: var(--font-display);
  font-weight: 500;
  font-size: clamp(2rem, 4vw, 2.8rem);
}
.summary {
  margin: 0;
  line-height: 1.65;
  color: rgba(20, 32, 27, 0.78);
}
.meta {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  margin-top: 0.8rem;
  color: rgba(20, 32, 27, 0.6);
}
.meta a {
  color: var(--moss-deep);
  font-weight: 600;
}
.readme {
  border: 1px solid var(--line);
  border-radius: 14px;
  background: var(--card);
  padding: 1.2rem;
}
.readme pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.92rem;
  line-height: 1.65;
  color: rgba(20, 32, 27, 0.88);
}
</style>
