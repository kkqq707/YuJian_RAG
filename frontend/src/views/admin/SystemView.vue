<template>
  <div class="system-page">
    <PageHeader title="系统监控" description="查看各组件运行状态和系统健康信息" />

    <!-- 健康检查 -->
    <div v-if="healthLoading" class="section">
      <h3 class="section-title">系统健康</h3>
      <div class="health-grid">
        <div v-for="i in 5" :key="i" class="app-card skeleton-card">
          <LoadingBlock variant="skeleton" :lines="2" />
        </div>
      </div>
    </div>

    <div v-else class="section">
      <div class="section-header">
        <h3 class="section-title">系统健康</h3>
        <el-button text size="small" @click="fetchHealth" :loading="healthLoading">
          <el-icon><RefreshCw /></el-icon>
          刷新
        </el-button>
      </div>
      <div class="health-grid">
        <div class="app-card health-card">
          <div class="health-icon" :class="health.backend ? 'ok' : 'error'">
            <el-icon :size="28"><Monitor /></el-icon>
          </div>
          <div class="health-info">
            <span class="health-name">Backend API</span>
            <StatusBadge :status="health.backend ? 'ok' : 'error'" />
          </div>
        </div>
        <div class="app-card health-card">
          <div class="health-icon" :class="health.database ? 'ok' : 'error'">
            <el-icon :size="28"><Coin /></el-icon>
          </div>
          <div class="health-info">
            <span class="health-name">Database</span>
            <StatusBadge :status="health.database ? 'ok' : 'error'" />
          </div>
        </div>
        <div class="app-card health-card">
          <div class="health-icon" :class="health.chroma ? 'ok' : 'error'">
            <el-icon :size="28"><DataBoard /></el-icon>
          </div>
          <div class="health-info">
            <span class="health-name">Chroma Vector DB</span>
            <StatusBadge :status="health.chroma ? 'ok' : 'error'" />
          </div>
        </div>
        <div class="app-card health-card">
          <div class="health-icon" :class="health.llm ? 'ok' : 'error'">
            <el-icon :size="28"><Connection /></el-icon>
          </div>
          <div class="health-info">
            <span class="health-name">LLM API</span>
            <StatusBadge :status="health.llm ? 'ok' : 'error'" />
          </div>
        </div>
        <div class="app-card health-card">
          <div class="health-icon" :class="health.embedding ? 'ok' : 'error'">
            <el-icon :size="28"><Cpu /></el-icon>
          </div>
          <div class="health-info">
            <span class="health-name">Embedding</span>
            <StatusBadge :status="health.embedding ? 'ok' : 'error'" />
          </div>
        </div>
      </div>
    </div>

    <!-- 系统状态详情 -->
    <div v-if="statusLoading" class="section">
      <h3 class="section-title">组件状态</h3>
      <div class="app-card">
        <LoadingBlock variant="skeleton" :lines="6" />
      </div>
    </div>

    <div v-else-if="statusError" class="section">
      <EmptyState title="状态加载失败" :description="statusError" type="search">
        <el-button type="primary" @click="fetchStatus">重新加载</el-button>
      </EmptyState>
    </div>

    <div v-else class="section">
      <h3 class="section-title">组件状态详情</h3>
      <div class="status-grid">
        <div class="app-card">
          <div class="status-row">
            <span class="status-label">整体状态</span>
            <StatusBadge :status="statusData?.overall_status || 'unknown'" />
          </div>
        </div>
        <div class="app-card">
          <div class="status-row">
            <span class="status-label">Embedding 模型</span>
            <StatusBadge :status="statusData?.embedding?.status || 'unknown'" />
          </div>
          <div class="status-detail" v-if="statusData?.embedding?.detail">
            {{ statusData.embedding.detail }}
          </div>
        </div>
        <div class="app-card">
          <div class="status-row">
            <span class="status-label">LLM / DeepSeek</span>
            <StatusBadge :status="statusData?.deepseek?.status || 'unknown'" />
          </div>
          <div class="status-detail" v-if="statusData?.deepseek?.detail">
            {{ statusData.deepseek.detail }}
          </div>
        </div>
        <div class="app-card">
          <div class="status-row">
            <span class="status-label">Chroma 向量库</span>
            <StatusBadge :status="statusData?.chroma?.status || 'unknown'" />
          </div>
          <div class="status-detail" v-if="statusData?.chroma?.detail">
            {{ statusData.chroma.detail }}
          </div>
        </div>
        <div class="app-card">
          <div class="status-row">
            <span class="status-label">SQLite 数据库</span>
            <StatusBadge :status="statusData?.sqlite?.status || 'unknown'" />
          </div>
          <div class="status-detail" v-if="statusData?.sqlite?.detail">
            {{ statusData.sqlite.detail }}
          </div>
        </div>
        <div class="app-card">
          <div class="status-row">
            <span class="status-label">API 版本</span>
            <span class="status-value">{{ statusData?.version || '--' }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Embedding 配置 -->
    <div v-if="!statusLoading && statusData" class="section">
      <h3 class="section-title">Embedding 模型配置</h3>
      <div class="app-card">
        <el-descriptions :column="3" border>
          <el-descriptions-item label="模型名称">
            {{ statusData.embedding?.model_name || statusData.stats?.embedding_model || '--' }}
          </el-descriptions-item>
          <el-descriptions-item label="模型路径">
            {{ statusData.embedding?.model_path || statusData.stats?.embedding_model_path || '--' }}
          </el-descriptions-item>
          <el-descriptions-item label="加载方式">
            <el-tag
              :type="loadMethodTagType"
              size="small"
              effect="plain"
            >
              {{ statusData.embedding?.load_method || statusData.stats?.embedding_load_method || '--' }}
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </div>

    <!-- 系统信息 -->
    <div v-if="!infoLoading" class="section">
      <h3 class="section-title">系统信息</h3>
      <div class="app-card">
        <el-descriptions :column="3" border>
          <el-descriptions-item label="系统名称">{{ info.app_name }}</el-descriptions-item>
          <el-descriptions-item label="版本">{{ info.version }}</el-descriptions-item>
          <el-descriptions-item label="部署模式">{{ info.deploy_mode }}</el-descriptions-item>
          <el-descriptions-item label="数据库">{{ info.database_type }}</el-descriptions-item>
          <el-descriptions-item label="向量库">{{ info.vector_store }}</el-descriptions-item>
          <el-descriptions-item label="LLM 模型">{{ info.model_name || '未配置' }}</el-descriptions-item>
        </el-descriptions>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import adminSystemApi from '@/api/adminSystem'
import type { AdminSystemStatusResponse, HealthCheckResponse, SystemInfoResponse } from '@/types/api'
import PageHeader from '@/components/common/PageHeader.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import LoadingBlock from '@/components/common/LoadingBlock.vue'
import { RefreshCw } from '@lucide/vue'
import { extractErrorMessage } from '@/utils/error'

const healthLoading = ref(true)
const statusLoading = ref(true)
const infoLoading = ref(true)
const statusError = ref('')

const health = reactive({
  backend: false,
  database: false,
  chroma: false,
  llm: false,
  embedding: false,
})

const statusData = ref<AdminSystemStatusResponse | null>(null)

const info = reactive({
  app_name: '企业智库 AI',
  version: '--',
  deploy_mode: '单企业版',
  database_type: 'SQLite',
  vector_store: 'Chroma',
  model_name: null as string | null,
})

/** 根据加载方式返回对应的 el-tag type */
const loadMethodTagType = computed(() => {
  const method = statusData.value?.embedding?.load_method || statusData.value?.stats?.embedding_load_method || ''
  if (method === '本地加载') return 'success'
  if (method === '正在下载模型') return 'warning'
  if (method === 'Hugging Face 缓存') return 'info'
  if (method === '镜像下载') return 'warning'
  if (method === '官方在线下载') return 'danger'
  return 'info'
})

async function fetchHealth() {
  healthLoading.value = true
  try {
    const result = await adminSystemApi.getHealthCheck()
    health.backend = result.backend
    health.database = result.database
    health.chroma = result.chroma
    health.llm = result.llm
    health.embedding = result.embedding
  } catch {
    // Health check failure — all default to false
  } finally {
    healthLoading.value = false
  }
}

async function fetchStatus() {
  statusLoading.value = true
  statusError.value = ''
  try {
    statusData.value = await adminSystemApi.getSystemStatus()
  } catch (err: unknown) {
    statusError.value = extractErrorMessage(err)
  } finally {
    statusLoading.value = false
  }
}

async function fetchInfo() {
  infoLoading.value = true
  try {
    const result = await adminSystemApi.getSystemInfo()
    info.app_name = result.app_name
    info.version = result.version
    info.deploy_mode = result.deploy_mode
    info.database_type = result.database_type
    info.vector_store = result.vector_store
    info.model_name = result.model_name
  } catch {
    // Info failure — use defaults
  } finally {
    infoLoading.value = false
  }
}

onMounted(() => {
  fetchHealth()
  fetchStatus()
  fetchInfo()
})
</script>

<style lang="scss" scoped>
.system-page {
  width: 100%;
  max-width: var(--content-max-width);
  margin: 0 auto;
}

.section {
  margin-bottom: $spacing-xl;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: $spacing-md;
}

.section-title {
  font-size: $font-size-base;
  font-weight: 600;
  color: $color-text-primary;
  margin-bottom: $spacing-md;

  .section-header & {
    margin-bottom: 0;
  }
}

// 健康卡片
.health-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: $spacing-md;
}

