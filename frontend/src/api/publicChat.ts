/**
 * 游客聊天 API — 无需 JWT 认证
 *
 * 与认证用户的 chat API 分离，使用独立的 axios 实例，
 * 不附加 Authorization 头，不触发 token 刷新逻辑。
 *
 * 安全策略:
 * - 不传递任何认证信息
 * - 仅暴露游客聊天所需的接口
 * - 不在浏览器控制台输出完整回答
 */

import axios from 'axios'

/** 游客聊天 — 独立的 axios 实例（无拦截器、无 Token） */
const publicRequest = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

/** 游客聊天响应 */
export interface PublicChatResponse {
  success: boolean
  answer: string
  refused: boolean
  refusal_reason: string | null
  model_name: string | null
  latency_seconds: number | null
  request_id: string
}

/**
 * 发送游客聊天问题
 *
 * @param question - 用户问题
 * @returns 回答结果（不含来源）
 */
async function askPublic(question: string): Promise<PublicChatResponse> {
  const response = await publicRequest.post<PublicChatResponse>('/public/chat', {
    question,
  })
  return response.data
}

const publicChatApi = {
  askPublic,
}

export default publicChatApi
