<template>
  <div class="user-layout">
    <!-- 移动端/平板 Drawer 遮罩 -->
    <transition name="fade">
      <div
        v-if="(isMobile || isTablet) && appStore.mobileSidebarOpen"
        class="user-layout__overlay"
        aria-hidden="true"
        @click="closeSidebar"
      />
    </transition>

    <!-- 左侧会话栏 -->
    <aside
      ref="sidebarRef"
      class="user-sidebar"
      :class="{
        'user-sidebar--collapsed': sidebarCollapsed && isDesktop,
        'user-sidebar--open': (isMobile || isTablet) && appStore.mobileSidebarOpen,
        'user-sidebar--closed': (isMobile || isTablet) && !appStore.mobileSidebarOpen,
      }"
      :aria-label="(isMobile || isTablet) ? '会话列表抽屉' : '会话侧栏'"
      :role="(isMobile || isTablet) ? 'dialog' : 'complementary'"
      :aria-modal="(isMobile || isTablet) ? 'true' : undefined"
    >
      <!-- 侧栏顶部：品牌 + 折叠按钮 -->
      <div class="user-sidebar__header" :style="{ paddingTop: isMobile ? 'var(--safe-area-top)' : undefined }">
        <div class="user-sidebar__brand" v-if="!sidebarCollapsed || isMobile || isTablet">
          <div class="user-logo-icon">
            <Sparkles :size="20" />
          </div>
          <span class="user-logo-text">企业智库 AI</span>
        </div>
        <el-button
          v-if="isDesktop"
          text
          :aria-label="sidebarCollapsed ? '展开侧栏' : '折叠侧栏'"
          class="collapse-btn touch-target"
          @click="appStore.toggleSidebar()"
        >
          <PanelLeftClose v-if="!sidebarCollapsed" :size="18" />
          <PanelLeftOpen v-else :size="18" />
        </el-button>
        <!-- 平板/移动端：关闭抽屉按钮 -->
        <el-button
          v-if="isMobile || isTablet"
          text
          aria-label="关闭会话列表"
          class="collapse-btn touch-target"
          @click="closeSidebar"
        >
          <X :size="20" />
        </el-button>
      </div>

      <!-- 展开状态下显示会话列表 -->
      <template v-if="!sidebarCollapsed || isMobile || isTablet">
        <SessionList
          :sessions="sessions"
          :active-id="activeSessionId"
          :is-mobile="isMobile"
          @create="handleCreateSession"
          @switch="handleSwitchSession"
          @delete="handleDeleteSession"
          @rename="handleRenameSession"
        />
      </template>

      <!-- 折叠状态下显示快捷图标（仅桌面端） -->
      <div v-else class="user-sidebar__collapsed-nav">
        <el-tooltip content="新建对话" placement="right">
          <el-button
            text
            class="collapsed-nav-btn touch-target"
            aria-label="新建对话"
            @click="handleCreateSession"
          >
            <Plus :size="20" />
          </el-button>
        </el-tooltip>
      </div>

      <!-- 底部用户区 -->
      <div class="user-sidebar__footer" :style="{ paddingBottom: isMobile ? 'var(--safe-area-bottom)' : undefined }">
        <router-link to="/profile" class="user-footer-link touch-target" aria-label="个人中心">
          <el-avatar :size="sidebarCollapsed && isDesktop ? 32 : 28" icon="UserFilled" />
          <span v-if="!sidebarCollapsed || isMobile || isTablet" class="user-footer-name">
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
              class="logout-btn touch-target"
              :class="{ 'logout-btn--collapsed': sidebarCollapsed && isDesktop }"
              aria-label="退出登录"
            >
              <LogOut :size="18" />
              <span v-if="!sidebarCollapsed || isMobile || isTablet">退出登录</span>
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
import { ref, onMounted, onUnmounted, watch, provide } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { useChatStore } from '@/stores/chat'
import { storeToRefs } from 'pinia'
import { Sparkles, Plus, LogOut, PanelLeftClose, PanelLeftOpen, X } from '@lucide/vue'
import { useResponsive } from '@/composables/useResponsive'
import SessionList from '@/components/chat/SessionList.vue'

