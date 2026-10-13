import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import axios from 'axios'
import { apiClient } from '@/api/client'

export type UserRole = 'student' | 'teacher' | 'admin'

export interface AuthUser {
  id: string
  username: string
  display_name: string
  role: UserRole
}

interface LoginResponse {
  access_token: string
  token_type: 'bearer'
  user: AuthUser
}

const TOKEN_KEY = 'lab-device-assistant-auth-token'
const USER_KEY = 'lab-device-assistant-auth-user'

function readStoredUser(): AuthUser | null {
  try {
    const value = sessionStorage.getItem(USER_KEY)
    if (!value) return null
    const parsed = JSON.parse(value) as AuthUser
    if (
      typeof parsed.id !== 'string' ||
      typeof parsed.username !== 'string' ||
      typeof parsed.display_name !== 'string' ||
      !['student', 'teacher', 'admin'].includes(parsed.role)
    ) return null
    return parsed
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref(sessionStorage.getItem(TOKEN_KEY) || '')
  const user = ref<AuthUser | null>(readStoredUser())
  const isAuthenticated = computed(() => Boolean(token.value && user.value))
  const error = ref('')
  const isLoading = ref(false)

  if (!token.value || !user.value) {
    token.value = ''
    user.value = null
    sessionStorage.removeItem(TOKEN_KEY)
    sessionStorage.removeItem(USER_KEY)
  }

  async function login(username: string, password: string): Promise<void> {
    error.value = ''
    isLoading.value = true
    try {
      const { data } = await apiClient.post<LoginResponse>('/api/v1/auth/login', {
        username,
        password
      })
      token.value = data.access_token
      user.value = data.user
      sessionStorage.setItem(TOKEN_KEY, data.access_token)
      sessionStorage.setItem(USER_KEY, JSON.stringify(data.user))
    } catch (cause) {
      if (axios.isAxiosError<{ detail?: string }>(cause)) {
        error.value = cause.response?.data?.detail || '登录失败，请检查用户名和密码后重试。'
      } else {
        error.value = '无法连接登录服务，请稍后重试。'
      }
      throw cause
    } finally {
      isLoading.value = false
    }
  }

  function logout(): void {
    token.value = ''
    user.value = null
    error.value = ''
    sessionStorage.removeItem(TOKEN_KEY)
    sessionStorage.removeItem(USER_KEY)
  }

  return { token, user, isAuthenticated, error, isLoading, login, logout }
})
