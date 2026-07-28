/**
 * 安全的 storage 封装
 *
 * 安全策略:
 * - 用户信息存储在 sessionStorage（全局固定 key，不依赖 userId 即可读取）
 * - 侧边栏折叠状态按用户隔离（用户专属 key: yujian:{userId}:sidebar_collapsed）
 * - 不使用全局共享 key 存储用户专属状态
 *
 * Key 分类:
 * - 全局认证 key（固定，不依赖 userId）: user_info, refresh_token
 * - 用户专属业务 key（依赖 userId）: sidebar_collapsed, chat_history, ...
 */

import type { StoredUser } from '@/types/user'
import {
  getUserStorage,
  setUserStorage,
  GLOBAL_KEYS,
} from './userStorage'

const SIDEBAR_KEY_BASE = 'sidebar_collapsed'

// ---- 用户信息（sessionStorage，全局固定 key） ----
//
// 使用全局 key `yujian:user_info` 而非 `yujian:{userId}:user_info`。
// 原因：恢复会话时必须先读取 user_info 才能获取 userId，
// 如果 key 本身依赖 userId 则形成循环依赖，导致无法恢复。

export function getStoredUser(): StoredUser | null {
  try {
    const raw = sessionStorage.getItem(GLOBAL_KEYS.USER_INFO)
    if (!raw) return null
    return JSON.parse(raw) as StoredUser
  } catch {
    sessionStorage.removeItem(GLOBAL_KEYS.USER_INFO)
    return null
  }
}

export function setStoredUser(user: StoredUser): void {
  sessionStorage.setItem(
    GLOBAL_KEYS.USER_INFO,
    JSON.stringify(user),
  )
}

export function clearStoredUser(): void {
  sessionStorage.removeItem(GLOBAL_KEYS.USER_INFO)
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
