/**
 * 应用全局状态 Store
 *
 * 安全策略:
 * - 侧边栏折叠状态按用户隔离存储
 * - 提供 reset 方法用于退出登录时清理
 * - 不与 auth/chat store 中的用户数据交叉
 * - 用户切换时自动重新加载该用户的侧边栏状态
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { setSidebarCollapsed } from '@/utils/storage'
import { getUserStorage } from '@/utils/userStorage'

const SIDEBAR_KEY_BASE = 'sidebar_collapsed'

export const useAppStore = defineStore('app', () => {
  // ---- State ----
  const sidebarCollapsed = ref(false)
  const globalLoading = ref(false)
  const backendOnline = ref(false)
  const mobileSidebarOpen = ref(false)
  const currentUserId = ref<number | null>(null)

  // ---- Actions ----

  function toggleSidebar(): void {
    sidebarCollapsed.value = !sidebarCollapsed.value
    setSidebarCollapsed(sidebarCollapsed.value)
  }

  function setSidebarState(collapsed: boolean): void {
    sidebarCollapsed.value = collapsed
    setSidebarCollapsed(collapsed)
  }

  /**
   * 为指定用户初始化侧边栏折叠状态
   *
   * 调用时机:
   * - 登录成功后
   * - 页面刷新后恢复会话时
   * - 账号切换时
   *
   * @param userId - 当前登录用户的 ID
   */
  function initializeSidebar(userId: number): void {
    currentUserId.value = userId
    try {
      sidebarCollapsed.value = getUserStorage<boolean>(
        SIDEBAR_KEY_BASE,
        false,
        userId,
      )
    } catch {
      sidebarCollapsed.value = false
    }
  }

  function toggleMobileSidebar(): void {
    mobileSidebarOpen.value = !mobileSidebarOpen.value
  }

  function setMobileSidebarOpen(open: boolean): void {
    mobileSidebarOpen.value = open
  }

  function setGlobalLoading(loading: boolean): void {
    globalLoading.value = loading
  }

  function setBackendOnline(online: boolean): void {
    backendOnline.value = online
  }

  /**
   * 重置应用 UI 状态（退出登录时调用）
   *
   * 保留:
   * - backendOnline: 不重置后端连接状态
   *
   * 重置:
   * - sidebarCollapsed: 重置为默认展开
   * - currentUserId: 清除当前用户 ID
   * - globalLoading: 重置为 false
   * - mobileSidebarOpen: 关闭移动端侧栏
   */
  function reset(): void {
    sidebarCollapsed.value = false
    currentUserId.value = null
    globalLoading.value = false
    mobileSidebarOpen.value = false
  }

  return {
    sidebarCollapsed,
    globalLoading,
    backendOnline,
    mobileSidebarOpen,
    currentUserId,
    toggleSidebar,
    setSidebarState,
    initializeSidebar,
    toggleMobileSidebar,
    setMobileSidebarOpen,
    setGlobalLoading,
    setBackendOnline,
    reset,
  }
})