.skeleton-card {
  min-height: 90px;
}

.health-card {
  display: flex;
  align-items: center;
  gap: $spacing-md;
  padding: $spacing-lg;
}

.health-icon {
  width: 52px;
  height: 52px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;

  &.ok {
    background: rgba($color-success, 0.1);
    color: $color-success;
  }

  &.error {
    background: rgba($color-danger, 0.1);
    color: $color-danger;
  }
}

.health-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.health-name {
  font-size: $font-size-sm;
  font-weight: 500;
  color: $color-text-primary;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

// 状态卡片
.status-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: $spacing-md;
}

.status-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 0;
  gap: $spacing-sm;
}

.status-label {
  font-size: $font-size-sm;
  color: $color-text-secondary;
}

.status-value {
  font-size: $font-size-sm;
  color: $color-text-primary;
  font-weight: 500;
}

.status-detail {
  font-size: $font-size-xs;
  color: $color-text-tertiary;
  margin-top: 4px;
  padding-top: 8px;
  border-top: 1px solid $color-border;
  word-break: break-word;
}

// ---- 统一响应式断点 ----

// Tablet (768px ~ 1199px)
@media (min-width: 768px) and (max-width: 1199px) {
  .health-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .status-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  :deep(.el-descriptions) {
    --el-descriptions-item-bordered-label-background: transparent;
  }
}

// Mobile (< 768px)
@media (max-width: 767px) {
  .health-grid {
    grid-template-columns: 1fr;
    gap: $spacing-sm;
  }

  .status-grid {
    grid-template-columns: 1fr;
    gap: $spacing-sm;
  }

  .health-card {
    padding: $spacing-md;
  }

  :deep(.el-descriptions__body .el-descriptions__table) {
    tr {
      display: flex;
      flex-direction: column;
    }

    .el-descriptions__cell {
      padding: $spacing-xs $spacing-sm;
    }
  }
}
</style>
