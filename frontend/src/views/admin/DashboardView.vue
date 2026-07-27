<template>
  <div class="dashboard-page">
    <PageHeader title="工作台" description="企业智库 AI 管理平台概览" />

    <!-- 企业运行概览 — 统计卡片 -->
    <div v-if="loading" class="stat-grid">
      <div v-for="i in 6" :key="i" class="app-card skeleton-card">
        <LoadingBlock variant="skeleton" :lines="2" />
      </div>
    </div>

    <div v-else-if="error" class="error-block">
      <EmptyState
        title="加载失败"
        :description="error"
        type="search"
      >
        <el-button type="primary" @click="fetchData">重新加载</el-button>
      </EmptyState>
    </div>

    <div v-else class="stat-grid">
      <StatisticCard
        label="知识库文件数"
        :value="stats.total_files"
        :icon="Files"
        icon-class="default"
      />
      <StatisticCard
        label="已索引文件数"
        :value="stats.indexed_files"
        :icon="FileCheck"
        icon-class="success"
      />
      <StatisticCard
        label="知识片段数"
        :value="stats.total_chunks"
        :icon="Layers"
        icon-class="default"
      />
      <StatisticCard
        label="向量总数"
        :value="stats.chroma_vectors"
        :icon="Database"
        icon-class="default"
      />
      <StatisticCard
        label="当前用户数"
        :value="stats.total_users"
        :icon="Users"
        icon-class="success"
      />
      <StatisticCard
        label="今日问答"
        :value="stats.today_questions"
        :icon="MessageSquare"
        icon-class="default"
      />
    </div>

    <!-- 快捷入口 -->
    <div class="quick-section">
      <h3 class="section-title">快捷入口</h3>
      <div class="quick-grid">
        <QuickEntryCard
          title="上传知识"
          description="上传文档扩充知识库"
          :icon="Upload"
          icon-class="default"
          @click="$router.push('/admin/knowledge')"
        />
        <QuickEntryCard
          title="新建用户"
          description="创建新用户账号"
          :icon="UserPlus"
          icon-class="success"
          @click="$router.push('/admin/users')"
        />
        <QuickEntryCard
          title="智能问答"
          description="预览管理员问答效果"
          :icon="MessageSquare"
          icon-class="default"
          @click="$router.push('/admin/chat-preview')"
        />
        <QuickEntryCard
          title="系统状态"
          description="查看组件运行状态"
          :icon="Monitor"
          icon-class="warning"
          @click="$router.push('/admin/system')"
        />
      </div>
    </div>

    <!-- 系统健康 -->
    <div class="health-section">
      <div class="section-header">
        <h3 class="section-title">系统健康</h3>
        <el-button text size="small" @click="fetchHealth" :loading="healthLoading">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </div>
      <div class="health-grid">
        <div class="health-item" v-for="item in healthItems" :key="item.label">
          <span :class="['health-dot', item.ok ? 'ok' : 'error']" />
          <span class="health-label">{{ item.label }}</span>
          <span v-if="item.detail" class="health-detail">{{ item.detail }}</span>
          <StatusBadge :status="item.ok ? 'ok' : 'error'" />
        </div>
      </div>
    </div>

    <!-- 系统运行状态 -->
    <div class="status-section">
      <h3 class="section-title">组件详情</h3>
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
        </div>
        <div class="app-card">
          <div class="status-row">
            <span class="status-label">LLM / DeepSeek</span>
            <StatusBadge :status="statusData?.deepseek?.status || 'unknown'" />
          </div>
        </div>
        <div class="app-card">
          <div class="status-row">
            <span class="status-label">Chroma 向量库</span>
            <StatusBadge :status="statusData?.chroma?.status || 'unknown'" />
          </div>
        </div>
        <div class="app-card">
          <div class="status-row">
            <span class="status-label">SQLite 数据库</span>
            <StatusBadge :status="statusData?.sqlite?.status || 'unknown'" />
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
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import adminSystemApi from '@/api/adminSystem'
import type { AdminSystemStatusResponse } from '@/types/api'
import PageHeader from '@/components/common/PageHeader.vue'
import StatisticCard from '@/components/dashboard/StatisticCard.vue'
import QuickEntryCard from '@/components/dashboard/QuickEntryCard.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import LoadingBlock from '@/components/common/LoadingBlock.vue'
import { Files, FileCheck, Layers, Database, Users, Upload, UserPlus, MessageSquare, Monitor, Cpu } from '@lucide/vue'
import { computed } from 'vue'
import { extractErrorMessage } from '@/utils/error'

