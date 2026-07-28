/**
 * 路由守卫 — 认证与权限控制
 *
 * 规则:
 * 1. 未登录访问需认证页面 → /login?redirect=原路径
 * 2. 已登录访问 /login → 按角色跳转
 * 3. 普通用户访问 adminOnly 页面 → /chat
 * 4. 管理员访问 userOnly 页面 → /admin/dashboard
 * 5. 根路径 / → 按角色跳转
 * 6. 页面标题自动更新
 * 7. 防止循环跳转
 * 8. restoreSession 支持并发去重
 */

import type { Router } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { useChatStore } from '@/stores/chat'
import { preloadAdminRoutes, getDefaultRouteByRole, resolvePostLoginRedirect } from './routes'

const TITLE_SUFFIX = ' | 企业智库 AI'

/**
 * 管理员默认跳转目标
 */
const ADMIN_DEFAULT = '/admin/dashboard'

/**
 * 普通用户默认跳转目标
 */
const USER_DEFAULT = '/chat'

/** 防止循环跳转 */
let lastRedirectTarget: string | null = null
let lastRedirectTime = 0
const REDIRECT_COOLDOWN_MS = 2000

function isRedirectLoop(target: string): boolean {
  const now = Date.now()
  if (lastRedirectTarget === target && now - lastRedirectTime < REDIRECT_COOLDOWN_MS) {
    return true
  }
  lastRedirectTarget = target
  lastRedirectTime = now
  return false
}

export function setupGuards(router: Router): void {
  router.beforeEach(async (to, _from, next) => {
    // ---- 页面标题 ----
    const pageTitle = (to.meta.title as string) || ''
    document.title = pageTitle ? `${pageTitle}${TITLE_SUFFIX}` : '企业智库 AI'

    const authStore = useAuthStore()
    const appStore = useAppStore()
    const chatStore = useChatStore()

    // ---- 访问登录页面：静默清理旧状态 ----
    if (to.name === 'Login') {
      chatStore.reset()
      appStore.reset()
      authStore.silentCleanup()
      authStore.initialized = true
      next()
      return
    }

    // ---- 恢复会话（支持并发去重） ----
    if (!authStore.sessionRestored) {
      await authStore.restoreSession()
    }

    // ---- 恢复会话后初始化侧边栏 ----
    if (authStore.user?.id) {
      appStore.initializeSidebar(authStore.user.id)
    }

    const isAuthenticated = authStore.isAuthenticated
    const isAdmin = authStore.isAdmin

    // ---- 1. 未登录 → 跳转登录页 ----
    if (to.meta.requiresAuth !== false && !isAuthenticated) {
      if (isRedirectLoop(to.fullPath)) {
        next()
        return
      }
      next({ name: 'Login', query: { redirect: to.fullPath } })
      return
    }

    // ---- 2. 已登录访问 /login → 按角色跳转 ----
    if (isAuthenticated && to.name === 'Login') {
      const target = getDefaultRouteByRole(isAdmin)
      next(target)
      return
    }

    // ---- 3. 根路径 → 按角色跳转 ----
    if (isAuthenticated && to.path === '/') {
      const target = getDefaultRouteByRole(isAdmin)
      next(target)
      return
    }

    // ---- 4. 普通用户访问 adminOnly 页面 → 重定向到 /chat ----
    if (to.meta.adminOnly && isAuthenticated && !isAdmin) {
      if (!isRedirectLoop(USER_DEFAULT)) {
        next(USER_DEFAULT)
        return
      }
    }

    // ---- 5. 管理员访问 userOnly 页面 → 重定向到 /admin/dashboard ----
    if (to.meta.userOnly && isAuthenticated && isAdmin) {
      if (!isRedirectLoop(ADMIN_DEFAULT)) {
        next(ADMIN_DEFAULT)
        return
      }
    }

    // ---- 6. 额外保护：管理员访问任何非 /admin/* 路径 ----
    if (isAuthenticated && isAdmin && to.path !== ADMIN_DEFAULT && !to.path.startsWith('/admin') && to.path !== '/login' && to.name !== 'NotFound' && to.name !== 'Forbidden') {
      if (!isRedirectLoop(ADMIN_DEFAULT)) {
        next(ADMIN_DEFAULT)
        return
      }
    }

    // ---- 7. 额外保护：普通用户访问 /admin/* 路径 ----
    if (isAuthenticated && !isAdmin && to.path.startsWith('/admin')) {
      if (!isRedirectLoop(USER_DEFAULT)) {
        next(USER_DEFAULT)
        return
      }
    }

    // ---- 后台预加载管理端高频页面 ----
    if (isAdmin) {
      preloadAdminRoutes()
    }

    // 重置防循环状态
    lastRedirectTarget = null
    next()
  })
}
