/**
 * 知识库管理 Store
 *
 * 安全策略:
 * - 不保存完整文件正文
 * - 不保存 Token
 * - 页面刷新后重新从 API 获取数据
 * - 不将管理数据长期写入 localStorage
 */

import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import adminFilesApi from '@/api/adminFiles'
import adminSystemApi from '@/api/adminSystem'
import { extractErrorMessage } from '@/utils/error'
import type {
  KnowledgeFileItem,
  FileUploadResponse,
  RebuildIndexResponse,
  KnowledgeStats,
} from '@/types/api'

export interface KnowledgeFilters {
  search: string
  fileType: string
  indexStatus: string
  dateRange: [string, string] | null
}

export interface KnowledgePagination {
  page: number
  pageSize: number
  total: number
}

export const useKnowledgeStore = defineStore('knowledge', () => {
  // ---- State ----
  const files = ref<KnowledgeFileItem[]>([])
  const statistics = ref<KnowledgeStats>({
    total_files: 0,
    indexed_files: 0,
    pending_files: 0,
    failed_files: 0,
    total_chunks: 0,
    total_vectors: 0,
    index_status: '未知',
    last_update_time: '',
  })
  const loading = ref(false)
  const uploading = ref(false)
  const rebuilding = ref(false)
  const error = ref('')

  const filters = reactive<KnowledgeFilters>({
    search: '',
    fileType: '',
    indexStatus: '',
    dateRange: null,
  })

  const pagination = reactive<KnowledgePagination>({
    page: 1,
    pageSize: 20,
    total: 0,
  })

  // ---- Actions ----

  /** 获取文件列表 */
  async function fetchFiles(): Promise<void> {
    loading.value = true
    error.value = ''
    try {
      const sourceType = filters.fileType || undefined
      const result = await adminFilesApi.listFiles({ source_type: sourceType })

      let fileList = result.files || []

      // 前端筛选（后端不支持的部分）
      if (filters.search) {
        const term = filters.search.toLowerCase()
        fileList = fileList.filter(
          (f) =>
            f.original_name.toLowerCase().includes(term) ||
            f.file_type.toLowerCase().includes(term) ||
            (f.file_hash && f.file_hash.toLowerCase().includes(term))
        )
      }

      if (filters.indexStatus) {
        fileList = fileList.filter((f) => f.index_status === filters.indexStatus)
      }

      // 默认不显示 deleted 文件
      fileList = fileList.filter((f) => f.index_status !== 'deleted')

      pagination.total = fileList.length

      // 前端分页
      const start = (pagination.page - 1) * pagination.pageSize
      files.value = fileList.slice(start, start + pagination.pageSize)
    } catch (err: unknown) {
      error.value = extractErrorMessage(err)
    } finally {
      loading.value = false
    }
  }

  /** 获取统计数据 */
  async function fetchStatistics(): Promise<void> {
    try {
      const [systemResult, indexResult] = await Promise.all([
        adminSystemApi.getSystemStatus(),
        adminFilesApi.getIndexStatus(),
      ])

      const pendingFiles = indexResult.pending_files || 0

      statistics.value = {
        total_files: systemResult.stats?.total_files || 0,
        indexed_files: systemResult.stats?.indexed_files || 0,
        pending_files: pendingFiles,
        failed_files:
          (systemResult.stats?.total_files || 0) -
          (systemResult.stats?.indexed_files || 0) -
          pendingFiles,
        total_chunks: systemResult.stats?.total_chunks || 0,
        total_vectors: indexResult.total_vectors || 0,
        index_status: indexResult.chroma_status === 'ok' ? '正常' : '异常',
        last_update_time: indexResult.last_update_time || '',
      }
    } catch {
      // 统计失败不阻塞列表
    }
  }

  /** 上传文件 */
  async function uploadFiles(filesToUpload: File[]): Promise<FileUploadResponse> {
    uploading.value = true
    try {
      const result = await adminFilesApi.uploadFiles(filesToUpload)
      await refreshAll()
      return result
    } finally {
      uploading.value = false
    }
  }

  /** 单文件索引 */
  async function indexFile(fileId: string): Promise<void> {
    try {
      await adminFilesApi.indexFile(fileId)
      await refreshAll()
    } catch (err: unknown) {
      throw new Error(extractErrorMessage(err))
    }
  }

  /** 删除文件 */
  async function deleteFile(fileId: string): Promise<void> {
    try {
      await adminFilesApi.deleteFile(fileId)
      await refreshAll()
    } catch (err: unknown) {
      throw new Error(extractErrorMessage(err))
    }
  }

  /** 重建全部索引 */
  async function rebuildIndex(): Promise<RebuildIndexResponse> {
    rebuilding.value = true
    try {
      const result = await adminFilesApi.rebuildIndex()
      await refreshAll()
      return result
    } finally {
      rebuilding.value = false
    }
  }

  /** 刷新全部数据 */
  async function refreshAll(): Promise<void> {
    await Promise.all([fetchFiles(), fetchStatistics()])
  }

  /** 重置筛选条件 */
  function resetFilters(): void {
    filters.search = ''
    filters.fileType = ''
    filters.indexStatus = ''
    filters.dateRange = null
    pagination.page = 1
  }

  /** 设置分页 */
  function setPage(page: number): void {
    pagination.page = page
  }

  return {
    // State
    files,
    statistics,
    loading,
    uploading,
    rebuilding,
    error,
    filters,
    pagination,
    // Actions
    fetchFiles,
    fetchStatistics,
    uploadFiles,
    indexFile,
    deleteFile,
    rebuildIndex,
    refreshAll,
    resetFilters,
    setPage,
  }
})
