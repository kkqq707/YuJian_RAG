<template>
  <div class="admin-layout">
    <!-- 移动端/平板 Drawer 遮罩 -->
    <transition name="fade">
      <div
        v-if="(isMobile || isTablet) && appStore.mobileSidebarOpen"
        class="admin-layout__overlay"
        aria-hidden="true"
        @click="closeDrawer"
      />
    </transition>

    <!-- 侧栏：desktop 固定 | tablet/mobile Drawer -->
    <aside
      ref="sidebarRef"
      :class="[
        'admin-sidebar',
        {
          'admin-sidebar--collapsed': isDesktop && appStore.sidebarCollapsed,
          'admin-sidebar--drawer-open': (isMobile || isTablet) && appStore.mobileSidebarOpen,
          'admin-sidebar--drawer-closed': (isMobile || isTablet) && !appStore.mobileSidebarOpen,
        },
      ]"
      :aria-label="(isMobile || isTablet) ? '管理导航抽屉' : '管理侧栏'"
      :role="(isMobile || isTablet) ? 'dialog' : 'complementary'"
      :aria-modal="(isMobile || isTablet) ? 'true' : undefined"
    >
      <!-- 侧栏头部 -->
      <div
        class="sidebar-header"
        :style="{ paddingTop: isMobile ? 'var(--safe-area-top)' : undefined }"
      >
        <div class="sidebar-logo">
          <div class="logo-icon">
            <BookOpen :size="24" />
          </div>
          <span
            v-show="!appStore.sidebarCollapsed || isMobile || isTablet"
            class="logo-text"
          >企业智库 AI</span>
        </div>
        <!-- 平板/移动端：关闭 Drawer 按钮 -->
        <el-button
          v-if="isMobile || isTablet"
          text
          aria-label="关闭管理导航"
          class="drawer-close-btn touch-target"
          @click="closeDrawer"
        >
          <X :size="20" />
        </el-button>
      </div>

      <!-- 导航菜单 -->
      <nav class="sidebar-menu" aria-label="管理导航">
        <el-menu
          :default-active="activeMenu"
          :collapse="isDesktop ? appStore.sidebarCollapsed : false"
          background-color="#0F172A"
          text-color="#94A3B8"
          active-text-color="#FFFFFF"
          router
          @select="onMenuSelect"
        >
          <el-menu-item
            v-for="item in permissionStore.adminMenuItems"
            :key="item.path"
            :index="item.path"
            @mouseenter="onMenuHover(item.path)"
          >
            <el-icon><component :is="item.icon" /></el-icon>
            <template #title>{{ item.title }}</template>
          </el-menu-item>
        </el-menu>
      </nav>

      <!-- 侧栏底部：管理员信息 -->
      <div
        class="sidebar-footer"
        :style="{ paddingBottom: isMobile ? 'var(--safe-area-bottom)' : undefined }"
      >
        <div class="sidebar-user">
          <el-avatar :size="32" icon="UserFilled" />
          <span
            v-show="!appStore.sidebarCollapsed || isMobile || isTablet"
            class="user-name"
          >
            {{ authStore.displayName }}
          </span>
          <el-tag
            v-show="!appStore.sidebarCollapsed || isMobile || isTablet"
            size="small"
            type="primary"
            class="role-tag"
          >
            管理员
          </el-tag>
        </div>
      </div>
    </aside>

    <!-- 主区域 -->
    <div
      :class="[
        'admin-main',
        { 'admin-main--collapsed': isDesktop && appStore.sidebarCollapsed },
      ]"
    >
      <!-- 顶部栏 -->
      <header
        class="admin-header"
        :style="{ paddingTop: isMobile ? 'var(--safe-area-top)' : undefined }"
      >
        <div class="header-left">
          <!-- 移动端/平板：菜单按钮 -->
          <el-button
            v-if="isMobile || isTablet"
            class="menu-btn touch-target"
            aria-label="打开管理导航"
            @click="openDrawer"
          >
            <Menu :size="20" />
          </el-button>
          <!-- 桌面端：折叠按钮 -->
          <el-button
            v-else
            class="collapse-btn"
            :icon="appStore.sidebarCollapsed ? 'Expand' : 'Fold'"
            text
            :aria-label="appStore.sidebarCollapsed ? '展开侧栏' : '折叠侧栏'"
            @click="appStore.toggleSidebar()"
          />
          <!-- 当前页面标题（移动端省略） -->
          <span class="header-page-title">{{ currentPageTitle }}</span>
          <AppBreadcrumb v-if="isDesktop" />
        </div>

        <div class="header-right">
          <div class="header-actions">
            <!-- 系统状态：桌面显示文字+点，移动端仅显示点 -->
            <el-tooltip
              :content="appStore.backendOnline ? '系统正常' : '连接断开'"
              placement="bottom"
            >
              <span
                class="status-dot"
                :class="appStore.backendOnline ? 'online' : 'offline'"
                role="status"
                :aria-label="appStore.backendOnline ? '系统正常' : '连接断开'"
              />
            </el-tooltip>
            <span v-if="isDesktop" class="status-text">
              {{ appStore.backendOnline ? '系统正常' : '连接断开' }}
            </span>
            <el-tooltip v-if="isDesktop" content="使用帮助" placement="bottom">
              <el-button circle text aria-label="使用帮助">
                <el-icon><QuestionFilled /></el-icon>
              </el-button>
            </el-tooltip>
          </div>
          <UserDropdown />
        </div>
      </header>

      <!-- 内容区 -->
      <main class="admin-content">
        <router-view v-slot="{ Component: RouteComponent }">
          <transition name="fade" mode="out-in">
            <component :is="RouteComponent" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted, onUnmounted, provide } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { usePermissionStore } from '@/stores/permission'