const router = useRouter()
const authStore = useAuthStore()
const appStore = useAppStore()
const chatStore = useChatStore()

// ---- 统一响应式（使用 useResponsive，不再用 window.innerWidth） ----
const { isMobile, isTablet, isDesktop } = useResponsive()
const { sidebarCollapsed } = storeToRefs(appStore)
const { sessions, activeSessionId } = storeToRefs(chatStore)

const sidebarRef = ref<HTMLElement>()

// ---- 暴露给子组件 ----
provide('isMobile', isMobile)
provide('isTablet', isTablet)
provide('isDesktop', isDesktop)

function closeSidebar() {
  appStore.setMobileSidebarOpen(false)
}

// ---- 键盘事件：Escape 关闭抽屉 ----
function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && appStore.mobileSidebarOpen) {
    closeSidebar()
  }
}

// ---- 路由变化后关闭抽屉 ----
watch(
  () => router.currentRoute.value.path,
  () => {
    if (appStore.mobileSidebarOpen) {
      closeSidebar()
    }
  },
)

// ---- Drawer 焦点管理 ----
watch(
  () => appStore.mobileSidebarOpen,
  (open) => {
    if (open) {
      // 打开后聚焦抽屉内的第一个可聚焦元素
      setTimeout(() => {
        const el = sidebarRef.value?.querySelector<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        )
        el?.focus()
      }, 300) // 等待 transition
    }
  },
)

// ---- 当从 tablet/mobile 切换到 desktop 时，关闭抽屉 ----
watch([isMobile, isTablet], ([mob, tab]) => {
  if (!mob && !tab) {
    appStore.setMobileSidebarOpen(false)
  }
})

// ---- 会话操作 ----
function handleCreateSession() {
  chatStore.createSession()
  if (isMobile.value || isTablet.value) closeSidebar()
}

async function handleSwitchSession(sessionId: string) {
  await chatStore.switchSession(sessionId)
  if (isMobile.value || isTablet.value) closeSidebar()
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
  const previousUserId = authStore.user?.id ?? null
  chatStore.reset()
  await authStore.logout()
  appStore.reset()
  closeSidebar()
  router.push('/login')
}

// ---- 生命周期 ----
onMounted(async () => {
  document.addEventListener('keydown', handleKeydown)
  if (authStore.isAuthenticated) {
    await chatStore.initialize()
  }
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<style lang="scss" scoped>
.user-layout {
  display: flex;
  height: var(--app-height);
  min-height: 0;
  overflow: hidden;
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
  width: var(--sidebar-width-desktop);
  flex: 0 0 var(--sidebar-width-desktop);
  background: $color-card-bg;
  border-right: 1px solid $color-border;
  display: flex;
  flex-direction: column;
  transition: width $transition-normal;
  position: relative;
  z-index: 100;

  &--collapsed {
    width: 64px;
    flex: 0 0 64px;
  }

  // 平板端：使用 Drawer 模式
  @media (min-width: 768px) and (max-width: 1199px) {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    width: min(86vw, 320px);
    transform: translateX(-100%);
    transition: transform $transition-normal;
    z-index: 100;
    box-shadow: $shadow-dropdown;

    &--open {
      transform: translateX(0);
    }

    &--closed {
      transform: translateX(-100%);
    }
  }

  // 移动端：Drawer 模式
  @media (max-width: 767px) {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    width: min(86vw, 320px);
    transform: translateX(-100%);
    transition: transform $transition-normal;
    z-index: 100;
    box-shadow: $shadow-dropdown;

    &--open {
      transform: translateX(0);
    }

    &--closed {
      transform: translateX(-100%);
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
  flex-shrink: 0;
}

.user-sidebar__brand {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  min-width: 0;
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
  flex-shrink: 0;
}

.user-logo-text {
  font-size: $font-size-base;
  font-weight: 600;
  color: $color-text-primary;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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

// ---- 底部 ----
.user-sidebar__footer {
  padding: $spacing-sm $spacing-md;
  border-top: 1px solid $color-border;
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex-shrink: 0;
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
  min-height: 0;
  overflow: hidden;
}

// ---- prefers-reduced-motion ----
@media (prefers-reduced-motion: reduce) {
  .user-sidebar {
    transition: none;
  }
}
</style>
