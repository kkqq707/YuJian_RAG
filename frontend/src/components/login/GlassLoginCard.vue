<template>
  <!--
    GlassLoginCard — 右侧登录玻璃卡片

    材质：玻璃拟态（rgba(35,55,125,0.32) + blur(18px)）
    效果：多色边缘渐变光效、悬浮、进入动画
    包含：表单、输入框、登录按钮、健康状态指示器
    不修改任何登录逻辑，仅负责视觉呈现
  -->
  <div class="glass-login-card">
    <!-- 顶部微光线 -->
    <div class="card__shine" />

    <!-- 边缘渐变发光（多色） -->
    <div class="card__edge-glow" />

    <!-- 卡片内容 -->
    <div class="card__body">
      <!-- 标题区 -->
      <h2 class="card__heading">欢迎回来</h2>
      <p class="card__subheading">登录您的账户，开启智能知识之旅</p>

      <!-- 错误提示 -->
      <div v-if="errorMessage" class="card__error">
        <AlertCircle :size="16" />
        <span>{{ errorMessage }}</span>
      </div>

      <!-- 登录表单 -->
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        class="card__form"
        @submit.prevent="emit('login')"
      >
        <!-- 用户名 / 邮箱 -->
        <el-form-item prop="username">
          <el-input
            v-model="form.username"
            placeholder="用户名 / 邮箱"
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
            placeholder="密码"
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
        <div class="card__options">
          <el-checkbox
            :model-value="rememberUsername"
            size="small"
            class="remember-check"
            @update:model-value="emit('update:rememberUsername', $event as boolean)"
          >
            记住用户名
          </el-checkbox>
        </div>

        <!-- 登录按钮：多色动态渐变 -->
        <button
          class="card__btn"
          :class="{ 'is-loading': loading, 'is-disabled': !canSubmit }"
          :disabled="!canSubmit || loading"
          type="submit"
          @click="handleClick"
        >
          <!-- Loading：AI 旋转动画 -->
          <span v-if="loading" class="btn-loading">
            <span class="btn-ai-spinner">
              <span class="spinner-ring" />
              <span class="spinner-core" />
            </span>
            验证中...
          </span>
          <span v-else class="btn-text">登 录</span>
        </button>
      </el-form>

      <!-- 底部状态栏 -->
      <div class="card__footer">
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
import { ref, computed, watch } from 'vue'
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
watch(() => props.initialUsername, (val) => {
  if (!form.value.username) {
    form.value.username = val
  }
})

// ---- 验证规则 ----
const rules = {
  username: [{
    validator: (_rule: unknown, value: string, callback: (err?: Error) => void) => {
      const result = validateUsername(value)
      callback(result === true ? undefined : new Error(result as string))
    }, trigger: 'blur',
  }],
  password: [{
    validator: (_rule: unknown, value: string, callback: (err?: Error) => void) => {
      const result = validatePassword(value)
      callback(result === true ? undefined : new Error(result as string))
    }, trigger: 'blur',
  }],
}

// ---- 计算属性 ----
const canSubmit = computed(() => {
  return form.value.username.trim() !== '' && form.value.password !== '' && !props.loading
})

