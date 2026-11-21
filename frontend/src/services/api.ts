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
  /**
   * Extract visit data from transcript.
   * Returns a draft (in-memory only, NOT saved to MongoDB).
   * Response includes draft_id, missing_fields, is_complete, next_prompt.
   */
  extract: (transcript: string, visit_type: string, extra?: Record<string, string>) =>
    api.post('/api/visits/extract/', { transcript, visit_type, ...extra }),

  list: (params?: object) => api.get('/api/visits/', { params }),
  detail: (id: string) => api.get(`/api/visits/${id}/`),

  correct: (id: string, field: string, value: unknown) =>
    api.patch(`/api/visits/${id}/correct/`, { field, value }),

  /** Legacy confirm for already-saved visit records */
  confirm: (id: string) => api.post(`/api/visits/${id}/confirm/`),

  // ── Draft management ──────────────────────────────────────────────────

  /** Get current state of a draft (not yet saved) */
  getDraft: (draftId: string) => api.get(`/api/visits/draft/${draftId}/`),

  /**
   * Add or correct a field in a draft.
   * Body: { field, value? } or { field, transcript } for voice re-extraction.
   */
  addDraftField: (draftId: string, data: { field: string; value?: unknown; transcript?: string }) =>
    api.post(`/api/visits/draft/${draftId}/add-field/`, data),

  /**
   * Confirm and save a completed draft to MongoDB.
   * This is the ONLY operation that writes a visit record to MongoDB.
   * Returns 422 if any mandatory field is missing or validation fails.
   */
  confirmDraft: (draftId: string) => api.post(`/api/visits/draft/${draftId}/confirm/`),

  /** Discard a draft without saving (cancel workflow). */
  discardDraft: (draftId: string) => api.delete(`/api/visits/draft/${draftId}/discard/`),
}

export const beneficiaryAPI = {
  list: (search?: string) => api.get('/api/beneficiaries/', { params: { search } }),
  detail: (id: string) => api.get(`/api/beneficiaries/${id}/`),
  create: (data: object) => api.post('/api/beneficiaries/', data),
  update: (id: string, data: object) => api.put(`/api/beneficiaries/${id}/`, data),
  delete: (id: string) => api.delete(`/api/beneficiaries/${id}/`),
  registerVoice: (data: { transcript: string; beneficiary_type: string; language?: string }) =>
    api.post('/api/beneficiaries/register-voice/', data),
  extractField: (data: { field: string; transcript: string; category?: string; language?: string }) =>
    api.post('/api/beneficiaries/extract-field/', data),
  checkDuplicate: (data: { name?: string; phone?: string; mother_beneficiary_id?: string; dob?: string }) =>
    api.post('/api/beneficiaries/check-duplicate/', data),
  lookup: (beneficiaryId: string) =>
    api.get(`/api/beneficiaries/lookup/${beneficiaryId}/`),
}

export const revisitAPI = {
  init: (data: { transcript: string; language?: string }) =>
    api.post('/api/visits/revisit/init/', data),
  extract: (data: {
    transcript: string;
    beneficiary_id: string;
    beneficiary_type?: string;
    language?: string;
  }) => api.post('/api/visits/revisit/extract/', data),
  extractField: (data: {
    field: string;
    transcript: string;
    category?: string;
    draft_id?: string;
    language?: string;
  }) => api.post('/api/visits/revisit/extract-field/', data),
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
