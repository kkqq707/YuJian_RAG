<template>
  <div class="user-layout">
    <!-- 移动端遮罩 -->
    <transition name="fade">
      <div
        v-if="isMobile && appStore.mobileSidebarOpen"
        class="user-layout__overlay"
        @click="closeSidebar"
      />
    </transition>

    <!-- 左侧会话栏 -->
    <aside
      class="user-sidebar"
      :class="{
        'user-sidebar--collapsed': sidebarCollapsed && !isMobile,
        'user-sidebar--open': isMobile && appStore.mobileSidebarOpen,
        'user-sidebar--closed': isMobile && !appStore.mobileSidebarOpen,
      }"
    >
      <!-- 侧栏顶部：品牌 + 折叠按钮 -->
      <div class="user-sidebar__header">
        <div class="user-sidebar__brand" v-if="!sidebarCollapsed || isMobile">
          <div class="user-logo-icon">
            <Sparkles :size="20" />
          </div>
          <span class="user-logo-text">企业智库 AI</span>
        </div>
        <el-button
          v-if="!isMobile"
          text
          class="collapse-btn"
          @click="appStore.toggleSidebar()"
        >
          <PanelLeftClose v-if="!sidebarCollapsed" :size="18" />
          <PanelLeftOpen v-else :size="18" />
        </el-button>
      </div>

      <!-- 展开状态下显示会话列表 -->
      <template v-if="!sidebarCollapsed || isMobile">
        <SessionList
          :sessions="sessions"
          :active-id="activeSessionId"
          @create="handleCreateSession"
          @switch="handleSwitchSession"
          @delete="handleDeleteSession"
          @rename="handleRenameSession"
        />
      </template>

      <!-- 折叠状态下显示快捷图标 -->
      <div v-else class="user-sidebar__collapsed-nav">
        <el-tooltip content="新建对话" placement="right">
          <el-button text class="collapsed-nav-btn" @click="handleCreateSession">
            <Plus :size="20" />
          </el-button>
        </el-tooltip>
      </div>

      <!-- 管理员后台入口 -->
      <div
        v-if="authStore.isAdmin"
        class="user-sidebar__admin-entry"
        :class="{ 'user-sidebar__admin-entry--collapsed': sidebarCollapsed && !isMobile }"
      >
        <router-link to="/admin/dashboard" class="admin-entry-link">
          <Shield :size="18" />
          <span v-if="!sidebarCollapsed || isMobile">管理后台</span>
        </router-link>
      </div>

      <!-- 底部用户区 -->
      <div class="user-sidebar__footer">
        <router-link to="/profile" class="user-footer-link">
          <el-avatar :size="sidebarCollapsed && !isMobile ? 32 : 28" icon="UserFilled" />
          <span v-if="!sidebarCollapsed || isMobile" class="user-footer-name">
            {{ authStore.displayName }}
          </span>
        </router-link>
        <el-popconfirm
          title="确定要退出登录吗？"
          confirm-button-text="退出"
          cancel-button-text="取消"
          width="200"
          @confirm="handleLogout"
        >
          <template #reference>
            <el-button
              text
              class="logout-btn"
              :class="{ 'logout-btn--collapsed': sidebarCollapsed && !isMobile }"
            >
              <LogOut :size="18" />
              <span v-if="!sidebarCollapsed || isMobile">退出登录</span>
            </el-button>
          </template>
        </el-popconfirm>
      </div>
    </aside>

    <!-- 右侧主区域 -->
    <div class="user-main">
      <router-view v-slot="{ Component: RouteComponent }">
        <transition name="fade" mode="out-in">
          <component :is="RouteComponent" />
        </transition>
      </router-view>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { useChatStore } from '@/stores/chat'
import { storeToRefs } from 'pinia'
import { Sparkles, Plus, LogOut, PanelLeftClose, PanelLeftOpen, Shield } from '@lucide/vue'
import SessionList from '@/components/chat/SessionList.vue'

const router = useRouter()
const authStore = useAuthStore()
const appStore = useAppStore()
const chatStore = useChatStore()

// ---- 响应式 ----
const isMobile = ref(false)
const { sidebarCollapsed } = storeToRefs(appStore)
const { sessions, activeSessionId } = storeToRefs(chatStore)

function checkMobile() {
  isMobile.value = window.innerWidth < 768
  if (!isMobile.value) {
    appStore.setMobileSidebarOpen(false)
  }
}

function closeSidebar() {
  appStore.setMobileSidebarOpen(false)
}

// 监听 ChatView 发出的 toggleSidebar 事件
// 通过 provide/inject 或监听子组件事件来处理
// 这里 ChatView 通过 emit 来通知父组件
// 实际上 ChatView emit('toggleSidebar') 需要被监听
// 我们通过 provide 一个方法来让 ChatView 调用

