/**
 * 认证 API — 登录、刷新、退出、当前用户、修改密码
 */

import request from './request'
import type {
  LoginRequest,
  TokenResponse,
  RefreshRequest,
  RefreshResponse,
  MessageResponse,
  ChangePasswordRequest,
  UserInfo,
} from '@/types/auth'

const authApi = {
  /** 登录 */
  login(data: LoginRequest): Promise<TokenResponse> {
    return request.post('/auth/login', data).then((res) => res.data)
  },

  /** 刷新 Token */
  refresh(data: RefreshRequest): Promise<RefreshResponse> {
    return request.post('/auth/refresh', data).then((res) => res.data)
  },

  /** 退出登录 */
  logout(data: RefreshRequest): Promise<MessageResponse> {
    return request.post('/auth/logout', data).then((res) => res.data)
  },

  /** 退出所有设备 */
  logoutAll(): Promise<MessageResponse> {
    return request.post('/auth/logout-all').then((res) => res.data)
  },

  /** 获取当前用户信息 */
  me(): Promise<{ user: UserInfo }> {
    return request.get('/auth/me').then((res) => res.data)
  },

  /** 修改密码 */
  changePassword(data: ChangePasswordRequest): Promise<MessageResponse> {
    return request.post('/auth/change-password', data).then((res) => res.data)
  },
}

export default authApi
