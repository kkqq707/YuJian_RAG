<template>
  <!--
    LoginCard — 右侧登录玻璃卡片

    材质：玻璃拟态（rgba(255,255,255,0.18) + blur(30px)）
    包含：表单、输入框、登录按钮、健康状态指示器
    不修改任何登录逻辑，仅负责视觉呈现
  -->
  <div class="login-card">
    <!-- 顶部微光边 -->
    <div class="login-card__shine" />

    <!-- 卡片内容 -->
    <div class="login-card__body">
      <!-- 卡片标题 -->
      <h2 class="login-card__heading">欢迎回来</h2>
      <p class="login-card__subheading">登录您的账户以继续</p>

      <!-- 错误提示 -->
      <div v-if="errorMessage" class="login-card__error">
        <AlertCircle :size="16" />
        <span>{{ errorMessage }}</span>
      </div>

      <!-- 登录表单 -->
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        class="login-card__form"
        @submit.prevent="emit('login')"
      >
        <!-- 用户名 -->
        <el-form-item prop="username">
          <el-input
            v-model="form.username"
            placeholder="请输入用户名"
            size="large"
            auto-complete="username"
            @keyup.enter="emit('login')"
          >
            <template #prefix>
              <User :size="18" class="input-icon" />
            </template>
          </el-input>
        </el-form-item>

        <!-- 密码 -->
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            :type="showPassword ? 'text' : 'password'"
            placeholder="请输入密码"
            size="large"
            auto-complete="current-password"
            @keyup.enter="emit('login')"
          >
            <template #prefix>
              <Lock :size="18" class="input-icon" />
            </template>
            <template #suffix>
              <button
                type="button"
                class="pwd-toggle"
                tabindex="-1"
                @click="showPassword = !showPassword"
              >
                <Eye v-if="!showPassword" :size="18" />
                <EyeOff v-else :size="18" />
              </button>
            </template>
          </el-input>
        </el-form-item>

        <!-- 记住用户名 -->
        <div class="login-card__options">
          <el-checkbox
            :model-value="rememberUsername"
            size="small"
            class="remember-check"
            @update:model-value="emit('update:rememberUsername', $event as boolean)"
          >
            记住用户名
          </el-checkbox>
        </div>

        <!-- 登录按钮 -->
        <button
          class="login-card__btn"
          :class="{ 'is-loading': loading, 'is-disabled': !canSubmit }"
          :disabled="!canSubmit || loading"
          type="submit"
          @click="handleClick"
        >
          <span v-if="loading" class="btn-loading">
            <span class="btn-spinner" />
            验证中...
          </span>
          <span v-else class="btn-text">登 录</span>
        </button>
      </el-form>

      <!-- 底部状态栏 -->
      <div class="login-card__footer">
        <div class="health-status">
          <template v-if="healthStatus === 'loading'">
            <span class="status-dot status-dot--loading" />
            <span class="status-label">检测服务状态...</span>
          </template>
          <template v-else-if="healthStatus === 'healthy'">
            <span class="status-dot status-dot--online" />
            <span class="status-label">系统在线</span>
          </template>
          <template v-else-if="healthStatus === 'unhealthy'">
            <span class="status-dot status-dot--warning" />
            <span class="status-label status-label--warning">服务异常</span>
          </template>
          <template v-else>
            <span class="status-dot status-dot--offline" />
            <span class="status-label status-label--offline">连接失败</span>
          </template>
        </div>
        <span class="version-label">v1.0 企业版</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { User, Lock, Eye, EyeOff, AlertCircle } from '@lucide/vue'
import { validateUsername, validatePassword } from '@/utils/validators'
import type { FormInstance } from 'element-plus'

// ---- Props ----
const props = defineProps<{
  loading: boolean
  errorMessage: string
  healthStatus: 'loading' | 'healthy' | 'unhealthy' | 'error'
  rememberUsername: boolean
  initialUsername: string
}>()

// ---- Emits ----
const emit = defineEmits<{
  login: []
  'update:rememberUsername': [value: boolean]
}>()

// ---- Refs ----
const formRef = ref<FormInstance>()
const showPassword = ref(false)

const form = ref({
  username: props.initialUsername,
  password: '',
})

// 同步外部用户名变更
import { watch } from 'vue'
watch(() => props.initialUsername, (val) => {
  if (!form.value.username) {
    form.value.username = val
  }
})

