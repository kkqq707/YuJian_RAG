/**
 * 路由守卫 — 认证与权限控制
 *
 * 规则:
 * 1. 未登录访问业务页 → /login
 * 2. 已登录访问 /login → 根据角色跳转
 * 3. user 访问 admin 路由 → /403
 * 4. admin 可以访问管理员页面
 * 5. 页面标题自动更新
 * 6. 权限判断不止隐藏菜单，路由也必须阻止
 * 7. 访问 /login 时静默清除所有旧 Token，不显示过期提示
 * 8. 防止循环跳转
 */

import type { Router } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { useChatStore } from '@/stores/chat'
import { preloadAdminRoutes } from './routes'

const TITLE_SUFFIX = ' | 企业智库 AI'

/** 防止循环跳转：最近一次重定向目标 */
let lastRedirectTarget: string | null = null
let lastRedirectTime = 0
const REDIRECT_COOLDOWN_MS = 2000

export function setupGuards(router: Router): void {
  router.beforeEach(async (to, _from, next) => {
    // 更新页面标题
    const pageTitle = (to.meta.title as string) || ''
    document.title = pageTitle ? `${pageTitle}${TITLE_SUFFIX}` : '企业智库 AI'

    const authStore = useAuthStore()
    const appStore = useAppStore()
    const chatStore = useChatStore()

    // 访问登录页面时：静默清除所有旧的认证状态和用户数据
    if (to.name === 'Login') {
      // 1. 重置聊天状态（清空会话列表、当前会话、消息）
      chatStore.reset()
      // 2. 重置应用 UI 状态
      appStore.reset()
      // 3. 清除所有旧 Token 和认证状态（不触发 API 调用）
      authStore.silentCleanup()
      authStore.initialized = true
      // 允许正常访问登录页
      next()
      return
    }

    // 等待 store 初始化完成（非登录页面才尝试恢复会话）
    if (!authStore.initialized) {
      await authStore.restoreSession()
    }

    // 恢复会话后初始化侧边栏状态（按当前用户加载）
    if (authStore.user?.id) {
      appStore.initializeSidebar(authStore.user.id)
    }

    const isAuthenticated = authStore.isAuthenticated
    const isAdmin = authStore.isAdmin
    const requiresAuth = to.meta.requiresAuth !== false
    const requiredRoles = (to.meta.roles as string[] | undefined) || []

    // 1. 未登录访问需认证的页面 → /login（防止循环）
    if (requiresAuth && !isAuthenticated) {
      const now = Date.now()
      const targetPath = to.fullPath
      // 如果 2 秒内重复跳转到同一目标，直接放行避免循环
      if (
        lastRedirectTarget === targetPath &&
        now - lastRedirectTime < REDIRECT_COOLDOWN_MS
      ) {
        next()
        return
      }
      lastRedirectTarget = '/login'
      lastRedirectTime = now
      next({ name: 'Login', query: { redirect: targetPath } })
      return
    }

    // 2. 已登录访问 /login → 根据角色跳转（已在上面处理，这里做防御）
    if (to.name === 'Login' && isAuthenticated) {
      if (isAdmin) {
        next({ name: 'Dashboard' })
      } else {
        next({ name: 'Chat' })
      }
      return
    }

    // 3. 角色检查
    if (requiresAuth && requiredRoles.length > 0 && isAuthenticated) {
      const userRole = authStore.user?.role
      if (!userRole || !requiredRoles.includes(userRole)) {
        next({ name: 'Forbidden' })
        return
      }
    }

    // 4. 普通用户尝试访问 /admin 路由
    if (to.path.startsWith('/admin') && isAuthenticated && !isAdmin) {
      next({ name: 'Forbidden' })
      return
    }

    // 后台预加载管理端高频页面 — 首次识别到管理员身份时触发
    if (isAdmin) {
      preloadAdminRoutes()
    }

    // 重置防循环状态
    lastRedirectTarget = null
    next()
  })
}
