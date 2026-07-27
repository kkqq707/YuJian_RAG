/**
 * 路由配置 — 企业智库 AI
 *
 * 路由层级:
 * - public: /login, /403, /*
 * - admin:  /admin/*
 * - user:   /chat, /history, /profile
 */

import type { RouteRecordRaw } from 'vue-router'

/**
 * 预加载高频管理页面 — 在应用挂载后调用，避免首次点击延迟
 *
 * 问题：Vite 开发模式下，懒加载组件在首次请求时才即时编译，
 * AdminLayout + Element Plus 依赖树较大，导致首次点击菜单时明显卡顿。
 * 预加载可提前触发模块转换和缓存，消除首次点击延迟。
 */
export function preloadAdminRoutes(): void {
  if (preloadScheduled) return
  preloadScheduled = true

  const preload = () => {
    import('@/layouts/AdminLayout.vue')
    import('@/views/admin/DashboardView.vue')
    import('@/views/admin/KnowledgeView.vue')
    import('@/views/admin/ChatPreviewView.vue')
    import('@/views/admin/SettingsView.vue')
  }
  if (typeof requestIdleCallback !== 'undefined') {
    requestIdleCallback(preload, { timeout: 2000 })
  } else {
    setTimeout(preload, 300)
  }
}

let preloadScheduled = false

const routes: RouteRecordRaw[] = [
  // ============================================================
  // Auth Layout (公开)
  // ============================================================
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/auth/LoginView.vue'),
    meta: {
      requiresAuth: false,
      title: '登录',
    },
  },

  // ============================================================
  // Admin Layout (管理员)
  // ============================================================
  {
    path: '/admin',
    component: () => import('@/layouts/AdminLayout.vue'),
    meta: { requiresAuth: true, roles: ['admin'] },
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/admin/DashboardView.vue'),
        meta: { title: '工作台', icon: 'Monitor' },
      },
      {
        path: 'chat-preview',
        name: 'ChatPreview',
        component: () => import('@/views/admin/ChatPreviewView.vue'),
        meta: { title: '智能问答', icon: 'Message' },
      },
      {
        path: 'knowledge',
        name: 'Knowledge',
        component: () => import('@/views/admin/KnowledgeView.vue'),
        meta: { title: '知识库管理', icon: 'Folder' },
      },
      {
        path: 'knowledge/:fileId',
        name: 'KnowledgeDetail',
        component: () => import('@/views/admin/KnowledgeDetailView.vue'),
        meta: { title: '文件详情', icon: 'Folder' },
      },
      {
        path: 'users',
        name: 'Users',
        component: () => import('@/views/admin/UsersView.vue'),
        meta: { title: '用户管理', icon: 'User' },
      },
      {
        path: 'audit-logs',
        name: 'AuditLogs',
        component: () => import('@/views/admin/AuditLogsView.vue'),
        meta: { title: '审计日志', icon: 'Document' },
      },
      {
        path: 'logs',
        name: 'SystemLogs',
        component: () => import('@/views/admin/SystemLogsView.vue'),
        meta: { title: '系统日志', icon: 'Tickets' },
      },
      {
        path: 'system',
        name: 'System',
        component: () => import('@/views/admin/SystemView.vue'),
        meta: { title: '系统监控', icon: 'DataAnalysis' },
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/admin/SettingsView.vue'),
        meta: { title: '系统设置', icon: 'Setting' },
      },
      {
        path: 'api-config',
        name: 'ApiConfig',
        component: () => import('@/views/admin/ApiConfigView.vue'),
        meta: { title: 'AI 服务配置', icon: 'Setting' },
      },
      {
        path: 'rag-config',
        name: 'RagConfig',
        component: () => import('@/views/admin/RAGConfigView.vue'),
        meta: { title: 'RAG 配置', icon: 'Operation' },
      },
      {
        path: 'profile',
        name: 'AdminProfile',
        component: () => import('@/views/admin/AdminProfileView.vue'),
        meta: { title: '个人中心', icon: 'User' },
      },
    ],
  },

  // ============================================================
  // User Layout (普通用户)
  // ============================================================
  {
    path: '/',
    component: () => import('@/layouts/UserLayout.vue'),
    meta: { requiresAuth: true, roles: ['admin', 'user'] },
    children: [
      {
        path: '',
        redirect: '/chat',
      },
      {
        path: 'chat',
        name: 'Chat',
        component: () => import('@/views/user/ChatView.vue'),
        meta: { title: '智能问答', icon: 'Message' },
      },
      {
        path: 'history',
        name: 'History',
        component: () => import('@/views/user/HistoryView.vue'),
        meta: { title: '历史记录', icon: 'Clock' },
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/user/ProfileView.vue'),
        meta: { title: '个人中心', icon: 'User' },
      },
    ],
  },

  // ============================================================
  // 错误页面
  // ============================================================
  {
    path: '/403',
    name: 'Forbidden',
    component: () => import('@/views/error/ForbiddenView.vue'),
    meta: { title: '无权限访问' },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/error/NotFoundView.vue'),
    meta: { title: '页面不存在' },
  },
]

export default routes
