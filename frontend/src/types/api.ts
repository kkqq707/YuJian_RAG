/** 统一错误响应 */
export interface ErrorDetail {
  code: string
  message: string
  detail?: string
  request_id: string
}

/** 分页参数 */
export interface PaginationParams {
  skip?: number
  limit?: number
}

/** 列表响应通用结构 */
export interface ListResponse<T> {
  success: boolean
  total: number
  [key: string]: unknown
}

// ---- 聊天 ----

export interface ChatRequest {
  question: string
}

/** 普通用户问答响应 — 不含 sources */
export interface UserChatResponse {
  success: boolean
  answer: string
  refused: boolean
  refusal_reason: string | null
  model_name: string | null
  latency_seconds: number | null
  request_id: string
}

/** 管理员来源条目 — RAG 3.0 增强版 */
export interface SourceItem {
  file_name: string
  version: string | null
  page: number | null
  content_preview: string
}

/** 检索调试 — 单条结果 */
export interface DebugResultItem {
  rank: number
  file_name: string
  content_preview: string
  hybrid_score?: number | null
  vector_score?: number | null
  bm25_score?: number | null
  rerank_score?: number | null
  version?: string | null
  page?: number | null
}

/** 检索调试 — RAG 配置 */
export interface DebugConfig {
  vector_weight: number
  keyword_weight: number
  rerank_enabled: boolean
  fetch_k: number
  rerank_top_k: number
}

/** 检索调试信息 — 完整检索链路 */
export interface DebugInfo {
  query: string
  initial_results: DebugResultItem[]
  reranked_results: DebugResultItem[] | null
  final_results: DebugResultItem[]
  refused: boolean
  refusal_reason: string | null
  config: DebugConfig | null
}

/** 管理员问答响应 — 可包含 sources 和调试信息 */
export interface AdminChatResponse extends UserChatResponse {
  sources: SourceItem[]
  debug_info: DebugInfo | null
}

// ---- 系统状态 ----

export interface ComponentStatus {
  status: string
  detail: string | null
  model_name?: string | null
  model_path?: string | null
  load_method?: string | null
  strategy?: string | null
}

export interface SystemStats {
  total_files: number
  indexed_files: number
  total_chunks: number
  chroma_vectors: number
  total_users: number
  active_users: number
  admin_users: number
  today_questions: number
  recent_uploads: Array<{
    id: string
    original_name: string
    file_type: string
    index_status: string
    upload_time: string | null
    chunk_count: number
  }>
  embedding_model: string
  embedding_model_path: string
  embedding_load_method: string
  chroma_collection: string
  llm_provider: string | null
  model_name: string | null
  last_index_update: string | null
}

export interface AdminSystemStatusResponse {
  success: boolean
  version: string
  overall_status: string
  embedding: ComponentStatus
  deepseek: ComponentStatus
  chroma: ComponentStatus
  sqlite: ComponentStatus
  stats: SystemStats
}

// ---- 审计日志 ----

export interface AuditLogItem {
  id: number
  admin_id: number
  admin_username: string
  action: string
  target_type: string | null
  target_id: string | null
  detail: string | null
  ip_address: string | null
  created_at: string | null
}

export interface AuditLogResponse {
  success: boolean
  total: number
  logs: AuditLogItem[]
}

// ---- 管理员文件管理 ----

export interface KnowledgeFileItem {
  id: string
  original_name: string
  stored_name: string
  file_type: string
  file_size: number
  file_hash: string
  source_type: string
  upload_status: string
  index_status: string
  chunk_count: number
  upload_time: string | null
  indexed_time: string | null
  error_message: string | null
  is_active: boolean
  current_version: string
  last_index_time: string | null
  preview_available: boolean
}

export interface FileListResponse {
  success: boolean
  total: number
  files: KnowledgeFileItem[]
}

export interface FileDeleteResponse {
  success: boolean
  message: string
  file_id: string
  deleted_chunks: number
}

export interface FileUploadResultItem {
  filename: string
  success: boolean
  file_id: string | null
  version?: string | null
  error: string | null
  skipped?: boolean
}

export interface FileUploadResponse {
  success: boolean
  message: string
  total: number
  succeeded: number
  failed: number
  skipped: number
  results: FileUploadResultItem[]
}

export interface RebuildIndexResponse {
  success: boolean
  message: string
  total_chunks: number
  elapsed_seconds: number
  error?: string | null
}

export interface IndexStatusResponse {
  success: boolean
  chroma_status: string
  total_vectors: number
  indexed_files: number
  pending_files: number
  total_chunks: number
  last_update_time: string | null
  embedding_model: string
  chroma_collection: string
}

/** 知识库统计（来自系统状态接口） */
export interface KnowledgeStats {
  total_files: number
  indexed_files: number
  pending_files: number
  failed_files: number
  total_chunks: number
  total_vectors: number
  index_status: string
  last_update_time: string
}

// ---- 管理员用户管理 ----

export interface AdminUserItem {
  id: number
  username: string
  display_name: string
  email: string | null
  role: string
  is_active: boolean
  is_superuser: boolean
  last_login_at: string | null
  created_at: string | null
  failed_login_attempts: number
  locked_until: string | null
}

