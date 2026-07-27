/**
 * 安全的 storage 封装
 *
 * 安全策略:
 * - 用户信息存储在 sessionStorage（用户级隔离 key）
 * - 侧边栏折叠状态按用户隔离
 * - 不使用全局共享 key 存储用户专属状态
 */

import type { StoredUser } from '@/types/user'
import {
  buildUserStorageKey,
  getUserStorage,
  setUserStorage,
  removeUserStorage,
} from './userStorage'

const USER_KEY_BASE = 'user_info'
const SIDEBAR_KEY_BASE = 'sidebar_collapsed'

// ---- 用户信息（sessionStorage） ----

export function getStoredUser(): StoredUser | null {
  const raw = sessionStorage.getItem(buildUserStorageKey(USER_KEY_BASE))
  if (!raw) return null
  try {
    return JSON.parse(raw) as StoredUser
  } catch {
    sessionStorage.removeItem(buildUserStorageKey(USER_KEY_BASE))
    return null
  }
}

export function setStoredUser(user: StoredUser): void {
  sessionStorage.setItem(
    buildUserStorageKey(USER_KEY_BASE, user.id),
    JSON.stringify(user),
  )
}

export function clearStoredUser(): void {
  // 清除所有可能的用户 session 数据（key 中包含 user_info）
  for (let i = sessionStorage.length - 1; i >= 0; i--) {
    const key = sessionStorage.key(i)
    if (key && key.includes(USER_KEY_BASE)) {
      sessionStorage.removeItem(key)
    }
  }
}

// ---- 侧边栏折叠状态（localStorage，按用户隔离） ----

export function getSidebarCollapsed(): boolean {
  try {
    return getUserStorage<boolean>(SIDEBAR_KEY_BASE, false)
  } catch {
    // 如果无法获取用户 ID（未登录），返回默认值
    return false
  }
}

export function setSidebarCollapsed(collapsed: boolean): void {
  try {
    setUserStorage(SIDEBAR_KEY_BASE, collapsed)
  } catch {
    // 未登录时静默失败
  }
}