// ---- 点击按钮（含扩散波纹效果） ----
function handleClick(e: MouseEvent) {
  if (!canSubmit.value) return

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
    background: rgba(255,255,255,0.25);
    pointer-events: none;
    animation: glass-ripple-expand 0.6s ease-out forwards;
  `
  ripple.className = 'btn-ripple'
  btn.appendChild(ripple)
  ripple.addEventListener('animationend', () => ripple.remove())

  emit('login')
}

// ---- 暴露表单给父组件 ----
defineExpose({ formRef, form })
</script>

<style lang="scss" scoped>
/* ============================================================
 * GlassLoginCard — 企业级玻璃登录卡片
 * 材质：rgba(35,55,125,0.32) + blur(18px) saturate(130%)
 * 尺寸：max-width 450px
 * 多色动态背景透过卡片可见
 * ============================================================ */

.glass-login-card {
  position: relative;
  width: 100%;
  max-width: 450px;
  /* 降低透明度，让多色渐变背景更明显穿透卡片 */
  background: rgba(35, 55, 125, 0.32);
  backdrop-filter: blur(18px) saturate(130%);
  -webkit-backdrop-filter: blur(18px) saturate(130%);
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 24px;
  overflow: hidden;
  /* 多层阴影含蓝紫青色调，反射背景多色 */
  box-shadow:
    0 8px 48px rgba(0, 0, 0, 0.25),
    0 0 60px rgba(18, 104, 232, 0.08),
    0 0 100px rgba(114, 52, 216, 0.06),
    0 0 140px rgba(8, 168, 200, 0.04),
    inset 0 1px 0 rgba(255, 255, 255, 0.08);
  animation: card-enter 0.7s ease-out;
  transition:
    transform 0.35s ease,
    box-shadow 0.35s ease;

  &:hover {
    transform: translateY(-3px);
    box-shadow:
      0 12px 56px rgba(0, 0, 0, 0.3),
      0 0 80px rgba(18, 104, 232, 0.12),
      0 0 120px rgba(114, 52, 216, 0.09),
      0 0 160px rgba(8, 168, 200, 0.06),
      inset 0 1px 0 rgba(255, 255, 255, 0.1);
  }
}

@keyframes card-enter {
  from {
    opacity: 0;
    transform: translateY(28px) scale(0.97);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

/* ---- 顶部微光线（多色） ---- */
.card__shine {
  position: absolute;
  top: 0;
  left: 10%;
  right: 10%;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(18, 104, 232, 0.45),
    rgba(114, 52, 216, 0.45),
    rgba(179, 54, 217, 0.35),
    rgba(8, 168, 200, 0.3),
    transparent
  );
  opacity: 0.75;
  pointer-events: none;
  z-index: 2;
}

/* ---- 边缘渐变发光（多色旋转） ---- */
.card__edge-glow {
  position: absolute;
  inset: -1px;
  border-radius: 24px;
  padding: 1px;
  background: linear-gradient(
    160deg,
    rgba(18, 104, 232, 0.3),
    rgba(58, 50, 163, 0.25),
    rgba(114, 52, 216, 0.2),
    rgba(179, 54, 217, 0.18),
    rgba(8, 168, 200, 0.2),
    rgba(24, 184, 160, 0.15),
    rgba(18, 104, 232, 0.25)
  );
  background-size: 300% 300%;
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
  z-index: 1;
  animation: edge-glow-rotate 6s ease-in-out infinite;
}

@keyframes edge-glow-rotate {
  0% {
    background-position: 0% 0%;
    opacity: 0.4;
  }
  25% {
    background-position: 50% 30%;
    opacity: 0.7;
  }
  50% {
    background-position: 100% 60%;
    opacity: 0.55;
  }
  75% {
    background-position: 50% 90%;
    opacity: 0.75;
  }
  100% {
    background-position: 0% 0%;
    opacity: 0.4;
  }
}

/* ---- 卡片内容区 ---- */
.card__body {
  padding: 48px 42px;
  position: relative;
  z-index: 1;
}

/* ---- 标题 ---- */
.card__heading {
  font-size: 28px;
  font-weight: 700;
  color: #fff;
  margin: 0 0 8px;
  letter-spacing: 1px;
}

.card__subheading {
  font-size: 14px;
  color: rgba(200, 210, 230, 0.55);
  margin: 0 0 32px;
  letter-spacing: 0.5px;
  line-height: 1.6;
}

/* ---- 错误提示 ---- */
.card__error {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: 10px;
  padding: 10px 14px;
  color: #fca5a5;
  font-size: 13px;
  margin-bottom: 24px;
}

/* ---- 表单 ---- */
.card__form {
  :deep(.el-form-item) {
    margin-bottom: 20px;
  }

  :deep(.el-form-item__error) {
    font-size: 12px;
    padding-top: 4px;
    color: #fca5a5;
  }
}

/* ---- 输入框 — 白色半透明玻璃风格，focus 蓝紫发光 ---- */
:deep(.el-input) {
  --el-input-bg-color: rgba(255, 255, 255, 0.85);
  --el-input-border-color: transparent;
  --el-input-hover-border-color: rgba(255, 255, 255, 0.3);
  --el-input-focus-border-color: rgba(80, 140, 220, 0.6);
  --el-input-placeholder-color: rgba(100, 120, 160, 0.4);
  --el-input-text-color: #1a1a2e;
}

:deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.88) !important;
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
  background: rgba(255, 255, 255, 0.93) !important;
  border-color: rgba(200, 210, 230, 0.4) !important;
}

:deep(.el-input__wrapper.is-focus) {
  background: rgba(255, 255, 255, 0.96) !important;
  border-color: rgba(80, 140, 220, 0.55) !important;
  box-shadow:
    0 0 0 3px rgba(80, 140, 220, 0.12),
    0 0 24px rgba(100, 120, 220, 0.08) !important;
}

:deep(.el-input__inner) {
  color: #1a1a2e !important;
  font-size: 14px !important;

  &::placeholder {
    color: rgba(100, 120, 160, 0.38) !important;
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

/* ---- 密码切换按钮 ---- */
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
.card__options {
  display: flex;
  justify-content: flex-start;
  align-items: center;
  margin-bottom: 28px;
}

.remember-check {
  :deep(.el-checkbox__label) {
    color: rgba(200, 210, 230, 0.55);
    font-size: 13px;
  }
  :deep(.el-checkbox__inner) {
    background: rgba(255, 255, 255, 0.12);
    border-color: rgba(255, 255, 255, 0.2);
  }
}

/* ============================================================
 * 登录按钮 — 固定紫色渐变（无动画、无颜色变化）
 * 颜色：固定紫蓝渐变，始终不变
 * hover：仅微移 + 阴影增强，不改变颜色
 * 保留所有 loading / disabled / 点击逻辑
 * ============================================================ */
.card__btn {
  position: relative;
  width: 100%;
  height: 50px;
  font-size: 16px;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(
    90deg,
    #6638d9 0%,
    #8a35df 50%,
    #b33bd1 100%
  );
  background-size: 100% 100%;
  background-position: center;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  letter-spacing: 5px;
  overflow: hidden;
  isolation: isolate;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease,
    filter 0.2s ease;

  &:hover:not(:disabled):not(.is-loading) {
    transform: translateY(-1px);
    filter: brightness(1.03);
    box-shadow:
      0 6px 24px rgba(102, 56, 217, 0.25),
      0 0 40px rgba(138, 53, 223, 0.12);
  }

  &:active:not(:disabled):not(.is-loading) {
    transform: translateY(0) scale(0.98);
    filter: brightness(0.98);
  }

  &.is-disabled {
    opacity: 0.4;
    cursor: not-allowed;
    filter: grayscale(0.2);
  }

  &.is-loading {
    cursor: wait;
    opacity: 0.88;
  }
}

.btn-text {
  position: relative;
  z-index: 1;
}

/* ---- Loading：AI 旋转动画 ---- */
.btn-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  position: relative;
  z-index: 1;
}

.btn-ai-spinner {
  position: relative;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.spinner-ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-top-color: #fff;
  border-right-color: rgba(168, 85, 247, 0.6);
  animation: ai-spin 0.8s linear infinite;
}

.spinner-core {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.7);
  box-shadow: 0 0 8px rgba(255, 255, 255, 0.4);
  animation: core-pulse 0.8s ease-in-out infinite;
}

@keyframes ai-spin {
  to { transform: rotate(360deg); }
}

@keyframes core-pulse {
  0%, 100% { transform: scale(0.8); opacity: 0.5; }
  50% { transform: scale(1.2); opacity: 1; }
}

/* ---- 底部状态栏 ---- */
.card__footer {
  margin-top: 32px;
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
    box-shadow: 0 0 8px rgba(52, 211, 153, 0.5);
  }
  &--warning {
    background: #fbbf24;
    box-shadow: 0 0 8px rgba(251, 191, 36, 0.5);
  }
  &--offline {
    background: #f87171;
    box-shadow: 0 0 8px rgba(248, 113, 113, 0.5);
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
  color: rgba(180, 200, 220, 0.48);
  letter-spacing: 0.3px;

  &--warning { color: #fbbf24; }
  &--offline { color: #f87171; }
}

.version-label {
  font-size: 12px;
  color: rgba(180, 200, 220, 0.32);
  letter-spacing: 0.5px;
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
}

/* ---- 全局波纹动画 ---- */
:global(.btn-ripple) {
  animation: glass-ripple-expand 0.6s ease-out forwards !important;
}

@keyframes glass-ripple-expand {
  0% { transform: scale(0); opacity: 1; }
  100% { transform: scale(4); opacity: 0; }
}

/* ============================================================
 * 性能与无障碍 — 减少动态模式
 * ============================================================ */

@media (prefers-reduced-motion: reduce) {
  .card__edge-glow {
    animation: none;
    opacity: 0.4;
  }
}

/* ============================================================
 * 响应式
 * ============================================================ */

@media (max-width: 900px) {
  .card__body {
    padding: 40px 34px;
  }
}

@media (max-width: 480px) {
  .glass-login-card {
    border-radius: 20px;
  }
  .card__body {
    padding: 30px 24px;
  }
  .card__heading {
    font-size: 24px;
  }
  .card__subheading {
    font-size: 13px;
    margin-bottom: 24px;
  }
}
</style>
