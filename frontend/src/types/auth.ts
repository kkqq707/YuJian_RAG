/** 用户角色 */
export type UserRole = 'admin' | 'user'

/** 安全的用户信息 — 不含 password_hash */
export interface UserInfo {
  id: number
  username: string
  display_name: string
  role: UserRole
}

/** 登录请求 */
export interface LoginRequest {
  username: string
  password: string
}

/** Token 响应 */
export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: UserInfo
}

/** Refresh 请求 */
export interface RefreshRequest {
  refresh_token: string
}

/** Refresh 响应 */
export interface RefreshResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

/** 修改密码请求 */
export interface ChangePasswordRequest {
  old_password: string
  new_password: string
}

/** 通用消息响应 */
export interface MessageResponse {
  success: boolean
  message: string
}
