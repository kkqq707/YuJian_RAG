/**
 * 认证 Store — 管理登录状态、Token、用户信息
 *
 * 安全策略:
 * - Access Token 仅保存在 Pinia 内存中
 * - Refresh Token 保存在 sessionStorage（用户级隔离）
 * - 不在 Store 中保存密码
 * - logout/forceLogout 清空全部认证状态并协调其他 store 重置
 * - refresh 失败自动退出
 * - 账号切换时清除所有用户专属运行时状态
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import authApi from '@/api/auth'
import { setAccessToken as setAxiosToken, setRefreshTokenValue } from '@/api/request'
import { setRefreshToken, clearAuthTokens, getRefreshToken } from '@/utils/token'
import { setStoredUser, clearStoredUser, getStoredUser } from '@/utils/storage'
import { clearAllUserStorage, runStorageMigration } from '@/utils/userStorage'
import type { UserInfo, LoginRequest, TokenResponse } from '@/types/auth'
import type { StoredUser } from '@/types/user'

// ---- 竞态防护 ----

/** 当前请求所属用户的 ID。响应返回时验证是否仍是同一用户 */
let requestOwnerId: number | null = null

export function setRequestOwnerId(userId: number | null): void {
  requestOwnerId = userId
}

export function getRequestOwnerId(): number | null {
  return requestOwnerId
}

/** 验证请求归属：如果响应对应的用户已经变更，返回 false */
export function validateRequestOwnership(userId: number): boolean {
  if (requestOwnerId === null) return true
  return requestOwnerId === userId
}

