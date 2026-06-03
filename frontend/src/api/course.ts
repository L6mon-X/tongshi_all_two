import http from './http'

export interface Course {
  id: number
  name: string
  created_at: string
  created_by?: string
  is_public?: boolean
  is_owner?: boolean
  material_count: number
  question_count: number
  class_count: number
}

export type CourseDetail = Course
export interface CourseListResult {
  courses: Course[]
  hint: string | null
}

export function getCourses() {
  return http.get<any, Course[] | CourseListResult>('/courses').then(data => {
    if (Array.isArray(data)) return data
    return data.courses
  })
}

export function getCourseDetail(id: number) {
  return http.get<any, CourseDetail>(`/courses/${id}`)
}

export function createCourse(data: { name: string }) {
  return http.post<any, { id: number }>('/courses', data)
}

export function addPublicCourse(id: number) {
  return http.post<any, { id: number }>(`/questions/courses/${id}/add`)
}

export function updateCourse(id: number, data: { name: string }) {
  return http.put<any, any>(`/courses/${id}`, data)
}

export function deleteCourse(id: number) {
  return http.delete<any, any>(`/courses/${id}`)
}
