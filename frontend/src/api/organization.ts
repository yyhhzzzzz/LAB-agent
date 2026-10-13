import { apiClient } from '@/api/client'

export interface College {
  id: string
  name: string
}

export interface Laboratory {
  id: string
  laboratory_number: string
  college_id: string
  manager_teacher_id: string
  manager_name?: string
}

export interface TeacherOption {
  id: string
  username: string
  display_name: string
  college_id: string | null
  college_name?: string | null
}

export interface StudentOption {
  id: string
  username: string
  display_name: string
  college_id: string | null
}

export interface CollegeCreatePayload {
  name: string
}

export interface LaboratoryCreatePayload {
  laboratory_number: string
  college_id: string
  manager_teacher_id: string
}

export interface StudentCreatePayload {
  username: string
  password: string
  display_name: string
  college_id?: string
  email?: string
}

export interface TeacherCreatePayload {
  username: string
  password: string
  display_name: string
  college_id: string
  email?: string
}

export async function listColleges(): Promise<College[]> {
  const { data } = await apiClient.get<College[]>('/api/v1/colleges')
  return data
}

export async function createCollege(payload: CollegeCreatePayload): Promise<College> {
  const { data } = await apiClient.post<College>('/api/v1/colleges', payload)
  return data
}

export async function listLaboratories(): Promise<Laboratory[]> {
  const { data } = await apiClient.get<Laboratory[]>('/api/v1/laboratories')
  return data
}

export async function listTeachers(): Promise<TeacherOption[]> {
  const { data } = await apiClient.get<TeacherOption[]>('/api/v1/users/teachers')
  return data
}

export async function listStudents(): Promise<StudentOption[]> {
  const { data } = await apiClient.get<StudentOption[]>('/api/v1/users/students')
  return data
}

export async function createLaboratory(payload: LaboratoryCreatePayload): Promise<Laboratory> {
  const { data } = await apiClient.post<Laboratory>('/api/v1/laboratories', payload)
  return data
}

export async function createStudent(payload: StudentCreatePayload): Promise<StudentOption> {
  const { data } = await apiClient.post<StudentOption>('/api/v1/users/students', payload)
  return data
}

export async function createTeacher(payload: TeacherCreatePayload): Promise<TeacherOption> {
  const { data } = await apiClient.post<TeacherOption>('/api/v1/users/teachers', payload)
  return data
}

export async function updateUserCollege(userId: string, collegeId: string): Promise<void> {
  await apiClient.patch(`/api/v1/users/${userId}/college`, { college_id: collegeId })
}
