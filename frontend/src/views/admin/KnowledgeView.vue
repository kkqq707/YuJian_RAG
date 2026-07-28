<template>
  <div class="knowledge-page">
    <!-- 页面头部 -->
    <PageHeader
      title="知识库管理"
      description="集中管理企业制度、产品资料、业务手册等知识文件。"
    >
      <template #extra>
        <div class="header-actions">
          <el-button @click="handleUploadClick">
            <el-icon><Upload /></el-icon>
            上传文件
          </el-button>
          <el-button :loading="refreshing" @click="handleRefresh">
            <el-icon><RefreshCw /></el-icon>
            刷新
          </el-button>
          <el-button type="warning" @click="showRebuildDialog = true">
            <el-icon><AlertTriangle /></el-icon>
            重建全部索引
          </el-button>
        </div>
      </template>
    </PageHeader>

    <!-- 统计卡片 -->
    <div v-if="!store.error" class="stat-grid">
      <StatisticCard
        label="文件总数"
        :value="store.statistics.total_files"
        :icon="Files"
        icon-class="default"
        :loading="store.loading"
      />
      <StatisticCard
        label="已索引文件数"
        :value="store.statistics.indexed_files"
        :icon="FileCheck"
        icon-class="success"
        :loading="store.loading"
      />
      <StatisticCard
        label="待索引文件数"
        :value="store.statistics.pending_files"
        :icon="Clock"
        icon-class="warning"
        :loading="store.loading"
      />
      <StatisticCard
        label="失败文件数"
        :value="store.statistics.failed_files"
        :icon="AlertCircle"
        icon-class="danger"
        :loading="store.loading"
      />
      <StatisticCard
        label="知识片段总数"
        :value="store.statistics.total_chunks"
        :icon="Layers"
        icon-class="default"
        :loading="store.loading"
      />
      <StatisticCard
        label="向量总数"
        :value="store.statistics.total_vectors"
        :icon="Database"
        icon-class="default"
        :loading="store.loading"
      />
      <StatisticCard
        label="索引状态"
        :value="store.statistics.index_status"
        :icon="Activity"
        icon-class="success"
        :loading="store.loading"
      />
    </div>

    <!-- 最后更新信息 -->
    <div v-if="!store.error && store.statistics.last_update_time" class="last-update-bar">
      <el-icon><Clock /></el-icon>
      <span>最后索引更新时间：{{ formattedUpdateTime }}</span>
    </div>

    <!-- 搜索与筛选 -->
    <div class="app-card filter-card">
      <div class="filter-row">
        <el-input
          v-model="store.filters.search"
          placeholder="搜索文件名..."
          clearable
          class="filter-input"
          @clear="handleFilterChange"
          @keyup.enter="handleFilterChange"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>

        <el-select
          v-model="store.filters.fileType"
          placeholder="文件类型"
          clearable
          class="filter-select"
          @change="handleFilterChange"
        >
          <el-option label="全部类型" value="" />
          <el-option label="TXT" value="txt" />
          <el-option label="MD" value="md" />
          <el-option label="PDF" value="pdf" />
          <el-option label="DOCX" value="docx" />
          <el-option label="XLSX" value="xlsx" />
        </el-select>

        <el-select
          v-model="store.filters.indexStatus"
          placeholder="索引状态"
          clearable
          class="filter-select"
          @change="handleFilterChange"
        >
          <el-option label="全部状态" value="" />
          <el-option label="待索引" value="pending" />
          <el-option label="索引中" value="processing" />
          <el-option label="已索引" value="indexed" />
          <el-option label="失败" value="failed" />
        </el-select>

        <el-button @click="handleResetFilters">重置筛选</el-button>
      </div>
    </div>

    <!-- 文件列表 -->
    <div class="app-card">
      <!-- Error state -->
      <div v-if="store.error" class="error-block">
        <EmptyState
          title="加载失败"
          :description="store.error"
          type="search"
        >
          <el-button type="primary" @click="handleRefresh">重新加载</el-button>
        </EmptyState>
      </div>

      <!-- Empty state -->
      <EmptyState
        v-else-if="!store.loading && store.files.length === 0"
        title="暂无知识文件"
        description='点击「上传文件」添加企业知识资料'
        type="folder"
      >
        <el-button type="primary" @click="handleUploadClick">上传文件</el-button>
      </EmptyState>

      <!-- File table -->
      <FileTable
        v-else
        :files="store.files"
        :loading="store.loading"
        :total="store.pagination.total"
        :page-size="store.pagination.pageSize"
        :current-page="store.pagination.page"
        @view-detail="handleViewDetail"
        @index-file="handleIndexFile"
        @delete-file="handleDeleteFile"
        @page-change="handlePageChange"
        @sort-change="handleSortChange"
      />
    </div>

    <!-- 上传文件 Dialog -->
    <UploadDialog
      v-model="showUploadDialog"
      @uploaded="handleUploaded"
    />

    <!-- 文件详情 Drawer -->
    <FileDetailDrawer
      v-model="showDetailDrawer"
      :file="detailFile"
    />

    <!-- 重建索引 Dialog -->
    <RebuildIndexDialog
      v-model="showRebuildDialog"
      @rebuilt="handleRebuilt"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useKnowledgeStore } from '@/stores/knowledge'
