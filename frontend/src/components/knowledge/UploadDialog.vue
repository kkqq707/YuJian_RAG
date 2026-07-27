<template>
  <el-dialog
    v-model="visible"
    title="上传知识文件"
    width="640px"
    :close-on-click-modal="false"
    @closed="handleClosed"
  >
    <!-- 上传区域 -->
    <el-upload
      ref="uploadRef"
      class="upload-area"
      drag
      multiple
      :auto-upload="false"
      :limit="10"
      :accept="allowedExtensions.join(',')"
      :on-change="handleFileChange"
      :on-remove="handleFileRemove"
      :on-exceed="handleExceed"
      :file-list="fileList"
    >
      <el-icon class="upload-icon"><UploadFilled /></el-icon>
      <div class="upload-text">
        <p class="upload-primary">将文件拖到此处，或 <em>点击选择</em></p>
        <p class="upload-secondary">
          支持 txt、md、pdf、docx、xlsx，单文件最大 20MB，一次最多 10 个文件
        </p>
      </div>
    </el-upload>

    <!-- 上传进度 -->
    <div v-if="uploading" class="upload-progress">
      <el-progress :percentage="progressPercent" :status="progressStatus" />
      <p class="progress-text">{{ progressText }}</p>
      <div class="progress-stages">
        <div
          v-for="stage in uploadStages"
          :key="stage.key"
          class="stage-item"
          :class="{ active: stage.active, done: stage.done }"
        >
          <el-icon v-if="stage.done" class="stage-icon done"><CircleCheckFilled /></el-icon>
          <el-icon v-else-if="stage.active" class="stage-icon active"><Loading /></el-icon>
          <el-icon v-else class="stage-icon pending"><Clock /></el-icon>
          <span class="stage-label">{{ stage.label }}</span>
        </div>
      </div>
    </div>

    <!-- 上传结果摘要 -->
    <div v-if="uploadResult" class="upload-result">
      <el-alert
        :type="uploadResult.failed === 0 ? 'success' : 'warning'"
        :closable="false"
        show-icon
      >
        <template #title>
          成功 {{ uploadResult.succeeded }} 个
          <template v-if="(uploadResult.skipped || 0) > 0">，跳过 {{ uploadResult.skipped }} 个（已存在）</template>
          <template v-if="uploadResult.failed > 0">，失败 {{ uploadResult.failed }} 个</template>
        </template>
      </el-alert>
      <ul v-if="uploadResult.results?.length" class="result-list">
        <li
          v-for="(item, index) in uploadResult.results"
          :key="index"
          :class="item.success ? 'result-ok' : 'result-fail'"
        >
          <span class="result-name">{{ item.filename }}</span>
          <span v-if="item.skipped" class="result-tag skip" :title="item.error || ''">
            已存在 — {{ item.error || '文件内容相同' }}
          </span>
          <span v-else-if="item.success" class="result-tag ok">
            成功{{ item.version ? ' (' + item.version + ')' : '' }}
          </span>
          <span v-else class="result-tag fail" :title="item.error || ''">
            失败 — {{ item.error || '未知错误' }}
          </span>
        </li>
      </ul>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleCancel" :disabled="uploading">取消</el-button>
        <el-button
          type="primary"
          :loading="uploading"
          :disabled="fileList.length === 0"
          @click="handleUpload"
        >
          {{ uploading ? '上传中...' : `开始上传 (${fileList.length})` }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import type { UploadInstance, UploadFile, UploadRawFile } from 'element-plus'
import { UploadFilled, CircleCheckFilled, Loading, Clock } from '@element-plus/icons-vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import type { FileUploadResponse } from '@/types/api'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  uploaded: [result: FileUploadResponse]
}>()

const allowedExtensions = ['.txt', '.md', '.pdf', '.docx', '.xlsx']
const maxFileSize = 20 * 1024 * 1024 // 20MB
const maxFileCount = 10

const knowledgeStore = useKnowledgeStore()

const visible = ref(props.modelValue)
const uploadRef = ref<UploadInstance>()
const fileList = ref<UploadFile[]>([])
const uploading = ref(false)
const uploadResult = ref<FileUploadResponse | null>(null)
const progressPercent = ref(0)
const progressStatus = ref<'success' | 'exception' | 'warning' | undefined>()

interface UploadStage {
  key: string
  label: string
  active: boolean
  done: boolean
}

const uploadStages = ref<UploadStage[]>([
  { key: 'upload', label: '上传中', active: false, done: false },
  { key: 'parse', label: '保存中', active: false, done: false },
  { key: 'done', label: '完成', active: false, done: false },
])

function advanceStage(stageKey: string): void {
  const stages = uploadStages.value
  for (const s of stages) {
    if (s.key === stageKey) {
      s.active = true
      s.done = false
    } else if (stages.indexOf(s) < stages.findIndex((x) => x.key === stageKey)) {
      s.active = false
      s.done = true
    } else {
      s.active = false
      s.done = false
    }
  }
}

import { watch } from 'vue'
watch(() => props.modelValue, (val) => {
  visible.value = val
})
watch(visible, (val) => {
  emit('update:modelValue', val)
})

const progressText = computed(() => {
  const activeStage = uploadStages.value.find((s) => s.active)
  if (activeStage) return activeStage.label + '...'
  return ''
})

