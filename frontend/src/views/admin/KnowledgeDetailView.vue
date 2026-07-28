<template>
  <div class="knowledge-detail-page">
    <!-- 页面头部 -->
    <PageHeader :title="pageTitle" description="查看文件详情、版本历史和内容预览。">
      <template #extra>
        <div class="header-actions">
          <el-button @click="handleGoBack">
            <el-icon><ArrowLeft /></el-icon>
            返回列表
          </el-button>
          <el-button type="warning" :loading="indexing" @click="handleReindex">
            <el-icon><Refresh /></el-icon>
            重新索引
          </el-button>
        </div>
      </template>
    </PageHeader>

    <!-- Loading -->
    <LoadingBlock v-if="loading" variant="skeleton" :lines="8" />

    <!-- Error -->
    <el-alert
      v-else-if="error"
      type="error"
      :title="error"
      :closable="false"
      show-icon
    />

    <!-- Content -->
    <template v-else-if="fileDetail">
      <!-- 文件信息卡片 -->
      <div class="app-card">
        <h4 class="section-title">文件信息</h4>
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">文件名</span>
            <span class="info-value">{{ fileDetail.original_name }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">当前版本</span>
            <span class="info-value">
              <el-tag size="small" type="primary">{{ fileDetail.current_version || 'v1' }}</el-tag>
            </span>
          </div>
          <div class="info-item">
            <span class="info-label">文件类型</span>
            <span class="info-value">
              <el-tag size="small">{{ fileDetail.file_type?.toUpperCase() }}</el-tag>
            </span>
          </div>
          <div class="info-item">
            <span class="info-label">文件大小</span>
            <span class="info-value">{{ formatFileSize(fileDetail.file_size) }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">文件哈希</span>
            <span class="info-value hash">{{ fileDetail.file_hash?.substring(0, 16) }}...</span>
          </div>
          <div class="info-item">
            <span class="info-label">上传时间</span>
            <span class="info-value">{{ formatTime(fileDetail.upload_time) }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">上传用户</span>
            <span class="info-value">管理员</span>
          </div>
          <div class="info-item">
            <span class="info-label">存储文件名</span>
            <span class="info-value mono">{{ fileDetail.stored_name }}</span>
          </div>
        </div>
      </div>

      <!-- 索引信息卡片 -->
      <div class="app-card">
        <h4 class="section-title">索引信息</h4>
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">索引状态</span>
            <span class="info-value">
              <StatusBadge :status="fileDetail.index_status" :label="indexStatusLabel" />
            </span>
          </div>
          <div class="info-item">
            <span class="info-label">Chunk 数量</span>
            <span class="info-value">{{ fileDetail.chunk_count }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">Vector 数量</span>
            <span class="info-value">{{ vectorCount }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">最后索引时间</span>
            <span class="info-value">{{ formatTime(fileDetail.last_index_time || fileDetail.indexed_time) }}</span>
          </div>
        </div>
      </div>

      <!-- 版本历史卡片 -->
      <div class="app-card">
        <div class="section-header">
          <h4 class="section-title">版本历史</h4>
        </div>
        <el-table :data="versions" style="width: 100%" stripe size="small">
          <el-table-column prop="version" label="版本" width="80" align="center">
            <template #default="scope">
              <el-tag
                size="small"
                :type="scope.row.version === fileDetail.current_version ? 'primary' : 'info'"
              >
                {{ scope.row.version }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="file_hash" label="文件哈希" width="180">
            <template #default="scope">
              <span class="cell-mono">{{ scope.row.file_hash?.substring(0, 16) }}...</span>
            </template>
          </el-table-column>
          <el-table-column prop="file_size" label="文件大小" width="100" align="right">
            <template #default="scope">
              {{ formatFileSize(scope.row.file_size) }}
            </template>
          </el-table-column>
          <el-table-column prop="change_type" label="变更类型" width="90" align="center">
            <template #default="scope">
              <el-tag size="small" :type="changeTypeTag(scope.row.change_type)">
                {{ changeTypeLabel(scope.row.change_type) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="operator" label="操作者" width="80" align="center" />
          <el-table-column prop="created_time" label="创建时间" width="170">
            <template #default="scope">
              <span class="cell-time">{{ formatTime(scope.row.created_time) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180" align="center" fixed="right">
            <template #default="scope">
              <div class="action-group">
                <el-button
                  v-if="scope.row.version !== fileDetail.current_version"
                  link
                  type="primary"
                  size="small"
                  @click="handleRestoreVersion(scope.row)"
                >
                  恢复
                </el-button>
                <el-button
                  v-if="versions.length > 1"
                  link
                  type="danger"
                  size="small"
                  @click="handleDeleteVersionClick(scope.row)"
                >
                  删除
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 内容预览卡片 -->
      <div class="app-card">
        <div class="section-header">
          <h4 class="section-title">内容预览</h4>
          <div class="preview-controls">
            <span class="page-info">
              第 {{ contentPage }} / {{ contentTotalPages }} 页
              ({{ formatFileSize(contentTotalChars) }} 字符)
            </span>
            <el-button-group>
              <el-button size="small" :disabled="contentPage <= 1" @click="handlePrevPage">
                <el-icon><ArrowLeft /></el-icon>
                上一页
              </el-button>
              <el-button
                size="small"
                :disabled="contentPage >= contentTotalPages"
                @click="handleNextPage"
              >
                下一页
                <el-icon><ArrowRight /></el-icon>
              </el-button>
            </el-button-group>
          </div>
        </div>

        <LoadingBlock v-if="contentLoading" variant="skeleton" :lines="10" />

        <div v-else-if="contentError" class="content-error">
          <el-alert type="warning" :title="contentError" :closable="false" show-icon />
          <el-button type="primary" size="small" class="reload-btn" @click="loadContent(1)">
            重新加载
          </el-button>
        </div>

        <div v-else class="content-preview markdown-body" v-html="renderedContent" />

        <!-- Chunks 预览 -->
        <div v-if="chunksPreview.length > 0" class="chunks-preview">
          <h5 class="subsection-title">知识片段预览（前 5 个）</h5>
          <div v-for="(chunk, idx) in chunksPreview" :key="idx" class="chunk-item">
            <span class="chunk-idx">#{{ idx + 1 }}</span>
            <span class="chunk-text">{{ chunk }}</span>
          </div>
        </div>
      </div>
    </template>

    <!-- 删除版本确认 Dialog -->
    <ConfirmDialog
      v-model="deleteVersionDialogVisible"
      title="删除版本"
      :message="deleteVersionMessage"
      confirm-type="danger"
      confirm-text="确认删除"
      @confirm="handleDeleteVersionConfirm"
      @cancel="deleteVersionTarget = null"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type TagProps } from 'element-plus'
import { ArrowLeft, ArrowRight, Refresh } from '@element-plus/icons-vue'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
import adminFilesApi from '@/api/adminFiles'
import { extractErrorMessage } from '@/utils/error'
import PageHeader from '@/components/common/PageHeader.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import LoadingBlock from '@/components/common/LoadingBlock.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import type { FileVersionItem } from '@/types/api'

const route = useRoute()
const router = useRouter()

const fileId = computed(() => route.params.fileId as string)
const pageTitle = computed(() => fileDetail.value?.original_name || '文件详情')

const loading = ref(false)
const error = ref('')
const indexing = ref(false)

// ---- File detail state ----
const fileDetail = ref<any>(null)
const versions = ref<FileVersionItem[]>([])
const vectorCount = ref(0)

// ---- Content preview state ----
const contentLoading = ref(false)
const contentError = ref('')
const contentText = ref('')
const contentPage = ref(1)
const contentTotalPages = ref(1)
const contentTotalChars = ref(0)
const chunksPreview = ref<string[]>([])

// ---- Version management state ----
const deleteVersionDialogVisible = ref(false)
const deleteVersionTarget = ref<FileVersionItem | null>(null)
const deleteVersionMessage = computed(() => {
  if (!deleteVersionTarget.value) return ''
  const v = deleteVersionTarget.value
  const isCurrent = v.version === fileDetail.value?.current_version
  return `删除版本 ${v.version} 后${isCurrent ? '，将自动回退到上一个可用版本。' : '。'}此操作不可撤销。`
})

// ---- Computed ----
const indexStatusLabel = computed(() => {
  const map: Record<string, string> = {
    pending: '待索引',
    processing: '索引中',
    indexed: '已索引',
    failed: '索引失败',
    deleted: '已删除',
  }
  return map[fileDetail.value?.index_status] || fileDetail.value?.index_status || ''
})

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
})

const renderedContent = computed(() => {
  if (!contentText.value) return '<p style="color:#999">暂无内容</p>'
  try {
    const html = md.render(contentText.value)
    return DOMPurify.sanitize(html)
  } catch {
    return contentText.value.replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>')
  }
})

// ---- Lifecycle ----
onMounted(() => {
  loadDetail()
})

// ---- Detail loading ----
async function loadDetail(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const result = await adminFilesApi.getFileDetail(fileId.value)
    if (result.success && result.file) {
      fileDetail.value = result.file
      versions.value = result.file.versions || []
      vectorCount.value = result.file.vector_count || 0
      // Load first page of content
      loadContent(1)
    } else {
      error.value = result.message || '文件不存在'
    }
  } catch (err: unknown) {
    error.value = extractErrorMessage(err)
  } finally {
    loading.value = false
  }
}

// ---- Content loading ----
async function loadContent(page: number): Promise<void> {
  contentLoading.value = true
  contentError.value = ''
  try {
    const result = await adminFilesApi.getFileContent(fileId.value, page, 10000)
    if (result.success) {
      contentText.value = result.content
      contentPage.value = result.page
      contentTotalPages.value = result.total_pages
      contentTotalChars.value = result.total_chars
      chunksPreview.value = result.chunks_preview || []
    } else {
      contentError.value = result.message || '无法加载内容'
    }
  } catch (err: unknown) {
    contentError.value = extractErrorMessage(err)
  } finally {
    contentLoading.value = false
  }
}

function handlePrevPage(): void {
  if (contentPage.value > 1) {
    loadContent(contentPage.value - 1)
  }
}

function handleNextPage(): void {
  if (contentPage.value < contentTotalPages.value) {
    loadContent(contentPage.value + 1)
  }
}

// ---- Reindex ----
async function handleReindex(): Promise<void> {
  indexing.value = true
  try {
    await adminFilesApi.indexFile(fileId.value)
    ElMessage.success('重新索引完成')
    await loadDetail()
  } catch (err: unknown) {
    ElMessage.error(extractErrorMessage(err))
  } finally {
    indexing.value = false
  }
}

// ---- Version management ----
function handleDeleteVersionClick(version: FileVersionItem | any): void {
  deleteVersionTarget.value = version
  deleteVersionDialogVisible.value = true
}

async function handleDeleteVersionConfirm(): Promise<void> {
  if (!deleteVersionTarget.value) return
  try {
    const result = await adminFilesApi.deleteVersion(
      fileId.value,
      deleteVersionTarget.value.id,
    )
    if (result.success) {
      ElMessage.success(result.message)
      deleteVersionDialogVisible.value = false
      deleteVersionTarget.value = null
      await loadDetail()
    } else {
      ElMessage.error(result.message)
    }
  } catch (err: unknown) {
    ElMessage.error(extractErrorMessage(err))
  }
}

async function handleRestoreVersion(version: FileVersionItem | any): Promise<void> {
  try {
    const result = await adminFilesApi.restoreVersion(fileId.value, version.id)
    if (result.success) {
      ElMessage.success(result.message)
      await loadDetail()
    } else {
      ElMessage.error(result.message)
    }
  } catch (err: unknown) {
    ElMessage.error(extractErrorMessage(err))
  }
}

// ---- Navigation ----
function handleGoBack(): void {
  router.push({ name: 'Knowledge' })
}

// ---- Utilities ----
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
  return new Date(time).toLocaleString('zh-CN')
}

function changeTypeTag(type: string): TagProps['type'] {
  const map: Record<string, TagProps['type']> = {
    create: 'success',
    update: 'warning',
    rollback: 'info',
  }
  return map[type] || 'info'
}

function changeTypeLabel(type: string): string {
  const map: Record<string, string> = {
    create: '创建',
    update: '更新',
    rollback: '回退',
  }
  return map[type] || type
}
</script>

<style lang="scss" scoped>
.knowledge-detail-page {
  width: 100%;
  max-width: var(--content-max-width);
  margin: 0 auto;
}

.header-actions {
  display: flex;
  gap: $spacing-sm;
  flex-wrap: wrap;
}

.section-title {
  font-size: $font-size-base;
  font-weight: 600;
  color: $color-text-primary;
  margin-bottom: $spacing-md;
  margin-top: 0;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: $spacing-md;
  gap: $spacing-sm;
  flex-wrap: wrap;

  .section-title {
    margin-bottom: 0;
  }
}

.subsection-title {
  font-size: $font-size-sm;
  font-weight: 600;
  color: $color-text-secondary;
  margin: $spacing-md 0 $spacing-sm;
}

// Info grid
.info-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: $spacing-md;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-label {
  font-size: $font-size-xs;
  color: $color-text-tertiary;
}

.info-value {
  font-size: $font-size-sm;
  color: $color-text-primary;
  word-break: break-all;

  &.hash, &.mono {
    font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
    font-size: $font-size-xs;
  }
}

// Cards
.app-card {
  margin-bottom: $spacing-lg;
}

// Table styles
.cell-mono {
  font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
  font-size: $font-size-xs;
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

// Content preview
.preview-controls {
  display: flex;
  align-items: center;
  gap: $spacing-md;
  flex-wrap: wrap;
}

.page-info {
  font-size: $font-size-xs;
  color: $color-text-tertiary;
}

.content-preview {
  max-height: 600px;
  overflow-y: auto;
  padding: $spacing-md;
  background: $color-page-bg;
  border-radius: $card-radius;
  border: 1px solid $color-border;
  font-size: $font-size-sm;
  line-height: 1.8;

  // Reset markdown body margin
  &.markdown-body {
    h1, h2, h3, h4 { margin-top: $spacing-md; }
    p { margin-bottom: $spacing-sm; }
    pre { background: #1e1e1e; color: #d4d4d4; padding: $spacing-sm; border-radius: 4px; overflow-x: auto; }
    code { font-family: 'SF Mono', Monaco, monospace; font-size: $font-size-xs; }
    blockquote { border-left: 3px solid $color-primary; padding-left: $spacing-sm; color: $color-text-secondary; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid $color-border; padding: $spacing-xs $spacing-sm; }
  }
}

.content-error {
  text-align: center;
  padding: $spacing-lg;

  .reload-btn {
    margin-top: $spacing-md;
  }
}

.chunks-preview {
  margin-top: $spacing-lg;
  padding-top: $spacing-md;
  border-top: 1px solid $color-border;
}

.chunk-item {
  display: flex;
  gap: $spacing-sm;
  padding: $spacing-xs 0;
  font-size: $font-size-xs;
  color: $color-text-secondary;

  + .chunk-item {
    border-top: 1px dashed $color-border;
  }
}

.chunk-idx {
  flex-shrink: 0;
  color: $color-primary;
  font-weight: 600;
}

.chunk-text {
  word-break: break-all;
  line-height: 1.6;
}

// ---- 统一响应式断点 ----

// Tablet (768px ~ 1199px)
@media (min-width: 768px) and (max-width: 1199px) {
  .info-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

// Mobile (< 768px)
@media (max-width: 767px) {
  .info-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: $spacing-sm;
  }

  .preview-controls {
    flex-direction: column;
    align-items: flex-start;
    width: 100%;
  }

  .header-actions {
    width: 100%;

    .el-button {
      flex: 1;
      min-height: var(--touch-target-min);
    }
  }

  .section-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
