/**
 * 路由配置 — 企业智库 AI
 *
 * 路由层级:
 * - public: /login, /403, /*
 * - admin:  /admin/*  (adminOnly)
 * - user:   /chat, /history, /profile  (userOnly)
 *
 * 权限元数据:
 * - requiresAuth: true  → 需要登录
 * - adminOnly: true     → 仅管理员可访问，普通用户访问重定向到 /chat
 * - userOnly: true      → 仅普通用户可访问，管理员访问重定向到 /admin/dashboard
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

/**
 * 根据角色获取登录后默认跳转路由
 * 统一函数，避免登录页和路由守卫中重复逻辑
 */
export function getDefaultRouteByRole(isAdmin: boolean): string {
  return isAdmin ? '/admin/dashboard' : '/chat'
}

/** 管理员可访问的路由前缀 */
const ADMIN_PREFIX = '/admin'

/** 普通用户可访问的路由集合 */
const USER_ROUTES = new Set(['/chat', '/history', '/profile'])

/**
 * 判断给定路径是否为普通用户业务页面
 */
export function isUserOnlyPath(path: string): boolean {
  return USER_ROUTES.has(path) || (!path.startsWith(ADMIN_PREFIX) && path !== '/login' && path !== '/403')
}

/**
 * 验证登录后 redirect 参数是否合法（按角色校验）
 *
 * @param redirect - 请求的 redirect 路径
 * @param isAdmin - 当前用户是否为管理员
 * @returns 合法的 redirect 路径，非法时返回 null
 */
export function resolvePostLoginRedirect(
  redirect?: string,
  isAdmin?: boolean,
): string | null {
  if (!redirect || redirect === '/login' || redirect === '/') {
    return null
  }

  if (isAdmin) {
    // 管理员只能 redirect 到 /admin/* 页面
    if (redirect.startsWith(ADMIN_PREFIX)) {
      return redirect
    }
    return null // 忽略普通用户页面 redirect
  }

  // 普通用户不能 redirect 到 /admin/*
  if (redirect.startsWith(ADMIN_PREFIX)) {
    return null
  }
  return redirect
}

const routes: RouteRecordRaw[] = [
  // ============================================================
  // Auth / 公开页面
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
  {
    path: '/ai',
    name: 'PublicChat',
    component: () => import('@/views/public/PublicChatView.vue'),
    meta: {
      requiresAuth: false,
      title: 'AI 智能助手',
    },
  },

  // ============================================================
  // Admin Layout (管理员专属)
  // ============================================================
  {
    path: '/admin',
    component: () => import('@/layouts/AdminLayout.vue'),
    meta: { requiresAuth: true, adminOnly: true },
    children: [
      {
        path: '',
        redirect: '/admin/dashboard',
      },
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/admin/DashboardView.vue'),
        meta: { title: '工作台', icon: 'Monitor', requiresAuth: true, adminOnly: true },
      },
      {
        path: 'chat-preview',
        name: 'ChatPreview',
        component: () => import('@/views/admin/ChatPreviewView.vue'),
        meta: { title: '智能问答', icon: 'Message', requiresAuth: true, adminOnly: true },
      },
      {
        path: 'knowledge',
        name: 'Knowledge',
        component: () => import('@/views/admin/KnowledgeView.vue'),
        meta: { title: '知识库管理', icon: 'Folder', requiresAuth: true, adminOnly: true },
      },
      {
        path: 'knowledge/:fileId',
        name: 'KnowledgeDetail',
        component: () => import('@/views/admin/KnowledgeDetailView.vue'),
        meta: { title: '文件详情', icon: 'Folder', requiresAuth: true, adminOnly: true },
      },
      {
        path: 'users',
        name: 'Users',
        component: () => import('@/views/admin/UsersView.vue'),
        meta: { title: '用户管理', icon: 'User', requiresAuth: true, adminOnly: true },
      },
      {
        path: 'audit-logs',
        name: 'AuditLogs',
        component: () => import('@/views/admin/AuditLogsView.vue'),
        meta: { title: '审计日志', icon: 'Document', requiresAuth: true, adminOnly: true },
      },
      {
        path: 'logs',
        name: 'SystemLogs',
        component: () => import('@/views/admin/SystemLogsView.vue'),
        meta: { title: '系统日志', icon: 'Tickets', requiresAuth: true, adminOnly: true },
      },
      {
        path: 'system',
        name: 'System',
        component: () => import('@/views/admin/SystemView.vue'),
        meta: { title: '系统监控', icon: 'DataAnalysis', requiresAuth: true, adminOnly: true },
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/admin/SettingsView.vue'),
        meta: { title: '系统设置', icon: 'Setting', requiresAuth: true, adminOnly: true },
      },
      {
        path: 'api-config',
        name: 'ApiConfig',
        component: () => import('@/views/admin/ApiConfigView.vue'),
        meta: { title: 'AI 服务配置', icon: 'Setting', requiresAuth: true, adminOnly: true },
      },
      {
        path: 'rag-config',
        name: 'RagConfig',
        component: () => import('@/views/admin/RAGConfigView.vue'),
        meta: { title: 'RAG 配置', icon: 'Operation', requiresAuth: true, adminOnly: true },
      },
      {
        path: 'profile',
        name: 'AdminProfile',
        component: () => import('@/views/admin/AdminProfileView.vue'),
        meta: { title: '个人中心', icon: 'User', requiresAuth: true, adminOnly: true },
      },
    ],
  },

  // ============================================================
  // User Layout (普通用户专属)
  // ============================================================
  {
    path: '/',
    component: () => import('@/layouts/UserLayout.vue'),
    meta: { requiresAuth: true, userOnly: true },
    children: [
      {
        path: '',
        redirect: '/chat',
      },
      {
        path: 'chat',
        name: 'Chat',
        component: () => import('@/views/user/ChatView.vue'),
        meta: { title: '智能问答', icon: 'Message', requiresAuth: true, userOnly: true },
      },
      {
        path: 'history',
        name: 'History',
        component: () => import('@/views/user/HistoryView.vue'),
        meta: { title: '历史记录', icon: 'Clock', requiresAuth: true, userOnly: true },
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/user/ProfileView.vue'),
        meta: { title: '个人中心', icon: 'User', requiresAuth: true, userOnly: true },
      },
    ],
  },

  // ============================================================
  // 错误页面（公开）
  // ============================================================
  {
    path: '/403',
    name: 'Forbidden',
    component: () => import('@/views/error/ForbiddenView.vue'),
    meta: { title: '无权限访问', requiresAuth: false },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/error/NotFoundView.vue'),
    meta: { title: '页面不存在', requiresAuth: false },
  },
]

export default routes
