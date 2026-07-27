<template>
  <div class="settings-page">
    <PageHeader title="系统设置" description="配置系统参数和高级选项" />

    <!-- 1. 系统信息 -->
    <div class="section">
      <h3 class="section-title">
        <el-icon><InfoFilled /></el-icon>
        系统信息
      </h3>
      <div class="app-card">
        <div v-if="infoLoading">
          <LoadingBlock variant="skeleton" :lines="5" />
        </div>
        <el-descriptions v-else :column="2" border>
          <el-descriptions-item label="系统名称">{{ sysInfo.app_name }}</el-descriptions-item>
          <el-descriptions-item label="版本">{{ sysInfo.version }}</el-descriptions-item>
          <el-descriptions-item label="部署模式">{{ sysInfo.deploy_mode }}</el-descriptions-item>
          <el-descriptions-item label="数据库">{{ sysInfo.database_type }}</el-descriptions-item>
          <el-descriptions-item label="向量库">{{ sysInfo.vector_store }}</el-descriptions-item>
          <el-descriptions-item label="LLM 模型">{{ sysInfo.model_name || '未配置' }}</el-descriptions-item>
        </el-descriptions>
      </div>
    </div>

    <!-- 2. 安全设置 -->
    <div class="section">
      <h3 class="section-title">
        <el-icon><Lock /></el-icon>
        安全设置
      </h3>
      <div class="app-card">
        <div v-if="secLoading">
          <LoadingBlock variant="skeleton" :lines="4" />
        </div>
        <div v-else class="security-content">
          <div class="setting-row">
            <div class="setting-info">
              <span class="setting-label">JWT 状态</span>
              <span class="setting-desc">JSON Web Token 签名密钥状态</span>
            </div>
            <StatusBadge :status="secInfo.jwt_initialized ? 'ok' : 'error'" />
          </div>
          <el-divider />
          <div class="setting-row">
            <div class="setting-info">
              <span class="setting-label">Token 有效期</span>
              <span class="setting-desc">Access Token 过期时间（分钟）</span>
            </div>
            <span class="setting-value">{{ secInfo.access_token_expire_minutes }} 分钟</span>
          </div>
          <el-divider />
          <div class="setting-row">
            <div class="setting-info">
              <span class="setting-label">Refresh Token 有效期</span>
              <span class="setting-desc">Refresh Token 过期时间（天）</span>
            </div>
            <span class="setting-value">{{ secInfo.refresh_token_expire_days }} 天</span>
          </div>
          <el-divider />
          <div class="setting-row">
            <div class="setting-info">
              <span class="setting-label">加密密钥</span>
              <span class="setting-desc">配置加密主密钥状态</span>
            </div>
            <StatusBadge :status="secInfo.encryption_configured ? 'ok' : 'error'" />
          </div>
          <el-divider />
          <div class="setting-action">
            <div class="setting-info">
              <span class="setting-label">重新生成 JWT 密钥</span>
              <span class="setting-desc">重新生成后所有用户需要重新登录</span>
            </div>
            <el-button type="danger" plain @click="showJWTConfirm = true">
              重新生成
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 3. 聊天设置 -->
    <div class="section">
      <h3 class="section-title">
        <el-icon><ChatDotRound /></el-icon>
        聊天设置
      </h3>
      <div class="app-card">
        <el-form label-width="180px" :model="chatForm">
          <el-form-item label="最大上下文长度 (tokens)">
            <el-input-number
              v-model="chatForm.chat_max_context_length"
              :min="500"
              :max="32000"
              :step="500"
            />
            <span class="form-hint">对话中包含的最大 token 数</span>
          </el-form-item>
          <el-form-item label="回答最大长度 (tokens)">
            <el-input-number
              v-model="chatForm.chat_max_answer_length"
              :min="100"
              :max="16000"
              :step="100"
            />
            <span class="form-hint">AI 回答的最大长度限制</span>
          </el-form-item>
          <el-form-item label="历史保存天数">
            <el-input-number
              v-model="chatForm.chat_history_days"
              :min="7"
              :max="365"
              :step="1"
            />
            <span class="form-hint">聊天记录自动清理前的保存天数</span>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="saveChatSettings" :loading="saving">
              保存设置
            </el-button>
          </el-form-item>
        </el-form>
      </div>
    </div>

    <!-- 4. 知识库设置 -->
    <div class="section">
      <h3 class="section-title">
        <el-icon><FolderOpened /></el-icon>
        知识库设置
      </h3>
      <div class="app-card">
        <el-form label-width="180px" :model="kbForm">
          <el-form-item label="Chunk Size">
            <el-input-number
              v-model="kbForm.kb_chunk_size"
              :min="100"
              :max="4000"
              :step="50"
            />
            <span class="form-hint">文档分割时的片段大小</span>
          </el-form-item>
          <el-form-item label="Chunk Overlap">
            <el-input-number
              v-model="kbForm.kb_chunk_overlap"
              :min="0"
              :max="1000"
              :step="10"
            />
            <span class="form-hint">相邻片段之间的重叠字符数</span>
          </el-form-item>
          <el-form-item label="Top K">
            <el-input-number
              v-model="kbForm.kb_top_k"
              :min="1"
              :max="20"
              :step="1"
            />
            <span class="form-hint">检索时返回的最相关片段数</span>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="saveKBSettings" :loading="saving">
              保存设置
            </el-button>
          </el-form-item>
        </el-form>
      </div>
    </div>

    <!-- JWT 重新生成确认 -->
    <el-dialog
      v-model="showJWTConfirm"
      title="确认重新生成 JWT 密钥"
      width="480px"
      :close-on-click-modal="false"
    >
      <el-alert
        title="警告：此操作不可撤销"
        type="error"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      >
        <p>重新生成 JWT 密钥后：</p>
        <ul>
          <li>所有用户的 Access Token 将立即失效</li>
          <li>所有用户的 Refresh Token 将立即失效</li>
          <li>所有用户需要重新登录</li>
        </ul>
      </el-alert>
      <template #footer>
        <el-button @click="showJWTConfirm = false">取消</el-button>
        <el-button type="danger" @click="confirmRegenJWT" :loading="regenLoading">
          确认重新生成
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import adminSystemApi from '@/api/adminSystem'
import type { SystemInfoResponse, SecuritySettingsResponse } from '@/types/api'
import PageHeader from '@/components/common/PageHeader.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import LoadingBlock from '@/components/common/LoadingBlock.vue'
import { extractErrorMessage } from '@/utils/error'

