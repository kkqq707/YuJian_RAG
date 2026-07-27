/**
 * 管理员 RAG 配置 API — RAG 3.0 参数管理
 */

import request from './request'

/** RAG 配置类型 */
export interface RAGConfigData {
  id: number | null
  chunk_size: number
  chunk_overlap: number
  top_k: number
  similarity_threshold: number
  hybrid_fetch_k: number
  vector_weight: number
  keyword_weight: number
  rerank_enable: boolean
  rerank_fetch_k: number
  rerank_top_k: number
  max_raw_distance: number
  min_relevance_score: number
  query_rewrite_enable: boolean
  updated_at: string | null
}

/** 获取当前 RAG 配置 */
async function getRAGConfig(): Promise<RAGConfigData> {
  const response = await request.get<RAGConfigData>('/admin/rag-config')
  return response.data
}

/** 更新 RAG 配置（局部更新） */
async function updateRAGConfig(data: Partial<RAGConfigData>): Promise<{
  success: boolean
  message: string
  config: RAGConfigData
}> {
  const response = await request.put<{
    success: boolean
    message: string
    config: RAGConfigData
  }>('/admin/rag-config', data)
  return response.data
}

/** 重置 RAG 配置为默认值 */
async function resetRAGConfig(): Promise<{
  success: boolean
  message: string
  config: RAGConfigData
}> {
  const response = await request.post<{
    success: boolean
    message: string
    config: RAGConfigData
  }>('/admin/rag-config/reset')
  return response.data
}

const adminRagConfigApi = {
  getRAGConfig,
  updateRAGConfig,
  resetRAGConfig,
}

export default adminRagConfigApi
