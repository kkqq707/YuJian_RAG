<template>
  <el-drawer
    v-model="visible"
    title="文件详情"
    :size="drawerSize"
    :close-on-click-modal="true"
    @closed="handleClosed"
  >
    <template v-if="file">
      <div class="detail-section">
        <h4 class="section-title">基本信息</h4>
        <div class="detail-grid">
          <div class="detail-item">
            <span class="detail-label">文件名</span>
            <span class="detail-value" :title="file.original_name">{{ file.original_name }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">版本</span>
            <span class="detail-value">
              <el-tag size="small" type="primary">{{ file.current_version || 'v1' }}</el-tag>
            </span>
          </div>
          <div class="detail-item">
            <span class="detail-label">文件类型</span>
            <span class="detail-value">
              <el-tag size="small">{{ file.file_type?.toUpperCase() }}</el-tag>
            </span>
          </div>
          <div class="detail-item">
            <span class="detail-label">文件大小</span>
            <span class="detail-value">{{ formatFileSize(file.file_size) }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">来源类型</span>
            <span class="detail-value">
              <el-tag size="small" :type="file.source_type === 'upload' ? 'success' : 'info'">
                {{ file.source_type === 'upload' ? '用户上传' : '内置文件' }}
              </el-tag>
            </span>
          </div>
          <div class="detail-item full-width">
            <span class="detail-label">文件哈希</span>
            <span class="detail-value mono">{{ file.file_hash?.substring(0, 32) }}...</span>
          </div>
        </div>
      </div>

      <div class="detail-section">
        <h4 class="section-title">索引信息</h4>
        <div class="detail-grid">
          <div class="detail-item">
            <span class="detail-label">索引状态</span>
            <span class="detail-value">
              <StatusBadge :status="file.index_status" :label="statusLabel" />
            </span>
          </div>
          <div class="detail-item">
            <span class="detail-label">片段数量</span>
            <span class="detail-value">{{ file.chunk_count }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">上传时间</span>
            <span class="detail-value">{{ formatTime(file.upload_time) }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">索引时间</span>
            <span class="detail-value">{{ formatTime(file.indexed_time) }}</span>
          </div>
        </div>
      </div>

      <!-- 查看完整详情链接 -->
      <div class="detail-section">
        <el-button type="primary" size="small" @click="handleViewFullDetail">
          <el-icon><View /></el-icon>
          查看完整详情与版本历史
        </el-button>
      </div>

      <!-- 错误信息 -->
      <div v-if="file.error_message" class="detail-section">
        <h4 class="section-title">错误信息</h4>
        <el-alert
          type="error"
          :closable="false"
          show-icon
          :description="safeErrorMessage"
        />
      </div>
    </template>

    <template v-else>
      <LoadingBlock variant="skeleton" :lines="6" />
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, computed, watch, inject } from 'vue'
import { useRouter } from 'vue-router'
import { View } from '@element-plus/icons-vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import LoadingBlock from '@/components/common/LoadingBlock.vue'
import type { KnowledgeFileItem } from '@/types/api'
import type { Ref } from 'vue'

const router = useRouter()

const props = defineProps<{
  modelValue: boolean
  file: KnowledgeFileItem | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const visible = ref(props.modelValue)

// ---- 响应式宽度 ----
const isMobile = inject<Ref<boolean>>('isMobile', ref(false))
const drawerSize = computed(() => isMobile.value ? 'calc(100vw - 24px)' : '480px')

watch(() => props.modelValue, (val) => {
  visible.value = val
})
watch(visible, (val) => {
  emit('update:modelValue', val)
})

const statusLabel = computed(() => {
  if (!props.file) return ''
  const map: Record<string, string> = {
    pending: '待索引',
    processing: '索引中',
    indexed: '已索引',
    failed: '索引失败',
    deleted: '已删除',
  }
  return map[props.file.index_status] || props.file.index_status
})

const safeErrorMessage = computed(() => {
  if (!props.file?.error_message) return ''
  // 安全化：移除可能的绝对路径
  return props.file.error_message
    .replace(/[A-Z]:\\[^\s]*/gi, '[路径已隐藏]')
    .replace(/\/home\/[^\s]*/g, '[路径已隐藏]')
    .replace(/\/Users\/[^\s]*/g, '[路径已隐藏]')
})

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

function handleClosed(): void {
  // clean up
}

function handleViewFullDetail(): void {
  if (props.file) {
    visible.value = false
    router.push({ name: 'KnowledgeDetail', params: { fileId: props.file.id } })
  }
}
</script>

<style lang="scss" scoped>
.detail-section {
  margin-bottom: $spacing-lg;

  + .detail-section {
    padding-top: $spacing-md;
    border-top: 1px solid $color-border;
  }
}

.section-title {
  font-size: $font-size-base;
  font-weight: 600;
  color: $color-text-primary;
  margin-bottom: $spacing-md;
}

.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: $spacing-md;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-label {
  font-size: $font-size-xs;
  color: $color-text-tertiary;
}

.detail-value {
  font-size: $font-size-sm;
  color: $color-text-primary;
  word-break: break-all;

  &.mono {
    font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
    font-size: $font-size-xs;
  }
}

.detail-item.full-width {
  grid-column: 1 / -1;
}
</style>
