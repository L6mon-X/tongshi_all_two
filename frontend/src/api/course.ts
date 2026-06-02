import http from './http'

export interface Course {
  id: number
  name: string
  created_at: string
  material_count: number
  question_count: number
  class_count: number
}

export type CourseDetail = Course

export function getCourses() {
  return http.get<any, Course[]>('/courses')
}

export function getCourseDetail(id: number) {
  return http.get<any, CourseDetail>(`/courses/${id}`)
}

export function createCourse(data: { name: string }) {
  return http.post<any, { id: number }>('/courses', data)
}

export function updateCourse(id: number, data: { name: string }) {
  return http.put<any, any>(`/courses/${id}`, data)
}

export function deleteCourse(id: number) {
  return http.delete<any, any>(`/courses/${id}`)
}