// 系统信息
const infoLoading = ref(true)
const sysInfo = reactive<SystemInfoResponse>({
  success: true,
  app_name: '企业智库 AI',
  version: '--',
  deploy_mode: '单企业版',
  database_type: 'SQLite',
  vector_store: 'Chroma',
  model_name: null,
})

// 安全设置
const secLoading = ref(true)
const secInfo = reactive<SecuritySettingsResponse>({
  success: true,
  jwt_initialized: false,
  jwt_algorithm: 'HS256',
  access_token_expire_minutes: 30,
  refresh_token_expire_days: 7,
  encryption_configured: false,
})

// 表单
const saving = ref(false)
const chatForm = reactive({
  chat_max_context_length: 4000,
  chat_max_answer_length: 2000,
  chat_history_days: 90,
})
const kbForm = reactive({
  kb_chunk_size: 500,
  kb_chunk_overlap: 50,
  kb_top_k: 5,
})

// JWT 确认
const showJWTConfirm = ref(false)
const regenLoading = ref(false)

async function loadSettings() {
  try {
    const result = await adminSystemApi.getSettings()
    const s = result.settings
    if (s.chat_max_context_length) chatForm.chat_max_context_length = parseInt(s.chat_max_context_length)
    if (s.chat_max_answer_length) chatForm.chat_max_answer_length = parseInt(s.chat_max_answer_length)
    if (s.chat_history_days) chatForm.chat_history_days = parseInt(s.chat_history_days)
    if (s.kb_chunk_size) kbForm.kb_chunk_size = parseInt(s.kb_chunk_size)
    if (s.kb_chunk_overlap) kbForm.kb_chunk_overlap = parseInt(s.kb_chunk_overlap)
    if (s.kb_top_k) kbForm.kb_top_k = parseInt(s.kb_top_k)
  } catch {
    // Use defaults
  }
}

async function loadSysInfo() {
  infoLoading.value = true
  try {
    const result = await adminSystemApi.getSystemInfo()
    Object.assign(sysInfo, result)
  } catch {
    // Use defaults
  } finally {
    infoLoading.value = false
  }
}

async function loadSecurity() {
  secLoading.value = true
  try {
    const result = await adminSystemApi.getSecuritySettings()
    Object.assign(secInfo, result)
  } catch {
    // Use defaults
  } finally {
    secLoading.value = false
  }
}

async function saveChatSettings() {
  saving.value = true
  try {
    await adminSystemApi.saveSettings({
      chat_max_context_length: String(chatForm.chat_max_context_length),
      chat_max_answer_length: String(chatForm.chat_max_answer_length),
      chat_history_days: String(chatForm.chat_history_days),
    })
    ElMessage.success('聊天设置已保存并生效')
  } catch (err: unknown) {
    ElMessage.error(extractErrorMessage(err))
  } finally {
    saving.value = false
  }
}

async function saveKBSettings() {
  saving.value = true
  try {
    await adminSystemApi.saveSettings({
      kb_chunk_size: String(kbForm.kb_chunk_size),
      kb_chunk_overlap: String(kbForm.kb_chunk_overlap),
      kb_top_k: String(kbForm.kb_top_k),
    })
    ElMessage.success('知识库设置已保存并生效')
  } catch (err: unknown) {
    ElMessage.error(extractErrorMessage(err))
  } finally {
    saving.value = false
  }
}

async function confirmRegenJWT() {
  regenLoading.value = true
  try {
    const result = await adminSystemApi.regenerateJWT()
    showJWTConfirm.value = false
    ElMessage.warning(result.message)
    // 刷新安全状态
    await loadSecurity()
  } catch (err: unknown) {
    ElMessage.error(extractErrorMessage(err))
  } finally {
    regenLoading.value = false
  }
}

onMounted(() => {
  loadSysInfo()
  loadSecurity()
  loadSettings()
})
</script>

<style lang="scss" scoped>
.settings-page {
  max-width: 1440px;
}

.section {
  margin-bottom: $spacing-xl;
}

.section-title {
  font-size: $font-size-base;
  font-weight: 600;
  color: $color-text-primary;
  margin-bottom: $spacing-md;
  display: flex;
  align-items: center;
  gap: $spacing-sm;
}

.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: $spacing-sm 0;
}

.setting-action {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: $spacing-sm 0;
}

.setting-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.setting-label {
  font-size: $font-size-sm;
  font-weight: 500;
  color: $color-text-primary;
}

.setting-desc {
  font-size: $font-size-xs;
  color: $color-text-tertiary;
}

.setting-value {
  font-size: $font-size-sm;
  font-weight: 500;
  color: $color-text-primary;
}

.security-content {
  .el-divider {
    margin: $spacing-xs 0;
  }
}

.form-hint {
  margin-left: $spacing-sm;
  font-size: $font-size-xs;
  color: $color-text-tertiary;
}
</style>
