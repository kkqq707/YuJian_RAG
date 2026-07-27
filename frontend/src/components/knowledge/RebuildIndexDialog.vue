<template>
  <el-dialog
    v-model="visible"
    title="重建全部索引"
    width="520px"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    @closed="handleClosed"
  >
    <!-- 风险说明 -->
    <div class="rebuild-warning">
      <el-alert type="warning" :closable="false" show-icon>
        <template #title>危险操作</template>
        <template #default>
          <ul class="warning-list">
            <li>重建索引将清空现有向量库并重新处理所有知识文件。</li>
            <li>处理过程中问答服务可能暂时不可用。</li>
            <li>根据文件数量，此操作可能需要数分钟。</li>
            <li>此操作不可中途取消。</li>
          </ul>
        </template>
      </el-alert>
    </div>

    <!-- 确认输入 -->
    <div class="confirm-input-section">
      <p class="confirm-label">
        请输入 <strong>REBUILD</strong> 以确认重建全部索引：
      </p>
      <el-input
        v-model="confirmText"
        placeholder="请输入 REBUILD"
        :disabled="rebuilding"
        @keyup.enter="handleConfirm"
      />
    </div>

    <!-- 进度状态 -->
    <div v-if="rebuilding" class="rebuild-progress">
      <el-alert type="info" :closable="false" show-icon>
        <template #title>正在重建索引，请稍候...</template>
      </el-alert>
    </div>

    <!-- 结果 -->
    <div v-if="result" class="rebuild-result">
      <el-alert
        :type="result.success ? 'success' : 'error'"
        :closable="false"
        show-icon
      >
        <template #title>
          {{ result.success ? '重建完成' : '重建失败' }}
        </template>
        <template v-if="result.success" #default>
          共生成 <strong>{{ result.total_chunks }}</strong> 个知识片段，
          耗时 <strong>{{ result.elapsed_seconds?.toFixed(1) }}</strong> 秒。
        </template>
      </el-alert>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleCancel" :disabled="rebuilding">取消</el-button>
        <el-button
          type="danger"
          :loading="rebuilding"
          :disabled="confirmText !== 'REBUILD'"
          @click="handleConfirm"
        >
          {{ rebuilding ? '重建中...' : '确认重建' }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useKnowledgeStore } from '@/stores/knowledge'
import { extractErrorMessage } from '@/utils/error'
import type { RebuildIndexResponse } from '@/types/api'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  rebuilt: [result: RebuildIndexResponse]
}>()

const knowledgeStore = useKnowledgeStore()

const visible = ref(props.modelValue)
const confirmText = ref('')
const rebuilding = ref(false)
const result = ref<RebuildIndexResponse | null>(null)

watch(() => props.modelValue, (val) => {
  visible.value = val
})
watch(visible, (val) => {
  emit('update:modelValue', val)
})

async function handleConfirm(): Promise<void> {
  if (confirmText.value !== 'REBUILD') return
  if (rebuilding.value) return

  rebuilding.value = true
  result.value = null

  try {
    const res = await knowledgeStore.rebuildIndex()
    result.value = res
    if (res.success) {
      ElMessage.success('索引重建完成')
      emit('rebuilt', res)
    } else {
      ElMessage.error(res.message || '重建失败')
    }
  } catch (err: unknown) {
    ElMessage.error(extractErrorMessage(err))
  } finally {
    rebuilding.value = false
  }
}

function handleCancel(): void {
  visible.value = false
}

function handleClosed(): void {
  confirmText.value = ''
  result.value = null
  rebuilding.value = false
}
</script>

<style lang="scss" scoped>
.rebuild-warning {
  margin-bottom: $spacing-lg;
}

.warning-list {
  margin: 0;
  padding-left: 20px;
  font-size: $font-size-sm;
  color: $color-text-secondary;

  li {
    margin-top: 4px;
  }
}

.confirm-input-section {
  margin-bottom: $spacing-lg;
}

.confirm-label {
  font-size: $font-size-sm;
  color: $color-text-secondary;
  margin-bottom: $spacing-sm;

  strong {
    color: $color-danger;
    font-family: 'SF Mono', Monaco, monospace;
  }
}

.rebuild-progress,
.rebuild-result {
  margin-bottom: $spacing-md;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: $spacing-sm;
}
</style>
