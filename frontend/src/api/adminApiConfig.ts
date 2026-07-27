/**
 * 管理员 API 配置 — 接口层
 *
 * 安全策略:
 * - 不在 console.log 输出 API Key
 * - 不在 localStorage 保存 API Key
 * - API Key 仅通过 HTTPS 传输
 */

import request from './request'

// ---- 类型定义 ----

export interface LLMConfigInfo {
  configured: boolean
  id: number | null
  provider: string | null
  base_url: string | null
  model: string | null
  enabled: boolean
  api_key_masked: string | null
}

export interface LLMConfigSaveRequest {
  provider: string
  base_url: string
  api_key: string
  model: string
  enabled: boolean
}

export interface TestConnectionRequest {
  base_url: string
  api_key: string
  model: string
}

export interface TestConnectionResponse {
  success: boolean
  model: string
  latency_ms: number
  response_preview: string
  error: string | null
}

export interface ModelItem {
  name: string
  provider: string
}

export interface ModelListResponse {
  success: boolean
  models: ModelItem[]
}

export interface SecurityStatus {
  jwt_initialized: boolean
  encryption_configured: boolean
  llm_configured: boolean
}

// ---- API 函数 ----

/** 获取当前 LLM 配置 */
export function getLLMConfig(): Promise<LLMConfigInfo> {
  return request.get('/admin/api-config').then((r) => r.data)
}

/** 保存 LLM 配置 */
export function saveLLMConfig(data: LLMConfigSaveRequest): Promise<LLMConfigInfo> {
  return request.post('/admin/api-config', data).then((r) => r.data)
}

/** 测试 LLM 连接 */
export function testLLMConnection(data: TestConnectionRequest): Promise<TestConnectionResponse> {
  return request.post('/admin/api-config/test', data).then((r) => r.data)
}

/** 测试已保存的 LLM 配置连接（无需传入 API Key） */
export function testSavedConnection(): Promise<TestConnectionResponse> {
  return request.post('/admin/api-config/test-saved').then((r) => r.data)
}

/** 获取可用模型列表 */
export function getModels(): Promise<ModelListResponse> {
  return request.get('/admin/models').then((r) => r.data)
}

/** 获取安全状态 */
export function getSecurityStatus(): Promise<SecurityStatus> {
  return request.get('/admin/security/status').then((r) => r.data)
}
