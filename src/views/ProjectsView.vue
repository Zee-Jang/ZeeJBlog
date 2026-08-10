<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api/client'
import { formatApiError } from '../utils/apiError'
import { useI18n } from '../i18n'
import { useAuthStore } from '../stores/auth'
import type { Project } from '../types'

interface ImportPreview {
  title: string
  summary: string
  github_url: string
  readme: string
  demo_url: string | null
  stack: string[]
  source: string
}

const auth = useAuthStore()
const router = useRouter()
const { t } = useI18n()
const projects = ref<Project[]>([])
const loading = ref(true)
const showForm = ref(false)
const title = ref('')
const summary = ref('')
const github = ref('')
const readme = ref('# 项目名\n\n写一点 README…')
const demoUrl = ref('')
const stack = ref<string[]>([])
const importUrl = ref('')
const importing = ref(false)
const importTip = ref('')
const error = ref('')

async function load() {
  loading.value = true
  try {
    const { data } = await api.get<Project[]>('/api/projects')
    projects.value = data
  } finally {
    loading.value = false
  }
}

function resetForm() {
  title.value = ''
  summary.value = ''
  github.value = ''
  readme.value = '# 项目名\n\n写一点 README…'
  demoUrl.value = ''
  stack.value = []
  importUrl.value = ''
  importTip.value = ''
  error.value = ''
}

async function importRemote() {
  error.value = ''
  importTip.value = ''
  const url = importUrl.value.trim()
  if (!url) {
    error.value = t('projects.importNeedUrl')
    return
  }
  importing.value = true
  try {
    const { data } = await api.post<ImportPreview>('/api/projects/import-preview', { url })
    title.value = data.title
    summary.value = data.summary
    github.value = data.github_url
    readme.value = data.readme || `# ${data.title}\n`
    demoUrl.value = data.demo_url || ''
    stack.value = data.stack || []
    importTip.value = t('projects.importOk', {
      source: data.source === 'gitee' ? 'Gitee' : 'GitHub',
    })
    showForm.value = true
  } catch (e: unknown) {
    error.value = formatApiError(e, t('projects.importFail'))
  } finally {
    importing.value = false
  }
}

async function publish() {
  error.value = ''
  try {
    await api.post('/api/projects', {
      title: title.value.trim(),
      summary: summary.value.trim(),
      github_url: github.value.trim() || null,
      readme: readme.value,
      demo_url: demoUrl.value.trim() || null,
      stack: stack.value,
    })
    showForm.value = false
    resetForm()
    await load()
  } catch (e: unknown) {
    error.value = formatApiError(e, t('common.publishFail'))
  }
}

function previewText(text: string) {
  return (text || '').replace(/\s+/g, ' ').trim()
}

function openProject(slug: string) {
  router.push(`/projects/${slug}`)
}

function onCardKey(e: KeyboardEvent, slug: string) {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault()
    openProject(slug)
  }
}

function toggleForm() {
  showForm.value = !showForm.value
  if (!showForm.value) {
    error.value = ''
    importTip.value = ''
  }
}

onMounted(load)
</script>