import { extractErrorMessage } from '@/utils/error'
import type { KnowledgeFileItem } from '@/types/api'

import PageHeader from '@/components/common/PageHeader.vue'
import StatisticCard from '@/components/dashboard/StatisticCard.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import FileTable from '@/components/knowledge/FileTable.vue'
import UploadDialog from '@/components/knowledge/UploadDialog.vue'
import FileDetailDrawer from '@/components/knowledge/FileDetailDrawer.vue'
import RebuildIndexDialog from '@/components/knowledge/RebuildIndexDialog.vue'

import {
  Files,
  FileCheck,
  Clock,
  AlertCircle,
  Layers,
  Upload,
  RefreshCw,
  AlertTriangle,
  Search,
  Database,
  Activity,
} from '@lucide/vue'

const store = useKnowledgeStore()

const refreshing = ref(false)
const showUploadDialog = ref(false)
const showDetailDrawer = ref(false)
const showRebuildDialog = ref(false)
const detailFile = ref<KnowledgeFileItem | null>(null)

// ---- 格式化最后索引更新时间 ----
const formattedUpdateTime = computed(() => {
  const raw = store.statistics.last_update_time
  if (!raw) return ''
  try {
    const date = new Date(raw)
    if (isNaN(date.getTime())) return raw
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')
    return `${year}-${month}-${day} ${hours}:${minutes}`
  } catch {
    return raw
  }
})

// ---- Lifecycle ----

onMounted(() => {
  store.refreshAll()
})

// ---- Actions ----

async function handleRefresh(): Promise<void> {
  refreshing.value = true
  try {
    await store.refreshAll()
  } finally {
    refreshing.value = false
  }
}

function handleUploadClick(): void {
  showUploadDialog.value = true
}

function handleUploaded(): void {
  showUploadDialog.value = false
}

function handleViewDetail(file: KnowledgeFileItem): void {
  detailFile.value = file
  showDetailDrawer.value = true
}

async function handleIndexFile(file: KnowledgeFileItem): Promise<void> {
  try {
    await store.indexFile(file.id)
    ElMessage.success(`文件 "${file.original_name}" 索引完成`)
  } catch (err: unknown) {
    ElMessage.error(extractErrorMessage(err))
  }
}

async function handleDeleteFile(fileId: string): Promise<void> {
  try {
    await store.deleteFile(fileId)
    ElMessage.success('文件已删除')
  } catch (err: unknown) {
    ElMessage.error(extractErrorMessage(err))
  }
}

function handleRebuilt(): void {
  showRebuildDialog.value = false
}

function handleFilterChange(): void {
  store.pagination.page = 1
  store.fetchFiles()
}

function handleResetFilters(): void {
  store.resetFilters()
  store.fetchFiles()
}

function handlePageChange(page: number): void {
  store.setPage(page)
  store.fetchFiles()
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
function handleSortChange(_sort: { prop: string; order: string }): void {
  // 后端排序可后续扩展
}
</script>

<style lang="scss" scoped>
.knowledge-page {
  width: 100%;
  max-width: var(--content-max-width);
  margin: 0 auto;
}

.header-actions {
  display: flex;
  gap: $spacing-sm;
  flex-wrap: wrap;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: $spacing-md;
  margin-bottom: $spacing-lg;
}

.last-update-bar {
  display: flex;
  align-items: center;
  gap: $spacing-xs;
  padding: $spacing-sm $spacing-md;
  margin-bottom: $spacing-lg;
  background: $color-page-bg;
  border-radius: $card-radius;
  font-size: $font-size-sm;
  color: $color-text-secondary;
  flex-wrap: wrap;

  .el-icon {
    color: $color-text-tertiary;
  }
}

.filter-card {
  margin-bottom: $spacing-lg;
}

.filter-row {
  display: flex;
  gap: $spacing-sm;
  align-items: center;
  flex-wrap: wrap;
}

.filter-input {
  width: 260px;
  flex-shrink: 0;
}

.filter-select {
  width: 150px;
  flex-shrink: 0;
}

.error-block {
  padding: $spacing-lg 0;
}

// ---- 统一响应式断点 ----

// Desktop large → 4 columns stats
@media (min-width: 1200px) and (max-width: 1599px) {
  .stat-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

// Tablet (768px ~ 1199px)
@media (min-width: 768px) and (max-width: 1199px) {
  .stat-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

// Mobile (< 768px)
@media (max-width: 767px) {
  .stat-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: $spacing-sm;
  }

  .filter-row {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-input,
  .filter-select {
    width: 100%;
  }

  .header-actions {
    width: 100%;

    .el-button {
      flex: 1;
      min-height: var(--touch-target-min);
    }
  }
}
</style>
