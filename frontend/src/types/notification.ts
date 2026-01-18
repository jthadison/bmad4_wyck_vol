/**
 * Notification type definitions
 *
 * TypeScript interfaces matching backend Pydantic models.
 * Story: 11.6 - Notification & Alert System
 */

export enum NotificationType {
  SIGNAL_GENERATED = 'signal_generated',
  RISK_WARNING = 'risk_warning',
  EMERGENCY_EXIT = 'emergency_exit',
  SYSTEM_ERROR = 'system_error',
}

export enum NotificationPriority {
  INFO = 'info',
  WARNING = 'warning',
  CRITICAL = 'critical',
}

export enum NotificationChannel {
  TOAST = 'toast',
  EMAIL = 'email',
  SMS = 'sms',
  PUSH = 'push',
}

export interface Notification {
  id: string
  notification_type: NotificationType
  priority: NotificationPriority
  title: string
  message: string
  metadata: Record<string, unknown>
  user_id: string
  read: boolean
  created_at: string
}

export interface QuietHours {
  enabled: boolean
  start_time: string // HH:MM format
  end_time: string // HH:MM format
  timezone: string
}

export interface ChannelPreferences {
  info_channels: NotificationChannel[]
  warning_channels: NotificationChannel[]
  critical_channels: NotificationChannel[]
}

export interface NotificationPreferences {
  user_id: string
  email_enabled: boolean
  email_address?: string
  sms_enabled: boolean
  sms_phone_number?: string
  push_enabled: boolean
  min_confidence_threshold: number
  quiet_hours: QuietHours
  channel_preferences: ChannelPreferences
  updated_at: string
}

export interface NotificationToast {
  type: 'notification_toast'
  sequence_number: number
  notification: Notification
  timestamp: string
}

export interface PushSubscription {
  user_id: string
  endpoint: string
  p256dh_key: string
  auth_key: string
  created_at: string
}

export interface NotificationResponse {
  success: boolean
  message?: string
  notification_id?: string
}

export interface PaginationInfo {
  returned_count: number
  total_count: number
  limit: number
  offset: number
  has_more: boolean
}

export interface NotificationListResponse {
  data: Notification[]
  pagination: PaginationInfo
}
