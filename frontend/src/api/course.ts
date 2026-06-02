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

function normalizeCourseList(data: Course[] | CourseListResult): Course[] {
  if (Array.isArray(data)) return data
  return data.courses
}

export async function getCourses() {
  const data = await http.get<any, Course[] | CourseListResult>('/questions/courses')
  return normalizeCourseList(data)
}

export function getCourseDetail(id: number) {
  return http.get<any, CourseDetail>(`/questions/courses/${id}`)
}

export function createCourse(data: { name: string; is_public?: boolean }) {
  return http.post<any, { id: number }>('/questions/courses', data)
}

export function updateCourse(id: number, data: { name: string; is_public?: boolean }) {
  return http.put<any, any>(`/questions/courses/${id}`, data)
}

export function deleteCourse(id: number) {
  return http.delete<any, any>(`/questions/courses/${id}`)
}
