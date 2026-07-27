/**
 * 管理员用户管理 API
 *
 * 安全策略:
 * - 不记录密码到日志或 console
 * - 不保存密码到 Store
 * - 所有接口自动带 Access Token
 */

import request from './request'
import type {
  UserListResponse,
  CreateUserResponse,
  UserStatusResponse,
  ChangeRoleResponse,
  ResetPasswordResponse,
  DeleteUserResponse,
} from '@/types/api'

export interface CreateUserParams {
  username: string
  password: string
  display_name?: string
  email?: string
  role?: string
}

export interface ListUsersParams {
  skip?: number
  limit?: number
  role?: string
  is_active?: boolean
  search?: string
}

const adminUsersApi = {
  /** 获取用户列表 */
  listUsers(params?: ListUsersParams): Promise<UserListResponse> {
    return request.get('/admin/users', { params }).then((res) => res.data)
  },

  /** 创建用户 */
  createUser(data: CreateUserParams): Promise<CreateUserResponse> {
    return request.post('/admin/users', data).then((res) => res.data)
  },

  /** 更新用户基础信息 */
  updateUser(
    userId: number,
    data: { display_name?: string; email?: string }
  ): Promise<UserStatusResponse> {
    return request.put(`/admin/users/${userId}`, data).then((res) => res.data)
  },

  /** 禁用用户 */
  disableUser(userId: number): Promise<UserStatusResponse> {
    return request.put(`/admin/users/${userId}/disable`).then((res) => res.data)
  },

  /** 启用用户 */
  enableUser(userId: number): Promise<UserStatusResponse> {
    return request.put(`/admin/users/${userId}/enable`).then((res) => res.data)
  },

  /** 修改角色 */
  changeRole(userId: number, role: string): Promise<ChangeRoleResponse> {
    return request.put(`/admin/users/${userId}/role`, { role }).then((res) => res.data)
  },

  /** 重置密码 */
  resetPassword(userId: number, newPassword: string): Promise<ResetPasswordResponse> {
    return request
      .post(`/admin/users/${userId}/reset-password`, { new_password: newPassword })
      .then((res) => res.data)
  },

  /** 删除用户（软删除） */
  deleteUser(userId: number): Promise<DeleteUserResponse> {
    return request.delete(`/admin/users/${userId}`).then((res) => res.data)
  },
}

export default adminUsersApi
