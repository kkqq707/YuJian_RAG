/**
 * 权限与菜单 Store
 */

import { defineStore } from 'pinia'
import { computed } from 'vue'
import { useAuthStore } from './auth'
import type { RouteRecordRaw } from 'vue-router'

export interface MenuItem {
  path: string
  title: string
  icon: string
  children?: MenuItem[]
  hidden?: boolean
}

export const usePermissionStore = defineStore('permission', () => {
  const authStore = useAuthStore()

  // ---- Admin 菜单 ----
  const adminMenuItems: MenuItem[] = [
    { path: '/admin/dashboard', title: '工作台', icon: 'Monitor' },
    { path: '/admin/knowledge', title: '知识库管理', icon: 'Folder' },
    { path: '/admin/chat-preview', title: '智能问答', icon: 'Message' },
    { path: '/admin/users', title: '用户管理', icon: 'User' },
    { path: '/admin/api-config', title: 'AI 服务配置', icon: 'Setting' },
    { path: '/admin/rag-config', title: 'RAG 配置', icon: 'Operation' },
    { path: '/admin/logs', title: '系统日志', icon: 'Tickets' },
    { path: '/admin/system', title: '系统监控', icon: 'DataAnalysis' },
    { path: '/admin/settings', title: '系统设置', icon: 'Setting' },
  ]

  // ---- User 菜单 ----
  const userMenuItems: MenuItem[] = [
    { path: '/chat', title: '智能问答', icon: 'Message' },
    { path: '/history', title: '历史记录', icon: 'Clock' },
    { path: '/profile', title: '个人中心', icon: 'User' },
  ]

  // ---- Getters ----
  const menuItems = computed(() => {
    if (authStore.isAdmin) return adminMenuItems
    return userMenuItems
  })

  const accessibleRoutes = computed(() => {
    // 返回当前角色可访问的路由路径列表
    if (authStore.isAdmin) {
      return [
        '/admin/dashboard',
        '/admin/chat-preview',
        '/admin/knowledge',
        '/admin/users',
        '/admin/api-config',
        '/admin/rag-config',
        '/admin/audit-logs',
        '/admin/logs',
        '/admin/system',
        '/admin/settings',
        '/admin/profile',
        '/chat',
        '/history',
        '/profile',
      ]
    }
    return ['/chat', '/history', '/profile']
  })

  return {
    adminMenuItems,
    userMenuItems,
    menuItems,
    accessibleRoutes,
  }
})
