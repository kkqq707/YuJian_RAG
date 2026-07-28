/**
 * 聊天会话 Store — 管理会话列表、消息、发送状态
 *
 * 安全策略:
 * - 不保存 Token、API Key
 * - 不保存后端原始异常
 * - 每次只发送当前新问题（不发送完整对话历史）
 * - 最多保存最近 50 个会话，每个会话最多 200 条消息
 * - 竞态防护：请求响应后验证用户是否变更，丢弃旧用户的响应
 * - reset/cleanup 退出登录时清除所有用户专属数据
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import chatApi from '@/api/chat'
import type { SessionItem, MessageItem } from '@/api/chat'
import { extractChatErrorMessage } from '@/utils/error'
import type { ChatSession, ChatMessage } from '@/types/chat'
import {
  validateRequestOwnership,
  useAuthStore,
} from '@/stores/auth'

// ---- 常量 ----
const MAX_SESSIONS = 50
const MAX_MESSAGES_PER_SESSION = 200
const MAX_TITLE_LENGTH = 24

// ---- 工具函数 ----

function makeTitle(text: string): string {
  const cleaned = text.replace(/\s+/g, ' ').trim()
  return cleaned.length > MAX_TITLE_LENGTH
    ? cleaned.slice(0, MAX_TITLE_LENGTH) + '...'
    : cleaned
}

/** 将后端 SessionItem 转为前端 ChatSession */
function sessionItemToChatSession(item: SessionItem): ChatSession {
  return {
    id: String(item.id),
    title: item.title,
    messages: [],
    createdAt: item.created_at,
    updatedAt: item.updated_at,
  }
}

/** 将后端 MessageItem 转为前端 ChatMessage */
function messageItemToChatMessage(item: MessageItem): ChatMessage {
  return {
    id: String(item.id),
    role: item.role as 'user' | 'assistant',
    content: item.content,
    createdAt: item.created_at,
    status: 'success',
  }
}

// ---- Store ----

