/**
 * 用户级 localStorage/sessionStorage 工具
 *
 * 解决的问题:
 * - 不同账号共用一个 localStorage key，导致切号后残留旧账号数据
 * - 旧版本全局 key（如 active_menu, current_session）不再使用
 *
 * 原则:
 * 1. 所有账号专属存储的 key 格式: yujian:{userId}:{baseKey}
 * 2. userId 从 authStore 实时读取，不缓存
 * 3. 无法确定用户 ID 时拒绝写入
 * 4. 退出登录后可安全清除指定用户的存储
 */

const NAMESPACE = 'yujian'

// ---- 全局存储 key（非用户专属） ----
// 这些 key 不包含 user ID，所有用户共享
export const GLOBAL_KEYS = {
  REMEMBERED_USERNAME: 'remembered_username',
  STORAGE_MIGRATION_VERSION: `${NAMESPACE}:storage_migration_version`,
} as const

// ---- 旧的共享 key（需要迁移/清理） ----
const LEGACY_SHARED_KEYS = [
  'active_menu',
  'current_session',
  'chat_draft',
  'chat_history',
  'sidebar_collapsed',
  'selected_model',
  'recent_page',
  'user_settings',
  'current_conversation',
  'selected_session',
  'pinia',
]

// ---- 获取当前用户 ID ----

let _userIdResolver: (() => number | null) | null = null

/**
 * 注册用户 ID 解析器（在 main.ts 中调用一次）
 */
export function registerUserIdResolver(resolver: () => number | null): void {
  _userIdResolver = resolver
}

function getCurrentUserId(): number | null {
  // 优先使用注册的解析器（实时反映当前登录用户）
  if (_userIdResolver) {
    const id = _userIdResolver()
    if (id !== null && id !== undefined) return id
    // 解析器返回 null/undefined 时继续尝试降级方案
  }

  // 降级：扫描 sessionStorage 查找用户信息
  // 用户信息 key 格式: yujian:{userId}:user_info
  try {
    const prefix = `${NAMESPACE}:`
    const suffix = ':user_info'
    for (let i = 0; i < sessionStorage.length; i++) {
      const key = sessionStorage.key(i)
      if (
        key &&
        key.startsWith(prefix) &&
        key.endsWith(suffix)
      ) {
        // 从 key 中提取 userId: yujian:{userId}:user_info
        const idStr = key.slice(prefix.length, key.length - suffix.length)
        const id = parseInt(idStr, 10)
        if (!isNaN(id) && id > 0) {
          return id
        }
      }
    }
  } catch {
    // ignore
  }
  return null
}

// ---- Key 构建 ----

export function buildUserStorageKey(
  baseKey: string,
  userId?: number | null,
): string {
  const id = userId ?? getCurrentUserId()
  if (id === null || id === undefined) {
    throw new Error(
      `Cannot build user storage key without user id: ${baseKey}`,
    )
  }
  return `${NAMESPACE}:${id}:${baseKey}`
}

// ---- 读写 ----

export function getUserStorage<T>(
  baseKey: string,
  fallback: T,
  userId?: number | null,
): T {
  try {
    const raw = localStorage.getItem(buildUserStorageKey(baseKey, userId))
    if (raw === null) return fallback
    return JSON.parse(raw) as T
  } catch {
    return fallback
  }
}

export function setUserStorage<T>(
  baseKey: string,
  value: T,
  userId?: number | null,
): void {
  try {
    localStorage.setItem(
      buildUserStorageKey(baseKey, userId),
      JSON.stringify(value),
    )
  } catch {
    // 存储满或禁用时静默失败
  }
}

export function removeUserStorage(
  baseKey: string,
  userId?: number | null,
): void {
  localStorage.removeItem(buildUserStorageKey(baseKey, userId))
}

// ---- 全局存储（非用户专属） ----

export function getGlobalStorage<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    if (raw === null) return fallback
    return JSON.parse(raw) as T
  } catch {
    return fallback
  }
}

export function setGlobalStorage<T>(key: string, value: T): void {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // ignore
  }
}

// ---- 用户级 sessionStorage ----

export function getUserSessionStorage<T>(
  baseKey: string,
  fallback: T,
  userId?: number | null,
): T {
  try {
    const raw = sessionStorage.getItem(buildUserStorageKey(baseKey, userId))
    if (raw === null) return fallback
    return JSON.parse(raw) as T
  } catch {
    return fallback
  }
}

export function setUserSessionStorage<T>(
  baseKey: string,
  value: T,
  userId?: number | null,
): void {
  try {
    sessionStorage.setItem(
      buildUserStorageKey(baseKey, userId),
      JSON.stringify(value),
    )
  } catch {
    // ignore
  }
}

export function removeUserSessionStorage(
  baseKey: string,
  userId?: number | null,
): void {
  sessionStorage.removeItem(buildUserStorageKey(baseKey, userId))
}

// ---- 清除用户所有存储 ----

/**
 * 清除指定用户在 localStorage 和 sessionStorage 中的所有数据
 */
export function clearAllUserStorage(userId: number | null): void {
  if (userId === null || userId === undefined) return

  const userPrefix = `${NAMESPACE}:${userId}:`

  // 清除 localStorage
  for (let i = localStorage.length - 1; i >= 0; i--) {
    const key = localStorage.key(i)
    if (key && key.startsWith(userPrefix)) {
      localStorage.removeItem(key)
    }
  }

  // 清除 sessionStorage
  for (let i = sessionStorage.length - 1; i >= 0; i--) {
    const key = sessionStorage.key(i)
    if (key && key.startsWith(userPrefix)) {
      sessionStorage.removeItem(key)
    }
  }
}

/**
 * 清除当前用户的所有存储（需要先知道用户 ID）
 */
export function clearCurrentUserAllStorage(): void {
  const userId = getCurrentUserId()
  if (userId !== null) {
    clearAllUserStorage(userId)
  }
}

// ---- 旧数据迁移 ----

const CURRENT_MIGRATION_VERSION = 2

/**
 * 执行旧 localStorage 数据迁移
 *
 * - v1→v2: 清除所有旧版本共享 key，无法确认归属的数据直接删除
 * - 设置版本标识，避免重复迁移
 */
export function runStorageMigration(): void {
  const version = localStorage.getItem(GLOBAL_KEYS.STORAGE_MIGRATION_VERSION)
  const currentVersion = version ? parseInt(version, 10) : 0

  if (currentVersion >= CURRENT_MIGRATION_VERSION) return

  // 清除所有旧版共享 key
  for (const key of LEGACY_SHARED_KEYS) {
    localStorage.removeItem(key)
  }

  // 标记迁移完成
  localStorage.setItem(
    GLOBAL_KEYS.STORAGE_MIGRATION_VERSION,
    String(CURRENT_MIGRATION_VERSION),
  )
}
