/**
 * 管理员知识库文件管理 API
 *
 * 安全策略:
 * - 所有接口自动带 Access Token（通过 request 拦截器）
 * - 不在 console 输出文件内容或 Token
 * - 上传使用 FormData
 */

import request from './request'
import type {
  FileListResponse,
  FileUploadResponse,
  FileDeleteResponse,
  RebuildIndexResponse,
  RebuildAcceptedResponse,
  IndexStatusResponse,
  FileDetailResponse,
  FileContentResponse,
  VersionActionResponse,
  OperationLogsResponse,
  DocumentTaskListResponse,
  DocumentTaskDetailResponse,
  TaskActionResponse,
  UploadAcceptedResponse,
} from '@/types/api'

const adminFilesApi = {
  /** 获取文件列表 */
  listFiles(params?: {
    source_type?: string
  }): Promise<FileListResponse> {
    return request.get('/admin/files', { params }).then((res) => res.data)
  },

  /** 上传文件（支持多文件）— Phase 8: 返回 202 */
  uploadFiles(files: File[]): Promise<UploadAcceptedResponse> {
    const formData = new FormData()
    files.forEach((file) => formData.append('files', file))
    return request
      .post('/admin/files/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((res) => res.data)
  },

  /** 获取文件详情（含版本历史） */
  getFileDetail(fileId: string): Promise<FileDetailResponse> {
    return request.get(`/admin/files/${fileId}`).then((res) => res.data)
  },

  /** 获取文件内容预览（分页） */
  getFileContent(
    fileId: string,
    page: number = 1,
    pageSize: number = 10000,
  ): Promise<FileContentResponse> {
    return request
      .get(`/admin/files/${fileId}/content`, { params: { page, page_size: pageSize } })
      .then((res) => res.data)
  },

  /** 删除文件 */
  deleteFile(fileId: string): Promise<FileDeleteResponse> {
    return request.delete(`/admin/files/${fileId}`).then((res) => res.data)
  },

  /** 删除文件版本 */
  deleteVersion(fileId: string, versionId: string): Promise<VersionActionResponse> {
    return request
      .delete(`/admin/files/${fileId}/versions/${versionId}`)
      .then((res) => res.data)
  },

  /** 恢复文件版本 */
  restoreVersion(fileId: string, versionId: string): Promise<VersionActionResponse> {
    return request
      .post(`/admin/files/${fileId}/versions/${versionId}/restore`)
      .then((res) => res.data)
  },

  /** 重建全部索引 — Phase 8: 返回 202 */
  rebuildIndex(): Promise<RebuildAcceptedResponse> {
    return request.post('/admin/files/rebuild-index').then((res) => res.data)
  },

  /** 获取索引状态 */
  getIndexStatus(): Promise<IndexStatusResponse> {
    return request.get('/admin/files/index-status').then((res) => res.data)
  },

  /** 单文件索引 — Phase 8: 返回 202 */
  indexFile(fileId: string): Promise<{ success: boolean; message: string; task_id?: number }> {
    return request.post(`/admin/files/${fileId}/index`).then((res) => res.data)
  },

  /** 获取操作日志 */
  getOperationLogs(limit: number = 50): Promise<OperationLogsResponse> {
    return request
      .get('/admin/files/operation-logs', { params: { limit } })
      .then((res) => res.data)
  },

  // ---- Phase 8: 文档后台任务 API ----

  /** 获取文档任务列表 */
  listTasks(params?: {
    status?: string
    task_type?: string
    document_id?: string
    offset?: number
    limit?: number
  }): Promise<DocumentTaskListResponse> {
    return request.get('/admin/document-tasks', { params }).then((res) => res.data)
  },

  /** 获取任务详情 */
  getTaskDetail(taskId: number): Promise<DocumentTaskDetailResponse> {
    return request.get(`/admin/document-tasks/${taskId}`).then((res) => res.data)
  },

  /** 取消任务 */
  cancelTask(taskId: number): Promise<TaskActionResponse> {
    return request.post(`/admin/document-tasks/${taskId}/cancel`).then((res) => res.data)
  },

  /** 重试任务 */
  retryTask(taskId: number): Promise<TaskActionResponse> {
    return request.post(`/admin/document-tasks/${taskId}/retry`).then((res) => res.data)
  },
}

export default adminFilesApi