export interface UserListResponse {
  success: boolean
  total: number
  users: AdminUserItem[]
}

export interface CreateUserResponse {
  success: boolean
  message: string
  user: AdminUserItem
}

export interface UserStatusResponse {
  success: boolean
  message: string
  user: AdminUserItem
}

export interface ChangeRoleResponse {
  success: boolean
  message: string
  user: AdminUserItem
}

export interface ResetPasswordResponse {
  success: boolean
  message: string
}

export interface DeleteUserResponse {
  success: boolean
  message: string
  user_id: number
}

/** 用户统计 */
export interface UserStats {
  total_users: number
  admin_users: number
  regular_users: number
  disabled_users: number
}

// ---- 系统日志 ----

export interface SystemLogItem {
  id: number
  user_id: number | null
  username: string
  module: string | null
  action: string
  status: string
  target_type: string | null
  target_id: string | null
  detail: string | null
  ip_address: string | null
  created_at: string | null
}

export interface SystemLogDetail extends SystemLogItem {
  user_agent: string | null
}

export interface SystemLogListResponse {
  success: boolean
  total: number
  items: SystemLogItem[]
}

// ---- 健康检查 ----

export interface HealthCheckResponse {
  success: boolean
  backend: boolean
  database: boolean
  chroma: boolean
  chroma_detail: string
  llm: boolean
  embedding: boolean
}

// ---- 系统设置 ----

export interface SystemSettingsResponse {
  success: boolean
  settings: Record<string, string>
}

// ---- 系统信息 ----

export interface SystemInfoResponse {
  success: boolean
  app_name: string
  version: string
  deploy_mode: string
  database_type: string
  vector_store: string
  model_name: string | null
}

// ---- 安全设置 ----

export interface SecuritySettingsResponse {
  success: boolean
  jwt_initialized: boolean
  jwt_algorithm: string
  access_token_expire_minutes: number
  refresh_token_expire_days: number
  encryption_configured: boolean
}

export interface JWTRegenResponse {
  success: boolean
  message: string
}

// ---- 模块列表 ----

export interface ModuleItem {
  value: string
  label: string
}

// ---- 文件版本 ----

export interface FileVersionItem {
  id: string
  file_id: string
  version: string
  file_hash: string
  file_size: number
  operator: string
  created_time: string
  change_type: string
  stored_name: string
}

export interface FileDetailResponse {
  success: boolean
  file: KnowledgeFileItem & {
    versions: FileVersionItem[]
    vector_count: number
  } | null
  message?: string | null
}

// ---- 文件内容预览 ----

export interface FileContentResponse {
  success: boolean
  content: string
  page: number
  page_size: number
  total_chars: number
  total_pages: number
  file_type: string
  chunks_preview: string[]
  message?: string | null
}

// ---- 版本操作 ----

export interface VersionActionResponse {
  success: boolean
  message: string
  was_current?: boolean
  current_version?: string | null
}

// ---- 操作日志 ----

export interface OperationLogItem {
  id: string
  user_id: string
  operation: string
  target: string
  time: string
  result: string
}

export interface OperationLogsResponse {
  success: boolean
  total: number
  logs: OperationLogItem[]
}

// ---- 文档后台任务 (Phase 8) ----

export interface DocumentTaskItem {
  id: number
  document_id: string
  task_type: string
  status: string  // pending | running | completed | failed | cancel_requested | cancelled
  progress: number
  current_step: string | null
  error_code: string | null
  error_message: string | null
  created_by: string
  created_at: string | null
  started_at: string | null
  completed_at: string | null
  cancelled_at: string | null
  retry_count: number
  original_task_id: number | null
  chunk_count: number | null
}

export interface DocumentTaskListResponse {
  success: boolean
  total: number
  tasks: DocumentTaskItem[]
}

export interface DocumentTaskDetailResponse {
  success: boolean
  task: DocumentTaskItem | null
  message?: string | null
}

export interface TaskActionResponse {
  success: boolean
  message: string
  task_id: number
  new_status?: string | null
  error_code?: string | null
}

export interface DocumentTaskMetrics {
  upload_active: number
  upload_waiting: number
  upload_total: number
  upload_rejected_total: number
  document_task_pending: number
  document_task_running: number
  document_task_completed_total: number
  document_task_failed_total: number
  document_task_cancelled_total: number
  document_task_queue_full_total: number
  document_parse_timeout_total: number
  document_index_timeout_total: number
  document_task_average_duration_ms: number
}

/** Phase 8: 上传异步响应 */
export interface UploadAcceptedResponse {
  success: boolean
  message: string
  total: number
  succeeded: number
  failed: number
  skipped: number
  results: Array<{
    filename: string
    success: boolean
    document_id: string | null
    task_id: number | null
    error: string | null
    error_code: string | null
    skipped?: boolean
  }>
}

/** Phase 8: 重建索引异步响应 */
export interface RebuildAcceptedResponse {
  success: boolean
  message: string
  task_id?: number | null
  status: string
}