<template>
  <main class="container page">
    <header class="head">
      <div>
        <h1>{{ t('projects.title') }}</h1>
        <p>{{ t('projects.desc') }}</p>
      </div>
      <button
        v-if="auth.isAdmin"
        class="btn primary"
        type="button"
        @click="toggleForm"
      >
        {{ showForm ? t('projects.collapse') : t('projects.publish') }}
      </button>
    </header>

    <form v-if="auth.isAdmin && showForm" class="composer" @submit.prevent="publish">
      <div class="import-box">
        <label>{{ t('projects.importLabel') }}</label>
        <p class="hint">{{ t('projects.importHint') }}</p>
        <div class="import-row">
          <input
            v-model="importUrl"
            type="url"
            :placeholder="t('projects.importPh')"
            @keydown.enter.prevent="importRemote"
          />
          <button
            class="btn ghost"
            type="button"
            :disabled="importing"
            @click="importRemote"
          >
            {{ importing ? t('projects.importing') : t('projects.importBtn') }}
          </button>
        </div>
        <p v-if="importTip" class="ok">{{ importTip }}</p>
      </div>

      <div class="field">
        <label>{{ t('projects.fieldTitle') }}</label>
        <input v-model="title" required maxlength="120" />
      </div>
      <div class="field">
        <label>{{ t('projects.fieldSummary') }}</label>
        <textarea v-model="summary" rows="2" required maxlength="2000" />
      </div>
      <div class="field">
        <label>{{ t('projects.fieldGithub') }}</label>
        <input v-model="github" :placeholder="t('projects.fieldGithubPh')" />
      </div>
      <div class="field">
        <label>{{ t('projects.fieldDemo') }}</label>
        <input v-model="demoUrl" :placeholder="t('projects.fieldDemoPh')" />
      </div>
      <div v-if="stack.length" class="field">
        <label>{{ t('projects.fieldStack') }}</label>
        <p class="stack-line">{{ stack.join(' · ') }}</p>
      </div>
      <div class="field">
        <label>{{ t('projects.fieldReadme') }}</label>
        <textarea v-model="readme" rows="10" class="readme" />
      </div>
      <p v-if="error" class="error">{{ error }}</p>
      <button class="btn primary" type="submit">{{ t('projects.submit') }}</button>
    </form>

    <p v-if="loading">{{ t('projects.loading') }}</p>
    <ul v-else class="list">
      <li
        v-for="project in projects"
        :key="project.slug"
        class="card"
        role="button"
        tabindex="0"
        @click="openProject(project.slug)"
        @keydown="onCardKey($event, project.slug)"
      >
        <div class="meta">
          <span class="tag">{{ project.status }}</span>
          <span v-if="project.owner_name" class="owner">by {{ project.owner_name }}</span>
          <a
            v-if="project.github_url"
            class="gh"
            :href="project.github_url"
            target="_blank"
            rel="noreferrer"
            @click.stop
          >
            {{ /gitee\.com/i.test(project.github_url || '') ? 'Gitee' : 'GitHub' }}
          </a>
        </div>
        <h2 class="clip">{{ previewText(project.title) }}</h2>
        <p class="clip">{{ previewText(project.summary) }}</p>
        <span class="readme-link">{{ t('projects.viewReadme') }}</span>
      </li>
      <li v-if="!projects.length" class="empty muted">{{ t('projects.empty') }}</li>
    </ul>
  </main>
</template>

<style scoped>
.page {
  padding: 2.8rem 0 1rem;
}
.head {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  margin-bottom: 1.2rem;
}
h1 {
  margin: 0 0 0.5rem;
  font-family: var(--font-display);
  font-size: clamp(2.2rem, 5vw, 3.2rem);
  font-weight: 500;
}
.head p {
  margin: 0;
  color: rgba(20, 32, 27, 0.7);
}
.composer {
  display: grid;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
  padding: 1rem;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: var(--card);
}
.import-box {
  display: grid;
  gap: 0.4rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--line);
  margin-bottom: 0.15rem;
}
.import-box > label {
  font-size: 0.85rem;
  color: rgba(20, 32, 27, 0.6);
}
.hint {
  margin: 0;
  font-size: 0.85rem;
  color: rgba(20, 32, 27, 0.55);
  line-height: 1.45;
}
.import-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}
.import-row input {
  flex: 1 1 14rem;
  min-width: 0;
  border-radius: 10px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.7);
  padding: 0.7rem 0.85rem;
  color: var(--ink);
  font-size: 16px;
}
.ok {
  margin: 0;
  color: var(--moss-deep);
  font-size: 0.9rem;
}
.stack-line {
  margin: 0;
  font-size: 0.92rem;
  color: rgba(20, 32, 27, 0.7);
}
.readme {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.9rem;
}
.error {
  margin: 0;
  color: var(--danger);
}
.list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: calc(1cm / 3);
  width: 100%;
}
.card {
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
.meta {
  display: flex;
  gap: 0.55rem;
  align-items: center;
  flex: 0 0 auto;
  min-width: 0;
  font-size: 0.8rem;
  color: rgba(20, 32, 27, 0.5);
}
.tag {
  font-size: 0.75rem;
  padding: 0.1rem 0.45rem;
  border-radius: 999px;
  background: rgba(47, 111, 94, 0.12);
  color: var(--moss-deep);
  text-transform: uppercase;
  flex-shrink: 0;
}
.owner {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.gh {
  margin-left: auto;
  color: var(--moss-deep);
  font-weight: 600;
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
.readme-link {
  margin-top: 0.15rem;
  color: var(--moss-deep);
  font-weight: 600;
  font-size: 0.9rem;
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
.empty {
  padding: 0.5rem 0;
  list-style: none;
}
.muted {
  color: rgba(20, 32, 27, 0.5);
}
@media (max-width: 700px) {
  .head {
    flex-direction: column;
  }
}
</style>