// ---- 验证规则 ----
const rules = {
  username: [{ validator: (_rule: unknown, value: string, callback: (err?: Error) => void) => {
    const result = validateUsername(value)
    callback(result === true ? undefined : new Error(result as string))
  }, trigger: 'blur' }],
  password: [{ validator: (_rule: unknown, value: string, callback: (err?: Error) => void) => {
    const result = validatePassword(value)
    callback(result === true ? undefined : new Error(result as string))
  }, trigger: 'blur' }],
}

// ---- 计算属性 ----
const canSubmit = computed(() => {
  return form.value.username.trim() !== '' && form.value.password !== '' && !props.loading
})

// ---- 点击按钮（含水波效果） ----
function handleClick(e: MouseEvent) {
  if (!canSubmit.value) return

  // 水波扩散效果
  const btn = e.currentTarget as HTMLElement
  const ripple = document.createElement('span')
  const rect = btn.getBoundingClientRect()
  const size = Math.max(rect.width, rect.height)
  ripple.style.cssText = `
    position: absolute;
    width: ${size}px;
    height: ${size}px;
    left: ${e.clientX - rect.left - size / 2}px;
    top: ${e.clientY - rect.top - size / 2}px;
    border-radius: 50%;
    background: rgba(255,255,255,0.2);
    pointer-events: none;
    animation: ripple-expand 0.6s ease-out forwards;
  `
  ripple.className = 'btn-ripple'
  btn.appendChild(ripple)
  ripple.addEventListener('animationend', () => ripple.remove())

  emit('login')
}

// ---- 暴露表单给父组件验证 ----
defineExpose({ formRef, form })
</script>

<style lang="scss" scoped>
/* ============================================================
 * LoginCard — 企业级玻璃登录卡片
 * ============================================================ */

.login-card {
  position: relative;
  width: 100%;
  max-width: 440px;
  background: rgba(255, 255, 255, 0.18);
  backdrop-filter: blur(30px);
  -webkit-backdrop-filter: blur(30px);
  border: 1px solid rgba(255, 255, 255, 0.25);
  border-radius: 24px;
  overflow: hidden;
  box-shadow:
    0 8px 40px rgba(0, 0, 0, 0.2),
    0 0 80px rgba(80, 120, 220, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.1);
  animation: card-enter 0.6s ease-out;
}

@keyframes card-enter {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 顶部微光线 */
.login-card__shine {
  position: absolute;
  top: 0;
  left: 10%;
  right: 10%;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(180, 200, 240, 0.5),
    rgba(160, 140, 230, 0.5),
    transparent
  );
  opacity: 0.7;
  pointer-events: none;
  z-index: 2;
}

/* 卡片内容区 */
.login-card__body {
  padding: 44px 40px;
  position: relative;
  z-index: 1;
}

/* ---- 标题 ---- */
.login-card__heading {
  font-size: 26px;
  font-weight: 700;
  color: #fff;
  margin: 0 0 6px;
  letter-spacing: 1px;
}

.login-card__subheading {
  font-size: 14px;
  color: rgba(200, 210, 230, 0.55);
  margin: 0 0 28px;
  letter-spacing: 0.5px;
}

/* ---- 错误提示 ---- */
.login-card__error {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: 10px;
  padding: 10px 14px;
  color: #fca5a5;
  font-size: 13px;
  margin-bottom: 22px;
}

/* ---- 表单 ---- */
.login-card__form {
  :deep(.el-form-item) {
    margin-bottom: 18px;
  }

  :deep(.el-form-item__error) {
    font-size: 12px;
    padding-top: 4px;
    color: #fca5a5;
  }
}

/* ---- 输入框 — 白色半透明玻璃风格 ---- */
:deep(.el-input) {
  --el-input-bg-color: rgba(255, 255, 255, 0.85);
  --el-input-border-color: transparent;
  --el-input-hover-border-color: rgba(255, 255, 255, 0.3);
  --el-input-focus-border-color: rgba(80, 140, 220, 0.6);
  --el-input-placeholder-color: rgba(100, 120, 160, 0.4);
  --el-input-text-color: #1a1a2e;
}

:deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.85) !important;
  border: 1px solid rgba(255, 255, 255, 0.3) !important;
  border-radius: 12px !important;
  box-shadow: none !important;
  padding: 2px 16px !important;
  transition:
    background 0.25s ease,
    border-color 0.25s ease,
    box-shadow 0.25s ease !important;
}

:deep(.el-input__wrapper:hover) {
  background: rgba(255, 255, 255, 0.92) !important;
  border-color: rgba(200, 210, 230, 0.4) !important;
}