function handleFileChange(file: UploadFile, fileListNew: UploadFile[]): void {
  // 校验扩展名
  const ext = '.' + (file.name || '').split('.').pop()?.toLowerCase()
  if (!allowedExtensions.includes(ext)) {
    ElMessage.error(`不支持的文件类型: ${file.name}，仅支持 txt、md、pdf、docx`)
    fileListNew.splice(fileListNew.indexOf(file), 1)
    return
  }

  // 校验大小
  const raw = file.raw as UploadRawFile
  if (raw && raw.size > maxFileSize) {
    ElMessage.error(`文件过大: ${file.name}，单文件最大 20MB`)
    fileListNew.splice(fileListNew.indexOf(file), 1)
    return
  }

  fileList.value = fileListNew
}

function handleFileRemove(): void {
  // fileList 由 el-upload 自动更新
}

function handleExceed(): void {
  ElMessage.warning(`一次最多上传 ${maxFileCount} 个文件`)
}

async function handleUpload(): Promise<void> {
  if (fileList.value.length === 0) {
    ElMessage.warning('请选择要上传的文件')
    return
  }

  uploading.value = true
  uploadResult.value = null
  progressPercent.value = 10

  // 重置阶段
  uploadStages.value.forEach((s) => { s.active = false; s.done = false })

  try {
    const rawFiles: File[] = []
    for (const f of fileList.value) {
      if (f.raw) {
        rawFiles.push(f.raw)
      }
    }

    if (rawFiles.length === 0) {
      ElMessage.warning('没有可上传的文件')
      uploading.value = false
      return
    }

    // Stage 1: 上传中
    advanceStage('upload')
    progressPercent.value = 30

    // API 调用（上传 + 保存，索引在后台异步执行）
    const result = await knowledgeStore.uploadFiles(rawFiles)

    // Stage 2: 保存中
    advanceStage('parse')
    progressPercent.value = 75

    // Stage 3: 完成（索引将在后台执行）
    advanceStage('done')
    progressPercent.value = 100
    progressStatus.value = result.failed === 0 ? 'success' : 'warning'
    uploadResult.value = result

    if (result.failed === 0) {
      ElMessage.success(`上传成功: ${result.succeeded} 个文件`)
    } else {
      ElMessage.warning(`上传完成: 成功 ${result.succeeded} 个，失败 ${result.failed} 个`)
    }

    emit('uploaded', result)
  } catch (err: unknown) {
    progressStatus.value = 'exception'
    const msg = err instanceof Error ? err.message : '上传失败'
    ElMessage.error(msg)
    // 标记当前活跃阶段失败
    const activeStage = uploadStages.value.find((s) => s.active)
    if (activeStage) {
      activeStage.active = false
    }
  } finally {
    uploading.value = false
  }
}

function handleCancel(): void {
  visible.value = false
}

function handleClosed(): void {
  fileList.value = []
  uploadResult.value = null
  progressPercent.value = 0
  progressStatus.value = undefined
  uploading.value = false
  uploadStages.value.forEach((s) => { s.active = false; s.done = false })
}
</script>

<style lang="scss" scoped>
.upload-area {
  width: 100%;
}

.upload-icon {
  font-size: 40px;
  color: $color-text-tertiary;
  margin-bottom: $spacing-sm;
}

.upload-text {
  text-align: center;
}

.upload-primary {
  font-size: $font-size-base;
  color: $color-text-primary;
  em {
    color: $color-primary;
    font-style: normal;
    cursor: pointer;
  }
}

.upload-secondary {
  font-size: $font-size-xs;
  color: $color-text-tertiary;
  margin-top: $spacing-xs;
}

.upload-progress {
  margin-top: $spacing-lg;
  .progress-text {
    font-size: $font-size-sm;
    color: $color-text-secondary;
    text-align: center;
    margin-top: $spacing-sm;
  }
}

.upload-result {
  margin-top: $spacing-lg;
}

.result-list {
  list-style: none;
  padding: 0;
  margin: $spacing-sm 0 0;
  max-height: 200px;
  overflow-y: auto;
}

.result-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: $spacing-xs $spacing-sm;
  font-size: $font-size-sm;
  border-radius: 4px;

  + li { margin-top: 2px; }

  &.result-ok { background: #f0fdf4; }
  &.result-fail { background: #fef2f2; }
}

.result-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-right: $spacing-sm;
}

.result-tag {
  flex-shrink: 0;
  font-size: $font-size-xs;
  padding: 1px 8px;
  border-radius: 4px;

  &.ok { color: $color-success; }
  &.skip { color: $color-warning; }
  &.fail { color: $color-danger; }
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: $spacing-sm;
}

.progress-stages {
  display: flex;
  justify-content: space-between;
  margin-top: $spacing-md;
  padding: 0 $spacing-sm;
}

.stage-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  opacity: 0.4;
  transition: opacity 0.3s;

  &.active {
    opacity: 1;
  }

  &.done {
    opacity: 0.8;
  }
}

.stage-icon {
  font-size: 20px;

  &.done {
    color: $color-success;
  }

  &.active {
    color: $color-primary;
    animation: spin 1s linear infinite;
  }

  &.pending {
    color: $color-text-tertiary;
  }
}

.stage-label {
  font-size: $font-size-xs;
  color: $color-text-secondary;
  white-space: nowrap;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
