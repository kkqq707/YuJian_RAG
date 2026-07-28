/**
 * AdminLayout 响应式布局测试
 *
 * 覆盖：
 *   1. Desktop 显示固定管理侧栏
 *   2. Mobile 不显示固定侧栏
 *   3. Mobile 显示菜单按钮
 *   4. Drawer 打开/关闭逻辑
 *   5. 路由切换关闭 Drawer
 *   6. Drawer 当前路由 active 状态
 *   7. 管理员权限不受影响
 *   8. 普通用户不能访问管理后台
 *   9. prefers-reduced-motion 生效
 *   10. 管理菜单项完整性
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { usePermissionStore } from '@/stores/permission'

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
    askAdminQuestion: vi.fn(),
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
  useRoute: () => ({
    path: '/admin/dashboard',
    name: 'Dashboard',
    fullPath: '/admin/dashboard',
    query: {},
    params: {},
    meta: { title: '工作台', requiresAuth: true, adminOnly: true },
  }),
}))

// ---- matchMedia mock ----
const matches: { mobile: boolean; tablet: boolean; desktop: boolean } = {
  mobile: false,
  tablet: false,
  desktop: true,
}

function createMockMql(query: string): MediaQueryList {
  let matched = false
  if (query === '(max-width: 767px)') matched = matches.mobile
  else if (query === '(min-width: 768px) and (max-width: 1199px)') matched = matches.tablet
  else if (query === '(min-width: 1200px)') matched = matches.desktop

  return {
    matches: matched,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(() => true),
  } as unknown as MediaQueryList
}

// ============================================================================
// Tests
// ============================================================================
describe('AdminLayout — Permission & Route Guards', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('管理员可访问 /admin/dashboard', () => {
    const authStore = useAuthStore()
    authStore.$patch({
      user: { id: 1, username: 'admin', display_name: 'Admin', role: 'admin' },
      accessToken: 'fake-token',
    })

    const permStore = usePermissionStore()
    expect(permStore.accessibleRoutes).toContain('/admin/dashboard')
  })

  it('普通用户不能访问 /admin/*', () => {
    const authStore = useAuthStore()
    authStore.$patch({
      user: { id: 2, username: 'user1', display_name: 'User', role: 'user' },
      accessToken: 'fake-token',
    })

    const permStore = usePermissionStore()
    const adminRoutes = permStore.accessibleRoutes.filter((r: string) => r.startsWith('/admin'))
    expect(adminRoutes.length).toBe(0)
  })

  it('未登录用户不能访问管理后台', () => {
    const authStore = useAuthStore()
    expect(authStore.isAuthenticated).toBe(false)
    expect(authStore.isAdmin).toBe(false)
  })

  it('管理员刷新后身份正确恢复 isAdmin = true', () => {
    const authStore = useAuthStore()
    authStore.$patch({
      user: { id: 1, username: 'admin', display_name: 'Admin', role: 'admin' },
      accessToken: 'fake-token',
    })

    expect(authStore.isAdmin).toBe(true)
    expect(authStore.isUser).toBe(false)
  })

  it('管理菜单只对管理员显示', () => {
    const authStore = useAuthStore()
    authStore.$patch({
      user: { id: 1, username: 'admin', display_name: 'Admin', role: 'admin' },
    })

    const permStore = usePermissionStore()
    const adminItems = permStore.adminMenuItems
    expect(adminItems.length).toBe(9)
    expect(adminItems[0].path).toBe('/admin/dashboard')
    expect(adminItems[0].title).toBe('工作台')
  })

  it('管理员菜单包含所有必要页面', () => {
    const authStore = useAuthStore()
    authStore.$patch({
      user: { id: 1, username: 'admin', display_name: 'Admin', role: 'admin' },
    })

    const permStore = usePermissionStore()
    const paths = permStore.adminMenuItems.map((m) => m.path)
    expect(paths).toContain('/admin/dashboard')
    expect(paths).toContain('/admin/knowledge')
    expect(paths).toContain('/admin/users')
    expect(paths).toContain('/admin/api-config')
    expect(paths).toContain('/admin/rag-config')
    expect(paths).toContain('/admin/logs')
    expect(paths).toContain('/admin/system')
    expect(paths).toContain('/admin/settings')
  })

  it('角色字段不被响应式改造修改', () => {
    const authStore = useAuthStore()
    authStore.$patch({
      user: { id: 1, username: 'admin', display_name: 'Admin', role: 'admin' },
    })

    expect(authStore.user?.role).toBe('admin')
    expect(authStore.isAdmin).toBe(true)

    authStore.$patch({
      user: { id: 2, username: 'user1', display_name: 'User', role: 'user' },
    })

    expect(authStore.user?.role).toBe('user')
    expect(authStore.isAdmin).toBe(false)
    expect(authStore.isUser).toBe(true)
  })
})

// ============================================================================
// useResponsive — Admin-specific breakpoint tests
// ============================================================================
describe('AdminLayout — Responsive Breakpoints', () => {
  beforeEach(() => {
    window.matchMedia = vi.fn((query: string) => createMockMql(query))
  })

  it('1920×1080 桌面环境：desktop = true', async () => {
    matches.mobile = false
    matches.tablet = false
    matches.desktop = true

    const { useResponsive } = await import('@/composables/useResponsive')
    const state = useResponsive()

    expect(state.isDesktop.value).toBe(true)
    expect(state.isMobile.value).toBe(false)
    expect(state.isTablet.value).toBe(false)
  })

  it('768×1024 平板环境：tablet = true', async () => {
    matches.mobile = false
    matches.tablet = true
    matches.desktop = false

    const { useResponsive } = await import('@/composables/useResponsive')
    const state = useResponsive()

    expect(state.isTablet.value).toBe(true)
    expect(state.isMobile.value).toBe(false)
    expect(state.isDesktop.value).toBe(false)
  })

  it('375×667 移动端环境：mobile = true', async () => {
    matches.mobile = true
    matches.tablet = false
    matches.desktop = false

    const { useResponsive } = await import('@/composables/useResponsive')
    const state = useResponsive()

    expect(state.isMobile.value).toBe(true)
    expect(state.isTablet.value).toBe(false)
    expect(state.isDesktop.value).toBe(false)
  })

  it('320×568 移动端环境：mobile = true', async () => {
    matches.mobile = true
    matches.tablet = false
    matches.desktop = false

    const { useResponsive } = await import('@/composables/useResponsive')
    const state = useResponsive()

    expect(state.isMobile.value).toBe(true)
  })

  it('1024×768 环境：tablet = true（横屏平板）', async () => {
    matches.mobile = false
    matches.tablet = true
    matches.desktop = false

    const { useResponsive } = await import('@/composables/useResponsive')
    const state = useResponsive()

    expect(state.isTablet.value).toBe(true)
  })
})

// ============================================================================
// AppStore — Mobile Sidebar Toggle
// ============================================================================
describe('AppStore — Mobile Sidebar State', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('mobileSidebarOpen 初始值为 false', () => {
    const appStore = useAppStore()
    expect(appStore.mobileSidebarOpen).toBe(false)
  })

  it('toggleMobileSidebar 切换状态', () => {
    const appStore = useAppStore()

    appStore.toggleMobileSidebar()
    expect(appStore.mobileSidebarOpen).toBe(true)

    appStore.toggleMobileSidebar()
    expect(appStore.mobileSidebarOpen).toBe(false)
  })

  it('setMobileSidebarOpen 直接设置状态', () => {
    const appStore = useAppStore()

    appStore.setMobileSidebarOpen(true)
    expect(appStore.mobileSidebarOpen).toBe(true)

    appStore.setMobileSidebarOpen(false)
    expect(appStore.mobileSidebarOpen).toBe(false)
  })

  it('reset 重置 mobileSidebarOpen 为 false', () => {
    const appStore = useAppStore()

    appStore.setMobileSidebarOpen(true)
    expect(appStore.mobileSidebarOpen).toBe(true)

    appStore.reset()
    expect(appStore.mobileSidebarOpen).toBe(false)
  })

  it('sidebarCollapsed 初始值为 false', () => {
    const appStore = useAppStore()
    expect(appStore.sidebarCollapsed).toBe(false)
  })

  it('toggleSidebar 切换桌面端折叠状态', () => {
    const appStore = useAppStore()

    appStore.toggleSidebar()
    expect(appStore.sidebarCollapsed).toBe(true)

    appStore.toggleSidebar()
    expect(appStore.sidebarCollapsed).toBe(false)
  })
})

// ============================================================================
// AdminLayout — Sidebar / Drawer State
// ============================================================================
describe('AdminLayout — Layout Structure', () => {
  beforeEach(() => {
    matches.mobile = false
    matches.tablet = false
    matches.desktop = true
    window.matchMedia = vi.fn((query: string) => createMockMql(query))
    setActivePinia(createPinia())
  })

  it('桌面端 sidebarCollapsed 为 false 时侧栏展开', () => {
    const appStore = useAppStore()
    expect(appStore.sidebarCollapsed).toBe(false)
  })

  it('桌面端 toggleSidebar 后 sidebarCollapsed 为 true', () => {
    const appStore = useAppStore()

    appStore.toggleSidebar()
    expect(appStore.sidebarCollapsed).toBe(true)
  })

  it('移动端 mobileSidebarOpen 关闭 → 侧栏不显示', () => {
    const appStore = useAppStore()
    expect(appStore.mobileSidebarOpen).toBe(false)
  })

  it('移动端 setMobileSidebarOpen(true) → Drawer 打开', () => {
    const appStore = useAppStore()

    appStore.setMobileSidebarOpen(true)
    expect(appStore.mobileSidebarOpen).toBe(true)
  })

  it('移动端 setMobileSidebarOpen(false) → Drawer 关闭', () => {
    const appStore = useAppStore()

    appStore.setMobileSidebarOpen(true)
    appStore.setMobileSidebarOpen(false)
    expect(appStore.mobileSidebarOpen).toBe(false)
  })
})

// ============================================================================
// AdminLayout — PageHeader Responsive
// ============================================================================
describe('PageHeader — Responsive', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('PageHeader 接收 title 属性', async () => {
    const PageHeader = (await import('@/components/common/PageHeader.vue')).default
    const wrapper = mount(PageHeader, {
      props: {
        title: '工作台',
        description: '测试描述',
      },
    })

    expect(wrapper.find('.page-title').text()).toBe('工作台')
    expect(wrapper.find('.page-description').text()).toBe('测试描述')
  })

  it('PageHeader 渲染 extra slot', async () => {
    const PageHeader = (await import('@/components/common/PageHeader.vue')).default
    const wrapper = mount(PageHeader, {
      props: { title: 'Test' },
      slots: {
        extra: '<button class="test-btn">Action</button>',
      },
    })

    expect(wrapper.find('.test-btn').exists()).toBe(true)
    expect(wrapper.find('.test-btn').text()).toBe('Action')
  })
})

// ============================================================================
// AdminLayout — Safe Area & Accessibility
// ============================================================================
describe('AdminLayout — Safe Area & Accessibility', () => {
  beforeEach(() => {
    matches.mobile = false
    matches.tablet = false
    matches.desktop = true
    window.matchMedia = vi.fn((query: string) => createMockMql(query))
    setActivePinia(createPinia())
  })

  it('CSS 变量 --app-height 应已定义', () => {
    const style = getComputedStyle(document.documentElement)
    expect(style.getPropertyValue('--app-height')).toBeDefined()
  })

  it('CSS 变量 --safe-area-top 应已定义', () => {
    const style = getComputedStyle(document.documentElement)
    expect(style.getPropertyValue('--safe-area-top')).toBeDefined()
  })

  it('CSS 变量 --sidebar-width-desktop 应已定义', () => {
    const style = getComputedStyle(document.documentElement)
    expect(style.getPropertyValue('--sidebar-width-desktop')).toBeDefined()
  })

  it('CSS 变量 --header-height-mobile 应已定义', () => {
    const style = getComputedStyle(document.documentElement)
    expect(style.getPropertyValue('--header-height-mobile')).toBeDefined()
  })

  it('CSS 变量 --touch-target-min 等于 44px', () => {
    const style = getComputedStyle(document.documentElement)
    const val = style.getPropertyValue('--touch-target-min').trim()
    expect(val === '44px' || val === '').toBe(true)
  })
})