import { useResponsive } from '@/composables/useResponsive'
import AppBreadcrumb from '@/components/layout/AppBreadcrumb.vue'
import UserDropdown from '@/components/layout/UserDropdown.vue'
import { BookOpen, X, Menu } from '@lucide/vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const appStore = useAppStore()
const permissionStore = usePermissionStore()

// ---- 统一响应式 ----
const { isMobile, isTablet, isDesktop } = useResponsive()

// ---- 暴露给子组件 ----
provide('isMobile', isMobile)
provide('isTablet', isTablet)
provide('isDesktop', isDesktop)

// ---- 当前页面标题 ----
const currentPageTitle = computed(() => {
  const metaTitle = route.meta.title
  if (metaTitle) return metaTitle as string
  // Fallback: 从 menu items 中查找
  const menuItem = permissionStore.adminMenuItems.find(
    (item) => item.path === route.path,
  )
  return menuItem?.title || ''
})

// ---- 当前激活菜单 ----
const activeMenu = computed(() => route.path)

// ---- Drawer 引用 ----
const sidebarRef = ref<HTMLElement>()

// ---- Drawer 操作 ----
function openDrawer() {
  appStore.setMobileSidebarOpen(true)
}

function closeDrawer() {
  appStore.setMobileSidebarOpen(false)
}

// ---- 菜单选中后关闭 Drawer ----
function onMenuSelect() {
  if (isMobile.value || isTablet.value) {
    closeDrawer()
  }
}

// ---- 键盘 Escape 关闭 Drawer ----
function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && appStore.mobileSidebarOpen) {
    closeDrawer()
  }
}

// ---- 路由变化后关闭 Drawer ----
watch(
  () => router.currentRoute.value.path,
  () => {
    if (appStore.mobileSidebarOpen) {
      closeDrawer()
    }
  },
)

// ---- Drawer 焦点管理 ----
watch(
  () => appStore.mobileSidebarOpen,
  (open) => {
    if (open) {
      setTimeout(() => {
        const el = sidebarRef.value?.querySelector<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        )
        el?.focus()
      }, 300) // 等待 transition
    }
  },
)

// ---- 从 tablet/mobile 切换到 desktop 时关闭 Drawer ----
watch([isMobile, isTablet], ([mob, tab]) => {
  if (!mob && !tab) {
    appStore.setMobileSidebarOpen(false)
  }
})

// ---- 菜单悬停预加载 ----
const routePreloadMap: Record<string, () => Promise<unknown>> = {
  '/admin/dashboard': () => import('@/views/admin/DashboardView.vue'),
  '/admin/knowledge': () => import('@/views/admin/KnowledgeView.vue'),
  '/admin/chat-preview': () => import('@/views/admin/ChatPreviewView.vue'),
  '/admin/settings': () => import('@/views/admin/SettingsView.vue'),
  '/admin/users': () => import('@/views/admin/UsersView.vue'),
  '/admin/api-config': () => import('@/views/admin/ApiConfigView.vue'),
  '/admin/rag-config': () => import('@/views/admin/RAGConfigView.vue'),
  '/admin/logs': () => import('@/views/admin/SystemLogsView.vue'),
  '/admin/system': () => import('@/views/admin/SystemView.vue'),
  '/admin/profile': () => import('@/views/admin/AdminProfileView.vue'),
}

function onMenuHover(path: string) {
  routePreloadMap[path]?.()
}

// ---- 生命周期 ----
onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<style lang="scss" scoped>
// ---- 根布局 ----
.admin-layout {
  display: flex;
  height: var(--app-height);
  min-height: 0;
  overflow: hidden;
  background: $color-page-bg;
}

// ---- 遮罩 ----
.admin-layout__overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 90;
}

