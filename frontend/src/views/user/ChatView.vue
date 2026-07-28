<template>
  <div class="chat-view">
    <!-- 顶部栏 -->
    <header class="chat-view__header">
      <div class="chat-view__header-left">
        <!-- 移动端/平板：菜单按钮 -->
        <el-button
          v-if="isMobile || isTablet"
          text
          class="mobile-menu-btn touch-target"
          aria-label="打开会话列表"
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
            <span class="chat-view__status-text">在线</span>
          </span>
        </div>
      </div>

      <!-- 知识库统计（仅管理员可见，但管理员不会进入此页面 — 保留兼容） -->
      <div v-if="authStore.isAdmin && !isMobile" class="chat-view__header-stats">
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
        <!-- 桌面端：文字按钮 -->
        <template v-if="isDesktop">
          <el-button text @click="handleNewChat">
            <Plus :size="16" />
            <span>新建对话</span>
          </el-button>
          <el-button text :disabled="!chatStore.hasMessages" @click="handleClearChat">
            <Trash2 :size="16" />
            <span>清空当前对话</span>
          </el-button>
        </template>
        <!-- 移动端/平板：新建对话图标按钮 + 更多菜单 -->
        <template v-else>
          <el-button
            text
            class="touch-target"
            aria-label="新建对话"
            @click="handleNewChat"
          >
            <Plus :size="20" />
          </el-button>
          <el-dropdown trigger="click" @command="handleMoreCommand">
            <el-button text class="touch-target" aria-label="更多操作">
              <MoreHorizontal :size="20" />
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="clear" :disabled="!chatStore.hasMessages">
                  <Trash2 :size="14" />
                  <span>清空当前对话</span>
                </el-dropdown-item>
                <!-- 管理员统计信息折叠到更多菜单 -->
                <template v-if="authStore.isAdmin && pageStats">
                  <el-dropdown-item disabled>
                    <FileText :size="14" />
                    <span>{{ pageStats.knowledge_files ?? '--' }} 文件</span>
                  </el-dropdown-item>
                  <el-dropdown-item disabled>
                    <Database :size="14" />
                    <span>{{ pageStats.knowledge_chunks ?? '--' }} 片段</span>
                  </el-dropdown-item>
                  <el-dropdown-item v-if="pageStats.model_name" disabled>
                    <Cpu :size="14" />
                    <span>{{ pageStats.model_name }}</span>
                  </el-dropdown-item>
                </template>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
      </div>
    </header>

    <!-- 消息区 -->
    <div
      ref="messageAreaRef"
      class="chat-view__messages"
      @scroll="handleScroll"
    >
      <!-- 空会话欢迎页 -->
      <WelcomePanel
        v-if="!chatStore.hasMessages"
        :sending="chatStore.sending"
        :is-mobile="isMobile"
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
            :is-mobile="isMobile"
            @retry="handleRetry(msg)"
            @regenerate="handleRegenerate"
          />
        </div>
      </div>
    </div>

    <!-- 回到底部浮动按钮 -->
    <transition name="fade">
      <div
        v-if="showScrollToBottom"
        class="chat-view__scroll-btn touch-target"
        role="button"
        tabindex="0"
        aria-label="回到底部"
        @click="scrollToBottom()"
        @keydown.enter="scrollToBottom()"
        @keydown.space.prevent="scrollToBottom()"
      >
        <ChevronDown :size="20" />
      </div>
    </transition>

    <!-- 输入区 -->
    <div class="chat-view__input">
      <ChatInput
        ref="chatInputRef"
        :sending="chatStore.sending"
        :max-length="maxQuestionLength"
        :is-mobile="isMobile"
        @send="handleSend"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, watch, inject, type Ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Trash2, Menu, ChevronDown, Database, FileText, Cpu, MoreHorizontal } from '@lucide/vue'
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

// ---- 统一响应式（通过 provide/inject 从 UserLayout 获取） ----
const isMobile = inject<Ref<boolean>>('isMobile', ref(false))
const isTablet = inject<Ref<boolean>>('isTablet', ref(false))
const isDesktop = inject<Ref<boolean>>('isDesktop', ref(true))

// ---- 输入 ----
const chatInputRef = ref<InstanceType<typeof ChatInput>>()
const maxQuestionLength = 2000

// ---- 页面统计 ----
const pageStats = ref<ChatPageStats | null>(null)

async function fetchPageStats() {
  if (!authStore.isAuthenticated || !authStore.isAdmin) return
  try {
    pageStats.value = await chatApi.getChatPageStats()
  } catch {
    // 静默失败
  }
}

// ---- 滚动（优化版：RAF 节流 + 智能跟随） ----
const messageAreaRef = ref<HTMLElement>()
const showScrollToBottom = ref(false)
let userScrolledUp = false
let scrollRafId: number | null = null
let lastScrollTime = 0
const SCROLL_THROTTLE_MS = 16 // ~60fps

function scrollToBottom(smooth = true) {
  // 使用 requestAnimationFrame 节流
  const now = performance.now()
  if (now - lastScrollTime < SCROLL_THROTTLE_MS) {
    // 排队下一次 RAF
    if (scrollRafId === null) {
      scrollRafId = requestAnimationFrame(() => {
        scrollRafId = null
        doScrollToBottom(smooth)
      })
    }
    return
  }
  doScrollToBottom(smooth)
}

