/**
 * 管理员系统管理 API
 */

import request from './request'
import type {
  AdminSystemStatusResponse,
  AuditLogResponse,
  SystemLogListResponse,
  SystemLogDetail,
  HealthCheckResponse,
  SystemSettingsResponse,
  SystemInfoResponse,
  SecuritySettingsResponse,
  JWTRegenResponse,
  ModuleItem,
} from '@/types/api'

const adminSystemApi = {
  /** 获取完整系统状态 */
  getSystemStatus(): Promise<AdminSystemStatusResponse> {
    return request.get('/admin/system').then((res) => res.data)
  },

  /** 获取审计日志 */
  getAuditLogs(params?: {
    skip?: number
    limit?: number
    action?: string
    admin_id?: number
  }): Promise<AuditLogResponse> {
    return request.get('/admin/system/logs', { params }).then((res) => res.data)
  },

  /** 获取系统日志（增强版） */
  getSystemLogs(params?: {
    page?: number
    page_size?: number
    module?: string
    status?: string
    username?: string
    start_time?: string
    end_time?: string
  }): Promise<SystemLogListResponse> {
    return request.get('/admin/logs', { params }).then((res) => res.data)
  },

  /** 获取系统日志详情 */
  getLogDetail(id: number): Promise<SystemLogDetail> {
    return request.get(`/admin/logs/${id}`).then((res) => res.data)
  },

  /** 系统健康检查 */
  getHealthCheck(): Promise<HealthCheckResponse> {
    return request.get('/admin/system/health').then((res) => res.data)
  },

  /** 获取系统信息 */
  getSystemInfo(): Promise<SystemInfoResponse> {
    return request.get('/admin/system/info').then((res) => res.data)
  },

  /** 获取模块列表 */
  getModules(): Promise<{ success: boolean; modules: ModuleItem[] }> {
    return request.get('/admin/system/modules').then((res) => res.data)
  },

  /** 获取安全设置 */
  getSecuritySettings(): Promise<SecuritySettingsResponse> {
    return request.get('/admin/system/security').then((res) => res.data)
  },

  /** 重新生成 JWT */
  regenerateJWT(): Promise<JWTRegenResponse> {
    return request.post('/admin/system/jwt/regenerate').then((res) => res.data)
  },

  /** 获取系统设置 */
  getSettings(): Promise<SystemSettingsResponse> {
    return request.get('/admin/system/settings').then((res) => res.data)
  },

  /** 保存系统设置 */
  saveSettings(settings: Record<string, string>): Promise<SystemSettingsResponse> {
    return request.put('/admin/system/settings', { settings }).then((res) => res.data)
  },
}

export default adminSystemApi
