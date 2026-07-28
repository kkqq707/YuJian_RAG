<template>
  <div
    class="chat-message"
    :class="[
      `chat-message--${message.role}`,
      { 'chat-message--error': message.status === 'error' },
    ]"
  >
    <!-- 助手消息：AI 图标 -->
    <div v-if="message.role === 'assistant'" class="chat-message__avatar">
      <div class="chat-message__avatar-icon">
        <Sparkles :size="isMobile ? 16 : 18" />
      </div>
    </div>

    <div class="chat-message__body">
      <!-- 消息内容 -->
      <div class="chat-message__content">
        <!-- 加载状态 -->
        <template v-if="message.status === 'sending' && !message.content">
          <div class="chat-message__loading">
            <span class="loading-dot" />
            <span class="loading-dot" />
            <span class="loading-dot" />
            <span class="loading-text">正在思考…</span>
          </div>
        </template>

        <!-- 错误状态 -->
        <template v-else-if="message.status === 'error'">
          <div class="chat-message__error">
            <AlertCircle :size="16" />
            <span>{{ message.errorMessage || '回答生成失败' }}</span>
            <el-button size="small" text type="primary" @click="$emit('retry')">
              重试
            </el-button>
          </div>
        </template>

        <!-- 正常内容：Markdown 渲染 -->
        <template v-else>
          <MarkdownRenderer :content="message.content" />
        </template>
      </div>

      <!-- 底部信息栏（仅助手消息） -->
      <div
        v-if="message.role === 'assistant' && message.status === 'success'"
        class="chat-message__footer"
      >
        <span v-if="message.latencySeconds != null" class="chat-message__latency">
          耗时 {{ message.latencySeconds.toFixed(1) }}s
        </span>
        <div class="chat-message__actions">
          <el-button size="small" text class="touch-target-min" aria-label="复制回答" @click="handleCopy">
            <Copy :size="14" />
            <span>{{ isMobile ? '' : '复制' }}</span>
          </el-button>
          <el-button
            size="small"
            text
            class="touch-target-min"
            aria-label="重新生成"
            :disabled="sending"
            @click="$emit('regenerate')"
          >
            <RefreshCw :size="14" />
            <span>{{ isMobile ? '' : '重新生成' }}</span>
          </el-button>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { Sparkles, AlertCircle, Copy, RefreshCw } from '@lucide/vue'
import MarkdownRenderer from './MarkdownRenderer.vue'
import type { ChatMessage as ChatMessageType } from '@/types/chat'

const props = defineProps<{
  message: ChatMessageType
  sending?: boolean
  isMobile?: boolean
}>()

defineEmits<{
  retry: []
  regenerate: []
}>()

async function handleCopy() {
  try {
    await navigator.clipboard.writeText(props.message.content)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.warning('复制失败，请手动选择文本复制')
  }
}
</script>

<style lang="scss" scoped>
.chat-message {
  display: flex;
  gap: $spacing-sm;
  margin-bottom: $spacing-lg;
  animation: msgFadeIn 0.3s ease;

  &--user {
    flex-direction: row-reverse;
    justify-content: flex-start;

    .chat-message__content {
      background: #EFF6FF;
      border-radius: 12px;
      border-bottom-right-radius: 4px;
      max-width: 70%;
      padding: 12px 16px;
      overflow-wrap: anywhere;
      word-break: break-word;
    }
  }

  &--assistant {
    .chat-message__content {
      background: $color-card-bg;
      border-radius: 12px;
      border-bottom-left-radius: 4px;
      max-width: 90%;
      padding: 16px 20px;
      box-shadow: $shadow-card;
      overflow-wrap: anywhere;
      word-break: break-word;
    }
  }

  &--error {
    .chat-message__content {
      border: 1px solid #fecaca;
      background: #fef2f2;
    }
  }
}

.chat-message__avatar {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
}

.chat-message__avatar-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: $color-primary-light;
  color: $color-primary;
  display: flex;
  align-items: center;
  justify-content: center;
}

.chat-message__body {
  min-width: 0;
  flex: 1;

  .chat-message--user & {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
  }
}

.chat-message__content {
  font-size: $font-size-base;
  line-height: 1.6;
  color: $color-text-primary;
}

// 加载动画
.chat-message__loading {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 0;

  .loading-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: $color-primary;
    opacity: 0.4;
    animation: dotPulse 1.4s infinite ease-in-out;

    &:nth-child(1) { animation-delay: 0s; }
    &:nth-child(2) { animation-delay: 0.2s; }
    &:nth-child(3) { animation-delay: 0.4s; }
  }

  .loading-text {
    margin-left: 8px;
    font-size: $font-size-sm;
    color: $color-text-tertiary;
  }
}

// 错误状态
.chat-message__error {
  display: flex;
  align-items: center;
  gap: 8px;
  color: $color-danger;
  font-size: $font-size-sm;
  padding: 4px 0;
  flex-wrap: wrap;
  overflow-wrap: anywhere;
}

// 底部信息栏
.chat-message__footer {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  margin-top: 8px;
  flex-wrap: wrap;
}

.chat-message__latency {
  font-size: $font-size-xs;
  color: $color-text-tertiary;
}

.chat-message__actions {
  display: flex;
  align-items: center;
  gap: 4px;

  :deep(.el-button) {
    font-size: $font-size-xs;
    color: $color-text-tertiary;
    padding: 2px 6px;

    &:hover {
      color: $color-primary;
      background: $color-primary-light;
    }
  }
}

.touch-target-min {
  min-height: var(--touch-target-min);
}

@keyframes msgFadeIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes dotPulse {
  0%, 80%, 100% {
    transform: scale(0.6);
    opacity: 0.3;
  }
  40% {
    transform: scale(1);
    opacity: 0.8;
  }
}

// ================================================================
// 平板端适配 (768px - 1199px)
// ================================================================
@media (min-width: 768px) and (max-width: 1199px) {
  .chat-message--user .chat-message__content {
    max-width: 78%;
  }
  .chat-message--assistant .chat-message__content {
    max-width: 94%;
  }
}

// ================================================================
// 移动端适配 (< 768px)
// ================================================================
@media (max-width: 767px) {
  .chat-message {
    gap: $spacing-xs;
    margin-bottom: $spacing-md;
  }

  .chat-message--user .chat-message__content {
    max-width: 85%;
    padding: 10px 14px;
  }

  .chat-message--assistant .chat-message__content {
    max-width: 96%;
    padding: 12px 14px;
  }

  .chat-message__avatar {
    width: 28px;
    height: 28px;
  }

  .chat-message__avatar-icon {
    width: 28px;
    height: 28px;
    border-radius: 8px;
  }

  .chat-message__actions :deep(.el-button) {
    padding: 4px;
  }
}

// ---- prefers-reduced-motion ----
@media (prefers-reduced-motion: reduce) {
  .chat-message {
    animation: none;
  }

  .chat-message__loading .loading-dot {
    animation: none;
    opacity: 0.6;
  }
}
</style>