const loading = ref(true)
const error = ref('')
const statusData = ref<AdminSystemStatusResponse | null>(null)

const stats = ref({
  total_files: 0,
  indexed_files: 0,
  total_chunks: 0,
  chroma_vectors: 0,
  total_users: 0,
  today_questions: 0,
  model_name: null as string | null,
})

// 健康检查状态
const healthLoading = ref(true)
const health = ref({
  backend: false,
  database: false,
  chroma: false,
  chroma_detail: '',
  llm: false,
  embedding: false,
})

async function fetchData() {
  loading.value = true
  error.value = ''
  try {
    const result = await adminSystemApi.getSystemStatus()
    statusData.value = result
    if (result.stats) {
      stats.value = {
        total_files: result.stats.total_files,
        indexed_files: result.stats.indexed_files,
        total_chunks: result.stats.total_chunks,
        chroma_vectors: result.stats.chroma_vectors || 0,
        total_users: result.stats.total_users,
        today_questions: result.stats.today_questions || 0,
        model_name: result.stats.model_name || null,
      }
    }
  } catch (err: unknown) {
    error.value = extractErrorMessage(err)
  } finally {
    loading.value = false
  }
}

async function fetchHealth() {
  healthLoading.value = true
  try {
    const result = await adminSystemApi.getHealthCheck()
    health.value.backend = result.backend
    health.value.database = result.database
    health.value.chroma = result.chroma
    health.value.chroma_detail = result.chroma_detail || ''
    health.value.llm = result.llm
    health.value.embedding = result.embedding
  } catch {
    // 健康检查失败不影响主功能
  } finally {
    healthLoading.value = false
  }
}

const healthItems = computed(() => [
  { label: 'Backend API', ok: health.value.backend, detail: '' },
  { label: 'Database', ok: health.value.database, detail: '' },
  { label: 'Chroma Vector DB', ok: health.value.chroma, detail: health.value.chroma_detail },
  { label: 'LLM API', ok: health.value.llm, detail: '' },
  { label: 'Embedding', ok: health.value.embedding, detail: '' },
])

onMounted(() => {
  fetchData()
  fetchHealth()
})
</script>

<style lang="scss" scoped>
.dashboard-page {
  max-width: 1440px;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: $spacing-md;
  margin-bottom: $spacing-xl;
}

.skeleton-card {
  min-height: 108px;
}

.error-block {
  margin-bottom: $spacing-xl;
}

.health-section,
.quick-section,
.status-section {
  margin-bottom: $spacing-xl;
}

.section-title {
  font-size: $font-size-base;
  font-weight: 600;
  color: $color-text-primary;
  margin-bottom: $spacing-md;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: $spacing-md;

  .section-title {
    margin-bottom: 0;
  }
}

.health-grid {
  display: flex;
  gap: $spacing-md;
  flex-wrap: wrap;
}

.health-item {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  padding: $spacing-sm $spacing-md;
  background: $color-card-bg;
  border: 1px solid $color-border;
  border-radius: $control-radius;
  min-width: 180px;
}

.health-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;

  &.ok {
    background: $color-success;
  }

  &.error {
    background: $color-danger;
  }
}

.health-label {
  font-size: $font-size-sm;
  color: $color-text-secondary;
  flex: 1;
}

.health-detail {
  font-size: $font-size-xs;
  color: $color-text-placeholder;
  margin-right: $spacing-sm;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.quick-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: $spacing-md;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: $spacing-md;
}

.status-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 0;
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

@media (max-width: 1400px) {
  .stat-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 1200px) {
  .stat-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .quick-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .status-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
