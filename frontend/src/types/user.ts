import type { UserRole } from './auth'

/** 本地存储的安全用户信息 */
export interface StoredUser {
  id: number
  username: string
  display_name: string
  role: UserRole
}
