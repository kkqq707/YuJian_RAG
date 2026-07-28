/**
 * 路由与权限逻辑单元测试
 *
 * 覆盖:
 * - getDefaultRouteByRole
 * - resolvePostLoginRedirect
 * - isUserOnlyPath
 * - Route meta 权限标记
 * - permission store accessibleRoutes
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { getDefaultRouteByRole, resolvePostLoginRedirect } from '@/router/routes'
import { usePermissionStore } from '@/stores/permission'
import { useAuthStore } from '@/stores/auth'

// Mock dependencies
vi.mock('@/api/auth', () => ({
  default: {
    login: vi.fn(),
    logout: vi.fn(),
    refresh: vi.fn(),
    me: vi.fn(),
    changePassword: vi.fn(),
  },
}))

vi.mock('@/api/chat', () => ({
  default: {
    listSessions: vi.fn(),
    createSession: vi.fn(),
    getSessionMessages: vi.fn(),
    sendMessage: vi.fn(),
    deleteSession: vi.fn(),
    askQuestion: vi.fn(),
  },
}))

vi.mock('@/api/request', () => ({
  setAccessToken: vi.fn(),
  setRefreshTokenValue: vi.fn(),
  getAccessTokenValue: vi.fn(),
  getRefreshTokenValue: vi.fn(),
}))

vi.mock('@/utils/token', () => ({
  getAccessToken: vi.fn(),
  setAccessToken: vi.fn(),
  clearAccessToken: vi.fn(),
  getRefreshToken: vi.fn(),
  setRefreshToken: vi.fn(),
  clearAuthTokens: vi.fn(),
}))

vi.mock('@/utils/storage', () => ({
  getStoredUser: vi.fn(),
  setStoredUser: vi.fn(),
  clearStoredUser: vi.fn(),
  getSidebarCollapsed: vi.fn().mockReturnValue(false),
  setSidebarCollapsed: vi.fn(),
}))

vi.mock('@/utils/userStorage', () => ({
  buildUserStorageKey: vi.fn(),
  getUserStorage: vi.fn(() => false),
  setUserStorage: vi.fn(),
  removeUserStorage: vi.fn(),
  clearAllUserStorage: vi.fn(),
  getGlobalStorage: vi.fn(() => null),
  setGlobalStorage: vi.fn(),
  registerUserIdResolver: vi.fn(),
  runStorageMigration: vi.fn(),
  GLOBAL_KEYS: { REMEMBERED_USERNAME: 'remembered_username', STORAGE_MIGRATION_VERSION: 'yujian:storage_migration_version' },
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useRoute: () => ({ path: '/chat', name: 'Chat', fullPath: '/chat', query: {}, params: {} }),
}))

// ============================================================================
// getDefaultRouteByRole
// ============================================================================
describe('getDefaultRouteByRole', () => {
  it('returns /admin/dashboard for admin', () => {
    expect(getDefaultRouteByRole(true)).toBe('/admin/dashboard')
  })

  it('returns /chat for non-admin', () => {
    expect(getDefaultRouteByRole(false)).toBe('/chat')
  })
})

// ============================================================================
// resolvePostLoginRedirect
// ============================================================================
describe('resolvePostLoginRedirect', () => {
  it('returns null for empty redirect', () => {
    expect(resolvePostLoginRedirect('', true)).toBeNull()
    expect(resolvePostLoginRedirect(undefined, false)).toBeNull()
  })

  it('returns null for /login redirect', () => {
    expect(resolvePostLoginRedirect('/login', true)).toBeNull()
  })

  it('returns null for / redirect', () => {
    expect(resolvePostLoginRedirect('/', true)).toBeNull()
  })

  it('allows admin to redirect to /admin/*', () => {
    expect(resolvePostLoginRedirect('/admin/dashboard', true)).toBe('/admin/dashboard')
    expect(resolvePostLoginRedirect('/admin/users', true)).toBe('/admin/users')
  })

  it('blocks admin from redirecting to /chat', () => {
    expect(resolvePostLoginRedirect('/chat', true)).toBeNull()
  })

  it('blocks admin from redirecting to /history', () => {
    expect(resolvePostLoginRedirect('/history', true)).toBeNull()
  })

  it('allows user to redirect to /chat', () => {
    expect(resolvePostLoginRedirect('/chat', false)).toBe('/chat')
  })

  it('allows user to redirect to /history', () => {
    expect(resolvePostLoginRedirect('/history', false)).toBe('/history')
  })

  it('blocks user from redirecting to /admin/*', () => {
    expect(resolvePostLoginRedirect('/admin/dashboard', false)).toBeNull()
    expect(resolvePostLoginRedirect('/admin/users', false)).toBeNull()
  })
})

// ============================================================================
// Permission Store — accessibleRoutes
// ============================================================================
describe('usePermissionStore — accessibleRoutes', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('admin accessibleRoutes should NOT include user-only paths', () => {
    const authStore = useAuthStore()
    authStore.$patch({
      user: { id: 1, username: 'admin', display_name: 'Admin', role: 'admin' },
    })

    const permStore = usePermissionStore()
    const routes = permStore.accessibleRoutes

    expect(routes).not.toContain('/chat')
    expect(routes).not.toContain('/history')
    expect(routes).not.toContain('/profile')
    expect(routes).toContain('/admin/dashboard')
  })

  it('user accessibleRoutes should include user paths', () => {
    const authStore = useAuthStore()
    authStore.$patch({
      user: { id: 2, username: 'user1', display_name: 'User 1', role: 'user' },
    })

    const permStore = usePermissionStore()
    const routes = permStore.accessibleRoutes

    expect(routes).toContain('/chat')
    expect(routes).toContain('/history')
    expect(routes).toContain('/profile')
  })

  it('user accessibleRoutes should NOT include admin paths', () => {
    const authStore = useAuthStore()
    authStore.$patch({
      user: { id: 2, username: 'user1', display_name: 'User 1', role: 'user' },
    })

    const permStore = usePermissionStore()
    const routes = permStore.accessibleRoutes

    expect(routes.every((r) => !r.startsWith('/admin'))).toBe(true)
  })
})

// ============================================================================
// AuthStore — role computation
// ============================================================================
describe('useAuthStore — role computation', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('isAdmin is true when role is admin', () => {
    const store = useAuthStore()
    store.$patch({
      user: { id: 1, username: 'admin', display_name: 'Admin', role: 'admin' },
      accessToken: 'fake-token',
    })
    expect(store.isAdmin).toBe(true)
    expect(store.isUser).toBe(false)
  })

  it('isUser is true when role is user', () => {
    const store = useAuthStore()
    store.$patch({
      user: { id: 2, username: 'user1', display_name: 'User', role: 'user' },
      accessToken: 'fake-token',
    })
    expect(store.isAdmin).toBe(false)
    expect(store.isUser).toBe(true)
  })

  it('sessionRestored starts as false', () => {
    const store = useAuthStore()
    expect(store.sessionRestored).toBe(false)
  })

  it('silentCleanup resets sessionRestored', () => {
    const store = useAuthStore()
    store.$patch({
      user: { id: 1, username: 'admin', display_name: 'Admin', role: 'admin' },
      accessToken: 'fake',
    })
    // Set sessionRestored to true first
    store.sessionRestored = true
    store.silentCleanup()
    expect(store.sessionRestored).toBe(false)
    expect(store.user).toBeNull()
  })
})
