<template>
  <div class="admin-layout">
    <!-- 侧栏 -->
    <aside :class="['admin-sidebar', { collapsed: appStore.sidebarCollapsed }]">
      <div class="sidebar-header">
        <div class="sidebar-logo">
          <div class="logo-icon">
            <BookOpen :size="24" />
          </div>
          <span v-show="!appStore.sidebarCollapsed" class="logo-text">企业智库 AI</span>
        </div>
      </div>

      <el-menu
        :default-active="activeMenu"
        :collapse="appStore.sidebarCollapsed"
        background-color="#0F172A"
        text-color="#94A3B8"
        active-text-color="#FFFFFF"
        class="sidebar-menu"
        router
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

      <div class="sidebar-footer">
        <div class="sidebar-user">
          <el-avatar :size="32" icon="UserFilled" />
          <span v-show="!appStore.sidebarCollapsed" class="user-name">
            {{ authStore.displayName }}
          </span>
          <el-tag
            v-show="!appStore.sidebarCollapsed"
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
    <div :class="['admin-main', { 'main-collapsed': appStore.sidebarCollapsed }]">
      <!-- 顶部栏 -->
      <header class="admin-header">
        <div class="header-left">
          <el-button
            class="collapse-btn"
            :icon="appStore.sidebarCollapsed ? 'Expand' : 'Fold'"
            text
            @click="appStore.toggleSidebar()"
          />
          <AppBreadcrumb />
        </div>

        <div class="header-right">
          <div class="header-actions">
            <span class="status-dot" :class="appStore.backendOnline ? 'online' : 'offline'" />
            <span class="status-text">
              {{ appStore.backendOnline ? '系统正常' : '连接断开' }}
            </span>
            <el-tooltip content="使用帮助" placement="bottom">
              <el-button circle text>
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
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { usePermissionStore } from '@/stores/permission'
import AppBreadcrumb from '@/components/layout/AppBreadcrumb.vue'
import UserDropdown from '@/components/layout/UserDropdown.vue'
import { BookOpen } from '@lucide/vue'

const route = useRoute()
const authStore = useAuthStore()
const appStore = useAppStore()
const permissionStore = usePermissionStore()

const activeMenu = computed(() => route.path)

// ---- 菜单悬停预加载 —— 鼠标移入菜单项时提前加载页面组件 ----
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
</script>

<style lang="scss" scoped>
.admin-layout {
  height: 100vh;
  overflow: hidden;
  background: $color-page-bg;
}

// ---- 侧栏 (固定定位) ----
.admin-sidebar {
  position: fixed;
  left: 0;
  top: 0;
  height: 100vh;
  width: $sidebar-width;
  background: $color-sidebar-bg;
  display: flex;
  flex-direction: column;
  transition: width $transition-normal;
  flex-shrink: 0;
  z-index: $z-sidebar;

  &.collapsed {
    width: $sidebar-collapse-width;
  }
}

.sidebar-header {
  height: $header-height;
  display: flex;
  align-items: center;
  padding: 0 $spacing-md;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
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

.sidebar-menu {
  flex: 1;
  border-right: none;
  padding-top: $spacing-sm;
  overflow-y: auto;
  overflow-x: hidden;

  .el-menu-item {
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

.sidebar-footer {
  padding: $spacing-md;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
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
}

.role-tag {
  flex-shrink: 0;
}

// ---- 主区域 (独立滚动) ----
.admin-main {
  margin-left: $sidebar-width;
  height: 100vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-width: 0;
  transition: margin-left $transition-normal;

  &.main-collapsed {
    margin-left: $sidebar-collapse-width;
  }
}

// ---- 顶部栏 ----
.admin-header {
  height: $header-height;
  background: $color-card-bg;
  border-bottom: 1px solid $color-border;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 $spacing-lg;
  flex-shrink: 0;
  z-index: $z-header;
}

.header-left,
.header-right {
  display: flex;
  align-items: center;
  gap: $spacing-md;
}

.collapse-btn {
  font-size: 18px;
  color: $color-text-secondary;
  &:hover {
    color: $color-text-primary;
  }
}

.header-actions {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  &.online { background: $color-success; }
  &.offline { background: $color-danger; }
}

.status-text {
  font-size: $font-size-xs;
  color: $color-text-tertiary;
}

// ---- 内容区 ----
.admin-content {
  flex: 1;
  overflow-y: auto;
  padding: $page-padding;
}
</style>
