<template>
  <div class="chat-preview-page">
    <PageHeader
      title="智能问答"
      description="管理员问答预览 — 可查看知识库引用来源和检索调试信息，用于调试和验证检索质量。"
    />

    <div class="preview-layout">
      <!-- 输入区 -->
      <div class="app-card input-card">
        <div class="input-area">
          <el-input
            v-model="question"
            type="textarea"
            :rows="3"
            placeholder="输入问题，测试知识库检索与回答效果..."
            :disabled="sending"
            @keyup.enter.exact="handleSend"
          />
          <div class="input-footer">
            <div class="input-options">
              <el-switch
                v-model="debugMode"
                active-text="检索调试"
                size="small"
                :disabled="sending"
              />
              <span class="input-hint">按 Enter 发送，Shift+Enter 换行</span>
            </div>
            <el-button
              type="primary"
              :loading="sending"
              :disabled="!question.trim()"
              @click="handleSend"
            >
              <el-icon><Promotion /></el-icon>
              发送
            </el-button>
          </div>
        </div>
      </div>

      <!-- 回答区域 -->
      <div v-if="lastResponse" class="response-area">
        <!-- 回答卡片 -->
        <div class="app-card response-card">
          <div class="response-header">
            <h3 class="response-title">回答</h3>
            <div class="response-meta">
              <span class="meta-item">
                耗时: {{ lastResponse.latency_seconds?.toFixed(2) }}s
              </span>
              <span class="meta-item">
                模型: {{ lastResponse.model_name || '--' }}
              </span>
              <span v-if="lastResponse.refused" class="meta-item refused-tag">
                已拒答
              </span>
              <el-button link type="primary" size="small" @click="handleCopy">
                <el-icon><CopyDocument /></el-icon>
                复制回答
              </el-button>
            </div>
          </div>

          <div v-if="lastResponse.refused" class="refused-block">
            <el-alert type="warning" :closable="false" show-icon>
              <template #title>
                {{ lastResponse.refusal_reason || '该问题不在知识库范围内，无法回答。' }}
              </template>
            </el-alert>
          </div>

          <div class="response-body">
            <MarkdownRenderer :content="lastResponse.answer" />
          </div>
        </div>

        <!-- 引用来源 — RAG 3.0 增强版：含版本号 -->
        <div v-if="lastResponse.sources && lastResponse.sources.length > 0" class="app-card sources-card">
          <div class="sources-header">
            <h3 class="sources-title">
              引用来源 ({{ lastResponse.sources.length }})
            </h3>
          </div>

          <el-collapse>
            <el-collapse-item
              v-for="(source, index) in lastResponse.sources"
              :key="index"
            >
              <template #title>
                <div class="source-title-row">
                  <span class="source-name">{{ source.file_name }}</span>
                  <span v-if="source.version" class="source-version">v{{ source.version }}</span>
                  <span v-if="source.page" class="source-page">第 {{ source.page }} 页</span>
                </div>
              </template>
              <div class="source-preview">
                {{ source.content_preview }}
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>

        <!-- 检索调试信息 — RAG 3.0 新增 -->
        <div v-if="debugMode && lastResponse.debug_info" class="app-card debug-card">
          <div class="debug-header">
            <h3 class="debug-title">检索调试信息</h3>
          </div>

          <!-- Query -->
          <div class="debug-section">
            <h4 class="debug-section-title">Query</h4>
            <div class="debug-query">{{ lastResponse.debug_info.query }}</div>
          </div>

          <!-- RAG Config -->
          <div v-if="lastResponse.debug_info.config" class="debug-section">
            <h4 class="debug-section-title">RAG 配置</h4>
            <div class="debug-config-grid">
              <div class="config-item">
                <span class="config-label">向量权重</span>
                <span class="config-value">{{ lastResponse.debug_info.config.vector_weight }}</span>
              </div>
              <div class="config-item">
                <span class="config-label">关键词权重</span>
                <span class="config-value">{{ lastResponse.debug_info.config.keyword_weight }}</span>
              </div>
              <div class="config-item">
                <span class="config-label">Reranker</span>
                <span class="config-value" :class="{ enabled: lastResponse.debug_info.config.rerank_enabled }">
                  {{ lastResponse.debug_info.config.rerank_enabled ? '已启用' : '未启用' }}
                </span>
              </div>
              <div class="config-item">
                <span class="config-label">召回数</span>
                <span class="config-value">{{ lastResponse.debug_info.config.fetch_k }}</span>
              </div>
              <div class="config-item">
                <span class="config-label">Rerank Top-K</span>
                <span class="config-value">{{ lastResponse.debug_info.config.rerank_top_k }}</span>
              </div>
            </div>
          </div>

          <!-- 初始检索结果 (Hybrid) -->
          <div class="debug-section">
            <h4 class="debug-section-title">
              初始检索 — Hybrid Search ({{ lastResponse.debug_info.initial_results.length }} 条)
            </h4>
            <el-table :data="lastResponse.debug_info.initial_results" size="small" stripe max-height="400">
              <el-table-column prop="rank" label="#" width="50" />
              <el-table-column prop="file_name" label="文件" min-width="140" />
              <el-table-column prop="content_preview" label="内容预览" min-width="200" show-overflow-tooltip />
              <el-table-column label="向量分数" width="90">
                <template #default="{ row }">
                  <span v-if="row.vector_score != null" class="score-val">{{ row.vector_score?.toFixed(4) }}</span>
                  <span v-else class="score-na">--</span>
                </template>
              </el-table-column>
              <el-table-column label="BM25 分数" width="90">
                <template #default="{ row }">
                  <span v-if="row.bm25_score != null" class="score-val">{{ row.bm25_score?.toFixed(4) }}</span>
                  <span v-else class="score-na">--</span>
                </template>
              </el-table-column>
              <el-table-column label="融合分数" width="90">
                <template #default="{ row }">
                  <span v-if="row.hybrid_score != null" class="score-val primary">{{ row.hybrid_score?.toFixed(4) }}</span>
                  <span v-else class="score-na">--</span>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <!-- Reranked 结果 -->
          <div v-if="lastResponse.debug_info.reranked_results" class="debug-section">
            <h4 class="debug-section-title">
              Reranker 重排序 ({{ lastResponse.debug_info.reranked_results.length }} 条)
            </h4>
            <el-table :data="lastResponse.debug_info.reranked_results" size="small" stripe max-height="300">
              <el-table-column prop="rank" label="#" width="50" />
              <el-table-column prop="file_name" label="文件" min-width="140" />
              <el-table-column prop="content_preview" label="内容预览" min-width="200" show-overflow-tooltip />
              <el-table-column label="Rerank 分数" width="100">
                <template #default="{ row }">
                  <span v-if="row.rerank_score != null" class="score-val rerank">{{ row.rerank_score?.toFixed(4) }}</span>
                  <span v-else class="score-na">--</span>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <!-- 最终上下文 -->
          <div class="debug-section">
            <h4 class="debug-section-title">
              最终上下文 — 送入 LLM ({{ lastResponse.debug_info.final_results.length }} 条)
            </h4>
            <el-table :data="lastResponse.debug_info.final_results" size="small" stripe max-height="300">
              <el-table-column prop="rank" label="#" width="50" />
              <el-table-column prop="file_name" label="文件" min-width="120" />
              <el-table-column label="版本" width="60">
                <template #default="{ row }">
                  <span v-if="row.version" class="version-tag">v{{ row.version }}</span>
                </template>
              </el-table-column>
              <el-table-column label="页码" width="60">
                <template #default="{ row }">
                  <span v-if="row.page">P{{ row.page }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="content_preview" label="内容预览" min-width="200" show-overflow-tooltip />
            </el-table>
          </div>

          <!-- 拒答信息 -->
          <div v-if="lastResponse.debug_info.refused" class="debug-section">
            <el-alert type="warning" :closable="false" show-icon>
              <template #title>
                拒答原因: {{ lastResponse.debug_info.refusal_reason || '未知' }}
              </template>
            </el-alert>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-if="!lastResponse && !sending" class="app-card">
        <EmptyState
          title="管理员问答预览"
          description="输入问题测试知识库的检索和回答效果。开启「检索调试」可查看完整检索链路（Hybrid Search → Reranker → LLM）。"
          type="default"
        />
      </div>

      <!-- 加载中 -->
      <div v-if="sending" class="app-card">
        <LoadingBlock variant="spinner" text="正在 Hybrid 检索 → Rerank → LLM 生成..." size="large" />
      </div>

      <!-- 错误 -->
      <div v-if="error" class="app-card">
        <EmptyState title="问答失败" :description="error" type="search">
          <el-button type="primary" @click="error = ''">重试</el-button>
        </EmptyState>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import chatApi from '@/api/chat'
import { extractChatErrorMessage } from '@/utils/error'
import type { AdminChatResponse } from '@/types/api'

import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import LoadingBlock from '@/components/common/LoadingBlock.vue'
import MarkdownRenderer from '@/components/chat/MarkdownRenderer.vue'
import { Promotion, CopyDocument } from '@element-plus/icons-vue'

const question = ref('')
const sending = ref(false)
const error = ref('')
const lastResponse = ref<AdminChatResponse | null>(null)
const debugMode = ref(false)

async function handleSend(): Promise<void> {
  const q = question.value.trim()
  if (!q || sending.value) return

  sending.value = true
  error.value = ''

  try {
    const result = await chatApi.askAdminQuestion(q, debugMode.value)
    lastResponse.value = result
    question.value = ''
  } catch (err: unknown) {
    error.value = extractChatErrorMessage(err)
  } finally {
    sending.value = false
  }
}

async function handleCopy(): Promise<void> {
  if (!lastResponse.value?.answer) return
  try {
    await navigator.clipboard.writeText(lastResponse.value.answer)
    ElMessage.success('回答已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败')
  }
}
</script>

<style lang="scss" scoped>
.chat-preview-page {
  max-width: 1060px;
}

.preview-layout {
  display: flex;
  flex-direction: column;
  gap: $spacing-md;
}

.input-card {
  padding: $spacing-lg;
}

.input-area {
  .el-textarea {
    margin-bottom: $spacing-sm;
  }
}

.input-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.input-options {
  display: flex;
  align-items: center;
  gap: $spacing-md;
}

.input-hint {
  font-size: $font-size-xs;
  color: $color-text-tertiary;
}

.response-area {
  display: flex;
  flex-direction: column;
  gap: $spacing-md;
}

.response-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: $spacing-md;
  flex-wrap: wrap;
  gap: $spacing-sm;
}

