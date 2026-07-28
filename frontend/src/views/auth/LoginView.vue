<template>
  <div class="login-page">
    <!-- ============================================================
     背景层 — AI 空间背景
     渐变流动 + 光球 + 网格 + 粒子网络 + 数据波浪
     ============================================================ -->
    <AiBackground>
      <template #particles>
        <AiParticleBackground />
      </template>
      <template #wave>
        <AiWaveBackground />
      </template>
    </AiBackground>

    <!-- ============================================================
     主布局 — 桌面端左右分栏 / 移动端上下布局
     左侧 45%：品牌展示 | 右侧 55%：登录卡片
     ============================================================ -->
    <div class="login-layout">
      <!-- 左侧：品牌区域 -->
      <div class="login-layout__brand">
        <BrandSection />
      </div>

      <!-- 右侧：登录玻璃卡片 -->
      <div class="login-layout__card">
        <GlassLoginCard
          ref="loginCardRef"
          :loading="loading"
          :error-message="errorMessage"
          :health-status="healthStatus"
          :remember-username="rememberUsername"
          :initial-username="form.username"
          @login="handleLogin"
          @update:remember-username="rememberUsername = $event"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * LoginView — 煜见AI 企业知识智能平台登录页
 *
 * 职责：编排 AI 背景 + 品牌区 + 登录卡片，处理登录逻辑
 * 不修改：token 逻辑、权限逻辑、登录接口
 */
import { ref, reactive, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { extractLoginErrorMessage } from '@/utils/error'
import { resolvePostLoginRedirect, getDefaultRouteByRole } from '@/router/routes'
import axios from 'axios'
import AiBackground from '@/components/login/AiBackground.vue'
import AiParticleBackground from '@/components/login/AiParticleBackground.vue'
import AiWaveBackground from '@/components/login/AiWaveBackground.vue'
import BrandSection from '@/components/login/BrandSection.vue'
import GlassLoginCard from '@/components/login/GlassLoginCard.vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

// ---- 状态 ----
const loginCardRef = ref<InstanceType<typeof GlassLoginCard> | null>(null)
const loading = ref(false)
const rememberUsername = ref(false)
const errorMessage = ref('')
const healthStatus = ref<'loading' | 'healthy' | 'unhealthy' | 'error'>('loading')

const form = reactive({
  username: '',
  password: '',
})

// ---- 记忆用户名 ----
const savedUsername = localStorage.getItem('remembered_username')
if (savedUsername) {
  form.username = savedUsername
  rememberUsername.value = true
}

// ---- 登录逻辑（与旧版完全相同，不修改） ----
async function handleLogin(): Promise<void> {
  // 从 GlassLoginCard 获取最新表单数据
  const card = loginCardRef.value
  if (!card) return

  // 同步表单数据
  form.username = card.form.username
  form.password = card.form.password

  // 基础检查
  if (!form.username.trim() || !form.password) return

  // 表单验证
  const valid = await card.formRef?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  errorMessage.value = ''

  try {
    await authStore.login({
      username: form.username.trim(),
      password: form.password,
    })

    if (rememberUsername.value) {
      localStorage.setItem('remembered_username', form.username.trim())
    } else {
      localStorage.removeItem('remembered_username')
    }

    // 按角色验证 redirect 参数
    const rawRedirect = route.query.redirect as string | undefined
    const isAdmin = authStore.isAdmin
    const validRedirect = resolvePostLoginRedirect(rawRedirect, isAdmin)
    const target = validRedirect || getDefaultRouteByRole(isAdmin)
    // 使用 replace 避免浏览器返回键回到登录页
    await router.replace(target)
  } catch (err: unknown) {
    errorMessage.value = extractLoginErrorMessage(err)
  } finally {
    loading.value = false
  }
}

// ---- 健康检查（与旧版完全相同，不修改） ----
async function checkHealth(): Promise<void> {
  healthStatus.value = 'loading'
  try {
    const response = await axios.get('/api/v1/health', { timeout: 5000 })
    const data = response.data

    const backendOk = data?.backend === true
    const databaseOk = data?.database === true
    const ragOk = data?.rag !== false

    if (response.status === 200 && backendOk && databaseOk && ragOk) {
      healthStatus.value = 'healthy'
    } else {
      healthStatus.value = 'unhealthy'
    }
  } catch {
    healthStatus.value = 'error'
  }
}

// ---- 生命周期 ----
onMounted(() => {
  errorMessage.value = ''
  authStore.silentCleanup()
  checkHealth()
})
</script>

<style lang="scss" scoped>
/* ============================================================
 * LoginView — 主布局样式（响应式改造第 2 阶段）
 *
 * 使用 Phase 1 统一断点体系：
 *   Mobile:  < 768px
 *   Tablet:  768px ~ 1199px
 *   Desktop: >= 1200px
 * ============================================================ */

.login-page {
  position: relative;
  min-height: var(--app-height);
  height: auto;
  display: flex;
  align-items: center;
  justify-content: center;
  /* 允许纵向滚动，解决移动端软键盘弹出后内容被遮挡的问题 */
  overflow-x: hidden;
  overflow-y: auto;
}

/* ============================================================
 * 桌面端 (>=1200px)：左右双栏 Grid 布局
 * ============================================================ */

.login-layout {
  position: relative;
  z-index: 2;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 440px);
  align-items: center;
  justify-items: center;
  width: min(1200px, calc(100% - 48px));
  padding: clamp(32px, 5vh, 56px) 0;
  gap: clamp(24px, 4vw, 56px);
}

