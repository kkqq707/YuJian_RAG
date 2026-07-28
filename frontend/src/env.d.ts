/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<object, object, unknown>
  export default component
}

// Vue Router 路由元信息类型扩展
export {}

declare module 'vue-router' {
  interface RouteMeta {
    /** 是否需要登录认证 */
    requiresAuth?: boolean
    /** 仅管理员可访问 */
    adminOnly?: boolean
    /** 仅普通用户可访问（管理员禁止） */
    userOnly?: boolean
    /** 页面标题 */
    title?: string
    /** @deprecated 使用 adminOnly / userOnly 替代 */
    roles?: string[]
    /** 菜单图标名 */
    icon?: string
  }
}
