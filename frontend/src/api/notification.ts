import http from './http'

export interface StudentNotification {
  id: number
  type: 'project_review' | string
  title: string
  content: string
  project_id: number | null
  is_read: boolean
  created_at: string
}

export function getNotifications() {
  return http.get<any, StudentNotification[]>('/notifications')
}

export function getNotificationUnreadCount() {
  return http.get<any, { count: number }>('/notifications/unread-count')
}

export function markNotificationRead(id: number) {
  return http.post<any, any>(`/notifications/${id}/read`)
}
