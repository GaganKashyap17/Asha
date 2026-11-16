import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('asha_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      sessionStorage.removeItem('asha_token')
      sessionStorage.removeItem('asha_user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api

export const authAPI = {
  login: (worker_id: string, password: string) =>
    api.post('/api/accounts/login/', { worker_id, password }),
  logout: () => api.post('/api/accounts/logout/'),
  me: () => api.get('/api/accounts/me/'),
}

export const voiceAPI = {
  createSession: (data: object) => api.post('/api/voice/sessions/', data),
  transcribe: (formData: FormData) =>
    api.post('/api/voice/transcribe/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
}

export const visitAPI = {
  extract: (transcript: string, visit_type: string) =>
    api.post('/api/visits/extract/', { transcript, visit_type }),
  list: (params?: object) => api.get('/api/visits/', { params }),
  detail: (id: string) => api.get(`/api/visits/${id}/`),
  correct: (id: string, field: string, value: unknown) =>
    api.patch(`/api/visits/${id}/correct/`, { field, value }),
  confirm: (id: string) => api.post(`/api/visits/${id}/confirm/`),
}

export const beneficiaryAPI = {
  list: (search?: string) => api.get('/api/beneficiaries/', { params: { search } }),
  detail: (id: string) => api.get(`/api/beneficiaries/${id}/`),
  create: (data: object) => api.post('/api/beneficiaries/', data),
}

export const followupAPI = {
  list: (status?: string) => api.get('/api/followups/', { params: { status } }),
  update: (id: string, data: object) => api.patch(`/api/followups/${id}/`, data),
}

export const alertAPI = {
  list: (resolved?: boolean) =>
    api.get('/api/alerts/', { params: { resolved } }),
  update: (id: string, data: object) => api.patch(`/api/alerts/${id}/`, data),
}

export const analyticsAPI = {
  dashboard: () => api.get('/api/analytics/dashboard/'),
  health: () => api.get('/api/analytics/health/'),
}