function doScrollToBottom(smooth: boolean) {
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
    lastScrollTime = performance.now()
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

// 新消息后自动滚动（仅在用户处于底部时）
watch(
  () => chatStore.activeMessages.length,
  () => {
    if (!userScrolledUp) {
      scrollToBottom(false)
    }
  },
)

// 消息内容变化时滚动（仅在用户处于底部时，使用 RAF 节流）
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

async function handleSend(question: string) {
  await chatStore.sendQuestion(question)
  userScrolledUp = false
  scrollToBottom()
}

async function handleSuggestedQuestion(question: string) {
  await chatStore.sendQuestion(question)
  userScrolledUp = false
  scrollToBottom()
}

function handleNewChat() {
  chatStore.createSession()
  userScrolledUp = false
  scrollToBottom()
}

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

function handleMoreCommand(command: string) {
  if (command === 'clear') {
    handleClearChat()
  }
}

async function handleRetry(_msg: ChatMessageType) {
  await chatStore.retryLastFailed()
  userScrolledUp = false
  scrollToBottom()
}

async function handleRegenerate() {
  await chatStore.regenerateLastAnswer()
  userScrolledUp = false
  scrollToBottom()
}

// ---- 生命周期 ----
onMounted(() => {
  fetchPageStats()
  nextTick(() => scrollToBottom(false))
})

onUnmounted(() => {
  // 清理 RAF
  if (scrollRafId !== null) {
    cancelAnimationFrame(scrollRafId)
    scrollRafId = null
  }
  // 停止旧会话的自动滚动
  userScrolledUp = true
})

defineExpose({ scrollToBottom })
</script>

<style lang="scss" scoped>
.chat-view {
  display: flex;
  flex-direction: column;
  height: var(--app-height);
  min-height: 0;
  overflow: hidden;
  background: $color-page-bg;
}

// ---- 顶部栏 ----
.chat-view__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 $spacing-lg;
  height: var(--header-height-desktop);
  background: $color-card-bg;
  border-bottom: 1px solid $color-border;
  flex: 0 0 auto;
  min-width: 0;
  gap: $spacing-sm;
}

.chat-view__header-left {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  min-width: 0;
  flex: 0 1 auto;
}

.mobile-menu-btn {
  flex-shrink: 0;
}

.chat-view__header-info {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  min-width: 0;
}

.chat-view__title {
  font-size: $font-size-lg;
  font-weight: 600;
  color: $color-text-primary;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chat-view__status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: $font-size-xs;
  color: $color-success;
  flex-shrink: 0;

  .status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: $color-success;
    flex-shrink: 0;
  }
}

.chat-view__header-stats {
  display: flex;
  align-items: center;
  gap: $spacing-md;
  flex: 1;
  justify-content: center;
  min-width: 0;
  overflow: hidden;
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
    flex-shrink: 0;
  }
}

.chat-view__header-right {
  display: flex;
  align-items: center;
  gap: $spacing-xs;
  flex-shrink: 0;

  :deep(.el-button) {
    font-size: $font-size-sm;
    color: $color-text-secondary;
  }
}

// ---- 消息区 ----
.chat-view__messages {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
  padding: $spacing-lg;
}

.chat-view__message-list {
  width: min(100%, 960px);
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
.chat-view {
  position: relative;
}

.chat-view__scroll-btn {
  position: absolute;
  bottom: 140px;
  left: 50%;
  transform: translateX(-50%);
  width: var(--touch-target-min);
  height: var(--touch-target-min);
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

  &:focus-visible {
    outline: 2px solid $color-primary;
    outline-offset: 2px;
  }
}

// ---- 输入区 ----
.chat-view__input {
  flex: 0 0 auto;
  padding: 0 $spacing-lg $spacing-sm;
  background: $color-page-bg;

  :deep(.chat-input) {
    width: min(100%, 960px);
    margin: 0 auto;
  }
}

// ================================================================
// 平板端适配 (768px - 1199px)
// ================================================================
@media (min-width: 768px) and (max-width: 1199px) {
  .chat-view__header {
    padding: 0 $spacing-md;
    height: var(--header-height-mobile);
  }

  .chat-view__header-stats {
    display: none; // 平板端隐藏统计信息到更多菜单
  }

  .chat-view__messages {
    padding: $spacing-md;
  }

  .chat-view__message-list {
    width: min(100%, 800px);
  }

  .chat-view__input {
    padding: 0 $spacing-md $spacing-sm;

    :deep(.chat-input) {
      width: min(100%, 800px);
    }
  }
}

// ================================================================
// 移动端适配 (< 768px)
// ================================================================
@media (max-width: 767px) {
  .chat-view__header {
    padding: 0 var(--page-padding-mobile);
    height: var(--header-height-mobile);
  }

  .chat-view__header-stats {
    display: none;
  }

  .chat-view__status-text {
    display: none; // 移动端隐藏"在线"文字，只保留绿色圆点
  }

  .chat-view__messages {
    padding: var(--page-padding-mobile);
  }

  .chat-view__message-list {
    width: 100%;
  }

  .chat-view__scroll-btn {
    bottom: 120px;
  }

  .chat-view__input {
    padding: 0 var(--page-padding-mobile);
    padding-bottom: max(var(--page-padding-mobile), var(--safe-area-bottom));

    :deep(.chat-input) {
      width: 100%;
    }
  }
}

// ---- prefers-reduced-motion ----
@media (prefers-reduced-motion: reduce) {
  .chat-view__scroll-btn {
    transition: none;
  }
}
</style>
