import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('../views/LoginView.vue'), meta: { guest: true } },
    { path: '/register', name: 'register', component: () => import('../views/RegisterView.vue'), meta: { guest: true } },
    { path: '/forgot-password', name: 'forgot', component: () => import('../views/ForgotPasswordView.vue'), meta: { guest: true } },
    {
      path: '/',
      component: () => import('../layouts/SiteLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        { path: '', name: 'home', component: () => import('../views/HomeView.vue') },
        { path: 'projects', name: 'projects', component: () => import('../views/ProjectsView.vue') },
        { path: 'projects/:slug', name: 'project-detail', component: () => import('../views/ProjectDetailView.vue') },
        { path: 'muses', name: 'muses', component: () => import('../views/MusesView.vue') },
        { path: 'diary', redirect: '/muses' },
        { path: 'social', name: 'social', component: () => import('../views/SocialHubView.vue') },
        { path: 'members', redirect: '/social' },
        { path: 'members/:id', redirect: '/social' },
        { path: 'requests', redirect: '/social' },
        { path: 'chat', redirect: '/social' },
        { path: 'profile', name: 'profile', component: () => import('../views/ProfileView.vue') },
        { path: 'notifications', name: 'notifications', component: () => import('../views/NotificationsView.vue') },
        { path: 'invites', name: 'invites', component: () => import('../views/InvitesView.vue') },
        { path: 'admin', name: 'admin', component: () => import('../views/AdminView.vue'), meta: { adminOnly: true } },
        {
          path: 'admin/invites',
          redirect: { name: 'admin', query: { panel: 'batchInvites' } },
        },
        { path: 'about', redirect: '/' },
      ],
    },
  ],
  scrollBehavior() {
    return { top: 0 }
  },
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.ready) await auth.bootstrap()
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.adminOnly && !auth.isAdmin) return { name: 'home' }
  if (to.meta.guest && auth.isAuthenticated && to.name !== 'forgot') return { name: 'home' }
  return true
})

export default router
