<template>
  <div class="rag-config-page">
    <PageHeader title="RAG 配置中心" description="调整检索参数，优化问答质量。修改后立即生效，无需重启服务。" />

    <!-- 保存状态 -->
    <el-alert v-if="saveMessage" :title="saveMessage" :type="saveSuccess ? 'success' : 'error'"
      closable show-icon class="mb-4" @close="saveMessage = ''" />

    <div class="config-grid">
      <!-- 1. 混合检索权重 -->
      <div class="app-card">
        <h3 class="card-title">
          <el-icon><Connection /></el-icon>
          混合检索权重
        </h3>
        <p class="card-desc">向量语义检索与 BM25 关键词检索的融合比例</p>

        <el-form label-width="140px" label-position="top">
          <el-form-item label="向量检索权重 (RAG_VECTOR_WEIGHT)">
            <div class="slider-row">
              <el-slider v-model="form.vector_weight" :min="0" :max="1" :step="0.05" show-input
                :format-tooltip="(v: number) => (v * 100).toFixed(0) + '%'" @input="onVectorWeightChange" />
            </div>
            <span class="form-hint">当前: {{ (form.vector_weight * 100).toFixed(0) }}% 向量 + {{
              (form.keyword_weight * 100).toFixed(0) }}% 关键词</span>
          </el-form-item>

          <el-form-item label="关键词检索权重 (RAG_KEYWORD_WEIGHT)">
            <div class="slider-row">
              <el-slider v-model="form.keyword_weight" :min="0" :max="1" :step="0.05" show-input
                :format-tooltip="(v: number) => (v * 100).toFixed(0) + '%'" @input="onKeywordWeightChange" />
            </div>
          </el-form-item>

          <el-form-item label="混合检索召回数 (HYBRID_FETCH_K)">
            <el-input-number v-model="form.hybrid_fetch_k" :min="5" :max="100" :step="5" />
            <span class="form-hint">每种检索方式初始召回的结果数量</span>
          </el-form-item>
        </el-form>
      </div>

      <!-- 2. Reranker 重排序 -->
      <div class="app-card">
        <h3 class="card-title">
          <el-icon><Sort /></el-icon>
          Reranker 重排序
        </h3>
        <p class="card-desc">Cross-Encoder 精细重排序，提升检索精度</p>

        <el-form label-width="140px" label-position="top">
          <el-form-item label="启用 Reranker (RERANK_ENABLE)">
            <el-switch v-model="form.rerank_enable" active-text="启用" inactive-text="关闭" />
          </el-form-item>

          <el-form-item label="Reranker 输入数量 (RERANK_FETCH_K)">
            <el-input-number v-model="form.rerank_fetch_k" :min="5" :max="100" :step="5" />
            <span class="form-hint">送入 Reranker 进行精细排序的文档数</span>
          </el-form-item>

          <el-form-item label="Reranker 输出数量 (RERANK_TOP_K)">
            <el-input-number v-model="form.rerank_top_k" :min="1" :max="20" :step="1" />
            <span class="form-hint">Reranker 返回给 LLM 的 Top-N 结果数</span>
          </el-form-item>
        </el-form>
      </div>

      <!-- 3. 查询增强 -->
      <div class="app-card">
        <h3 class="card-title">
          <el-icon><EditPen /></el-icon>
          查询增强
        </h3>
        <p class="card-desc">自动改写用户查询，提升检索召回率</p>

        <el-form label-width="160px" label-position="top">
          <el-form-item label="启用查询改写 (QUERY_REWRITE_ENABLE)">
            <el-switch v-model="form.query_rewrite_enable" active-text="启用" inactive-text="关闭" />
          </el-form-item>
          <p class="card-desc-inline">
            开启后自动将简短口语化查询（如"怎么请假"）改写为精确检索语句（如"企业员工请假制度、审批流程、假期规则"），提升企业知识库检索效果。
          </p>
        </el-form>
      </div>

      <!-- 5. 拒答阈值 -->
      <div class="app-card">
        <h3 class="card-title">
          <el-icon><Filter /></el-icon>
          拒答阈值
        </h3>
        <p class="card-desc">控制检索结果置信度判断的敏感度，影响系统是否拒答</p>

        <el-form label-width="160px" label-position="top">
          <el-form-item label="L2 距离上限 (MAX_RAW_DISTANCE)">
            <div class="slider-row">
              <el-slider v-model="form.max_raw_distance" :min="0.5" :max="2.0" :step="0.05" show-input />
            </div>
            <span class="form-hint">L2 距离超过此值视为不相关。值越小越严格，默认 1.15</span>
          </el-form-item>

          <el-form-item label="相关度下限 (MIN_RELEVANCE_SCORE)">
            <div class="slider-row">
              <el-slider v-model="form.min_relevance_score" :min="0" :max="1" :step="0.05" show-input />
            </div>
            <span class="form-hint">余弦相似度低于此值视为不相关。值越大越严格，默认 0.32</span>
          </el-form-item>
        </el-form>
      </div>

      <!-- 6. 文本切分 -->
      <div class="app-card">
        <h3 class="card-title">
          <el-icon><Scissor /></el-icon>
          文本切分
        </h3>
        <p class="card-desc">文档入库时的切分参数（修改后需重建索引生效）</p>

        <el-form label-width="140px" label-position="top">
          <el-form-item label="切分大小 (CHUNK_SIZE)">
            <el-input-number v-model="form.chunk_size" :min="100" :max="4000" :step="50" />
            <span class="form-hint">每个文本块的字符数</span>
          </el-form-item>

          <el-form-item label="切分重叠 (CHUNK_OVERLAP)">
            <el-input-number v-model="form.chunk_overlap" :min="0" :max="1000" :step="25" />
            <span class="form-hint">相邻文本块的重叠字符数</span>
          </el-form-item>

          <el-form-item label="返回片段数 (TOP_K)">
            <el-input-number v-model="form.top_k" :min="1" :max="20" :step="1" />
            <span class="form-hint">最终返回给 LLM 的上下文片段数量</span>
          </el-form-item>
        </el-form>
      </div>
    </div>

    <!-- 操作按钮 -->
    <div class="action-bar">
      <el-button type="primary" :loading="saving" @click="handleSave">
        <el-icon><Check /></el-icon>
        保存配置
      </el-button>
      <el-button :loading="resetting" @click="handleReset">
        <el-icon><RefreshLeft /></el-icon>
        重置为默认值
      </el-button>
      <el-button @click="handleRefresh">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/common/PageHeader.vue'
