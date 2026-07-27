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

    const redirect = (route.query.redirect as string) || ''
    if (authStore.isAdmin) {
      router.push(redirect || '/admin/dashboard')
    } else {
      router.push(redirect || '/chat')
    }
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
 * LoginView — 主布局样式
 * ============================================================ */

.login-page {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

/* ---- 主布局：桌面端左右分栏 ---- */
.login-layout {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  max-width: 1280px;
  padding: 48px 56px;
  gap: 0;
}

/* 左侧品牌区域 — 45% */
.login-layout__brand {
  flex: 0 0 45%;
  max-width: 45%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding-right: 56px;
}

/* 右侧登录卡片 — 55% */
.login-layout__card {
  flex: 0 0 55%;
  max-width: 55%;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* ============================================================
 * 响应式 — 平板及以下：上下布局
 * ============================================================ */

@media (max-width: 900px) {
  .login-layout {
    flex-direction: column;
    padding: 32px 24px;
    gap: 0;
  }

  .login-layout__brand {
    flex: none;
    max-width: 100%;
    width: 100%;
    padding-right: 0;
    padding-bottom: 8px;
  }

  .login-layout__card {
    flex: none;
    max-width: 100%;
    width: 100%;
    max-width: 450px;
  }
}

/* 小屏手机 */
@media (max-width: 480px) {
  .login-layout {
    padding: 20px 16px;
  }
}

/* 矮屏幕 */
@media (max-height: 700px) {
  .login-layout {
    padding: 20px 40px;
  }

  .login-layout__brand {
    padding-bottom: 0;
  }
}

/* 大屏幕优化 */
@media (min-width: 1600px) {
  .login-layout {
    max-width: 1440px;
  }
}
</style>
