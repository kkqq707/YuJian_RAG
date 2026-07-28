/**
 * 问答 API
 *
 * 安全策略:
 * - 不在浏览器控制台输出完整回答、Token 或请求头
 * - 普通问答响应类型中不定义 sources
 * - 不使用 any
 */

import request from './request'
import type { UserChatResponse, AdminChatResponse } from '@/types/api'

/** 聊天页面统计信息 */
export interface ChatPageStats {
  status: string
  vector_store: string
  knowledge_chunks: number
  knowledge_files: number
  enterprise_name: string
  llm_configured: boolean
  llm_provider: string | null
  model_name: string | null
}

// ---- 问答 ----

/** 普通用户问答 — 不返回 sources */
async function askQuestion(question: string): Promise<UserChatResponse> {
  const response = await request.post<UserChatResponse>('/chat', { question })
  return response.data
}

/** 管理员问答预览 — 可返回安全来源和调试信息 */
async function askAdminQuestion(question: string, debug: boolean = false): Promise<AdminChatResponse> {
  const response = await request.post<AdminChatResponse>(
    `/admin/chat-preview?debug=${debug}`,
    { question }
  )
  return response.data
}

/** 获取聊天页面统计信息（需要登录） */
async function getChatPageStats(): Promise<ChatPageStats> {
  const response = await request.get<ChatPageStats>('/system/status')
  return response.data
}

// ---- 聊天历史 ----

/** 会话响应类型 */
export interface SessionItem {
  id: number
  title: string
  message_count: number
  created_at: string
  updated_at: string
}

/** 消息响应类型 */
export interface MessageItem {
  id: number
  session_id: number
  role: string
  content: string
  created_at: string
}

/** 发送消息响应类型 */
export interface SendMessageResult {
  success: boolean
  answer: string
  refused: boolean
  refusal_reason: string | null
  model_name: string | null
  latency_seconds: number | null
  request_id: string
  user_message: MessageItem
  assistant_message: MessageItem
}

/** 获取用户的所有会话（分页） */
async function listSessions(page: number = 1, pageSize: number = 20): Promise<{
  success: boolean
  sessions: SessionItem[]
  total: number
  page: number
  page_size: number
}> {
  const response = await request.get<{
    success: boolean
    sessions: SessionItem[]
    total: number
    page: number
    page_size: number
  }>('/chat/sessions', { params: { page, page_size: pageSize } })
  return response.data
}

/** 创建新会话 */
async function createSession(title?: string): Promise<{ success: boolean; session: SessionItem }> {
  const response = await request.post<{ success: boolean; session: SessionItem }>('/chat/sessions', {
    title: title || '新对话',
  })
  return response.data
}

/** 获取会话消息 */
async function getSessionMessages(sessionId: number): Promise<{
  success: boolean
  session_id: number
  messages: MessageItem[]
}> {
  const response = await request.get<{
    success: boolean
    session_id: number
    messages: MessageItem[]
  }>(`/chat/sessions/${sessionId}/messages`)
  return response.data
}

/** 发送消息并保存到数据库 */
async function sendMessage(sessionId: number, question: string): Promise<SendMessageResult> {
  const response = await request.post<SendMessageResult>('/chat/message', {
    session_id: sessionId,
    question,
  })
  return response.data
}

/** 删除会话 */
async function deleteSession(sessionId: number): Promise<{ success: boolean; message: string; session_id: number }> {
  const response = await request.delete<{ success: boolean; message: string; session_id: number }>(
    `/chat/sessions/${sessionId}`
  )
  return response.data
}

/** 更新会话标题 */
async function updateSessionTitle(sessionId: number, title: string): Promise<{
  success: boolean
  message: string
  session_id: number
  title: string
}> {
  const response = await request.put<{
    success: boolean
    message: string
    session_id: number
    title: string
  }>(`/chat/sessions/${sessionId}/title`, { title })
  return response.data
}

/** 清空会话消息 */
async function clearSessionMessages(sessionId: number): Promise<{
  success: boolean
  message: string
  session_id: number
  deleted_count: number
}> {
  const response = await request.delete<{
    success: boolean
    message: string
    session_id: number
    deleted_count: number
  }>(`/chat/sessions/${sessionId}/messages`)
  return response.data
}

/** 删除单条消息 */
async function deleteMessage(messageId: number): Promise<{
  success: boolean
  message: string
  message_id: number
}> {
  const response = await request.delete<{
    success: boolean
    message: string
    message_id: number
  }>(`/chat/messages/${messageId}`)
  return response.data
}

/** 提交消息反馈（点赞/点踩） */
async function submitMessageFeedback(messageId: number, rating: 'like' | 'dislike', comment?: string): Promise<{
  success: boolean
  message: string
  message_id: number
  rating: string
}> {
  const response = await request.post<{
    success: boolean
    message: string
    message_id: number
    rating: string
  }>(`/chat/messages/${messageId}/feedback`, { rating, comment })
  return response.data
}

const chatApi = {
  // 问答
  askQuestion,
  askAdminQuestion,
  getChatPageStats,
  // 聊天历史
  listSessions,
  createSession,
  getSessionMessages,
  sendMessage,
  deleteSession,
  updateSessionTitle,
  clearSessionMessages,
  deleteMessage,
  submitMessageFeedback,
}

export default chatApi