// ---- 会话操作 ----
function handleCreateSession() {
  chatStore.createSession()
  if (isMobile.value) closeSidebar()
}

async function handleSwitchSession(sessionId: string) {
  await chatStore.switchSession(sessionId)
  if (isMobile.value) closeSidebar()
}

function handleDeleteSession(sessionId: string) {
  chatStore.deleteSession(sessionId)
  ElMessage.success('对话已删除')
}

async function handleRenameSession(sessionId: string, newTitle: string) {
  const ok = await chatStore.renameSession(sessionId, newTitle)
  if (ok) {
    ElMessage.success('重命名成功')
  } else {
    ElMessage.warning('重命名失败，名称不合法')
  }
}

// ---- 退出登录 ----
async function handleLogout() {
  // 1. 先保存当前用户 ID
  const previousUserId = authStore.user?.id ?? null

  // 2. 重置用户相关 store
  chatStore.reset()

  // 3. 退出登录（authStore.logout 会清除认证状态和存储）
  await authStore.logout()

  // 4. 重置应用 UI 状态
  appStore.reset()

  // 5. 跳转到登录页
  router.push('/login')
}

// ---- 生命周期 ----
onMounted(async () => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
  // 仅当用户已认证时才加载会话列表，避免未认证请求触发 401
  if (authStore.isAuthenticated) {
    await chatStore.initialize()
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})
</script>

<style lang="scss" scoped>
.user-layout {
  display: flex;
  min-height: 100vh;
  background: $color-page-bg;
}

// ---- 遮罩 ----
.user-layout__overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 90;
}

// ---- 侧栏 ----
.user-sidebar {
  width: 280px;
  background: $color-card-bg;
  border-right: 1px solid $color-border;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: width $transition-normal;
  position: relative;
  z-index: 100;

  &--collapsed {
    width: 64px;
  }

  // 移动端
  @media (max-width: 768px) {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    width: 280px;
    transform: translateX(-100%);
    transition: transform $transition-normal;
    z-index: 100;

    &--open {
      transform: translateX(0);
    }

    &--closed {
      transform: translateX(-100%);
    }
  }

  // 平板
  @media (min-width: 769px) and (max-width: 1024px) {
    width: 240px;

    &--collapsed {
      width: 60px;
    }
  }
}

// ---- 侧栏头部 ----
.user-sidebar__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: $spacing-md;
  border-bottom: 1px solid $color-border;
}

.user-sidebar__brand {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
}

.user-logo-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: $color-primary;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
}

.user-logo-text {
  font-size: $font-size-base;
  font-weight: 600;
  color: $color-text-primary;
}

.collapse-btn {
  color: $color-text-tertiary;
  padding: 4px !important;
  min-height: auto !important;

  &:hover {
    color: $color-text-primary;
    background: #f1f5f9;
  }
}

// ---- 折叠导航 ----
.user-sidebar__collapsed-nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: $spacing-md;
}

.collapsed-nav-btn {
  padding: 8px !important;
  min-height: auto !important;
  color: $color-text-tertiary;

  &:hover {
    color: $color-primary;
    background: $color-primary-light;
  }
}

// ---- 管理员入口 ----
.user-sidebar__admin-entry {
  padding: $spacing-xs $spacing-md;
  border-top: 1px solid $color-border;

  &--collapsed {
    display: flex;
    justify-content: center;
    padding: $spacing-xs;
  }
}

.admin-entry-link {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  padding: 10px $spacing-sm;
  border-radius: $control-radius;
  text-decoration: none;
  color: $color-primary;
  font-size: $font-size-sm;
  font-weight: 500;
  transition: all $transition-fast;
  border: 1px solid $color-primary;

  &:hover {
    background: $color-primary;
    color: #fff;
  }
}

// ---- 底部 ----
.user-sidebar__footer {
  padding: $spacing-sm $spacing-md;
  border-top: 1px solid $color-border;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.user-footer-link {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  padding: 8px $spacing-sm;
  border-radius: $control-radius;
  text-decoration: none;
  color: $color-text-primary;
  transition: background $transition-fast;

  &:hover {
    background: #f1f5f9;
  }
}

.user-footer-name {
  font-size: $font-size-sm;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.logout-btn {
  width: 100%;
  justify-content: flex-start;
  gap: $spacing-sm;
  color: $color-text-tertiary;
  padding: 8px $spacing-sm;
  border-radius: $control-radius;

  &:hover {
    color: $color-danger;
    background: #fef2f2;
  }

  &--collapsed {
    justify-content: center;
    padding: 8px;
  }
}

// ---- 主区域 ----
.user-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}
</style>