/* 左侧品牌区域 */
.login-layout__brand {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 右侧登录卡片 */
.login-layout__card {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* ============================================================
 * 平板端 (768px ~ 1199px)：压缩双栏
 * 768-900px 区间双栏可能拥挤，切换为居中单栏
 * 使用容器查询在不引入全局断点的前提下处理内部布局
 * ============================================================ */

@media (min-width: 768px) and (max-width: 1199px) {
  .login-layout {
    grid-template-columns: minmax(0, 1fr) minmax(300px, 420px);
    width: min(960px, calc(100% - 32px));
    padding: clamp(24px, 4vh, 40px) 0;
    gap: clamp(16px, 3vw, 36px);
  }
}

/* 平板窄区间优化：当容器宽度不足时切换单栏 */
@container (max-width: 700px) {
  .login-layout {
    grid-template-columns: 1fr;
    max-width: 450px;
    margin: 0 auto;
    gap: 8px;
  }

  .login-layout__brand {
    padding-bottom: 0;
  }
}

/* ============================================================
 * 移动端 (<768px)：单栏布局，含 safe-area 适配
 * ============================================================ */

@media (max-width: 767px) {
  .login-page {
    align-items: flex-start;
    padding:
      calc(var(--page-padding-mobile) + var(--safe-area-top))
      max(var(--page-padding-mobile), var(--safe-area-right))
      calc(var(--page-padding-mobile) + var(--safe-area-bottom) + 20px)
      max(var(--page-padding-mobile), var(--safe-area-left));
  }

  .login-layout {
    grid-template-columns: 1fr;
    width: 100%;
    max-width: 420px;
    padding: 0;
    gap: 4px;
  }

  .login-layout__brand {
    padding-bottom: 0;
    width: 100%;
  }

  .login-layout__card {
    width: 100%;
  }
}

/* ============================================================
 * 矮屏幕适配（高度不足时减少间距）
 * ============================================================ */

@media (max-height: 700px) {
  .login-layout {
    padding: 16px 0;
  }

  .login-layout__brand {
    padding-bottom: 0;
  }
}

/* ============================================================
 * 大屏幕优化 (>=1600px)
 * ============================================================ */

@media (min-width: 1600px) {
  .login-layout {
    width: min(1400px, calc(100% - 64px));
    grid-template-columns: minmax(0, 1fr) minmax(380px, 480px);
  }
}
</style>
