/**
 * Axios 实例 — 统一请求封装
 *
 * 功能:
 * - 自动添加 Authorization 头
 * - 401 自动刷新 Token
 * - 同一时间只允许一次 refresh 请求
 * - 防止无限刷新循环
 * - 不在 console.log 输出 Token
 * - 401 处理防并发锁，避免多个请求同时触发多次 logout
 */

import axios, { type AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { getRefreshToken as getStoredRefreshToken, setRefreshToken as setStoredRefreshToken, clearAuthTokens } from '@/utils/token'

const REFRESH_TOKEN_KEY = 'refresh_token'

const request = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// ---- Token 管理 ----

let accessToken: string | null = null
let refreshTokenValue: string | null = null
let isRefreshing = false
let refreshSubscribers: Array<(token: string) => void> = []
let refreshMaxRetries = 3
let refreshRetryCount = 0

/** 401 认证失效处理锁 — 确保多个并发 401 只触发一次统一登出 */
let handlingAuthFailure = false

export function setAccessToken(token: string | null): void {
  accessToken = token
}

export function getAccessTokenValue(): string | null {
  return accessToken
}

export function setRefreshTokenValue(token: string | null): void {
  refreshTokenValue = token
}

export function getRefreshTokenValue(): string | null {
  return refreshTokenValue
}

function onRefreshed(token: string): void {
  refreshSubscribers.forEach((cb) => cb(token))
  refreshSubscribers = []
}

function addRefreshSubscriber(cb: (token: string) => void): void {
  refreshSubscribers.push(cb)
}

// ---- 刷新逻辑 ----

async function doRefreshToken(): Promise<string> {
  const storedRefreshToken = getStoredRefreshToken()
  if (!storedRefreshToken) {
    throw new Error('No refresh token available')
  }

  const response = await axios.post('/api/v1/auth/refresh', {
    refresh_token: storedRefreshToken,
  })

  const data = response.data
  accessToken = data.access_token
  refreshTokenValue = data.refresh_token
  setStoredRefreshToken(data.refresh_token)

  // 通知 Pinia auth store 同步新的 accessToken（页面刷新后 auth store 的 token 已丢失）
  window.dispatchEvent(new CustomEvent('auth:token-refreshed', {
    detail: { accessToken: data.access_token, refreshToken: data.refresh_token },
  }))

  return data.access_token
}

/**
 * 统一认证失效处理 — 带并发锁，多个 401 只执行一次
 * - 清除 Token
 * - 触发 auth:logout 事件
 */
function handleAuthFailureOnce(): void {
  if (handlingAuthFailure) {
    return
  }
  handlingAuthFailure = true

  // 重置刷新状态
  isRefreshing = false
  refreshRetryCount = 0
  refreshSubscribers = []

  // 清除本地 Token
  accessToken = null
  refreshTokenValue = null
  clearAuthTokens()

  // 触发全局登出事件（由 App.vue 处理路由跳转和状态清理）
  window.dispatchEvent(new CustomEvent('auth:logout'))

  // 锁在下一个微任务中释放，确保同批次的 401 都被拦截
  setTimeout(() => {
    handlingAuthFailure = false
  }, 500)
}

// ---- 请求拦截器 ----

request.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (accessToken && config.headers) {
      config.headers.Authorization = `Bearer ${accessToken}`
    }
    return config
  },
  (error: AxiosError) => {
    return Promise.reject(error)
  },
)

// ---- 响应拦截器 ----

request.interceptors.response.use(
  (response: AxiosResponse) => {
    return response
  },
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

    // 429 限流处理 — Phase 9
    if (error.response?.status === 429) {
      const data = error.response.data as Record<string, unknown> | undefined
      const detail = (data?.detail as string) || '请求过于频繁，请稍后重试'
      const retryAfter = (data?.retry_after as number) || 30
      // 触发全局 429 事件（各组件可监听以恢复 UI 状态）
      window.dispatchEvent(new CustomEvent('api:rate-limited', {
        detail: {
          url: originalRequest.url,
          retry_after: retryAfter,
          detail: detail,
        },
      }))
      // 增强错误对象
      ;(error as unknown as Record<string, unknown>).rateLimitedDetail = detail
      ;(error as unknown as Record<string, unknown>).retryAfter = retryAfter
      return Promise.reject(error)
    }

    // 401 处理
    if (error.response?.status === 401 && !originalRequest._retry) {
      // 跳过登录和刷新接口
      const url = originalRequest.url || ''
      if (url.includes('/auth/login') || url.includes('/auth/refresh')) {
        return Promise.reject(error)
      }

      // 如果当前已在登录页面，不触发登出事件（避免循环）
      if (window.location.pathname === '/login') {
        return Promise.reject(error)
      }

      // 超出最大刷新重试次数 → 统一认证失效处理
      if (refreshRetryCount >= refreshMaxRetries) {
        handleAuthFailureOnce()
        return Promise.reject(error)
      }

      if (isRefreshing) {
        // 等待当前刷新完成
        return new Promise((resolve) => {
          addRefreshSubscriber((token: string) => {
            if (originalRequest.headers) {
              originalRequest.headers.Authorization = `Bearer ${token}`
            }
            originalRequest._retry = true
            resolve(request(originalRequest))
          })
        })
      }

      isRefreshing = true
      originalRequest._retry = true
      refreshRetryCount += 1

      try {
        const newToken = await doRefreshToken()
        isRefreshing = false
        refreshRetryCount = 0
        onRefreshed(newToken)
        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${newToken}`
        }
        return request(originalRequest)
      } catch {
        // 刷新失败 → 统一认证失效处理
        handleAuthFailureOnce()
        return Promise.reject(error)
      }
    }

    return Promise.reject(error)
  },
)

export default request
