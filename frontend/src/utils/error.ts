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

    const errorCode = data?.error?.code || ''

    switch (status) {
      case 401:
        return '登录已过期，请重新登录'
      case 403:
        return '没有访问权限'
      case 409:
        // Phase 7: 重复操作
        if (errorCode === 'DUPLICATE_OPERATION') {
          return data?.error?.message || '该操作正在进行中，请勿重复提交'
        }
        return data?.error?.message || '操作冲突，请稍后重试'
      case 423:
        return '账户已被锁定，请稍后再试'
      case 429:
        return data?.error?.message || '请求过于频繁，请稍后再试'
      case 500:
        return data?.error?.message || data?.detail || data?.message || '服务暂不可用，请稍后再试'
      case 503:
        // Phase 7: 数据库与向量库繁忙
        if (errorCode === 'DATABASE_BUSY') {
          return data?.error?.message || '系统当前繁忙，请稍后重试'
        }
        if (errorCode === 'VECTOR_STORE_BUSY') {
          return data?.error?.message || '知识库正在处理其他任务，请稍后再试'
        }
        if (errorCode === 'VECTOR_STORE_OPERATION_FAILED') {
          return data?.error?.message || '知识库操作失败，请联系管理员'
        }
        return data?.error?.message || '服务暂不可用，请稍后重试'
      case 504:
        return data?.error?.message || '请求处理超时，请稍后重试'
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
    const axiosError = error as {
      response?: {
        status?: number
        data?: {
          message?: string
          detail?: string
          error?: { message?: string; code?: string }
        }
      }
    }
    const status = axiosError.response?.status
    const data = axiosError.response?.data

    // 优先从后端统一错误格式提取消息
    const errorCode = data?.error?.code || ''
    const serverMessage = data?.error?.message || data?.detail || data?.message || ''

    switch (status) {
      case 401:
        return '登录已过期，请重新登录'
      case 403:
        return '权限不足，无法使用问答服务'
      case 429:
        // Phase 6: 区分用户请求超限和通用限流
        if (errorCode === 'USER_REQUEST_LIMIT') {
          return serverMessage || '当前已有回答正在生成，请稍候。'
        }
        return serverMessage || '请求过于频繁，请稍后再试'
      case 500:
        return '服务暂不可用，请稍后再试'
      case 503:
        // Phase 6: 推理服务暂不可用 / 排队超时
        if (errorCode === 'INFERENCE_QUEUE_TIMEOUT') {
          return serverMessage || '当前问答请求较多，请稍后重试'
        }
        if (errorCode === 'INFERENCE_UNAVAILABLE') {
          return serverMessage || '模型服务暂不可用，请稍后重试或联系管理员'
        }
        // Phase 7: 数据库与向量库繁忙
        if (errorCode === 'DATABASE_BUSY') {
          return serverMessage || '系统当前繁忙，请稍后重试'
        }
        if (errorCode === 'VECTOR_STORE_BUSY') {
          return serverMessage || '知识库正在处理其他任务，请稍后再试'
        }
        if (errorCode === 'VECTOR_STORE_OPERATION_FAILED') {
          return serverMessage || '知识库操作失败，请联系管理员'
        }
        return serverMessage || '问答服务暂不可用，请稍后重试'
      case 409:
        // Phase 7: 重复操作（如索引重建中）
        if (errorCode === 'DUPLICATE_OPERATION') {
          return serverMessage || '该文档正在处理中，请勿重复提交'
        }
        return serverMessage || '操作冲突，请稍后重试'
      case 504:
        // Phase 6: 推理执行超时
        if (errorCode === 'INFERENCE_EXECUTION_TIMEOUT') {
          return serverMessage || '本次处理超时，请缩短问题或稍后重试'
        }
        return serverMessage || '回答生成超时，请稍后重试'
      default:
        return serverMessage || '问答服务异常，请稍后再试'
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
