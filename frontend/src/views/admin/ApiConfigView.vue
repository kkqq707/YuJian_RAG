<template>
  <div class="api-config-page">
    <!-- 页面标题 -->
    <PageHeader
      title="AI 服务配置"
      description="配置企业 AI 模型服务，支持 OpenAI 兼容接口。修改后立即生效，无需重启服务。"
    />

    <div class="config-grid">
      <!-- 当前配置卡片 -->
      <el-card class="config-card" shadow="never">
        <template #header>
          <div class="card-header">
            <el-icon><InfoFilled /></el-icon>
            <span>当前 LLM 配置</span>
            <el-tag v-if="config.configured" type="success" size="small" class="status-tag">
              已配置
            </el-tag>
            <el-tag v-else type="info" size="small" class="status-tag">
              未配置
            </el-tag>
          </div>
        </template>

        <el-descriptions v-if="config.configured" :column="1" border>
          <el-descriptions-item label="服务商">
            {{ config.provider || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="接口地址">
            <span class="mono-text">{{ config.base_url || '-' }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="模型">
            <el-tag type="primary" size="small">{{ config.model || '-' }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="API Key">
            <span class="mono-text">{{ config.api_key_masked || '未设置' }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-switch
              :model-value="config.enabled"
              disabled
              active-text="已启用"
              inactive-text="已禁用"
            />
          </el-descriptions-item>
        </el-descriptions>

        <el-empty
          v-else
          description="尚未配置 AI 模型服务"
          :image-size="80"
        >
          <template #description>
            <p class="empty-hint">
              请在下方的编辑区域填写 API 配置，或确保 .env 文件中已配置环境变量。
            </p>
          </template>
        </el-empty>
      </el-card>

      <!-- 编辑配置卡片 -->
      <el-card class="config-card" shadow="never">
        <template #header>
          <div class="card-header">
            <el-icon><Edit /></el-icon>
            <span>编辑配置</span>
          </div>
        </template>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-position="top"
          class="config-form"
        >
          <el-form-item label="服务商" prop="provider">
            <el-select v-model="form.provider" class="full-width">
              <el-option
                label="OpenAI 兼容"
                value="openai-compatible"
              />
              <el-option
                label="DeepSeek"
                value="deepseek"
              />
              <el-option
                label="OpenAI"
                value="openai"
              />
            </el-select>
          </el-form-item>

          <el-form-item label="接口地址 (Base URL)" prop="base_url">
            <el-input
              v-model="form.base_url"
              placeholder="例如: https://api.deepseek.com/v1"
              clearable
            />
            <template #extra>
              <span class="form-hint">
                请输入完整的 API 地址，包含 https:// 和版本路径（如 /v1）
              </span>
            </template>
          </el-form-item>

          <el-form-item label="API Key" prop="api_key">
            <el-input
              v-model="form.api_key"
              type="password"
              show-password
              placeholder="输入 API Key（以 sk- 开头）"
              autocomplete="new-password"
            />
            <template #extra>
              <span class="form-hint">
                API Key 将使用 AES-256 加密存储，不会以明文形式保存
              </span>
            </template>
          </el-form-item>

          <el-form-item label="模型" prop="model">
            <el-select
              v-model="form.model"
              class="full-width"
              filterable
              allow-create
              placeholder="选择或输入模型名称"
              :loading="modelsLoading"
            >
              <el-option
                v-for="m in availableModels"
                :key="m.name"
                :label="`${m.name} (${m.provider})`"
                :value="m.name"
              />
            </el-select>
            <template #extra>
              <span class="form-hint">
                支持自定义模型名称，输入后按回车确认
              </span>
            </template>
          </el-form-item>

          <el-form-item label="启用">
            <el-switch
              v-model="form.enabled"
              active-text="启用此配置"
              inactive-text="禁用"
            />
          </el-form-item>
        </el-form>

        <!-- 操作按钮 -->
        <div class="form-actions">
          <el-button
            type="primary"
            :loading="saving"
            :icon="Check"
            @click="handleSave"
          >
            保存配置
          </el-button>

          <el-button
            :loading="testing"
            :icon="Connection"
            @click="handleTestConnection"
          >
            测试连接
          </el-button>

          <el-button
            :icon="RefreshLeft"
            @click="handleReset"
          >
            恢复默认
          </el-button>
        </div>

        <!-- 测试结果 -->
        <div v-if="testResult !== null" class="test-result">
          <el-alert
            :type="testResult.success ? 'success' : 'error'"
            :closable="true"
            show-icon
            @close="testResult = null"
          >
            <template #title>
              <template v-if="testResult.success">
                连接成功！模型: {{ testResult.model }}，延迟: {{ testResult.latency_ms }}ms
              </template>
              <template v-else>
                连接失败: {{ testResult.error }}
              </template>
            </template>
            <template v-if="testResult.success && testResult.response_preview">
              <p class="response-preview">
                响应预览: {{ testResult.response_preview }}
              </p>
            </template>
          </el-alert>
        </div>
      </el-card>

      <!-- 安全状态卡片 -->
      <el-card class="config-card" shadow="never">
        <template #header>
          <div class="card-header">
            <el-icon><Lock /></el-icon>
            <span>安全状态</span>
          </div>
        </template>

        <el-descriptions :column="2" border>
          <el-descriptions-item label="JWT 密钥">
            <el-tag :type="security.jwt_initialized ? 'success' : 'danger'" size="small">
              {{ security.jwt_initialized ? '已初始化' : '未初始化' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="加密密钥">
            <el-tag :type="security.encryption_configured ? 'success' : 'danger'" size="small">
              {{ security.encryption_configured ? '已就绪' : '未配置' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="LLM 配置">
            <el-tag :type="security.llm_configured ? 'success' : 'info'" size="small">
              {{ security.llm_configured ? '已配置' : '未配置' }}
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>

        <el-alert
          type="warning"
          :closable="false"
          show-icon
          class="security-notice"
        >
          <template #title>
            安全提示
          </template>
          <p>
            JWT 密钥和 API Key 均以加密形式存储在数据库中。
            请勿将加密密钥 <code>CONFIG_ENCRYPTION_KEY</code> 泄露给未授权人员。
          </p>
        </el-alert>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import {
  InfoFilled,
  Edit,
  Check,
  Connection,
  RefreshLeft,
  Lock,
} from '@element-plus/icons-vue'
import PageHeader from '@/components/common/PageHeader.vue'
import {
  getLLMConfig,
  saveLLMConfig,
  testLLMConnection,
  getModels,
  getSecurityStatus,
  type LLMConfigInfo,
  type TestConnectionResponse,
  type ModelItem,
  type SecurityStatus,
} from '@/api/adminApiConfig'

// ---- 表单 ----
const formRef = ref<FormInstance>()
const form = reactive({
  provider: 'openai-compatible',
  base_url: '',
  api_key: '',
  model: '',
  enabled: true,
})

const rules: FormRules = {
  provider: [{ required: true, message: '请选择服务商', trigger: 'blur' }],
  base_url: [
    { required: true, message: '请输入接口地址', trigger: 'blur' },
    {
      pattern: /^https?:\/\/.+/,
      message: '接口地址必须以 http:// 或 https:// 开头',
      trigger: 'blur',
    },
  ],
  model: [{ required: true, message: '请选择或输入模型名称', trigger: 'blur' }],
}

// ---- 状态 ----
const config = ref<LLMConfigInfo>({
  configured: false,
  id: null,
  provider: null,
  base_url: null,
  model: null,
  enabled: false,
  api_key_masked: null,
})

const security = reactive<SecurityStatus>({
  jwt_initialized: false,
  encryption_configured: false,
  llm_configured: false,
})

const saving = ref(false)
const testing = ref(false)
const testResult = ref<TestConnectionResponse | null>(null)
const availableModels = ref<ModelItem[]>([])
const modelsLoading = ref(false)

// ---- 初始化 ----
onMounted(async () => {
  await Promise.all([loadConfig(), loadModels(), loadSecurity()])
})

async function loadConfig(): Promise<void> {
  try {
    const data = await getLLMConfig()
    config.value = data
    // 预填表单（不填 API Key — 需要管理员重新输入）
    if (data.configured) {
      form.provider = data.provider || 'openai-compatible'
      form.base_url = data.base_url || ''
      form.model = data.model || ''
      form.enabled = data.enabled
      // 不清空 api_key 字段，但也不预填
    }
  } catch {
    // 静默处理
  }
}

async function loadModels(): Promise<void> {
  modelsLoading.value = true
  try {
    const data = await getModels()
    if (data.success) {
      availableModels.value = data.models
    }
  } catch {
    // 使用默认模型列表
  } finally {
    modelsLoading.value = false
  }
}

async function loadSecurity(): Promise<void> {
  try {
    const data = await getSecurityStatus()
    Object.assign(security, data)
  } catch {
    // 静默处理
  }
}

// ---- 操作 ----
async function handleSave(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    const result = await saveLLMConfig({
      provider: form.provider,
      base_url: form.base_url,
      api_key: form.api_key,
      model: form.model,
      enabled: form.enabled,
    })
    config.value = result
    ElMessage.success('配置已保存，缓存已刷新')
    // 重新加载安全状态
    await loadSecurity()
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message
    ElMessage.error(msg || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleTestConnection(): Promise<void> {
  const apiKey = form.api_key
  if (!apiKey) {
    ElMessage.warning('请先输入 API Key')
    return
  }
  if (!form.base_url) {
    ElMessage.warning('请先输入接口地址')
    return
  }
  if (!form.model) {
    ElMessage.warning('请先选择或输入模型名称')
    return
  }

  testing.value = true
  testResult.value = null
  try {
    const result = await testLLMConnection({
      base_url: form.base_url,
      api_key: apiKey,
      model: form.model,
    })
    testResult.value = result
    if (result.success) {
      ElMessage.success(`连接成功！延迟: ${result.latency_ms}ms`)
    } else {
      ElMessage.error(result.error || '连接失败')
    }
  } catch (e: unknown) {
    const errMsg = (e as Error).message || '测试请求失败'
    testResult.value = {
      success: false,
      model: form.model,
      latency_ms: 0,
      response_preview: '',
      error: errMsg,
    }
    ElMessage.error(errMsg)
  } finally {
    testing.value = false
  }
}

function handleReset(): void {
  form.provider = 'openai-compatible'
  form.base_url = ''
  form.api_key = ''
  form.model = ''
  form.enabled = true
  testResult.value = null
  formRef.value?.resetFields()
  ElMessage.info('表单已重置')
}
</script>

<style lang="scss" scoped>
.api-config-page {
  width: 100%;
  max-width: 960px;
  margin: 0 auto;
}

.config-grid {
  display: flex;
  flex-direction: column;
  gap: $spacing-lg;
}

.config-card {
  border: 1px solid $color-border;
  border-radius: $border-radius-lg;

  :deep(.el-card__header) {
    padding: $spacing-md $spacing-lg;
    background: $color-bg-secondary;
    border-bottom: 1px solid $color-border;
  }

  :deep(.el-card__body) {
    padding: $spacing-lg;
  }
}

.card-header {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  font-weight: 600;
  font-size: $font-size-md;
  color: $color-text-primary;
  flex-wrap: wrap;

  .status-tag {
    margin-left: auto;
  }
}

.config-form {
  max-width: 560px;
}

.mono-text {
  font-family: monospace;
  font-size: $font-size-sm;
  color: $color-text-secondary;
  word-break: break-all;
}

.form-hint {
  font-size: $font-size-xs;
  color: $color-text-tertiary;
  word-break: break-word;
}

.form-actions {
  display: flex;
  gap: $spacing-md;
  margin-top: $spacing-lg;
  flex-wrap: wrap;
}

.test-result {
  margin-top: $spacing-lg;

  .response-preview {
    margin: $spacing-sm 0 0;
    font-family: monospace;
    font-size: $font-size-sm;
    color: $color-text-secondary;
    word-break: break-all;
  }
}

.security-notice {
  margin-top: $spacing-md;

  p {
    margin: $spacing-xs 0 0;
    font-size: $font-size-sm;
    color: $color-text-secondary;
    word-break: break-word;

    code {
      background: $color-bg-tertiary;
      padding: 1px 4px;
      border-radius: 2px;
      font-size: $font-size-xs;
    }
  }
}

.full-width {
  width: 100%;
}

.empty-hint {
  color: $color-text-tertiary;
  font-size: $font-size-sm;
}

// ---- 移动端适配 ----
@media (max-width: 767px) {
  .config-card {
    :deep(.el-card__header) {
      padding: $spacing-sm $spacing-md;
    }

    :deep(.el-card__body) {
      padding: $spacing-md;
    }
  }

  .config-form {
    max-width: 100%;
  }

  .form-actions {
    flex-direction: column;

    .el-button {
      width: 100%;
      min-height: var(--touch-target-min);
    }
  }
}
</style>
