/**
 * Store 单元测试 — 验证响应式和账号隔离
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { useChatStore } from '@/stores/chat'

// Mock API modules
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
    listSessions: vi.fn().mockResolvedValue({ sessions: [], total: 0, page: 1, page_size: 20 }),
    createSession: vi.fn(),
    getSessionMessages: vi.fn(),
    sendMessage: vi.fn(),
    deleteSession: vi.fn(),
    askQuestion: vi.fn(),
    getChatPageStats: vi.fn(),
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

vi.mock('@/utils/userStorage', () => {
  const store: Record<string, string> = {}
  return {
    buildUserStorageKey: vi.fn((key: string, userId?: number) =>
      userId ? `yujian:${userId}:${key}` : `yujian:unknown:${key}`,
    ),
    getUserStorage: vi.fn((key: string, fallback: unknown) => {
      const k = String(key)
      return k in store ? JSON.parse(store[k]) : fallback
    }),
    setUserStorage: vi.fn((key: string, value: unknown) => {
      store[String(key)] = JSON.stringify(value)
    }),
    removeUserStorage: vi.fn((key: string) => {
      delete store[String(key)]
    }),
    clearAllUserStorage: vi.fn(),
    getGlobalStorage: vi.fn(() => null),
    setGlobalStorage: vi.fn(),
    registerUserIdResolver: vi.fn(),
    runStorageMigration: vi.fn(),
    GLOBAL_KEYS: {
      REMEMBERED_USERNAME: 'remembered_username',
      STORAGE_MIGRATION_VERSION: 'yujian:storage_migration_version',
    },
  }
})

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
  }),
  useRoute: () => ({
    path: '/chat',
    name: 'Chat',
    fullPath: '/chat',
    query: {},
    params: {},
  }),
}))

describe('useAppStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('should toggle sidebar and update state reactively', () => {
    const store = useAppStore()
    expect(store.sidebarCollapsed).toBe(false)

    store.toggleSidebar()
    expect(store.sidebarCollapsed).toBe(true)

    store.toggleSidebar()
    expect(store.sidebarCollapsed).toBe(false)
  })

  it('should set sidebar state explicitly', () => {
    const store = useAppStore()
    store.setSidebarState(true)
    expect(store.sidebarCollapsed).toBe(true)

    store.setSidebarState(false)
    expect(store.sidebarCollapsed).toBe(false)
  })

  it('should reset to defaults', () => {
    const store = useAppStore()
    store.toggleSidebar()
    store.setGlobalLoading(true)
    store.setMobileSidebarOpen(true)

    store.reset()

    expect(store.sidebarCollapsed).toBe(false)
    expect(store.globalLoading).toBe(false)
    expect(store.mobileSidebarOpen).toBe(false)
    // backendOnline should NOT be reset
  })

  it('should toggle mobile sidebar', () => {
    const store = useAppStore()
    expect(store.mobileSidebarOpen).toBe(false)

    store.toggleMobileSidebar()
    expect(store.mobileSidebarOpen).toBe(true)

    store.setMobileSidebarOpen(false)
    expect(store.mobileSidebarOpen).toBe(false)
  })
})

describe('useAuthStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('should start unauthenticated', () => {
    const store = useAuthStore()
    expect(store.isAuthenticated).toBe(false)
    expect(store.user).toBeNull()
    expect(store.accessToken).toBeNull()
  })

  it('should clear state on silentCleanup', () => {
    const store = useAuthStore()
    // Simulate having user data
    store.$patch({
      accessToken: 'fake-token',
      user: { id: 1, username: 'test', display_name: 'Test', role: 'user' },
    })

    store.silentCleanup()

    expect(store.accessToken).toBeNull()
    expect(store.user).toBeNull()
    expect(store.initialized).toBe(false) // not changed by silentCleanup
  })

  it('should clear state on forceLogout', async () => {
    const store = useAuthStore()
    store.$patch({
      accessToken: 'fake-token',
      user: { id: 1, username: 'test', display_name: 'Test', role: 'user' },
    })

    await store.forceLogout()

    expect(store.accessToken).toBeNull()
    expect(store.user).toBeNull()
  })

  it('should correctly compute isAdmin and isUser', () => {
    const store = useAuthStore()
    store.$patch({
      user: { id: 1, username: 'admin', display_name: 'Admin', role: 'admin' },
    })
    expect(store.isAdmin).toBe(true)
    expect(store.isUser).toBe(false)

    store.$patch({
      user: { id: 2, username: 'user1', display_name: 'User 1', role: 'user' },
    })
    expect(store.isAdmin).toBe(false)
    expect(store.isUser).toBe(true)
  })

  it('should compute userId correctly', () => {
    const store = useAuthStore()
    expect(store.userId).toBeNull()

    store.$patch({
      user: { id: 42, username: 'test', display_name: 'Test', role: 'user' },
    })
    expect(store.userId).toBe(42)
  })
})

describe('useChatStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('should start with empty sessions', () => {
    const store = useChatStore()
    expect(store.sessions).toEqual([])
    expect(store.activeSessionId).toBeNull()
    expect(store.hasMessages).toBe(false)
    expect(store.sending).toBe(false)
  })

  it('should create a new session (local, no API call)', () => {
    const store = useChatStore()
    store.createSession()
    expect(store.activeSessionId).toBeNull()
    // createSession just clears activeSessionId to show welcome panel
  })

  it('should clear session', () => {
    const store = useChatStore()
    // Simulate having an active session
    store.$patch({
      activeSessionId: '123',
    })
    store.clearSession()
    expect(store.activeSessionId).toBeNull()
  })

  it('should reset to empty state', () => {
    const store = useChatStore()
    store.$patch({
      sessions: [
        {
          id: '1',
          title: 'Test',
          messages: [],
          createdAt: '2024-01-01',
          updatedAt: '2024-01-01',
        },
      ],
      activeSessionId: '1',
      sending: true,
      initialized: true,
    })

    store.reset()

    expect(store.sessions).toEqual([])
    expect(store.activeSessionId).toBeNull()
    expect(store.sending).toBe(false)
    expect(store.initialized).toBe(false)
  })

  it('should have empty activeMessages when no session', () => {
    const store = useChatStore()
    expect(store.activeMessages).toEqual([])
    expect(store.activeSession).toBeNull()
  })

  it('should delete session and clear active if it was active', async () => {
    const store = useChatStore()
    store.$patch({
      sessions: [
        {
          id: '1',
          title: 'Session 1',
          messages: [],
          createdAt: '2024-01-01',
          updatedAt: '2024-01-01',
        },
      ],
      activeSessionId: '1',
    })

    await store.deleteSession('1')

    expect(store.sessions).toEqual([])
    expect(store.activeSessionId).toBeNull()
  })

  it('should not activate session when switching to non-existent session', async () => {
    const store = useChatStore()
    store.$patch({
      activeSessionId: null,
    })

    await store.switchSession('nonexistent')

    // Should not change since session doesn't exist
    expect(store.activeSessionId).toBeNull()
  })
})