:deep(.el-input__wrapper.is-focus) {
  background: rgba(255, 255, 255, 0.95) !important;
  border-color: rgba(80, 140, 220, 0.5) !important;
  box-shadow:
    0 0 0 3px rgba(80, 140, 220, 0.1),
    0 0 20px rgba(80, 140, 220, 0.06) !important;
}

:deep(.el-input__inner) {
  color: #1a1a2e !important;
  font-size: 14px !important;

  &::placeholder {
    color: rgba(100, 120, 160, 0.4) !important;
    font-size: 13px;
  }
}

.input-icon {
  color: rgba(120, 140, 180, 0.55);
  transition: color 0.25s ease;
}

:deep(.el-input__wrapper.is-focus) .input-icon {
  color: rgba(80, 120, 200, 0.7);
}

/* ---- 密码切换 ---- */
.pwd-toggle {
  background: none;
  border: none;
  color: rgba(120, 140, 180, 0.5);
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  transition: color 0.2s ease;

  &:hover {
    color: rgba(140, 160, 200, 0.7);
  }
}

/* ---- 记住用户名 ---- */
.login-card__options {
  display: flex;
  justify-content: flex-start;
  align-items: center;
  margin-bottom: 26px;
}

.remember-check {
  :deep(.el-checkbox__label) {
    color: rgba(200, 210, 230, 0.55);
    font-size: 13px;
  }
  :deep(.el-checkbox__inner) {
    background: rgba(255, 255, 255, 0.15);
    border-color: rgba(255, 255, 255, 0.2);
  }
}

/* ---- 登录按钮 — 渐变蓝紫 ---- */
.login-card__btn {
  position: relative;
  width: 100%;
  height: 48px;
  font-size: 16px;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, #4facfe 0%, #7b6af0 50%, #8f5cff 100%);
  border: none;
  border-radius: 12px;
  cursor: pointer;
  letter-spacing: 4px;
  overflow: hidden;
  isolation: isolate;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease,
    filter 0.2s ease;

  &:hover:not(:disabled):not(.is-loading) {
    transform: translateY(-2px);
    filter: brightness(1.05);
    box-shadow:
      0 8px 30px rgba(79, 172, 254, 0.3),
      0 0 60px rgba(143, 92, 255, 0.15);
  }

  &:active:not(:disabled):not(.is-loading) {
    transform: translateY(0) scale(0.98);
    filter: brightness(0.97);
  }

  &.is-disabled {
    opacity: 0.4;
    cursor: not-allowed;
    filter: grayscale(0.2);
  }

  &.is-loading {
    cursor: wait;
    opacity: 0.85;
  }
}

.btn-text {
  position: relative;
  z-index: 1;
}

.btn-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  position: relative;
  z-index: 1;
}

.btn-spinner {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.25);
  border-top-color: #fff;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ---- 底部状态栏 ---- */
.login-card__footer {
  margin-top: 30px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.health-status {
  display: flex;
  align-items: center;
  gap: 7px;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;

  &--online {
    background: #34d399;
    box-shadow: 0 0 6px rgba(52, 211, 153, 0.5);
  }
  &--warning {
    background: #fbbf24;
    box-shadow: 0 0 6px rgba(251, 191, 36, 0.5);
  }
  &--offline {
    background: #f87171;
    box-shadow: 0 0 6px rgba(248, 113, 113, 0.5);
  }
  &--loading {
    background: #64748b;
    animation: dot-pulse 1.2s ease-in-out infinite;
  }
}

@keyframes dot-pulse {
  0%, 100% { opacity: 0.4; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1); }
}

.status-label {
  font-size: 12px;
  color: rgba(180, 200, 220, 0.5);
  letter-spacing: 0.3px;

  &--warning { color: #fbbf24; }
  &--offline { color: #f87171; }
}

.version-label {
  font-size: 12px;
  color: rgba(180, 200, 220, 0.35);
  letter-spacing: 0.5px;
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
}

/* 全局波纹动画 */
:global(.btn-ripple) {
  animation: ripple-expand 0.6s ease-out forwards !important;
}

@keyframes ripple-expand {
  0% { transform: scale(0); opacity: 1; }
  100% { transform: scale(4); opacity: 0; }
}

/* ============================================================
 * 响应式
 * ============================================================ */

@media (max-width: 900px) {
  .login-card__body {
    padding: 36px 32px;
  }
}

@media (max-width: 480px) {
  .login-card {
    border-radius: 20px;
  }
  .login-card__body {
    padding: 28px 22px;
  }
  .login-card__heading {
    font-size: 22px;
  }
}
</style>
