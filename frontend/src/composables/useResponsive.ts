/**
 * useResponsive — 统一响应式设备判断 composable
 *
 * 基于 window.matchMedia，不使用持续监听 window.innerWidth。
 * 正确注册和清理监听器，组件卸载后不残留事件。
 * 所有调用者使用统一断点，不允许各自定义不同断点。
 *
 * 断点规范：
 *   Mobile:  < 768px
 *   Tablet:  768px ~ 1199px
 *   Desktop: ≥ 1200px
 */

import { ref, onUnmounted, readonly, type Ref } from 'vue'

/** 统一媒体查询字符串（与 breakpoints.css 保持一致） */
export const MOBILE_MEDIA_QUERY = '(max-width: 767px)'
export const TABLET_MEDIA_QUERY =
  '(min-width: 768px) and (max-width: 1199px)'
export const DESKTOP_MEDIA_QUERY = '(min-width: 1200px)'

export interface ResponsiveState {
  readonly isMobile: Ref<boolean>
  readonly isTablet: Ref<boolean>
  readonly isDesktop: Ref<boolean>
}

/**
 * 检查当前是否在浏览器环境
 * 支持 SSR 和测试环境下没有 window 的情况
 */
function hasWindow(): boolean {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function'
}

/**
 * 使用 matchMedia 创建响应式查询
 *
 * @returns 只读响应式状态 { isMobile, isTablet, isDesktop }
 */
export function useResponsive(): ResponsiveState {
  const isMobile = ref(false)
  const isTablet = ref(false)
  const isDesktop = ref(false)

  // SSR / 无 window 环境：全部返回 false，不抛异常
  if (!hasWindow()) {
    return {
      isMobile: readonly(isMobile),
      isTablet: readonly(isTablet),
      isDesktop: readonly(isDesktop),
    }
  }

  // 创建 matchMedia 查询
  const mobileQuery = window.matchMedia(MOBILE_MEDIA_QUERY)
  const tabletQuery = window.matchMedia(TABLET_MEDIA_QUERY)
  const desktopQuery = window.matchMedia(DESKTOP_MEDIA_QUERY)

  // 初始化当前值
  isMobile.value = mobileQuery.matches
  isTablet.value = tabletQuery.matches
  isDesktop.value = desktopQuery.matches

  // change 事件处理器
  function onMobileChange(e: MediaQueryListEvent) {
    isMobile.value = e.matches
  }
  function onTabletChange(e: MediaQueryListEvent) {
    isTablet.value = e.matches
  }
  function onDesktopChange(e: MediaQueryListEvent) {
    isDesktop.value = e.matches
  }

  // 注册监听器
  mobileQuery.addEventListener('change', onMobileChange)
  tabletQuery.addEventListener('change', onTabletChange)
  desktopQuery.addEventListener('change', onDesktopChange)

  // 组件卸载后移除监听器
  onUnmounted(() => {
    mobileQuery.removeEventListener('change', onMobileChange)
    tabletQuery.removeEventListener('change', onTabletChange)
    desktopQuery.removeEventListener('change', onDesktopChange)
  })

  return {
    isMobile: readonly(isMobile),
    isTablet: readonly(isTablet),
    isDesktop: readonly(isDesktop),
  }
}
