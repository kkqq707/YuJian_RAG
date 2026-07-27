<template>
  <div class="chat-view">
    <!-- 顶部栏 -->
    <div class="chat-view__header">
      <div class="chat-view__header-left">
        <el-button
          v-if="isMobile"
          text
          class="mobile-menu-btn"
          @click="appStore.toggleMobileSidebar()"
        >
          <Menu :size="20" />
        </el-button>
        <div class="chat-view__header-info">
          <h2 class="chat-view__title">
            {{ pageStats?.enterprise_name || '企业智库 AI' }} 助手
          </h2>
          <span class="chat-view__status">
            <span class="status-dot" />
            在线
          </span>
        </div>
      </div>

      <!-- 知识库统计（仅管理员可见） -->
      <div v-if="authStore.isAdmin" class="chat-view__header-stats">
        <div class="header-stat-item">
          <FileText :size="14" />
          <span>{{ pageStats?.knowledge_files ?? '--' }} 文件</span>
        </div>
        <div class="header-stat-item">
          <Database :size="14" />
          <span>{{ pageStats?.knowledge_chunks ?? '--' }} 片段</span>
        </div>
        <div class="header-stat-item" v-if="pageStats?.model_name">
          <Cpu :size="14" />
          <span>{{ pageStats.model_name }}</span>
        </div>
      </div>

      <div class="chat-view__header-right">
        <el-button text @click="handleNewChat">
          <Plus :size="16" />
          <span>新建对话</span>
        </el-button>
        <el-button text @click="handleClearChat" :disabled="!chatStore.hasMessages">
          <Trash2 :size="16" />
          <span>清空当前对话</span>
        </el-button>
      </div>
    </div>

    <!-- 消息区 -->
    <div ref="messageAreaRef" class="chat-view__messages" @scroll="handleScroll">
      <!-- 空会话欢迎页 -->
      <WelcomePanel
        v-if="!chatStore.hasMessages"
        :sending="chatStore.sending"
        @select="handleSuggestedQuestion"
      />

      <!-- 消息列表 -->
      <div v-else class="chat-view__message-list">
        <div
          v-for="msg in chatStore.activeMessages"
          :key="msg.id"
          class="chat-view__message-wrapper"
        >
          <!-- 系统消息：拒答提示 -->
          <div
            v-if="msg.role === 'system'"
            class="chat-view__system-msg"
          >
            {{ msg.content }}
          </div>

          <!-- 用户/助手消息 -->
          <ChatMessage
            v-else
            :message="msg"
            :sending="chatStore.sending"
            @retry="handleRetry(msg)"
            @regenerate="handleRegenerate"
          />
        </div>
      </div>
    </div>

    <!-- 回到底部浮动按钮 -->
    <transition name="fade">
      <div v-if="showScrollToBottom" class="chat-view__scroll-btn" @click="scrollToBottom()">
        <ChevronDown :size="20" />
      </div>
    </transition>

    <!-- 输入区 -->
    <div class="chat-view__input">
      <ChatInput
        ref="chatInputRef"
        :sending="chatStore.sending"
        :max-length="maxQuestionLength"
        @send="handleSend"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Trash2, Menu, ChevronDown, Database, FileText, Cpu } from '@lucide/vue'
import { useChatStore } from '@/stores/chat'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import chatApi, { type ChatPageStats } from '@/api/chat'
import WelcomePanel from '@/components/chat/WelcomePanel.vue'
import ChatMessage from '@/components/chat/ChatMessage.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import type { ChatMessage as ChatMessageType } from '@/types/chat'

const chatStore = useChatStore()
const appStore = useAppStore()
const authStore = useAuthStore()

// ---- 响应式判断 ----
const isMobile = ref(window.innerWidth < 768)

function handleResize() {
  isMobile.value = window.innerWidth < 768
}

// ---- 输入 ----
const chatInputRef = ref<InstanceType<typeof ChatInput>>()
const maxQuestionLength = 2000

// ---- 页面统计 ----
const pageStats = ref<ChatPageStats | null>(null)

async function fetchPageStats() {
  // 仅管理员可调用 /system/status，普通用户调用会返回 401
  if (!authStore.isAuthenticated || !authStore.isAdmin) return
  try {
    pageStats.value = await chatApi.getChatPageStats()
  } catch {
    // 静默失败，保持默认值
  }
}

// ---- 滚动 ----
const messageAreaRef = ref<HTMLElement>()
const showScrollToBottom = ref(false)
let userScrolledUp = false

function scrollToBottom(smooth = true) {
  nextTick(() => {
    const el = messageAreaRef.value
    if (el) {
      el.scrollTo({
        top: el.scrollHeight,
        behavior: smooth ? 'smooth' : 'instant',
      })
    }
    showScrollToBottom.value = false
    userScrolledUp = false
  })
}

function handleScroll() {
  const el = messageAreaRef.value
  if (!el) return
  const threshold = 120
  const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < threshold
  userScrolledUp = !isNearBottom
  showScrollToBottom.value = userScrolledUp
}

