/**
 * userStorage 单元测试 — 验证用户级存储隔离
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import {
  buildUserStorageKey,
  getUserStorage,
  setUserStorage,
  removeUserStorage,
  clearAllUserStorage,
  getGlobalStorage,
  setGlobalStorage,
  registerUserIdResolver,
  runStorageMigration,
  GLOBAL_KEYS,
} from '@/utils/userStorage'

// Mock localStorage and sessionStorage
const storageMock: Record<string, string> = {}
const sessionMock: Record<string, string> = {}

beforeEach(() => {
  // Clear mocks
  Object.keys(storageMock).forEach((k) => delete storageMock[k])
  Object.keys(sessionMock).forEach((k) => delete sessionMock[k])

  // Mock localStorage
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(
    (key: unknown) => storageMock[key as string] ?? null,
  )
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(
    (key: unknown, value: unknown) => {
      storageMock[key as string] = String(value)
    },
  )
  vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(
    (key: unknown) => {
      delete storageMock[key as string]
    },
  )
  Object.defineProperty(Storage.prototype, 'length', {
    get: () => Object.keys(storageMock).length,
    configurable: true,
  })
  vi.spyOn(Storage.prototype, 'key').mockImplementation(
    (index: unknown) => Object.keys(storageMock)[index as number] ?? null,
  )

  // Mock sessionStorage
  const sessionProto = Object.getPrototypeOf(sessionStorage) || sessionStorage
  vi.spyOn(sessionProto, 'getItem').mockImplementation(
    (key: unknown) => sessionMock[key as string] ?? null,
  )
  vi.spyOn(sessionProto, 'setItem').mockImplementation(
    (key: unknown, value: unknown) => {
      sessionMock[key as string] = String(value)
    },
  )
  vi.spyOn(sessionProto, 'removeItem').mockImplementation(
    (key: unknown) => {
      delete sessionMock[key as string]
    },
  )
  Object.defineProperty(sessionProto, 'length', {
    get: () => Object.keys(sessionMock).length,
    configurable: true,
  })
  vi.spyOn(sessionProto, 'key').mockImplementation(
    (index: unknown) => Object.keys(sessionMock)[index as number] ?? null,
  )
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('buildUserStorageKey', () => {
  it('should build key with explicitly provided user ID', () => {
    const key = buildUserStorageKey('active_menu', 12)
    expect(key).toBe('yujian:12:active_menu')
  })

  it('should build key using registered resolver', () => {
    registerUserIdResolver(() => 35)
    const key = buildUserStorageKey('active_menu')
    expect(key).toBe('yujian:35:active_menu')
  })

  it('should throw when no user ID is available', () => {
    registerUserIdResolver(() => null)
    expect(() => buildUserStorageKey('active_menu')).toThrow(
      'Cannot build user storage key without user id',
    )
  })
})

describe('getUserStorage / setUserStorage / removeUserStorage', () => {
  it('should store and retrieve user-scoped data', () => {
    setUserStorage('sidebar_collapsed', true, 12)
    const result = getUserStorage('sidebar_collapsed', false, 12)
    expect(result).toBe(true)
  })

  it('should return fallback when key does not exist', () => {
    const result = getUserStorage('nonexistent', { default: true }, 12)
    expect(result).toEqual({ default: true })
  })

  it('should isolate data between different users', () => {
    setUserStorage('active_menu', '/chat', 12)
    setUserStorage('active_menu', '/history', 35)

    expect(getUserStorage('active_menu', '', 12)).toBe('/chat')
    expect(getUserStorage('active_menu', '', 35)).toBe('/history')
  })

  it('should remove user-scoped data', () => {
    setUserStorage('chat_draft', 'hello', 12)
    removeUserStorage('chat_draft', 12)
    expect(getUserStorage('chat_draft', null, 12)).toBeNull()
  })

  it('should handle corrupted JSON gracefully', () => {
    const key = buildUserStorageKey('corrupted', 12)
    localStorage.setItem(key, '{invalid json')
    const result = getUserStorage('corrupted', 'fallback', 12)
    expect(result).toBe('fallback')
  })
})

describe('clearAllUserStorage', () => {
  it('should clear all keys for a specific user', () => {
    setUserStorage('key1', 'value1', 12)
    setUserStorage('key2', 'value2', 12)
    setUserStorage('key1', 'value1', 35) // different user

    clearAllUserStorage(12)

    // User 12's data should be gone
    expect(getUserStorage('key1', null, 12)).toBeNull()
    expect(getUserStorage('key2', null, 12)).toBeNull()

    // User 35's data should still exist
    expect(getUserStorage('key1', '', 35)).toBe('value1')
  })

  it('should not clear global keys', () => {
    setGlobalStorage('theme', 'dark')
    setUserStorage('sidebar', true, 12)

    clearAllUserStorage(12)

    expect(getGlobalStorage('theme', '')).toBe('dark')
  })
})

describe('global storage', () => {
  it('should store and retrieve global data', () => {
    setGlobalStorage('theme', 'dark')
    expect(getGlobalStorage('theme', 'light')).toBe('dark')
  })

  it('should return fallback for missing global data', () => {
    expect(getGlobalStorage('nonexistent', 'default')).toBe('default')
  })
})

describe('runStorageMigration', () => {
  it('should clear legacy shared keys on first run', () => {
    // Set up some legacy keys
    localStorage.setItem('active_menu', '/chat')
    localStorage.setItem('current_session', '123')
    localStorage.setItem('sidebar_collapsed', 'true')

    runStorageMigration()

    // Legacy keys should be removed
    expect(localStorage.getItem('active_menu')).toBeNull()
    expect(localStorage.getItem('current_session')).toBeNull()
    expect(localStorage.getItem('sidebar_collapsed')).toBeNull()

    // Migration version should be set
    expect(localStorage.getItem(GLOBAL_KEYS.STORAGE_MIGRATION_VERSION)).toBe('2')
  })

  it('should only run once (idempotent)', () => {
    localStorage.setItem(GLOBAL_KEYS.STORAGE_MIGRATION_VERSION, '2')
    localStorage.setItem('active_menu', 'test')

    runStorageMigration()

    // Should not clear again since migration is complete
    expect(localStorage.getItem('active_menu')).toBe('test')
  })
})
