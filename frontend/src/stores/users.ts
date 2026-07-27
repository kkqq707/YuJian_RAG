/**
 * 用户管理 Store
 *
 * 安全策略:
 * - 不保存密码
 * - 不保存 Token
 * - 页面刷新后重新从 API 获取数据
 * - 不将管理数据长期写入 localStorage
 */

import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import adminUsersApi from '@/api/adminUsers'
import { extractErrorMessage } from '@/utils/error'
import type {
  AdminUserItem,
  CreateUserResponse,
  UserStatusResponse,
  ChangeRoleResponse,
  ResetPasswordResponse,
  DeleteUserResponse,
  UserStats,
} from '@/types/api'
import type { CreateUserParams, ListUsersParams } from '@/api/adminUsers'

export interface UserFilters {
  search: string
  role: string
  isActive: string
}

export interface UserPagination {
  page: number
  pageSize: number
  total: number
}

export const useUsersStore = defineStore('users', () => {
  // ---- State ----
  const users = ref<AdminUserItem[]>([])
  const statistics = ref<UserStats>({
    total_users: 0,
    admin_users: 0,
    regular_users: 0,
    disabled_users: 0,
  })
  const loading = ref(false)
  const error = ref('')

  const filters = reactive<UserFilters>({
    search: '',
    role: '',
    isActive: '',
  })

  const pagination = reactive<UserPagination>({
    page: 1,
    pageSize: 20,
    total: 0,
  })

  // ---- Actions ----

  /** 获取用户列表 */
  async function fetchUsers(): Promise<void> {
    loading.value = true
    error.value = ''
    try {
      const params: ListUsersParams = {
        skip: (pagination.page - 1) * pagination.pageSize,
        limit: pagination.pageSize,
      }
      if (filters.search) params.search = filters.search
      if (filters.role) params.role = filters.role
      if (filters.isActive !== '') {
        params.is_active = filters.isActive === 'active'
      }

      const result = await adminUsersApi.listUsers(params)
      users.value = result.users || []
      pagination.total = result.total
    } catch (err: unknown) {
      error.value = extractErrorMessage(err)
    } finally {
      loading.value = false
    }
  }

  /** 获取用户统计 */
  async function fetchStatistics(): Promise<void> {
    try {
      // 获取所有用户来统计
      const result = await adminUsersApi.listUsers({ limit: 500 })
      const all = result.users || []

      statistics.value = {
        total_users: result.total,
        admin_users: all.filter((u) => u.role === 'admin').length,
        regular_users: all.filter((u) => u.role === 'user').length,
        disabled_users: all.filter((u) => !u.is_active).length,
      }
    } catch {
      // 统计失败不阻塞列表
    }
  }

  /** 创建用户 */
  async function createUser(data: CreateUserParams): Promise<CreateUserResponse> {
    const result = await adminUsersApi.createUser(data)
    await refreshAll()
    return result
  }

  /** 更新用户基础信息 */
  async function updateUser(
    userId: number,
    data: { display_name?: string; email?: string }
  ): Promise<UserStatusResponse> {
    const result = await adminUsersApi.updateUser(userId, data)
    await refreshAll()
    return result
  }

  /** 启用用户 */
  async function enableUser(userId: number): Promise<UserStatusResponse> {
    const result = await adminUsersApi.enableUser(userId)
    await refreshAll()
    return result
  }

  /** 禁用用户 */
  async function disableUser(userId: number): Promise<UserStatusResponse> {
    const result = await adminUsersApi.disableUser(userId)
    await refreshAll()
    return result
  }

  /** 修改角色 */
  async function changeRole(userId: number, role: string): Promise<ChangeRoleResponse> {
    const result = await adminUsersApi.changeRole(userId, role)
    await refreshAll()
    return result
  }

  /** 重置密码 */
  async function resetPassword(
    userId: number,
    newPassword: string
  ): Promise<ResetPasswordResponse> {
    const result = await adminUsersApi.resetPassword(userId, newPassword)
    return result
  }

  /** 删除用户 */
  async function deleteUser(userId: number): Promise<DeleteUserResponse> {
    const result = await adminUsersApi.deleteUser(userId)
    await refreshAll()
    return result
  }

  /** 刷新全部数据 */
  async function refreshAll(): Promise<void> {
    await Promise.all([fetchUsers(), fetchStatistics()])
  }

  /** 重置筛选条件 */
  function resetFilters(): void {
    filters.search = ''
    filters.role = ''
    filters.isActive = ''
    pagination.page = 1
  }

  /** 设置分页 */
  function setPage(page: number): void {
    pagination.page = page
  }

  return {
    // State
    users,
    statistics,
    loading,
    error,
    filters,
    pagination,
    // Actions
    fetchUsers,
    fetchStatistics,
    createUser,
    updateUser,
    enableUser,
    disableUser,
    changeRole,
    resetPassword,
    deleteUser,
    refreshAll,
    resetFilters,
    setPage,
  }
})
