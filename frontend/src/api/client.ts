import axios from 'axios'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '',
  headers: { Accept: 'application/json' }
})

apiClient.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('lab-device-assistant-auth-token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export { apiClient }
