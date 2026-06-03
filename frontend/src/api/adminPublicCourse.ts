import http from './http'
import type { Material, MaterialCreatePayload } from './material'
import type { Question } from './question'

export interface AdminPublicCourse {
  id: number
  name: string
  created_at: string
  created_by: string
  is_public: boolean
  material_count: number
  question_count: number
}

export type AdminMaterialPayload = Omit<MaterialCreatePayload, 'course_id'>

export interface AdminQuestionPayload {
  type: 'choice' | 'fill'
  stem: string
  options: string[]
  answer: string
  explanation: string
}

export function getAdminPublicCourses() {
  return http.get<any, AdminPublicCourse[]>('/admin/public-courses')
}

export function createAdminPublicCourse(data: { name: string }) {
  return http.post<any, AdminPublicCourse>('/admin/public-courses', data)
}

export function updateAdminPublicCourse(id: number, data: { name: string }) {
  return http.put<any, AdminPublicCourse>(`/admin/public-courses/${id}`, data)
}

export function deleteAdminPublicCourse(id: number) {
  return http.delete<any, any>(`/admin/public-courses/${id}`)
}

export function getAdminPublicMaterials(courseId: number) {
  return http.get<any, Material[]>(`/admin/public-courses/${courseId}/materials`)
}

export function createAdminPublicMaterial(courseId: number, data: AdminMaterialPayload) {
  return http.post<any, Material>(`/admin/public-courses/${courseId}/materials`, data)
}

export function updateAdminPublicMaterial(courseId: number, materialId: number, data: AdminMaterialPayload) {
  return http.put<any, Material>(`/admin/public-courses/${courseId}/materials/${materialId}`, data)
}

export function deleteAdminPublicMaterial(courseId: number, materialId: number) {
  return http.delete<any, any>(`/admin/public-courses/${courseId}/materials/${materialId}`)
}

export function getAdminPublicQuestions(courseId: number) {
  return http.get<any, Question[]>(`/admin/public-courses/${courseId}/questions`)
}

export function createAdminPublicQuestion(courseId: number, data: AdminQuestionPayload) {
  return http.post<any, Question>(`/admin/public-courses/${courseId}/questions`, data)
}

export function updateAdminPublicQuestion(courseId: number, questionId: number, data: AdminQuestionPayload) {
  return http.put<any, Question>(`/admin/public-courses/${courseId}/questions/${questionId}`, data)
}

export function deleteAdminPublicQuestion(courseId: number, questionId: number) {
  return http.delete<any, any>(`/admin/public-courses/${courseId}/questions/${questionId}`)
}
