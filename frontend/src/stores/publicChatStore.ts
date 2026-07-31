/**
 * 游客聊天 Store — 纯前端状态管理，不依赖后端会话
 *
 * 与用户 Chat Store 完全独立:
 * - 不使用认证 Store
 * - 不创建/管理后端会话
 * - 不保存聊天历史
 * - 仅维护当前页面的消息列表
 *
 * 安全策略:
 * - 不保存 Token、API Key
 * - 不保存后端原始异常
 * - 最多保留 50 条消息（内存限制）
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import publicChatApi from '@/api/publicChat'
import { extractChatErrorMessage } from '@/utils/error'

// ---- 常量 ----
const MAX_MESSAGES = 50

// ---- 类型 ----

export interface PublicChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  createdAt: string
  status: 'success' | 'sending' | 'error'
  errorMessage?: string | null
  latencySeconds?: number | null
  refused?: boolean
}

export const usePublicChatStore = defineStore('publicChat', () => {
  // ================================================================
  // State
  // ================================================================
  const messages = ref<PublicChatMessage[]>([])
  const sending = ref(false)

  // ================================================================
  // Getters
  // ================================================================
  const hasMessages = computed(() => messages.value.length > 0)

  // ================================================================
  // Actions
  // ================================================================

  /** 发送问题并获取回答 */
  async function sendQuestion(question: string): Promise<void> {
    if (sending.value) return

    const trimmed = question.trim()
    if (!trimmed) return

    // 1. 插入用户消息
    messages.value.push({
      id: `user_${Date.now()}`,
      role: 'user',
      content: trimmed,
      createdAt: new Date().toISOString(),
      status: 'success',
    })

    // 2. 插入助手占位消息
    const assistantMsg: PublicChatMessage = {
      id: `asst_${Date.now()}`,
      role: 'assistant',
      content: '',
      createdAt: new Date().toISOString(),
      status: 'sending',
    }
    messages.value.push(assistantMsg)
    trimMessages()

    // 3. 发送请求
    sending.value = true
    try {
      const result = await publicChatApi.askPublic(trimmed)

      assistantMsg.content = result.answer
      assistantMsg.status = 'success'
      assistantMsg.latencySeconds = result.latency_seconds
      assistantMsg.refused = result.refused
    } catch (error: unknown) {
      assistantMsg.status = 'error'
      assistantMsg.errorMessage = extractChatErrorMessage(error)
    } finally {
      sending.value = false
    }
  }

  /** 重试最后一条失败消息 */
  async function retryLastFailed(): Promise<void> {
    if (sending.value) return

    const msgs = messages.value
    let lastErrorIdx = -1
    for (let i = msgs.length - 1; i >= 0; i--) {
      if (msgs[i].role === 'assistant' && msgs[i].status === 'error') {
        lastErrorIdx = i
        break
      }
    }
    if (lastErrorIdx === -1) return

    let lastUserIdx = -1
    for (let i = lastErrorIdx - 1; i >= 0; i--) {
      if (msgs[i].role === 'user') {
        lastUserIdx = i
        break
      }
    }
    if (lastUserIdx === -1) return

    const userQuestion = msgs[lastUserIdx].content

    // 移除失败消息
    msgs.splice(lastErrorIdx, 1)

    // 重新发送
    await sendQuestion(userQuestion)
  }

  /** 清空所有消息 */
  function clearMessages(): void {
    messages.value = []
    sending.value = false
  }

  /** 裁剪消息（保留最近 MAX_MESSAGES 条） */
  function trimMessages(): void {
    if (messages.value.length > MAX_MESSAGES) {
      messages.value = messages.value.slice(-MAX_MESSAGES)
    }
  }

  return {
    // State
    messages,
    sending,
    // Getters
    hasMessages,
    // Actions
    sendQuestion,
    retryLastFailed,
    clearMessages,
  }
})
