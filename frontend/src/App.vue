<template>
  <router-view />
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import { useChatStore } from '@/stores/chat'
import { registerUserIdResolver, runStorageMigration } from '@/utils/userStorage'
import { preloadAdminRoutes } from '@/router/routes'
import axios from 'axios'

const HEALTH_POLL_INTERVAL = 30000

const appStore = useAppStore()
const router = useRouter()
const authStore = useAuthStore()
const chatStore = useChatStore()

// 健康检查轮询定时器（全局唯一实例）
let healthTimer: ReturnType<typeof setInterval> | null = null

// 注册用户 ID 解析器，供 userStorage 工具使用
registerUserIdResolver(() => authStore.user?.id ?? null)

// 执行旧 localStorage 数据迁移
runStorageMigration()

// 监听用户切换，自动重新加载侧边栏折叠状态
// - 登录成功: userId null → number → 加载该用户的侧边栏状态
// - 退出登录: userId number → null → 重置侧边栏为展开
// - 账号切换: userId A → null → B → 分别加载各自的侧边栏状态
watch(
  () => authStore.userId,
  (newUserId, oldUserId) => {
    if (!newUserId) {
      // 用户登出：重置侧边栏状态
      appStore.reset()
      // 停止全局健康检查轮询（退出登录后不再需要）
      stopHealthPolling()
      return
    }

    // 用户登录或切换：加载该用户的侧边栏状态
    if (newUserId !== oldUserId) {
      appStore.initializeSidebar(newUserId)
    }
  },
  { immediate: true },
)

// ---- 全局健康检查（仅检测后端核心组件 backend + database） ----

async function checkBackend() {
  try {
    const response = await axios.get('/api/v1/health', { timeout: 5000 })
    const data = response.data
    // 使用布尔字段判断，与 LoginView 健康检查逻辑保持一致
    if (data?.backend === true && data?.database === true) {
      appStore.setBackendOnline(true)
    } else {
      appStore.setBackendOnline(false)
    }
  } catch {
    appStore.setBackendOnline(false)
  }
}

/** 启动全局健康检查轮询（单例模式 — 同一时间只存在一个实例） */
function startHealthPolling() {
  if (healthTimer) {
    return // 已在运行，不重复创建
  }
  healthTimer = setInterval(checkBackend, HEALTH_POLL_INTERVAL)
}

/** 停止全局健康检查轮询 */
function stopHealthPolling() {
  if (healthTimer) {
    clearInterval(healthTimer)
    healthTimer = null
  }
}

// ---- 认证事件处理 ----

/** 全局登出事件处理器（由 axios 401 拦截器触发） */
function handleAuthLogout() {
  // 防止在登录页触发循环跳转
  if (window.location.pathname === '/login') return
  // 停止健康检查轮询
  stopHealthPolling()
  // 重置聊天和应用状态
  chatStore.reset()
  appStore.reset()
  authStore.forceLogout()
  router.push({ name: 'Login', query: { redirect: window.location.pathname } })
}

/** Token 刷新事件处理器（由 axios 401 拦截器在成功刷新后触发） */
function handleTokenRefreshed(event: CustomEvent<{ accessToken: string; refreshToken: string }>) {
  authStore.syncAccessToken(event.detail.accessToken)
}

// ---- 生命周期 ----

onMounted(() => {
  // 首次检查
  checkBackend()
  // 启动全局健康检查轮询（仅检测 /api/v1/health 公共端点，不涉及 admin 接口）
  startHealthPolling()
  // 预加载高频管理页面 — 应用就绪后在后台触发模块转换，消除首次点击延迟
  if (authStore.isAdmin) {
    preloadAdminRoutes()
  }
})

window.addEventListener('auth:logout', handleAuthLogout)
window.addEventListener('auth:token-refreshed', handleTokenRefreshed as EventListener)

onUnmounted(() => {
  stopHealthPolling()
  window.removeEventListener('auth:logout', handleAuthLogout)
  window.removeEventListener('auth:token-refreshed', handleTokenRefreshed as EventListener)
})
</script>

<style lang="scss">
@use '@/assets/styles/global.scss';
</style>