import adminRagConfigApi from '@/api/adminRagConfig'
import type { RAGConfigData } from '@/api/adminRagConfig'

const saving = ref(false)
const resetting = ref(false)
const saveMessage = ref('')
const saveSuccess = ref(true)

const form = reactive<RAGConfigData>({
  id: null,
  chunk_size: 500,
  chunk_overlap: 100,
  top_k: 4,
  similarity_threshold: 0.32,
  hybrid_fetch_k: 20,
  vector_weight: 0.7,
  keyword_weight: 0.3,
  rerank_enable: true,
  rerank_fetch_k: 20,
  rerank_top_k: 5,
  max_raw_distance: 1.15,
  min_relevance_score: 0.32,
  query_rewrite_enable: true,
  updated_at: null,
})

onMounted(() => {
  loadConfig()
})

async function loadConfig() {
  try {
    const data = await adminRagConfigApi.getRAGConfig()
    Object.assign(form, data)
  } catch (e: any) {
    ElMessage.error('加载 RAG 配置失败: ' + (e?.message || '未知错误'))
  }
}

function onVectorWeightChange(val: number | number[]) {
  form.keyword_weight = Math.round((1 - (Array.isArray(val) ? val[0] : val)) * 100) / 100
}

function onKeywordWeightChange(val: number | number[]) {
  form.vector_weight = Math.round((1 - (Array.isArray(val) ? val[0] : val)) * 100) / 100
}

async function handleSave() {
  saving.value = true
  saveMessage.value = ''
  try {
    const result = await adminRagConfigApi.updateRAGConfig({
      chunk_size: form.chunk_size,
      chunk_overlap: form.chunk_overlap,
      top_k: form.top_k,
      similarity_threshold: form.similarity_threshold,
      hybrid_fetch_k: form.hybrid_fetch_k,
      vector_weight: form.vector_weight,
      keyword_weight: form.keyword_weight,
      rerank_enable: form.rerank_enable,
      rerank_fetch_k: form.rerank_fetch_k,
      rerank_top_k: form.rerank_top_k,
      max_raw_distance: form.max_raw_distance,
      min_relevance_score: form.min_relevance_score,
      query_rewrite_enable: form.query_rewrite_enable,
    })
    saveSuccess.value = true
    saveMessage.value = result.message || '配置已保存，新配置立即生效'
    ElMessage.success('RAG 配置已保存')
  } catch (e: any) {
    saveSuccess.value = false
    saveMessage.value = '保存失败: ' + (e?.message || '未知错误')
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function handleReset() {
  resetting.value = true
  saveMessage.value = ''
  try {
    const result = await adminRagConfigApi.resetRAGConfig()
    Object.assign(form, result.config)
    saveSuccess.value = true
    saveMessage.value = '已重置为默认值'
    ElMessage.success('已重置为默认值')
  } catch (e: any) {
    ElMessage.error('重置失败: ' + (e?.message || '未知错误'))
  } finally {
    resetting.value = false
  }
}

function handleRefresh() {
  loadConfig()
}
</script>

<style lang="scss" scoped>
.rag-config-page {
  max-width: 1200px;
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: $spacing-lg;
  margin-top: $spacing-lg;
}

@media (max-width: 900px) {
  .config-grid {
    grid-template-columns: 1fr;
  }
}

.app-card {
  padding: $spacing-lg;
}

.card-title {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  font-size: $font-size-base;
  font-weight: 600;
  color: $color-text-primary;
  margin: 0 0 $spacing-xs 0;
}

.card-desc {
  font-size: $font-size-sm;
  color: $color-text-tertiary;
  margin: 0 0 $spacing-md 0;
}

.slider-row {
  width: 100%;
}

.form-hint {
  display: block;
  font-size: $font-size-xs;
  color: $color-text-tertiary;
  margin-top: $spacing-xs;
}

.action-bar {
  display: flex;
  gap: $spacing-md;
  margin-top: $spacing-xl;
  padding-top: $spacing-lg;
  border-top: 1px solid $color-border;
}
</style>
