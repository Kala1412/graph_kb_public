import { createRouter, createWebHistory } from 'vue-router'

const getRoleFromToken = (token) => {
  if (!token) return ''
  const parts = token.split('.')
  if (parts.length < 2) return ''
  try {
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, '=')
    const payload = JSON.parse(atob(padded))
    return payload?.role || ''
  } catch {
    return ''
  }
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/login/index.vue'),
      meta: { title: '登录' },
    },
    {
      path: '/',
      name: 'home',
      redirect: '/dashboard',
      component: () => import('../views/layout/index.vue'),
      children: [
        {
          path: '/dashboard',
          name: 'dashboard',
          component: () => import('../views/dashboard/index.vue'),
          meta: { title: '仪表板' },
        },
        {
          path: '/workspace',
          name: 'workspace',
          component: () => import('../views/workspace/index.vue'),
          meta: { title: '工作台' },
        },
        {
          path: '/knowledge',
          name: 'knowledge',
          component: () => import('../views/knowledge/index.vue'),
          meta: { title: '知识库' },
        },
        {
          path: '/forum',
          name: 'forum',
          component: () => import('../views/forum/index.vue'),
          meta: { title: '讨论区' },
        },
        {
          path: '/forum/:postId',
          name: 'forum-detail',
          component: () => import('../views/forum/detail.vue'),
          meta: { title: '帖子详情' },
        },
        {
          path: '/knowledge/:kbId',
          name: 'knowledge-detail',
          component: () => import('../views/knowledge/detail.vue'),
          meta: { title: '知识库详情' },
        },
        {
          path: '/chat',
          name: 'chat',
          component: () => import('../views/chat/index.vue'),
          meta: { title: '聊天', keepAlive: true },
        },
        {
          path: '/graph',
          name: 'knowledge-graph',
          component: () => import('../views/graph/index.vue'),
          meta: { title: '知识图谱' },
        },
        {
          path: '/about',
          name: 'about',
          component: () => import('../views/about/index.vue'),
          meta: { title: '关于' },
        },
        {
          path: '/profile',
          name: 'profile',
          component: () => import('../views/profile/index.vue'),
          meta: { title: '个人信息' },
        },
      ],
    },
    {
      path: '/admin',
      name: 'admin-layout',
      redirect: '/admin/dashboard',
      component: () => import('../views/admin/layout/index.vue'),
      meta: { requiresRole: 'admin', title: '系统管理' },
      children: [
        {
          path: 'dashboard',
          name: 'admin-dashboard',
          component: () => import('../views/admin/dashboard/index.vue'),
          meta: { title: '管理概览' },
        },
        {
          path: 'users',
          name: 'admin-users',
          component: () => import('../views/admin/users/index.vue'),
          meta: { title: '用户管理' },
        },
        {
          path: 'knowledge',
          name: 'admin-knowledge',
          component: () => import('../views/admin/knowledge/index.vue'),
          meta: { title: '知识库管理' },
        },
        {
          path: 'knowledge/:kbId',
          name: 'admin-knowledge-detail',
          component: () => import('../views/admin/knowledge/detail.vue'),
          meta: { title: '知识库详情管理' },
        },
        {
          path: 'sessions',
          name: 'admin-sessions',
          component: () => import('../views/admin/sessions/index.vue'),
          meta: { title: '对话管理' },
        },
        {
          path: 'medical-profiles',
          name: 'admin-medical-profiles',
          component: () => import('../views/admin/medical-profiles/index.vue'),
          meta: { title: '个人病症管理' },
        },
        {
          path: 'audit-logs',
          name: 'admin-audit',
          component: () => import('../views/admin/audit/index.vue'),
          meta: { title: '审计日志' },
        },
        {
          path: 'forum',
          name: 'admin-forum',
          component: () => import('../views/admin/forum/index.vue'),
          meta: { title: '讨论区管理' },
        },
      ],
    },
  ],
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  const role = getRoleFromToken(token) || localStorage.getItem('role')

  if (to.path === '/login') {
    next()
  } else if (!token) {
    localStorage.removeItem('role')
    next('/login')
  } else if (to.path === '/' && role === 'admin') {
    next('/admin/dashboard')
  } else if (to.meta?.requiresRole && to.meta.requiresRole !== role) {
    next('/dashboard')
  } else {
    next()
  }
})

const stableRouteTitleMap = {
  login: '登录',
  dashboard: '仪表板',
  workspace: '工作台',
  knowledge: '知识库',
  forum: '讨论区',
  'forum-detail': '帖子详情',
  'knowledge-detail': '知识库详情',
  chat: '智能问答',
  'knowledge-graph': '知识图谱',
  about: '关于系统',
  profile: '个人中心',
  'admin-layout': '系统管理',
  'admin-dashboard': '管理概览',
  'admin-users': '用户管理',
  'admin-knowledge': '知识库管理',
  'admin-knowledge-detail': '知识库详情管理',
  'admin-sessions': '对话管理',
  'admin-medical-profiles': '个人病症管理',
  'admin-audit': '审计日志',
  'admin-forum': '讨论区管理',
}

router.afterEach((to) => {
  const pageTitle =
    stableRouteTitleMap[to.name] ||
    (to.meta?.title ? String(to.meta.title) : '医疗知识库')
  document.title = `${pageTitle} | 医疗知识图谱问答系统`
})

export default router
