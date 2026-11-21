import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Users, Search, Plus, Eye, Calendar, Baby, Edit3, Trash2,
  X, AlertTriangle, CheckCircle2, Loader2, Phone, MapPin, Home, Mic
} from 'lucide-react'
import { beneficiaryAPI } from '../services/api'

export interface Beneficiary {
  beneficiary_id: string
  name: string
  age?: number
  gender?: string
  phone?: string
  village?: string
  household?: string
  pregnancy_status?: string
  pregnancy_month?: number
  expected_delivery_date?: string
  newborn_age_days?: number
  last_visit_date?: string
  next_visit_date?: string
  is_deleted?: boolean
  is_archived?: boolean
}

interface VisitHistoryItem {
  _id?: string
  id?: string
  visit_type?: string
  visit_date?: string
  weight_kg?: number
  pregnancy_month?: number
  anc_completed?: boolean
  ifa_given?: boolean
  vaccinations?: string[]
  danger_signs?: string[]
  danger_flag?: boolean
  confirmation_status?: string
}

export default function BeneficiaryPage() {
  const [beneficiaries, setBeneficiaries] = useState<Beneficiary[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<Beneficiary | null>(null)

  // Modals state
  const [showAddModal, setShowAddModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [showHistoryModal, setShowHistoryModal] = useState(false)

  // Target beneficiary for edit / delete / history
  const [activeBeneficiary, setActiveBeneficiary] = useState<Beneficiary | null>(null)
  const [beneficiaryVisits, setBeneficiaryVisits] = useState<VisitHistoryItem[]>([])
  const [loadingHistory, setLoadingHistory] = useState(false)

  // Form states
  const [formData, setFormData] = useState<Partial<Beneficiary>>({
    name: '',
    age: undefined,
    gender: 'female',
    phone: '',
    village: '',
    household: '',
    pregnancy_status: 'not_pregnant',
    pregnancy_month: undefined,
    expected_delivery_date: '',
    newborn_age_days: undefined,
    next_visit_date: '',
  })
  const [formError, setFormError] = useState('')
  const [formSubmitting, setFormSubmitting] = useState(false)
  const [successMsg, setSuccessMsg] = useState('')

  useEffect(() => {
    fetchBeneficiaries()
  }, [])

  function fetchBeneficiaries() {
    setLoading(true)
    beneficiaryAPI.list()
      .then(r => setBeneficiaries(r.data.results || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  function statusColor(s?: string) {
    if (s === 'pregnant') return 'bg-blue-100 text-blue-700'
    if (s === 'postnatal') return 'bg-purple-100 text-purple-700'
    return 'bg-gray-100 text-gray-600'
  }

  const filtered = beneficiaries.filter(b =>
    b.name.toLowerCase().includes(search.toLowerCase()) ||
    b.beneficiary_id.toLowerCase().includes(search.toLowerCase()) ||
    (b.village && b.village.toLowerCase().includes(search.toLowerCase())) ||
    (b.household && b.household.toLowerCase().includes(search.toLowerCase()))
  )

  // ── Open Add Modal ──────────────────────────────────────
  function handleOpenAdd() {
    setFormData({
      name: '',
      age: undefined,
      gender: 'female',
      phone: '',
      village: '',
      household: '',
      pregnancy_status: 'not_pregnant',
      pregnancy_month: undefined,
      expected_delivery_date: '',
      newborn_age_days: undefined,
      next_visit_date: '',
    })
    setFormError('')
    setShowAddModal(true)
  }

  // ── Open Edit Modal ─────────────────────────────────────
  function handleOpenEdit(b: Beneficiary) {
    setActiveBeneficiary(b)
    setFormData({
      name: b.name || '',
      age: b.age,
      gender: b.gender || 'female',
      phone: b.phone || '',
      village: b.village || '',
      household: b.household || '',
      pregnancy_status: b.pregnancy_status || 'not_pregnant',
      pregnancy_month: b.pregnancy_month,
      expected_delivery_date: b.expected_delivery_date || '',
      newborn_age_days: b.newborn_age_days,
      next_visit_date: b.next_visit_date || '',
    })
    setFormError('')
    setShowEditModal(true)
  }

  // ── Open Delete Modal ───────────────────────────────────
  function handleOpenDelete(b: Beneficiary) {
    setActiveBeneficiary(b)
    setShowDeleteModal(true)
  }

  // ── Open History Modal ──────────────────────────────────
  function handleOpenHistory(b: Beneficiary) {
    setActiveBeneficiary(b)
    setShowHistoryModal(true)
    setLoadingHistory(true)
    beneficiaryAPI.detail(b.beneficiary_id)
      .then(res => {
        setBeneficiaryVisits(res.data.visit_history || [])
      })
      .catch(() => setBeneficiaryVisits([]))
      .finally(() => setLoadingHistory(false))
  }

  // ── Submit Add Beneficiary ──────────────────────────────
  async function handleSubmitAdd(e: React.FormEvent) {
    e.preventDefault()
    if (!formData.name?.trim()) {
      setFormError('Beneficiary name is required.')
      return
    }
    setFormSubmitting(true)
    setFormError('')
    try {
      const payload: Record<string, unknown> = {
        name: formData.name.trim(),
        gender: formData.gender || 'female',
        pregnancy_status: formData.pregnancy_status || 'not_pregnant',
      }
      if (formData.age) payload.age = Number(formData.age)
      if (formData.phone) payload.phone = formData.phone.trim()
      if (formData.village) payload.village = formData.village.trim()
      if (formData.household) payload.household = formData.household.trim()
      if (formData.pregnancy_status === 'pregnant' && formData.pregnancy_month) {
        payload.pregnancy_month = Number(formData.pregnancy_month)
      }
      if (formData.pregnancy_status === 'pregnant' && formData.expected_delivery_date) {
        payload.expected_delivery_date = formData.expected_delivery_date
      }
      if (formData.pregnancy_status === 'postnatal' && formData.newborn_age_days !== undefined) {
        payload.newborn_age_days = Number(formData.newborn_age_days)
      }
      if (formData.next_visit_date) payload.next_visit_date = formData.next_visit_date

      const res = await beneficiaryAPI.create(payload)
      const newBene = res.data
      setBeneficiaries(prev => [newBene, ...prev])
      setShowAddModal(false)
      setSuccessMsg(`Beneficiary ${newBene.name} (${newBene.beneficiary_id}) registered successfully!`)
      setTimeout(() => setSuccessMsg(''), 4000)
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { error?: string } } }
      setFormError(axiosErr?.response?.data?.error || 'Failed to register beneficiary. Please check your data.')
    } finally {
      setFormSubmitting(false)
    }
  }

  // ── Submit Edit Beneficiary ─────────────────────────────
  async function handleSubmitEdit(e: React.FormEvent) {
    e.preventDefault()
    if (!activeBeneficiary) return
    if (!formData.name?.trim()) {
      setFormError('Beneficiary name is required.')
      return
    }
    setFormSubmitting(true)
    setFormError('')
    try {
      const payload: Record<string, unknown> = {
        name: formData.name.trim(),
        gender: formData.gender || 'female',
        pregnancy_status: formData.pregnancy_status || 'not_pregnant',
        phone: formData.phone?.trim() || '',
        village: formData.village?.trim() || '',
        household: formData.household?.trim() || '',
      }
      if (formData.age !== undefined && formData.age !== null) payload.age = Number(formData.age)
      if (formData.pregnancy_status === 'pregnant') {
        payload.pregnancy_month = formData.pregnancy_month ? Number(formData.pregnancy_month) : null
        payload.expected_delivery_date = formData.expected_delivery_date || null
      } else {
        payload.pregnancy_month = null
        payload.expected_delivery_date = null
      }
      if (formData.pregnancy_status === 'postnatal') {
        payload.newborn_age_days = formData.newborn_age_days !== undefined ? Number(formData.newborn_age_days) : null
      } else {
        payload.newborn_age_days = null
      }
      if (formData.next_visit_date) payload.next_visit_date = formData.next_visit_date

      const res = await beneficiaryAPI.update(activeBeneficiary.beneficiary_id, payload)
      const updated = res.data
      setBeneficiaries(prev => prev.map(b => b.beneficiary_id === updated.beneficiary_id ? updated : b))
      if (selected?.beneficiary_id === updated.beneficiary_id) {
        setSelected(updated)
      }
      setShowEditModal(false)
      setSuccessMsg(`Beneficiary ${updated.name} updated successfully!`)
      setTimeout(() => setSuccessMsg(''), 4000)
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { error?: string } } }
      setFormError(axiosErr?.response?.data?.error || 'Failed to update beneficiary.')
    } finally {
      setFormSubmitting(false)
    }
  }

  // ── Confirm Delete Beneficiary ──────────────────────────
  async function handleConfirmDelete() {
    if (!activeBeneficiary) return
    setFormSubmitting(true)
    try {
      await beneficiaryAPI.delete(activeBeneficiary.beneficiary_id)
      setBeneficiaries(prev => prev.filter(b => b.beneficiary_id !== activeBeneficiary.beneficiary_id))
      if (selected?.beneficiary_id === activeBeneficiary.beneficiary_id) {
        setSelected(null)
      }
      setShowDeleteModal(false)
      setSuccessMsg(`Beneficiary ${activeBeneficiary.name} safely archived. Historical visits remain intact.`)
      setTimeout(() => setSuccessMsg(''), 4000)
    } catch {
      setFormError('Failed to archive beneficiary. Please try again.')
    } finally {
      setFormSubmitting(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <Users className="w-7 h-7 text-green-600" /> Beneficiaries
        </h2>
        <div className="flex items-center gap-2">
          <Link
            to="/register"
            className="flex items-center gap-2 px-4 py-2.5 bg-green-50 border border-green-300 text-green-800 rounded-xl text-sm font-semibold hover:bg-green-100 transition-colors shadow-sm"
          >
            <Mic className="w-4 h-4 text-green-700" /> Voice Register
          </Link>
          <button
            onClick={handleOpenAdd}
            className="flex items-center gap-2 px-4 py-2.5 bg-green-700 text-white rounded-xl text-sm font-semibold hover:bg-green-800 transition-colors shadow-sm"
          >
            <Plus className="w-4 h-4" /> Add Beneficiary
          </button>
        </div>
      </div>

      {/* Success Notification */}
      {successMsg && (
        <div className="bg-green-50 border border-green-200 text-green-800 rounded-2xl px-4 py-3 text-sm flex items-center gap-2">
          <CheckCircle2 className="w-5 h-5 text-green-600 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Search Input */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search by name, ID, village, or household…"
          className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-2xl text-sm focus:outline-none focus:ring-2 focus:ring-green-500 bg-white"
        />
      </div>

      {/* Grid or Loader */}
      {loading ? (
        <div className="grid sm:grid-cols-2 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-36 bg-green-100 rounded-2xl animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 gap-4">
          {filtered.map(b => (
            <div
              key={b.beneficiary_id}
              className={`bg-white rounded-2xl p-5 shadow-sm hover:shadow-md transition-shadow cursor-pointer border ${
                selected?.beneficiary_id === b.beneficiary_id ? 'border-green-500 ring-2 ring-green-100' : 'border-transparent'
              }`}
              onClick={() => setSelected(selected?.beneficiary_id === b.beneficiary_id ? null : b)}
            >
              <div className="flex items-start justify-between mb-3">
                <div>
                  <p className="font-semibold text-gray-900">{b.name}</p>
                  <p className="text-xs text-gray-500">
                    {b.beneficiary_id} {b.age !== undefined && b.age !== null ? `· Age ${b.age}` : ''} {b.gender ? `· ${b.gender}` : ''}
                  </p>
                </div>
                <span className={`text-xs px-2.5 py-1 rounded-full font-medium capitalize ${statusColor(b.pregnancy_status)}`}>
                  {b.pregnancy_status?.replace('_', ' ') || 'Registered'}
                </span>
              </div>

              <div className="text-sm text-gray-600 space-y-1">
                {(b.village || b.household) && (
                  <p className="truncate">
                    📍 {b.village || 'Village'}{b.household ? ` · ${b.household}` : ''}
                  </p>
                )}
                {b.phone && (
                  <p className="text-xs text-gray-500 flex items-center gap-1">
                    <Phone className="w-3 h-3 text-gray-400" /> {b.phone}
                  </p>
                )}
                {b.pregnancy_status === 'pregnant' && b.pregnancy_month && (
                  <p><Baby className="inline w-3 h-3 mr-1 text-blue-500" />Month {b.pregnancy_month} of pregnancy</p>
                )}
                {b.pregnancy_status === 'postnatal' && b.newborn_age_days !== undefined && (
                  <p><Baby className="inline w-3 h-3 mr-1 text-purple-500" />Newborn — {b.newborn_age_days} days old</p>
                )}
                {b.last_visit_date && (
                  <p className="text-xs text-gray-500"><Calendar className="inline w-3 h-3 mr-1 text-gray-400" />Last visit: {b.last_visit_date}</p>
                )}
                {b.next_visit_date && (
                  <p className="text-green-700 font-medium text-xs">📅 Next visit: {b.next_visit_date}</p>
                )}
              </div>

              {/* Action Buttons */}
              <div className="mt-4 pt-4 border-t border-gray-100 flex items-center justify-between gap-2 flex-wrap">
                <button
                  type="button"
                  onClick={e => {
                    e.stopPropagation()
                    handleOpenHistory(b)
                  }}
                  className="flex items-center gap-1 px-3 py-1.5 bg-green-50 text-green-700 rounded-lg text-xs font-medium hover:bg-green-100 transition-colors"
                >
                  <Eye className="w-3 h-3" /> View History
                </button>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={e => {
                      e.stopPropagation()
                      handleOpenEdit(b)
                    }}
                    className="flex items-center gap-1 px-3 py-1.5 bg-blue-50 text-blue-700 rounded-lg text-xs font-medium hover:bg-blue-100 transition-colors"
                  >
                    <Edit3 className="w-3 h-3" /> Edit
                  </button>
                  <button
                    type="button"
                    onClick={e => {
                      e.stopPropagation()
                      handleOpenDelete(b)
                    }}
                    className="flex items-center gap-1 px-3 py-1.5 bg-red-50 text-red-600 rounded-lg text-xs font-medium hover:bg-red-100 transition-colors"
                  >
                    <Trash2 className="w-3 h-3" /> Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
          {filtered.length === 0 && (
            <div className="bg-white rounded-2xl p-10 text-center col-span-2 shadow-sm">
              <Users className="w-12 h-12 text-gray-300 mx-auto mb-2" />
              <p className="text-gray-500 font-medium">No beneficiaries found</p>
              <p className="text-gray-400 text-xs mt-1">Try a different search term or register a new beneficiary above.</p>
            </div>
          )}
        </div>
      )}

      {/* ────────────────────────────────────────────────────────── */}
      {/* ADD BENEFICIARY MODAL                                      */}
      {/* ────────────────────────────────────────────────────────── */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-3xl max-w-lg w-full max-h-[90vh] overflow-y-auto p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-gray-100">
              <h3 className="font-bold text-lg text-gray-900 flex items-center gap-2">
                <Plus className="w-5 h-5 text-green-600" /> Register New Beneficiary
              </h3>
              <button
                onClick={() => setShowAddModal(false)}
                className="text-gray-400 hover:text-gray-600 p-1 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {formError && (
              <div className="bg-red-50 border border-red-200 text-red-700 p-3 rounded-xl text-xs flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                <span>{formError}</span>
              </div>
            )}

            <form onSubmit={handleSubmitAdd} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Full Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Lakshmi Sundaram"
                  value={formData.name || ''}
                  onChange={e => setFormData(f => ({ ...f, name: e.target.value }))}
                  className="w-full border border-gray-300 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Age</label>
                  <input
                    type="number"
                    min="0"
                    max="120"
                    placeholder="e.g. 24"
                    value={formData.age ?? ''}
                    onChange={e => setFormData(f => ({ ...f, age: e.target.value ? Number(e.target.value) : undefined }))}
                    className="w-full border border-gray-300 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Gender</label>
                  <select
                    value={formData.gender || 'female'}
                    onChange={e => setFormData(f => ({ ...f, gender: e.target.value }))}
                    className="w-full border border-gray-300 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                  >
                    <option value="female">Female</option>
                    <option value="male">Male</option>
                    <option value="other">Other</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Phone Number</label>
                <input
                  type="tel"
                  placeholder="e.g. 9876543210"
                  value={formData.phone || ''}
                  onChange={e => setFormData(f => ({ ...f, phone: e.target.value }))}
                  className="w-full border border-gray-300 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Village</label>
                  <input
                    type="text"
                    placeholder="e.g. Tambaram"
                    value={formData.village || ''}
                    onChange={e => setFormData(f => ({ ...f, village: e.target.value }))}
                    className="w-full border border-gray-300 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Household / Address</label>
                  <input
                    type="text"
                    placeholder="e.g. House 12, Gandhi St"
                    value={formData.household || ''}
                    onChange={e => setFormData(f => ({ ...f, household: e.target.value }))}
                    className="w-full border border-gray-300 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Health / Pregnancy Status</label>
                <select
                  value={formData.pregnancy_status || 'not_pregnant'}
                  onChange={e => setFormData(f => ({ ...f, pregnancy_status: e.target.value }))}
                  className="w-full border border-gray-300 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                >
                  <option value="not_pregnant">General / Not Pregnant</option>
                  <option value="pregnant">Pregnant</option>
                  <option value="postnatal">Postnatal / Newborn Mother</option>
                </select>
              </div>

              {formData.pregnancy_status === 'pregnant' && (
                <div className="grid grid-cols-2 gap-3 bg-blue-50/70 p-3 rounded-2xl border border-blue-100">
                  <div>
                    <label className="block text-xs font-medium text-blue-900 mb-1">Pregnancy Month (1-9)</label>
                    <input
                      type="number"
                      min="1"
                      max="9"
                      placeholder="e.g. 7"
                      value={formData.pregnancy_month ?? ''}
                      onChange={e => setFormData(f => ({ ...f, pregnancy_month: e.target.value ? Number(e.target.value) : undefined }))}
                      className="w-full border border-blue-200 rounded-xl px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-blue-900 mb-1">Expected Delivery Date</label>
                    <input
                      type="date"
                      value={formData.expected_delivery_date || ''}
                      onChange={e => setFormData(f => ({ ...f, expected_delivery_date: e.target.value }))}
                      className="w-full border border-blue-200 rounded-xl px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                    />
                  </div>
                </div>
              )}

              {formData.pregnancy_status === 'postnatal' && (
                <div className="bg-purple-50/70 p-3 rounded-2xl border border-purple-100">
                  <label className="block text-xs font-medium text-purple-900 mb-1">Newborn Age (in Days)</label>
                  <input
                    type="number"
                    min="0"
                    max="365"
                    placeholder="e.g. 14"
                    value={formData.newborn_age_days ?? ''}
                    onChange={e => setFormData(f => ({ ...f, newborn_age_days: e.target.value ? Number(e.target.value) : undefined }))}
                    className="w-full border border-purple-200 rounded-xl px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 bg-white"
                  />
                </div>
              )}

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Scheduled Next Visit Date</label>
                <input
                  type="date"
                  value={formData.next_visit_date || ''}
                  onChange={e => setFormData(f => ({ ...f, next_visit_date: e.target.value }))}
                  className="w-full border border-gray-300 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2.5 text-gray-600 bg-gray-100 rounded-xl text-sm font-medium hover:bg-gray-200 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={formSubmitting}
                  className="flex items-center gap-2 px-5 py-2.5 bg-green-700 text-white rounded-xl text-sm font-semibold hover:bg-green-800 transition-colors disabled:opacity-50"
                >
                  {formSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                  Save Beneficiary
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ────────────────────────────────────────────────────────── */}
      {/* EDIT BENEFICIARY MODAL                                     */}
      {/* ────────────────────────────────────────────────────────── */}
      {showEditModal && activeBeneficiary && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-3xl max-w-lg w-full max-h-[90vh] overflow-y-auto p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-gray-100">
              <div>
                <h3 className="font-bold text-lg text-gray-900 flex items-center gap-2">
                  <Edit3 className="w-5 h-5 text-blue-600" /> Edit Beneficiary
                </h3>
                <p className="text-xs text-gray-500 mt-0.5">ID: {activeBeneficiary.beneficiary_id}</p>
              </div>
              <button
                onClick={() => setShowEditModal(false)}
                className="text-gray-400 hover:text-gray-600 p-1 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {formError && (
              <div className="bg-red-50 border border-red-200 text-red-700 p-3 rounded-xl text-xs flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                <span>{formError}</span>
              </div>
            )}

            <form onSubmit={handleSubmitEdit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Full Name *</label>
                <input
                  type="text"
                  required
                  value={formData.name || ''}
                  onChange={e => setFormData(f => ({ ...f, name: e.target.value }))}
                  className="w-full border border-gray-300 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Age</label>
                  <input
                    type="number"
                    min="0"
                    max="120"
                    value={formData.age ?? ''}
                    onChange={e => setFormData(f => ({ ...f, age: e.target.value ? Number(e.target.value) : undefined }))}
                    className="w-full border border-gray-300 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Gender</label>
                  <select
                    value={formData.gender || 'female'}
                    onChange={e => setFormData(f => ({ ...f, gender: e.target.value }))}
                    className="w-full border border-gray-300 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="female">Female</option>
                    <option value="male">Male</option>
                    <option value="other">Other</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Phone Number</label>
                <input
                  type="tel"
                  value={formData.phone || ''}
                  onChange={e => setFormData(f => ({ ...f, phone: e.target.value }))}
                  className="w-full border border-gray-300 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Village</label>
                  <input
                    type="text"
                    value={formData.village || ''}
                    onChange={e => setFormData(f => ({ ...f, village: e.target.value }))}
                    className="w-full border border-gray-300 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Household / Address</label>
                  <input
                    type="text"
                    value={formData.household || ''}
                    onChange={e => setFormData(f => ({ ...f, household: e.target.value }))}
                    className="w-full border border-gray-300 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Health / Pregnancy Status</label>
                <select
                  value={formData.pregnancy_status || 'not_pregnant'}
                  onChange={e => setFormData(f => ({ ...f, pregnancy_status: e.target.value }))}
                  className="w-full border border-gray-300 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="not_pregnant">General / Not Pregnant</option>
                  <option value="pregnant">Pregnant</option>
                  <option value="postnatal">Postnatal / Newborn Mother</option>
                </select>
              </div>

              {formData.pregnancy_status === 'pregnant' && (
                <div className="grid grid-cols-2 gap-3 bg-blue-50/70 p-3 rounded-2xl border border-blue-100">
                  <div>
                    <label className="block text-xs font-medium text-blue-900 mb-1">Pregnancy Month (1-9)</label>
                    <input
                      type="number"
                      min="1"
                      max="9"
                      value={formData.pregnancy_month ?? ''}
                      onChange={e => setFormData(f => ({ ...f, pregnancy_month: e.target.value ? Number(e.target.value) : undefined }))}
                      className="w-full border border-blue-200 rounded-xl px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-blue-900 mb-1">Expected Delivery Date</label>
                    <input
                      type="date"
                      value={formData.expected_delivery_date || ''}
                      onChange={e => setFormData(f => ({ ...f, expected_delivery_date: e.target.value }))}
                      className="w-full border border-blue-200 rounded-xl px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                    />
                  </div>
                </div>
              )}

              {formData.pregnancy_status === 'postnatal' && (
                <div className="bg-purple-50/70 p-3 rounded-2xl border border-purple-100">
                  <label className="block text-xs font-medium text-purple-900 mb-1">Newborn Age (in Days)</label>
                  <input
                    type="number"
                    min="0"
                    max="365"
                    value={formData.newborn_age_days ?? ''}
                    onChange={e => setFormData(f => ({ ...f, newborn_age_days: e.target.value ? Number(e.target.value) : undefined }))}
                    className="w-full border border-purple-200 rounded-xl px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 bg-white"
                  />
                </div>
              )}

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Next Visit Date</label>
                <input
                  type="date"
                  value={formData.next_visit_date || ''}
                  onChange={e => setFormData(f => ({ ...f, next_visit_date: e.target.value }))}
                  className="w-full border border-gray-300 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => setShowEditModal(false)}
                  className="px-4 py-2.5 text-gray-600 bg-gray-100 rounded-xl text-sm font-medium hover:bg-gray-200 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={formSubmitting}
                  className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 text-white rounded-xl text-sm font-semibold hover:bg-blue-700 transition-colors disabled:opacity-50"
                >
                  {formSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ────────────────────────────────────────────────────────── */}
      {/* DELETE / ARCHIVE CONFIRMATION MODAL                        */}
      {/* ────────────────────────────────────────────────────────── */}
      {showDeleteModal && activeBeneficiary && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3 text-red-600">
              <div className="w-12 h-12 rounded-2xl bg-red-100 flex items-center justify-center shrink-0">
                <AlertTriangle className="w-6 h-6" />
              </div>
              <div>
                <h3 className="font-bold text-lg text-gray-900">Archive Beneficiary?</h3>
                <p className="text-xs text-gray-500">{activeBeneficiary.name} ({activeBeneficiary.beneficiary_id})</p>
              </div>
            </div>

            <p className="text-sm text-gray-600 leading-relaxed">
              Are you sure you want to remove <span className="font-semibold text-gray-900">{activeBeneficiary.name}</span> from the active beneficiaries list?
            </p>

            <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-xs text-amber-800">
              🛡️ <span className="font-semibold">Safety Guarantee:</span> All historical visit logs, vaccinations, and past records remain permanently preserved in History and Analytics.
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowDeleteModal(false)}
                className="px-4 py-2.5 text-gray-600 bg-gray-100 rounded-xl text-sm font-medium hover:bg-gray-200 transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmDelete}
                disabled={formSubmitting}
                className="flex items-center gap-2 px-5 py-2.5 bg-red-600 text-white rounded-xl text-sm font-semibold hover:bg-red-700 transition-colors disabled:opacity-50"
              >
                {formSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                Yes, Archive Beneficiary
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ────────────────────────────────────────────────────────── */}
      {/* VIEW HISTORY MODAL                                         */}
      {/* ────────────────────────────────────────────────────────── */}
      {showHistoryModal && activeBeneficiary && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-3xl max-w-2xl w-full max-h-[85vh] flex flex-col p-6 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-gray-100 shrink-0">
              <div>
                <h3 className="font-bold text-lg text-gray-900 flex items-center gap-2">
                  <Eye className="w-5 h-5 text-green-600" /> Visit History
                </h3>
                <p className="text-xs text-gray-500 mt-0.5">
                  {activeBeneficiary.name} · {activeBeneficiary.beneficiary_id}
                </p>
              </div>
              <button
                onClick={() => setShowHistoryModal(false)}
                className="text-gray-400 hover:text-gray-600 p-1 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="overflow-y-auto py-4 space-y-3 flex-1">
              {loadingHistory ? (
                <div className="py-12 flex flex-col items-center justify-center text-gray-400 gap-2">
                  <Loader2 className="w-6 h-6 animate-spin text-green-600" />
                  <p className="text-xs">Loading visit records…</p>
                </div>
              ) : beneficiaryVisits.length > 0 ? (
                beneficiaryVisits.map((v, idx) => (
                  <div key={v._id || v.id || idx} className="bg-gray-50 rounded-2xl p-4 border border-gray-100 space-y-2">
                    <div className="flex items-center justify-between flex-wrap gap-2">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-gray-900 capitalize text-sm">{v.visit_type} Visit</span>
                        {v.danger_flag && (
                          <span className="bg-red-100 text-red-700 text-xs px-2 py-0.5 rounded-full flex items-center gap-1">
                            <AlertTriangle className="w-3 h-3" /> Danger Flag
                          </span>
                        )}
                      </div>
                      <span className="text-xs text-gray-500">{v.visit_date || 'Date not recorded'}</span>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs text-gray-600 pt-1">
                      {v.weight_kg !== undefined && v.weight_kg !== null && (
                        <p><span className="text-gray-400">Weight:</span> {v.weight_kg} kg</p>
                      )}
                      {v.pregnancy_month && (
                        <p><span className="text-gray-400">Pregnancy:</span> Month {v.pregnancy_month}</p>
                      )}
                      {v.anc_completed !== undefined && (
                        <p><span className="text-gray-400">ANC:</span> {v.anc_completed ? 'Completed' : 'Not completed'}</p>
                      )}
                      {v.ifa_given !== undefined && (
                        <p><span className="text-gray-400">IFA:</span> {v.ifa_given ? 'Given' : 'Not given'}</p>
                      )}
                      {v.confirmation_status && (
                        <p><span className="text-gray-400">Status:</span> <span className="capitalize font-medium text-green-700">{v.confirmation_status}</span></p>
                      )}
                    </div>

                    {v.vaccinations && v.vaccinations.length > 0 && (
                      <p className="text-xs text-gray-600"><span className="text-gray-400">Vaccinations:</span> {v.vaccinations.join(', ')}</p>
                    )}

                    {v.danger_signs && v.danger_signs.length > 0 && (
                      <div className="bg-red-50 text-red-700 rounded-xl p-2 text-xs">
                        ⚠️ <span className="font-medium">Danger signs recorded:</span> {v.danger_signs.join(', ')}
                      </div>
                    )}
                  </div>
                ))
              ) : (
                <div className="text-center py-12 text-gray-400">
                  <Calendar className="w-10 h-10 mx-auto mb-2 text-gray-300" />
                  <p className="text-sm font-medium text-gray-500">No visits recorded yet</p>
                  <p className="text-xs text-gray-400 mt-1">Visits completed for this beneficiary will appear here.</p>
                </div>
              )}
            </div>

            <div className="pt-3 border-t border-gray-100 flex justify-end shrink-0">
              <button
                type="button"
                onClick={() => setShowHistoryModal(false)}
                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-xl text-sm font-medium hover:bg-gray-200 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