.response-title {
  font-size: $font-size-lg;
  font-weight: 600;
  color: $color-text-primary;
}

.response-meta {
  display: flex;
  align-items: center;
  gap: $spacing-md;
  flex-wrap: wrap;
}

.meta-item {
  font-size: $font-size-xs;
  color: $color-text-tertiary;
}

.refused-tag {
  color: $color-warning;
  font-weight: 500;
}

.refused-block {
  margin-bottom: $spacing-md;
}

.response-body {
  line-height: 1.8;
  font-size: $font-size-base;
}

// ---- 来源卡片 ----
.sources-header {
  margin-bottom: $spacing-sm;
}

.sources-title {
  font-size: $font-size-base;
  font-weight: 600;
  color: $color-text-primary;
}

.source-title-row {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  flex-wrap: wrap;
}

.source-name {
  font-weight: 500;
}

.source-version {
  font-size: $font-size-xs;
  color: $color-primary;
  background: var(--el-color-primary-light-9);
  padding: 1px 6px;
  border-radius: 4px;
}

.source-page {
  font-size: $font-size-xs;
  color: $color-text-tertiary;
}

.source-preview {
  font-size: $font-size-sm;
  color: $color-text-secondary;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  padding: $spacing-sm;
  background: #f8fafc;
  border-radius: 6px;
  max-height: 300px;
  overflow-y: auto;
}

