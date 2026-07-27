<template>
  <div class="profile-view">
    <div class="profile-view__container">
      <h2 class="page-title">个人中心</h2>

      <!-- 用户信息卡片 -->
      <div class="app-card profile-card">
        <div class="profile-info">
          <el-avatar :size="64" icon="UserFilled" class="profile-avatar" />
          <div class="profile-details">
            <h3>{{ authStore.displayName }}</h3>
            <p class="profile-username">@{{ authStore.user?.username }}</p>
            <el-tag size="small" :type="authStore.isAdmin ? 'danger' : 'info'">
              {{ authStore.isAdmin ? '管理员' : '普通用户' }}
            </el-tag>
          </div>
        </div>
      </div>

      <!-- 修改密码 -->
      <div class="app-card profile-password-card">
        <h3 class="card-title">修改密码</h3>
        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-width="100px"
          label-position="top"
          class="password-form"
        >
          <el-form-item label="旧密码" prop="oldPassword">
            <el-input
              v-model="form.oldPassword"
              type="password"
              placeholder="请输入旧密码"
              show-password
              autocomplete="current-password"
            />
          </el-form-item>

          <el-form-item label="新密码" prop="newPassword">
            <el-input
              v-model="form.newPassword"
              type="password"
              placeholder="至少 10 个字符，需包含字母和数字"
              show-password
              autocomplete="new-password"
            />
          </el-form-item>

          <el-form-item label="确认新密码" prop="confirmPassword">
            <el-input
              v-model="form.confirmPassword"
              type="password"
              placeholder="请再次输入新密码"
              show-password
              autocomplete="new-password"
            />
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              :loading="changing"
              :disabled="changing"
              @click="handleChangePassword"
            >
              修改密码
            </el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- 退出登录 -->
      <div class="app-card profile-logout-card">
        <div class="logout-info">
          <div>
            <h4>退出登录</h4>
            <p class="text-secondary text-sm">退出当前账号，返回登录页面</p>
          </div>
          <el-popconfirm
            title="确定要退出登录吗？"
            confirm-button-text="退出"
            cancel-button-text="取消"
            width="200"
            @confirm="handleLogout"
          >
            <template #reference>
              <el-button type="danger" plain>退出登录</el-button>
            </template>
          </el-popconfirm>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { useChatStore } from '@/stores/chat'
import { validateNewPassword } from '@/utils/validators'

const router = useRouter()
const authStore = useAuthStore()
const appStore = useAppStore()
const chatStore = useChatStore()

// ---- 表单 ----
const formRef = ref<FormInstance>()
const changing = ref(false)

const form = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
})

const validateConfirmPassword = (_rule: unknown, value: string, callback: (error?: Error) => void) => {
  if (!value) {
    callback(new Error('请确认新密码'))
  } else if (value !== form.newPassword) {
    callback(new Error('两次输入的新密码不一致'))
  } else {
    callback()
  }
}

const rules: FormRules = {
  oldPassword: [
    { required: true, message: '请输入旧密码', trigger: 'blur' },
  ],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        const result = validateNewPassword(value)
        if (result === true) {
          callback()
        } else {
          callback(new Error(result))
        }
      },
      trigger: 'blur',
    },
  ],
  confirmPassword: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' },
  ],
}

// ---- 操作 ----

async function handleChangePassword() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  changing.value = true
  try {
    await authStore.changePassword(form.oldPassword, form.newPassword)
    ElMessage.success('密码修改成功，请重新登录')
    router.push('/login')
  } catch (error: unknown) {
    const msg = (error as { response?: { data?: { message?: string } } })?.response?.data?.message
      || '密码修改失败'
    ElMessage.error(msg)
  } finally {
    changing.value = false
  }
}

async function handleLogout() {
  chatStore.reset()
  await authStore.logout()
  appStore.reset()
  router.push('/login')
}
</script>

<style lang="scss" scoped>
.profile-view {
  height: 100vh;
  overflow-y: auto;
  background: $color-page-bg;
}

.profile-view__container {
  max-width: 640px;
  margin: 0 auto;
  padding: $page-padding;
}

// ---- 用户信息卡片 ----
.profile-card {
  margin-bottom: $spacing-lg;
}

.profile-info {
  display: flex;
  align-items: center;
  gap: $spacing-lg;
}

.profile-avatar {
  flex-shrink: 0;
}

.profile-details {
  h3 {
    font-size: $font-size-xl;
    font-weight: 600;
    color: $color-text-primary;
    margin-bottom: 4px;
  }
}

.profile-username {
  font-size: $font-size-sm;
  color: $color-text-secondary;
  margin-bottom: $spacing-sm;
}

// ---- 修改密码 ----
.profile-password-card {
  margin-bottom: $spacing-lg;

  .card-title {
    font-size: $font-size-lg;
    font-weight: 600;
    color: $color-text-primary;
    margin-bottom: $spacing-lg;
  }
}

.password-form {
  max-width: 400px;
}

// ---- 退出登录 ----
.profile-logout-card {
  .logout-info {
    display: flex;
    align-items: center;
    justify-content: space-between;

    h4 {
      font-size: $font-size-base;
      font-weight: 500;
      color: $color-text-primary;
      margin-bottom: 2px;
    }
  }
}

@media (max-width: 768px) {
  .profile-view__container {
    padding: $spacing-md;
  }
  .profile-info {
    flex-direction: column;
    text-align: center;
  }
  .logout-info {
    flex-direction: column;
    gap: $spacing-md;
    text-align: center;
  }
}
</style>