export const useAuthStore = defineStore('auth', () => {
  // ---- State ----
  const accessToken = ref<string | null>(null)
  const user = ref<StoredUser | null>(null)
  const initialized = ref(false)
  const loading = ref(false)

  // ---- Getters ----
  // 已认证 = 有用户信息 + (有 accessToken 或 有 refreshToken 可恢复)
  // 页面刷新后 accessToken 丢失，但只要有 refreshToken 就可以通过 401 拦截器自动恢复
  const isAuthenticated = computed(() => {
    if (!user.value) return false
    if (accessToken.value) return true
    // 页面刷新后 accessToken 为 null，但 refreshToken 在 sessionStorage 中可用
    if (getRefreshToken()) return true
    return false
  })
  const isAdmin = computed(() => user.value?.role === 'admin')
  const isUser = computed(() => user.value?.role === 'user')
  const displayName = computed(() => user.value?.display_name || user.value?.username || '')

  /** 暴露当前用户 ID，供 userStorage 工具使用 */
  const userId = computed(() => user.value?.id ?? null)

  // ---- Actions ----

  /** 登录 */
  async function login(data: LoginRequest): Promise<void> {
    loading.value = true
    try {
      const result: TokenResponse = await authApi.login(data)
      applyToken(result)
      applyUser(result.user)
      initialized.value = true

      // 设置竞态防护的请求归属用户
      setRequestOwnerId(result.user.id)

      // 登录成功后执行存储迁移
      runStorageMigration()
    } finally {
      loading.value = false
    }
  }

  /** 刷新 Token */
  async function refreshToken(): Promise<void> {
    const storedRefresh = getRefreshToken()
    if (!storedRefresh) {
      throw new Error('No refresh token')
    }
    const result = await authApi.refresh({ refresh_token: storedRefresh })
    // 应用新 Token
    accessToken.value = result.access_token
    setAxiosToken(result.access_token)
    setRefreshToken(result.refresh_token)
    setRefreshTokenValue(result.refresh_token)
  }

  /** 获取当前用户信息 */
  async function fetchCurrentUser(): Promise<void> {
    try {
      const result = await authApi.me()
      const userInfo = result.user || result
      if (userInfo && userInfo.id) {
        const stored: StoredUser = {
          id: userInfo.id,
          username: userInfo.username,
          display_name: (userInfo as unknown as Record<string, string>).display_name || '',
          role: userInfo.role,
        }
        user.value = stored
        setStoredUser(stored)
      }
    } catch {
      // 获取用户信息失败，清除状态
      await forceLogout()
    }
  }

  /** 退出登录 */
  async function logout(): Promise<void> {
    const previousUserId = user.value?.id ?? null

    try {
      const storedRefresh = getRefreshToken()
      if (storedRefresh) {
        await authApi.logout({ refresh_token: storedRefresh })
      }
    } catch {
      // 即使服务端退出失败，也清理本地状态
    } finally {
      await performFullCleanup(previousUserId)
    }
  }

  /** 恢复会话（页面刷新时调用） */
  async function restoreSession(): Promise<void> {
    if (initialized.value) return

    const storedUser = getStoredUser()
    const storedRefresh = getRefreshToken()

    if (storedUser && storedRefresh) {
      // 从 sessionStorage 恢复用户信息
      user.value = storedUser
      setRequestOwnerId(storedUser.id)

      // 主动刷新 accessToken，避免首次 API 请求触发 401
      try {
        await refreshToken()
      } catch {
        // 刷新失败（如 refresh token 过期），清除状态让用户重新登录
        user.value = null
        setRequestOwnerId(null)
        clearAuthTokens()
        clearStoredUser()
      }
    }

    initialized.value = true
  }

  /** 从 axios 拦截器同步 accessToken 到 Pinia store（401 刷新成功后调用） */
  function syncAccessToken(token: string): void {
    accessToken.value = token
  }

  /** 修改密码 */
  async function changePassword(oldPassword: string, newPassword: string): Promise<void> {
    await authApi.changePassword({
      old_password: oldPassword,
      new_password: newPassword,
    })
    // 修改密码后强制退出
    await forceLogout()
  }

  // ---- 内部方法 ----

  function applyToken(result: TokenResponse): void {
    accessToken.value = result.access_token
    setAxiosToken(result.access_token)
    setRefreshToken(result.refresh_token)
    setRefreshTokenValue(result.refresh_token)
  }

  function applyUser(userInfo: UserInfo): void {
    const stored: StoredUser = {
      id: userInfo.id,
      username: userInfo.username,
      display_name: userInfo.display_name || '',
      role: userInfo.role,
    }
    user.value = stored
    setStoredUser(stored)
  }

  /**
   * 强制退出 — 清除所有认证状态，并通知其他 store 重置
   *
   * 与 logout 的区别：不调用后端 API
   */
  async function forceLogout(): Promise<void> {
    const previousUserId = user.value?.id ?? null
    await performFullCleanup(previousUserId)
  }

  /**
   * 静默清除所有认证状态 — 不触发 API 调用，不显示错误提示
   *
   * 用于:
   * - 访问 /login 页面时清理旧会话
   * - 路由守卫检测到未认证时清理
   */
  function silentCleanup(): void {
    const previousUserId = user.value?.id ?? null

    accessToken.value = null
    user.value = null
    setAxiosToken(null)
    setRefreshTokenValue(null)
    clearAuthTokens()
    clearStoredUser()
    setRequestOwnerId(null)

    // 清除 localStorage 中的遗留数据
    localStorage.removeItem('remembered_username')

    // 清除旧用户的存储
    if (previousUserId !== null) {
      clearAllUserStorage(previousUserId)
    }
  }

  // ---- 完整清理流程 ----

  /**
   * 执行完整清理：认证状态 + 用户级存储 + 通知其他 store
   *
   * 调用顺序:
   * 1. 保存退出前的用户 ID
   * 2. 清除认证状态
   * 3. 清除用户专属存储
   * 4. 通知其他 store 重置
   * 5. 取消竞态防护
   */
  async function performFullCleanup(previousUserId: number | null): Promise<void> {
    // Step 1: 清除认证状态
    accessToken.value = null
    user.value = null
    setAxiosToken(null)
    setRefreshTokenValue(null)
    clearAuthTokens()
    clearStoredUser()

    // Step 2: 清除竞态防护标记（在清除其他 store 之前）
    setRequestOwnerId(null)

    // Step 3: 清除该用户的 localStorage/sessionStorage
    if (previousUserId !== null) {
      clearAllUserStorage(previousUserId)
    }

    // Step 4: 清除遗留全局 key
    localStorage.removeItem('remembered_username')
  }

  return {
    // State
    accessToken,
    user,
    initialized,
    loading,
    // Getters
    isAuthenticated,
    isAdmin,
    isUser,
    displayName,
    userId,
    // Actions
    login,
    refreshToken,
    fetchCurrentUser,
    logout,
    restoreSession,
    changePassword,
    forceLogout,
    silentCleanup,
    syncAccessToken,
  }
})
