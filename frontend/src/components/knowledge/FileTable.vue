<template>
  <div class="file-table-wrapper">
    <el-table
      :data="files"
      style="width: 100%"
      v-loading="loading"
      stripe
    >
      <!-- 文件名 -->
      <el-table-column prop="original_name" label="文件名" min-width="180" show-overflow-tooltip>
        <template #default="scope">
          <span class="file-name" @click="handleViewDetail(f(scope.row))">{{ f(scope.row).original_name }}</span>
        </template>
      </el-table-column>

      <!-- 版本 -->
      <el-table-column prop="current_version" label="版本" width="70" align="center">
        <template #default="scope">
          <el-tag size="small" type="primary">{{ f(scope.row).current_version || 'v1' }}</el-tag>
        </template>
      </el-table-column>

      <!-- 文件类型 -->
      <el-table-column prop="file_type" label="类型" width="80" align="center">
        <template #default="scope">
          <el-tag size="small" type="info">{{ f(scope.row).file_type?.toUpperCase() }}</el-tag>
        </template>
      </el-table-column>

      <!-- 文件大小 -->
      <el-table-column prop="file_size" label="大小" width="90" align="right">
        <template #default="scope">
          <span class="cell-mono">{{ formatFileSize(f(scope.row).file_size) }}</span>
        </template>
      </el-table-column>

      <!-- 文件哈希 -->
      <el-table-column prop="file_hash" label="哈希(SHA-256)" width="130" show-overflow-tooltip>
        <template #default="scope">
          <span class="cell-mono hash">{{ f(scope.row).file_hash?.substring(0, 12) }}...</span>
        </template>
      </el-table-column>

      <!-- 上传时间 -->
      <el-table-column prop="upload_time" label="上传时间" width="160" sortable="custom">
        <template #default="scope">
          <span class="cell-time">{{ formatTime(f(scope.row).upload_time) }}</span>
        </template>
      </el-table-column>

      <!-- 索引状态 -->
      <el-table-column prop="index_status" label="索引状态" width="110" align="center">
        <template #default="scope">
          <StatusBadge :status="f(scope.row).index_status" :label="indexStatusLabel(f(scope.row).index_status)" />
        </template>
      </el-table-column>

      <!-- chunk 数量 -->
      <el-table-column prop="chunk_count" label="片段数" width="80" align="center">
        <template #default="scope">
          <span class="cell-mono">{{ f(scope.row).chunk_count }}</span>
        </template>
      </el-table-column>

      <!-- 任务进度 (Phase 8) -->
      <el-table-column label="任务进度" width="140" align="center">
        <template #default="scope">
          <template v-if="getDocTask(f(scope.row).id)">
            <el-progress
              :percentage="getDocTask(f(scope.row).id)!.progress"
              :status="taskProgressStatus(getDocTask(f(scope.row).id)!)"
              :stroke-width="6"
              style="width: 100%"
            />
            <span class="task-step">{{ getDocTask(f(scope.row).id)!.current_step || getDocTask(f(scope.row).id)!.status }}</span>
          </template>
          <span v-else class="cell-mono">--</span>
        </template>
      </el-table-column>

      <!-- 操作 -->
      <el-table-column label="操作" width="280" align="center" fixed="right">
        <template #default="scope">
          <div class="action-group">
            <el-button link type="primary" size="small" @click="handleViewContent(f(scope.row))">
              查看
            </el-button>
            <el-button link type="primary" size="small" @click="handleViewDetail(f(scope.row))">
              详情
            </el-button>
            <!-- Phase 8: 取消按钮（pending/running） -->
            <el-button
              v-if="getDocTask(f(scope.row).id) && canCancel(getDocTask(f(scope.row).id)!)"
              link
              type="warning"
              size="small"
              @click="handleCancelTask(f(scope.row))"
            >
              取消
            </el-button>
            <!-- Phase 8: 重试按钮（failed） -->
            <el-button
              v-if="getDocTask(f(scope.row).id) && canRetry(getDocTask(f(scope.row).id)!)"
              link
              type="warning"
              size="small"
              @click="handleRetryTask(f(scope.row))"
            >
              重试
            </el-button>
            <!-- 索引按钮（无活跃任务时可用） -->
            <el-button
              v-if="!getDocTask(f(scope.row).id) && (f(scope.row).index_status === 'pending' || f(scope.row).index_status === 'failed')"
              link
              type="warning"
              size="small"
              :loading="indexingId === f(scope.row).id"
              :disabled="indexingId !== null"
              @click="handleIndex(f(scope.row))"
            >
              索引
            </el-button>
            <el-button
              v-if="!getDocTask(f(scope.row).id) && f(scope.row).index_status === 'indexed'"
              link
              type="warning"
              size="small"
              :loading="indexingId === f(scope.row).id"
              :disabled="indexingId !== null"
              @click="handleReindex(f(scope.row))"
            >
              重索引
            </el-button>
            <el-button
              link
              type="danger"
              size="small"
              @click="handleDeleteClick(f(scope.row))"
            >
              删除
            </el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div v-if="total > 0" class="table-pagination">
      <el-pagination
        :current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="handlePageChange"
      />
    </div>

    <!-- Confirm Dialog for delete -->
    <ConfirmDialog
      v-model="deleteDialogVisible"
      title="删除知识文件"
      :message="deleteMessage"
      confirm-type="danger"
      confirm-text="确认删除"
      @confirm="handleDeleteConfirm"
      @cancel="deleteTarget = null"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import StatusBadge from '@/components/common/StatusBadge.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import { extractErrorMessage } from '@/utils/error'
