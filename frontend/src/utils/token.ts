/**
 * Token 管理工具
 *
 * 安全策略:
 * - Access Token 保存在 Pinia 内存中，不写入持久存储
 * - Refresh Token 保存在 sessionStorage
 * - 不在 console.log 输出 Token
 * - 不在 URL 中传递 Token
 */

const REFRESH_TOKEN_KEY = 'refresh_token'

export function getAccessToken(): string | null {
  // Access Token 由 Pinia store 管理，此处作为兼容层
  return null
}

export function setAccessToken(_token: string): void {
  // Access Token 仅保存在 Pinia store 内存中
  // 此函数为接口兼容保留
}

export function clearAccessToken(): void {
  // 由 authStore.logout() 统一清理
}

export function getRefreshToken(): string | null {
  return sessionStorage.getItem(REFRESH_TOKEN_KEY)
}

export function setRefreshToken(token: string): void {
  sessionStorage.setItem(REFRESH_TOKEN_KEY, token)
}

export function clearAuthTokens(): void {
  sessionStorage.removeItem(REFRESH_TOKEN_KEY)
}
