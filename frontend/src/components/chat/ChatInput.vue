<template>
  <div class="chat-input">
    <div class="chat-input__wrapper">
      <el-input
        ref="textareaRef"
        v-model="inputText"
        type="textarea"
        :rows="textareaRows"
        :maxlength="maxLength"
        :disabled="disabled"
        :placeholder="isMobile ? '请输入问题…' : '请输入您的问题…'"
        resize="none"
        aria-label="输入问题"
        @keydown="handleKeydown"
        @input="handleInput"
      />
      <div class="chat-input__footer">
        <span class="chat-input__hint">
          回答基于企业内部知识库生成，请以正式文件为准。
        </span>
        <el-button
          type="primary"
          :disabled="!canSend || disabled"
          :loading="sending"
          class="chat-input__send-btn touch-target"
          :aria-label="sending ? '正在发送' : '发送消息'"
          @click="handleSend"
        >
          <span class="chat-input__send-text">发送</span>
          <Send :size="18" class="chat-input__send-icon" />
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Send } from '@lucide/vue'

const props = withDefaults(defineProps<{
  sending?: boolean
  disabled?: boolean
  maxLength?: number
  isMobile?: boolean
}>(), {
  sending: false,
  disabled: false,
  maxLength: 2000,
  isMobile: false,
})

const emit = defineEmits<{
  send: [question: string]
}>()

const inputText = ref('')
const textareaRef = ref<InstanceType<typeof import('element-plus').ElInput>>()

const textareaRows = ref(1)
const maxRows = props.isMobile ? 4 : 6

const canSend = computed(() => {
  return inputText.value.trim().length > 0 && !props.sending && !props.disabled
})

function handleKeydown(event: Event | KeyboardEvent) {
  const e = event as KeyboardEvent
  // Enter 发送（不含 Shift），移动端 Enter 也发送（保持项目现有行为）
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
  // Ctrl+Enter 也发送
  if (e.key === 'Enter' && e.ctrlKey) {
    e.preventDefault()
    handleSend()
  }
}

function handleInput() {
  nextTick(() => {
    const el = textareaRef.value?.$el?.querySelector('textarea') as HTMLTextAreaElement | null
    if (el) {
      el.style.height = 'auto'
      const lineHeight = 24
      const minHeight = lineHeight + 16
      const maxHeight = lineHeight * maxRows + 16
      const scrollHeight = el.scrollHeight
      el.style.height = Math.min(Math.max(scrollHeight, minHeight), maxHeight) + 'px'

      const newRows = Math.min(Math.ceil((scrollHeight - 16) / lineHeight), maxRows)
      textareaRows.value = Math.max(1, newRows)
    }
  })

  if (inputText.value.length >= props.maxLength) {
    ElMessage.warning(`问题长度不能超过 ${props.maxLength} 个字符`)
  }
}

function handleSend() {
  if (!canSend.value) return
  const question = inputText.value.trim()
  if (!question) return

  if (question.length > props.maxLength) {
    ElMessage.warning(`问题长度不能超过 ${props.maxLength} 个字符`)
    return
  }

  emit('send', question)
  inputText.value = ''
  textareaRows.value = 1

  nextTick(() => {
    const el = textareaRef.value?.$el?.querySelector('textarea') as HTMLTextAreaElement | null
    if (el) {
      el.style.height = 'auto'
    }
  })
}

function clear(): void {
  inputText.value = ''
  textareaRows.value = 1
}

defineExpose({ clear })
</script>

<style lang="scss" scoped>
.chat-input {
  padding: $spacing-md 0;
}

.chat-input__wrapper {
  background: $color-card-bg;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(16, 24, 40, 0.06);
  padding: $spacing-md;

  :deep(.el-textarea__inner) {
    border: none !important;
    box-shadow: none !important;
    background: transparent;
    font-size: $font-size-base;
    line-height: 1.6;
    padding: 4px 0;
    min-height: 28px;
    max-height: 160px;
    overflow-wrap: anywhere;
    word-break: break-word;

    &:focus {
      box-shadow: none !important;
    }
  }
}

.chat-input__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: $spacing-sm;
  padding-top: $spacing-sm;
  border-top: 1px solid $color-border;
  gap: $spacing-sm;
}

.chat-input__hint {
  font-size: $font-size-xs;
  color: $color-text-tertiary;
  flex: 1;
  min-width: 0;
  overflow-wrap: anywhere;
}

.chat-input__send-btn {
  flex-shrink: 0;
}

.chat-input__send-icon {
  display: none;
}

:deep(.el-button--primary) {
  --el-button-bg-color: #{$color-primary};
  --el-button-border-color: #{$color-primary};
  --el-button-hover-bg-color: #{$color-primary-hover};
  --el-button-hover-border-color: #{$color-primary-hover};
}

// ================================================================
// 移动端适配 (< 768px)
// ================================================================
@media (max-width: 767px) {
  .chat-input {
    padding: $spacing-sm 0;
  }

  .chat-input__wrapper {
    padding: $spacing-sm;
    border-radius: 10px;
  }

  .chat-input__hint {
    font-size: 11px;
    line-height: 1.4;
  }

  .chat-input__send-text {
    display: none;
  }

  .chat-input__send-icon {
    display: block;
  }

  .chat-input__send-btn {
    min-width: var(--touch-target-min);
    min-height: var(--touch-target-min);
    padding: 0;
    border-radius: 50%;

    :deep(.el-icon) {
      margin: 0;
    }
  }

  :deep(.el-textarea__inner) {
    font-size: 16px; // 防止 iOS 缩放
  }
}
</style>