import { useKnowledgeStore } from '@/stores/knowledge'
import type { KnowledgeFileItem, DocumentTaskItem } from '@/types/api'

const router = useRouter()
const store = useKnowledgeStore()

const props = defineProps<{
  files: KnowledgeFileItem[]
  loading: boolean
  total: number
  pageSize: number
  currentPage: number
}>()

const emit = defineEmits<{
  'view-detail': [file: KnowledgeFileItem]
  'view-content': [file: KnowledgeFileItem]
  'index-file': [file: KnowledgeFileItem]
  'delete-file': [fileId: string]
  'page-change': [page: number]
  'cancel-task': [taskId: number]
  'retry-task': [taskId: number]
}>()

const indexingId = ref<string | null>(null)
const deleteDialogVisible = ref(false)
const deleteTarget = ref<KnowledgeFileItem | null>(null)

/** Phase 8: 获取文档关联的活跃任务 */
function getDocTask(docId: string): DocumentTaskItem | undefined {
  return store.getDocumentTask(docId)
}

function canCancel(task: DocumentTaskItem): boolean {
  return ['pending', 'running'].includes(task.status)
}

function canRetry(task: DocumentTaskItem): boolean {
  return ['failed', 'cancelled'].includes(task.status)
}

function taskProgressStatus(task: DocumentTaskItem): 'success' | 'exception' | 'warning' | undefined {
  if (task.status === 'completed') return 'success'
  if (task.status === 'failed') return 'exception'
  if (task.status === 'cancelled') return 'warning'
  return undefined
}

function handleCancelTask(file: KnowledgeFileItem): void {
  const task = getDocTask(file.id)
  if (task) emit('cancel-task', task.id)
}

function handleRetryTask(file: KnowledgeFileItem): void {
  const task = getDocTask(file.id)
  if (task) emit('retry-task', task.id)
}

const deleteMessage = computed(() => {
  if (!deleteTarget.value) return ''
  return `删除后，文件 "${deleteTarget.value.original_name}" 及其知识索引将无法继续用于问答。此操作不可撤销。`
})

/** Type-safe row accessor for Element Plus table slots */
function f(row: unknown): KnowledgeFileItem {
  return row as KnowledgeFileItem
}

function formatFileSize(bytes: number): string {
  if (!bytes || bytes === 0) return '--'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let size = bytes
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024
    i++
  }
  return `${size.toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

function formatTime(time: string | null): string {
  if (!time) return '--'
  return new Date(time).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function indexStatusLabel(status: string): string {
  const map: Record<string, string> = {
    pending: '待索引',
    processing: '索引中',
    indexed: '已索引',
    failed: '失败',
    deleted: '已删除',
  }
  return map[status] || status
}

function handleViewContent(file: KnowledgeFileItem): void {
  router.push({ name: 'KnowledgeDetail', params: { fileId: file.id } })
}

function handleViewDetail(file: KnowledgeFileItem): void {
  emit('view-detail', file)
}

async function handleIndex(file: KnowledgeFileItem): Promise<void> {
  indexingId.value = file.id
  try {
    emit('index-file', file)
  } finally {
    indexingId.value = null
  }
}

async function handleReindex(file: KnowledgeFileItem): Promise<void> {
  indexingId.value = file.id
  try {
    emit('index-file', file)
  } finally {
    indexingId.value = null
  }
}

function handleDeleteClick(file: KnowledgeFileItem): void {
  deleteTarget.value = file
  deleteDialogVisible.value = true
}

async function handleDeleteConfirm(): Promise<void> {
  if (!deleteTarget.value) return
  try {
    emit('delete-file', deleteTarget.value.id)
    deleteDialogVisible.value = false
    deleteTarget.value = null
  } catch (err: unknown) {
    ElMessage.error(extractErrorMessage(err))
  }
}

function handlePageChange(page: number): void {
  emit('page-change', page)
}
</script>

<style lang="scss" scoped>
.file-table-wrapper {
  // 横向滚动容器
  max-width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;

  .el-table {
    border-radius: $card-radius;
    min-width: 700px; // 保证小屏幕下表格可横向滚动
  }
}

.file-name {
  color: $color-primary;
  cursor: pointer;
  &:hover {
    text-decoration: underline;
  }
}

.cell-mono {
  font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
  font-size: $font-size-sm;
}

.cell-time {
  font-size: $font-size-sm;
  color: $color-text-secondary;
}

.action-group {
  display: flex;
  gap: 4px;
  justify-content: center;
  flex-wrap: wrap;
}

.table-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: $spacing-md;
}

.task-step {
  font-size: $font-size-xs;
  color: $color-text-tertiary;
  display: block;
  margin-top: 2px;
}

// ---- 移动端适配 ----
@media (max-width: 767px) {
  .table-pagination {
    justify-content: center;

    :deep(.el-pagination) {
      .el-pagination__total {
        display: none;
      }
    }
  }
}
</style>
