/**
 * 聊天消息与会话类型
 *
 * 安全策略:
 * - 普通用户类型中禁止出现 sources、file_name、page、content_preview、
 *   chunk_id、raw_distance、relevance_score
 * - 这些字段仅限管理员 AdminChatResponse 使用（定义在 types/api.ts）
 */

/** 消息角色 */
export type ChatRole = 'user' | 'assistant' | 'system'

/** 消息状态 */
export type MessageStatus = 'sending' | 'success' | 'error'

/** 单条聊天消息 */
export interface ChatMessage {
  id: string
  role: ChatRole
  content: string
  createdAt: string
  status?: MessageStatus
  latencySeconds?: number | null
  refused?: boolean
  errorMessage?: string | null
}

/** 聊天会话 */
export interface ChatSession {
  id: string
  title: string
  messages: ChatMessage[]
  createdAt: string
  updatedAt: string
}

/** 创建会话参数 */
export interface CreateSessionParams {
  title?: string
}

/** 发送问题参数 */
export interface SendQuestionParams {
  question: string
}
