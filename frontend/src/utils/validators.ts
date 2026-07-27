/**
 * 表单验证工具
 */

/** 验证用户名非空 */
export function validateUsername(value: string): string | true {
  if (!value || !value.trim()) {
    return '请输入用户名'
  }
  if (value.trim().length > 150) {
    return '用户名长度不能超过 150 个字符'
  }
  return true
}

/** 验证密码非空 */
export function validatePassword(value: string): string | true {
  if (!value) {
    return '请输入密码'
  }
  if (value.length < 1) {
    return '请输入密码'
  }
  return true
}

/** 验证新密码强度 */
export function validateNewPassword(value: string): string | true {
  if (!value) {
    return '请输入新密码'
  }
  if (value.length < 10) {
    return '密码至少需要 10 个字符'
  }
  if (!/[a-zA-Z]/.test(value)) {
    return '密码必须包含字母'
  }
  if (!/[0-9]/.test(value)) {
    return '密码必须包含数字'
  }
  return true
}