// ---- 调试卡片 ----
.debug-card {
  padding: $spacing-lg;
  border: 1px solid var(--el-color-warning-light-5);
  background: #fffdf5;
}

.debug-header {
  margin-bottom: $spacing-md;
}

.debug-title {
  font-size: $font-size-base;
  font-weight: 600;
  color: $color-text-primary;
  display: flex;
  align-items: center;
  gap: $spacing-xs;

  &::before {
    content: '🔍';
  }
}

.debug-section {
  margin-bottom: $spacing-lg;

  &:last-child {
    margin-bottom: 0;
  }
}

.debug-section-title {
  font-size: $font-size-sm;
  font-weight: 600;
  color: $color-text-secondary;
  margin-bottom: $spacing-sm;
}

.debug-query {
  font-size: $font-size-sm;
  color: $color-text-primary;
  padding: $spacing-sm;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  font-family: monospace;
}

.debug-config-grid {
  display: flex;
  flex-wrap: wrap;
  gap: $spacing-sm;
}

.config-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  font-size: $font-size-xs;
}

.config-label {
  color: $color-text-tertiary;
}

.config-value {
  font-weight: 600;
  color: $color-text-primary;

  &.enabled {
    color: $color-success;
  }
}

// ---- 分数颜色 ----
.score-val {
  font-family: monospace;
  font-size: $font-size-xs;
  color: $color-text-secondary;

  &.primary {
    color: $color-primary;
    font-weight: 600;
  }

  &.rerank {
    color: var(--el-color-success);
    font-weight: 600;
  }
}

.score-na {
  color: $color-text-placeholder;
}

.version-tag {
  font-size: $font-size-xs;
  color: $color-primary;
  background: var(--el-color-primary-light-9);
  padding: 0 4px;
  border-radius: 3px;
}
</style>