// ---- 侧栏基础 ----
.admin-sidebar {
  width: $sidebar-width;
  flex: 0 0 $sidebar-width;
  background: $color-sidebar-bg;
  display: flex;
  flex-direction: column;
  transition: width $transition-normal;
  position: relative;
  z-index: $z-sidebar;

  // 桌面端折叠
  &--collapsed {
    width: $sidebar-collapse-width;
    flex: 0 0 $sidebar-collapse-width;
  }

  // 平板端：Drawer 模式
  @media (min-width: 768px) and (max-width: 1199px) {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    width: min(86vw, 320px);
    flex: none;
    transform: translateX(-100%);
    transition: transform $transition-normal;
    box-shadow: $shadow-dropdown;

    &--drawer-open {
      transform: translateX(0);
    }

    &--drawer-closed {
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
    flex: none;
    transform: translateX(-100%);
    transition: transform $transition-normal;
    box-shadow: $shadow-dropdown;

    &--drawer-open {
      transform: translateX(0);
    }

    &--drawer-closed {
      transform: translateX(-100%);
    }
  }
}

// ---- 侧栏头部 ----
.sidebar-header {
  height: $header-height;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 $spacing-md;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  flex-shrink: 0;
}

.sidebar-logo {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  overflow: hidden;
}

.logo-icon {
  color: $color-primary;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.logo-text {
  font-size: $font-size-lg;
  font-weight: 600;
  color: #ffffff;
  white-space: nowrap;
}

.drawer-close-btn {
  color: #94a3b8;
  padding: 4px !important;
  min-height: auto !important;

  &:hover {
    color: #ffffff;
    background: rgba(255, 255, 255, 0.1);
  }
}

// ---- 导航菜单 ----
.sidebar-menu {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  overscroll-behavior: contain;

  .el-menu {
    border-right: none;
  }

  :deep(.el-menu) {
    padding-top: $spacing-sm;
  }

  :deep(.el-menu-item) {
    margin: 2px $spacing-sm;
    border-radius: $control-radius;
    height: 44px;
    line-height: 44px;

    &:hover {
      background: $color-sidebar-hover !important;
    }

    &.is-active {
      background: $color-sidebar-active !important;
    }
  }
}

// ---- 侧栏底部 ----
.sidebar-footer {
  padding: $spacing-md;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  flex-shrink: 0;
}

.sidebar-user {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  overflow: hidden;
}

.user-name {
  color: #e2e8f0;
  font-size: $font-size-sm;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
}

.role-tag {
  flex-shrink: 0;
}

// ---- 主区域 ----
.admin-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  transition: margin-left $transition-normal;

  // 桌面端折叠时减少左边距（现在使用 flex，无需 margin）
  &--collapsed {
    // flex 布局下无需额外处理
  }
}

// ---- 顶部栏 ----
.admin-header {
  height: $header-height;
  min-height: $header-height;
  background: $color-card-bg;
  border-bottom: 1px solid $color-border;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 $spacing-lg;
  flex-shrink: 0;
  z-index: $z-header;

  // 移动端缩小 header
  @media (max-width: 767px) {
    height: var(--header-height-mobile);
    min-height: var(--header-height-mobile);
    padding: 0 var(--page-padding-mobile);
  }

  // 平板端
  @media (min-width: 768px) and (max-width: 1199px) {
    padding: 0 var(--page-padding-tablet);
  }
}

.header-left,
.header-right {
  display: flex;
  align-items: center;
  gap: $spacing-md;
  min-width: 0;
}

.header-left {
  flex: 1;
  min-width: 0;
}

.header-right {
  flex-shrink: 0;
}

// ---- 当前页面标题 ----
.header-page-title {
  font-size: $font-size-base;
  font-weight: 600;
  color: $color-text-primary;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;

  // 桌面端：隐藏（breadcrumb 已显示）
  @media (min-width: 1200px) {
    display: none;
  }
}

// ---- 菜单按钮（移动端/平板） ----
.menu-btn {
  padding: 8px !important;
  min-height: auto !important;
  color: $color-text-secondary;
  flex-shrink: 0;

  &:hover {
    color: $color-text-primary;
    background: #f1f5f9;
  }
}

// ---- 折叠按钮（桌面端） ----
.collapse-btn {
  font-size: 18px;
  color: $color-text-secondary;
  flex-shrink: 0;

  &:hover {
    color: $color-text-primary;
  }
}

// ---- 状态指示 ----
.header-actions {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;

  &.online {
    background: $color-success;
  }

  &.offline {
    background: $color-danger;
  }
}

.status-text {
  font-size: $font-size-xs;
  color: $color-text-tertiary;
  white-space: nowrap;

  @media (max-width: 767px) {
    display: none;
  }
}

// ---- 内容区 ----
.admin-content {
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
  padding: $page-padding;

  // 移动端缩小内边距
  @media (max-width: 767px) {
    padding: var(--page-padding-mobile);
    padding-bottom: calc(var(--page-padding-mobile) + var(--safe-area-bottom));
  }

  // 平板端
  @media (min-width: 768px) and (max-width: 1199px) {
    padding: var(--page-padding-tablet);
  }
}

// ---- prefers-reduced-motion ----
@media (prefers-reduced-motion: reduce) {
  .admin-sidebar {
    transition: none;
  }

  .admin-main {
    transition: none;
  }
}
</style>