// 新消息后自动滚动
watch(
  () => chatStore.activeMessages.length,
  () => {
    if (!userScrolledUp) {
      scrollToBottom(false)
    }
  },
)

// 消息内容变化时滚动（回答完成后）
watch(
  () => {
    const msgs = chatStore.activeMessages
    if (msgs.length === 0) return ''
    const last = msgs[msgs.length - 1]
    return last?.content + last?.status
  },
  () => {
    if (!userScrolledUp) {
      scrollToBottom(false)
    }
  },
)

// ---- 操作 ----

/** 发送问题 */
async function handleSend(question: string) {
  await chatStore.sendQuestion(question)
  scrollToBottom()
}

/** 推荐问题点击 */
async function handleSuggestedQuestion(question: string) {
  await chatStore.sendQuestion(question)
  scrollToBottom()
}

/** 新建对话 */
function handleNewChat() {
  chatStore.createSession()
  scrollToBottom()
}

/** 清空当前对话 */
function handleClearChat() {
  ElMessageBox.confirm('确定要清空当前对话吗？此操作不可恢复。', '清空对话', {
    confirmButtonText: '清空',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(() => {
    chatStore.clearSession()
    ElMessage.success('对话已清空')
  }).catch(() => {
    // 取消操作
  })
}

/** 重试发送（移除失败消息，使用原问题重新请求） */
async function handleRetry(_msg: ChatMessageType) {
  await chatStore.retryLastFailed()
  scrollToBottom()
}

/** 重新生成 */
async function handleRegenerate() {
  await chatStore.regenerateLastAnswer()
  scrollToBottom()
}

// ---- 生命周期 ----
onMounted(() => {
  // chatStore 由 UserLayout 统一初始化（传入用户名以隔离存储）
  fetchPageStats()
  window.addEventListener('resize', handleResize)
  nextTick(() => scrollToBottom(false))
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})

defineExpose({ scrollToBottom })
</script>

<style lang="scss" scoped>
.chat-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: $color-page-bg;
}

// ---- 顶部栏 ----
.chat-view__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px $spacing-lg;
  background: $color-card-bg;
  border-bottom: 1px solid $color-border;
  flex-shrink: 0;
}

.chat-view__header-left {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
}

.mobile-menu-btn {
  display: none;
}

.chat-view__header-info {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
}

.chat-view__title {
  font-size: $font-size-lg;
  font-weight: 600;
  color: $color-text-primary;
  margin: 0;
}

.chat-view__status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: $font-size-xs;
  color: $color-success;

  .status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: $color-success;
  }
}

.chat-view__header-stats {
  display: flex;
  align-items: center;
  gap: $spacing-md;
  flex: 1;
  justify-content: center;
}

.header-stat-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: $font-size-xs;
  color: $color-text-secondary;
  white-space: nowrap;

  svg {
    color: $color-text-tertiary;
  }
}

.chat-view__header-right {
  display: flex;
  align-items: center;
  gap: $spacing-xs;

  :deep(.el-button) {
    font-size: $font-size-sm;
    color: $color-text-secondary;
  }
}

// ---- 消息区 ----
.chat-view__messages {
  flex: 1;
  overflow-y: auto;
  padding: $spacing-lg;
}

.chat-view__message-list {
  max-width: 900px;
  margin: 0 auto;
}

.chat-view__message-wrapper {
  margin-bottom: 0;
}

.chat-view__system-msg {
  text-align: center;
  padding: 8px 16px;
  margin: $spacing-md 0;
  font-size: $font-size-sm;
  color: $color-text-tertiary;
  background: #f0f4ff;
  border-radius: 8px;
  max-width: 500px;
  margin-left: auto;
  margin-right: auto;
}

// ---- 回到底部 ----
.chat-view__scroll-btn {
  position: absolute;
  bottom: 140px;
  left: 50%;
  transform: translateX(-50%);
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: $color-card-bg;
  box-shadow: $shadow-dropdown;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 10;
  color: $color-text-secondary;
  transition: all $transition-fast;

  &:hover {
    color: $color-primary;
    box-shadow: 0 4px 20px rgba(16, 24, 40, 0.12);
  }
}

// ---- 输入区 ----
.chat-view__input {
  flex-shrink: 0;
  padding: 0 $spacing-lg;
  background: $color-page-bg;
  border-top: 1px solid transparent;

  :deep(.chat-input) {
    max-width: 900px;
    margin: 0 auto;
  }
}

// ---- 响应式 ----
@media (max-width: 768px) {
  .chat-view__header {
    padding: 10px $spacing-md;
  }

  .mobile-menu-btn {
    display: flex;
  }

  .chat-view__header-right {
    :deep(.el-button span) {
      display: none;
    }
  }

  .chat-view__messages {
    padding: $spacing-md;
  }

  .chat-view__input {
    padding: 0 $spacing-sm;
  }
}
</style>
