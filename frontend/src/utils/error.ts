/**
 * 统一错误处理工具
 */

import type { ErrorDetail } from '@/types/api'

/** 从 Axios 错误中提取安全的错误消息 */
export function extractErrorMessage(error: unknown): string {
  if (error && typeof error === 'object' && 'response' in error) {
    const axiosError = error as { response?: { status?: number; data?: ErrorDetail & { error?: { message?: string; code?: string } } } }
    const status = axiosError.response?.status
    const data = axiosError.response?.data

    switch (status) {
      case 401:
        return '登录已过期，请重新登录'
      case 403:
        return '没有访问权限'
      case 423:
        return '账户已被锁定，请稍后再试'
      case 429:
        return '请求过于频繁，请稍后再试'
      case 500:
        // 返回服务器真实错误信息，帮助诊断问题
        return data?.error?.message || data?.detail || data?.message || '服务暂不可用，请稍后再试'
      default:
        return data?.error?.message || data?.detail || data?.message || '请求失败，请稍后再试'
    }
  }

  if (error && typeof error === 'object' && 'message' in error) {
    const msgError = error as { message: string }
    if (msgError.message === 'Network Error') {
      return '无法连接服务器，请检查网络'
    }
    return msgError.message
  }

  return '未知错误'
}

/** 从登录错误中提取安全的错误消息（登录专属） */
export function extractLoginErrorMessage(error: unknown): string {
  if (error && typeof error === 'object' && 'response' in error) {
    const axiosError = error as {
      response?: {
        status?: number
        data?: {
          detail?: string
          message?: string
          error?: { message?: string; code?: string }
        }
      }
    }
    const status = axiosError.response?.status
    const data = axiosError.response?.data

    // 优先从新的统一错误格式中提取消息
    const serverMessage = data?.error?.message || data?.detail || data?.message

    switch (status) {
      case 401:
        // 登录接口的 401: 用户名或密码错误
        return serverMessage || '用户名或密码错误'
      case 423:
        return serverMessage || '账户已被锁定，请稍后再试'
      case 429:
        return '请求过于频繁，请稍后再试'
      case 500:
        return '服务器异常，请稍后再试'
      default:
        return serverMessage || '登录失败，请稍后再试'
    }
  }

  if (error && typeof error === 'object' && 'message' in error) {
    const msgError = error as { message: string }
    if (msgError.message === 'Network Error') {
      return '无法连接服务器，请检查网络'
    }
    if (msgError.message.includes('timeout')) {
      return '连接超时，请检查网络'
    }
    return '无法连接服务器，请检查网络'
  }

  return '登录失败，请稍后再试'
}

/** 判断是否为网络错误 */
export function isNetworkError(error: unknown): boolean {
  if (error && typeof error === 'object' && 'message' in error) {
    const msg = (error as { message: string }).message
    return msg === 'Network Error' || msg.includes('timeout') || msg.includes('ECONNREFUSED')
  }
  return false
}

/** 判断是否为超时错误 */
export function isTimeoutError(error: unknown): boolean {
  if (error && typeof error === 'object') {
    const err = error as { code?: string; message?: string }
    if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
      return true
    }
  }
  return false
}

/** 提取问答专用错误消息 */
export function extractChatErrorMessage(error: unknown): string {
  if (error && typeof error === 'object' && 'response' in error) {
    const axiosError = error as { response?: { status?: number; data?: { message?: string } } }
    const status = axiosError.response?.status

    switch (status) {
      case 401:
        return '登录已过期，请重新登录'
      case 403:
        return '权限不足，无法使用问答服务'
      case 429:
        return '请求过于频繁，请稍后再试'
      case 500:
        return '服务暂不可用，请稍后再试'
      default:
        return axiosError.response?.data?.message || '问答服务异常，请稍后再试'
    }
  }

  if (isTimeoutError(error)) {
    return '回答生成超时，请稍后重试'
  }

  if (isNetworkError(error)) {
    return '无法连接问答服务，请检查网络'
  }

  return '未知错误，请稍后再试'
}