export const useChatStore = defineStore('chat', () => {
  // ================================================================
  // State
  // ================================================================
  const sessions = ref<ChatSession[]>([])
  const activeSessionId = ref<string | null>(null)
  const sending = ref(false)
  const initialized = ref(false)

  // 竞态防护：记录当前正在请求的用户 ID
  let currentRequestUserId: number | null = null

  function getAuthUserId(): number | null {
    try {
      const authStore = useAuthStore()
      return authStore.user?.id ?? null
    } catch {
      return null
    }
  }

  function isSameUser(): boolean {
    if (currentRequestUserId === null) return true
    const authUserId = getAuthUserId()
    if (authUserId === null) return false
    return currentRequestUserId === authUserId
  }

  // ================================================================
  // Getters
  // ================================================================
  const activeSession = computed<ChatSession | null>(() => {
    if (!activeSessionId.value) return null
    return sessions.value.find((s) => s.id === activeSessionId.value) || null
  })

  const activeMessages = computed<ChatMessage[]>(() => {
    return activeSession.value?.messages || []
  })

  const hasMessages = computed(() => {
    return activeMessages.value.length > 0
  })

  // ================================================================
  // Actions — 初始化与会话管理
  // ================================================================

  /**
   * 初始化：从后端加载用户会话列表（仅列表，不加载消息，不选中任何会话）。
   *
   * 进入 /chat 页面默认显示欢迎面板（新对话），
   * 刷新浏览器保持历史列表但不恢复聊天。
   */
  async function initialize(): Promise<void> {
    const userId = getAuthUserId()
    if (userId === null) return

    currentRequestUserId = userId

    // 先清空旧数据
    sessions.value = []
    activeSessionId.value = null
    initialized.value = false

    try {
      const result = await chatApi.listSessions(1, 20)

      // 竞态防护：响应返回后验证用户未切换
      if (!validateRequestOwnership(userId)) {
        return
      }

      sessions.value = result.sessions.map(sessionItemToChatSession)
      // 不自动选中会话、不自动创建会话 → 显示欢迎面板
    } catch {
      // 加载失败，保持空列表
    }
    initialized.value = true
  }

  /**
   * 完全重置聊天状态（退出登录时调用）
   * 清除所有会话、消息、发送状态
   */
  function reset(): void {
    sessions.value = []
    activeSessionId.value = null
    sending.value = false
    initialized.value = false
    currentRequestUserId = null
  }

  /** @deprecated 使用 reset() 替代 */
  function cleanup(): void {
    reset()
  }

  /**
   * 新建对话 — 清空当前消息，取消选中会话。
   *
   * 不会立即创建后端 session，session 在首次发送消息时延迟创建。
   * ChatView 显示欢迎面板。
   */
  function createSession(): void {
    activeSessionId.value = null
  }

  /** 切换到指定会话并加载消息（用户点击历史时触发） */
  async function switchSession(sessionId: string): Promise<void> {
    const exists = sessions.value.find((s) => s.id === sessionId)
    if (!exists) return

    const userId = getAuthUserId()
    if (userId !== null) {
      currentRequestUserId = userId
    }

    activeSessionId.value = sessionId
    await loadMessages(sessionId)
  }

  /** 重命名会话 */
  async function renameSession(sessionId: string, newTitle: string): Promise<boolean> {
    const trimmed = newTitle.trim()
    if (!trimmed || trimmed.length > 255) return false
    const session = sessions.value.find((s) => s.id === sessionId)
    if (!session) return false

    // 乐观更新
    const oldTitle = session.title
    session.title = trimmed
    session.updatedAt = new Date().toISOString()

    // 后端持久化（跳过本地会话）
    if (!sessionId.startsWith('local_')) {
      try {
        await chatApi.updateSessionTitle(Number(sessionId), trimmed)
      } catch {
        // 回滚
        session.title = oldTitle
        return false
      }
    }
    return true
  }

  /**
   * 删除会话（后端 + 本地）。
   *
   * 如果删除的是当前活跃会话，清空 activeSessionId（回到新对话）。
   * 不会自动切换到其他会话。
   */
  async function deleteSession(sessionId: string): Promise<void> {
    const idx = sessions.value.findIndex((s) => s.id === sessionId)
    if (idx === -1) return

    // 后端删除（跳过本地回退会话）
    if (!sessionId.startsWith('local_')) {
      try {
        await chatApi.deleteSession(Number(sessionId))
      } catch {
        // 继续本地删除
      }
    }

    sessions.value.splice(idx, 1)

    // 如果删除的是当前活跃会话，回到新对话状态
    if (activeSessionId.value === sessionId) {
      activeSessionId.value = null
    }
  }

  /** 清空当前对话 — 回到新对话状态，不删除后端会话 */
  function clearSession(): void {
    activeSessionId.value = null
  }

  // ================================================================
  // Actions — 问答
  // ================================================================

  /**
   * 发送问题并获取回答。
   *
   * 如果当前无活跃会话（activeSessionId 为 null），
   * 先创建后端 session，再发送消息。
   */
  async function sendQuestion(question: string): Promise<void> {
    if (sending.value) return

    const trimmed = question.trim()
    if (!trimmed) return

    const userId = getAuthUserId()
    if (userId !== null) {
      currentRequestUserId = userId
    }

    // ---- 延迟创建 session（如果还没有活跃会话） ----
    if (!activeSessionId.value) {
      const title = makeTitle(trimmed)
      try {
        const result = await chatApi.createSession(title)

        if (!validateRequestOwnership(userId!)) return

        const session = sessionItemToChatSession(result.session)
        sessions.value.unshift(session)
        activeSessionId.value = session.id
        trimSessions()
      } catch {
        if (!isSameUser()) return
        // API 失败时创建本地回退会话
        const fallbackSession: ChatSession = {
          id: `local_${Date.now()}`,
          title: title,
          messages: [],
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        }
        sessions.value.unshift(fallbackSession)
        activeSessionId.value = fallbackSession.id
        trimSessions()
      }
    }

    const session = activeSession.value
    if (!session) return

    // 更新会话标题（首次提问时基于问题生成）
    if (session.messages.length === 0) {
      session.title = makeTitle(trimmed)
    }

    // 1. 插入用户消息（先用本地时间，后续用后端返回的时间替换）
    const userMsg: ChatMessage = {
      id: `user_${Date.now()}`,
      role: 'user',
      content: trimmed,
      createdAt: new Date().toISOString(),
      status: 'success',
    }
    session.messages.push(userMsg)

    // 2. 插入助手占位消息
    const assistantMsg: ChatMessage = {
      id: `asst_${Date.now()}`,
      role: 'assistant',
      content: '',
      createdAt: new Date().toISOString(),
      status: 'sending',
    }
    session.messages.push(assistantMsg)
    session.updatedAt = new Date().toISOString()
    trimMessages(session)

    // 3. 发送请求
    sending.value = true
    try {
      let response: {
        answer: string
        refused: boolean
        latency_seconds: number | null
        user_message?: { id: number; created_at: string }
        assistant_message?: { id: number; created_at: string }
      }

      if (!session.id.startsWith('local_')) {
        const result = await chatApi.sendMessage(Number(session.id), trimmed)

        if (!validateRequestOwnership(userId!)) {
          sending.value = false
          return
        }

        // 使用后端返回的消息 ID 和创建时间（后端时间为权威时间源）
        userMsg.id = String(result.user_message.id)
        userMsg.createdAt = result.user_message.created_at
        assistantMsg.id = String(result.assistant_message.id)
        assistantMsg.createdAt = result.assistant_message.created_at
        response = result
      } else {
        // 本地会话使用旧 API（不回存消息）
        const result = await chatApi.askQuestion(trimmed)

        if (!validateRequestOwnership(userId!)) {
          sending.value = false
          return
        }

        response = result
      }

      assistantMsg.content = response.answer
      assistantMsg.status = 'success'
      assistantMsg.latencySeconds = response.latency_seconds
      assistantMsg.refused = response.refused
      session.updatedAt = new Date().toISOString()
    } catch (error: unknown) {
      if (!isSameUser()) {
        sending.value = false
        return
      }
      assistantMsg.status = 'error'
      assistantMsg.errorMessage = extractChatErrorMessage(error)
      session.updatedAt = new Date().toISOString()
    } finally {
      sending.value = false
    }
  }

  /** 错误后重试：移除失败消息并重新发送最后一个问题 */
  async function retryLastFailed(): Promise<void> {
    const session = activeSession.value
    if (!session || sending.value) return

    const userId = getAuthUserId()
    if (userId !== null) {
      currentRequestUserId = userId
    }

    const msgs = session.messages
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

    // 移除失败的消息
    msgs.splice(lastErrorIdx, 1)

    // 插入新的助手占位消息
    const assistantMsg: ChatMessage = {
      id: `asst_${Date.now()}`,
      role: 'assistant',
      content: '',
      createdAt: new Date().toISOString(),
      status: 'sending',
    }
    msgs.push(assistantMsg)
    session.updatedAt = new Date().toISOString()

    // 发送请求
    sending.value = true
    try {
      let response: { answer: string; refused: boolean; latency_seconds: number | null }
      if (!session.id.startsWith('local_')) {
        const result = await chatApi.sendMessage(Number(session.id), userQuestion)

        if (!validateRequestOwnership(userId!)) {
          sending.value = false
          return
        }

        assistantMsg.id = String(result.assistant_message.id)
        assistantMsg.createdAt = result.assistant_message.created_at
        response = result
      } else {
        response = await chatApi.askQuestion(userQuestion)

        if (!validateRequestOwnership(userId!)) {
          sending.value = false
          return
        }
      }
      assistantMsg.content = response.answer
      assistantMsg.status = 'success'
      assistantMsg.latencySeconds = response.latency_seconds
      assistantMsg.refused = response.refused
      session.updatedAt = new Date().toISOString()
    } catch (error: unknown) {
      if (!isSameUser()) {
        sending.value = false
        return
      }
      assistantMsg.status = 'error'
      assistantMsg.errorMessage = extractChatErrorMessage(error)
      session.updatedAt = new Date().toISOString()
    } finally {
      sending.value = false
    }
  }

  /** 重新生成最后一个回答（替换原回答） */
  async function regenerateLastAnswer(): Promise<void> {
    const session = activeSession.value
    if (!session || sending.value) return

    const userId = getAuthUserId()
    if (userId !== null) {
      currentRequestUserId = userId
    }

    const msgs = session.messages
    let lastUserIdx = -1
    for (let i = msgs.length - 1; i >= 0; i--) {
      if (msgs[i].role === 'user') {
        lastUserIdx = i
        break
      }
    }
    if (lastUserIdx === -1) return

    const userQuestion = msgs[lastUserIdx].content

    const targetAssistantIdx = lastUserIdx + 1
    if (targetAssistantIdx >= msgs.length) {
      const assistantMsg: ChatMessage = {
        id: `asst_${Date.now()}`,
        role: 'assistant',
        content: '',
        createdAt: new Date().toISOString(),
        status: 'sending',
      }
      msgs.push(assistantMsg)
    } else if (msgs[targetAssistantIdx].role === 'assistant') {
      msgs[targetAssistantIdx].content = ''
      msgs[targetAssistantIdx].status = 'sending'
      msgs[targetAssistantIdx].errorMessage = null
      msgs[targetAssistantIdx].refused = false
    } else {
      const assistantMsg: ChatMessage = {
        id: `asst_${Date.now()}`,
        role: 'assistant',
        content: '',
        createdAt: new Date().toISOString(),
        status: 'sending',
      }
      msgs.splice(targetAssistantIdx, 0, assistantMsg)
    }

    const assistantMsg = msgs[targetAssistantIdx]
    session.updatedAt = new Date().toISOString()

    sending.value = true
    try {
      let response: { answer: string; refused: boolean; latency_seconds: number | null }
      if (!session.id.startsWith('local_')) {
        const result = await chatApi.sendMessage(Number(session.id), userQuestion)

        if (!validateRequestOwnership(userId!)) {
          sending.value = false
          return
        }

        assistantMsg.id = String(result.assistant_message.id)
        assistantMsg.createdAt = result.assistant_message.created_at
        response = result
      } else {
        response = await chatApi.askQuestion(userQuestion)

        if (!validateRequestOwnership(userId!)) {
          sending.value = false
          return
        }
      }
      assistantMsg.content = response.answer
      assistantMsg.status = 'success'
      assistantMsg.latencySeconds = response.latency_seconds
      assistantMsg.refused = response.refused
      session.updatedAt = new Date().toISOString()
    } catch (error: unknown) {
      if (!isSameUser()) {
        sending.value = false
        return
      }
      assistantMsg.status = 'error'
      assistantMsg.errorMessage = extractChatErrorMessage(error)
      session.updatedAt = new Date().toISOString()
    } finally {
      sending.value = false
    }
  }

  // ================================================================
  // 内部方法
  // ================================================================

  /** 从后端加载会话消息 */
  async function loadMessages(sessionId: string): Promise<void> {
    // 跳过本地会话
    if (sessionId.startsWith('local_')) return

    const session = sessions.value.find((s) => s.id === sessionId)
    if (!session) return

    const userId = getAuthUserId()
    if (userId === null) return

    try {
      const result = await chatApi.getSessionMessages(Number(sessionId))

      // 竞态防护
      if (!validateRequestOwnership(userId)) {
        return
      }

      session.messages = result.messages.map(messageItemToChatMessage)
    } catch {
      // 加载失败，保持原有消息
    }
  }

  /** 裁剪会话数量（保留最近 MAX_SESSIONS 个） */
  function trimSessions(): void {
    if (sessions.value.length > MAX_SESSIONS) {
      sessions.value = sessions.value.slice(0, MAX_SESSIONS)
    }
  }

  /** 裁剪会话消息数量（保留最近 MAX_MESSAGES_PER_SESSION 条） */
  function trimMessages(session: ChatSession): void {
    if (session.messages.length > MAX_MESSAGES_PER_SESSION) {
      session.messages = session.messages.slice(-MAX_MESSAGES_PER_SESSION)
    }
  }

  return {
    // State
    sessions,
    activeSessionId,
    sending,
    initialized,
    // Getters
    activeSession,
    activeMessages,
    hasMessages,
    // Actions
    initialize,
    reset,
    createSession,
    switchSession,
    renameSession,
    deleteSession,
    clearSession,
    sendQuestion,
    retryLastFailed,
    regenerateLastAnswer,
    cleanup,
  }
})
