import { useEffect, useState, useMemo } from 'react'
import {
  Calendar,
  CheckCircle2,
  AlertTriangle,
  Clock,
  MapPin,
  Phone,
  Search,
  X,
  ShieldAlert,
} from 'lucide-react'
import { followupAPI, beneficiaryAPI } from '../services/api'
import { getCallHistory } from '../components/ivr/ivrService'

export interface Followup {
  _id?: string
  beneficiary_id?: string
  beneficiary_name?: string
  phone?: string
  mobile_number?: string
  village?: string
  household?: string
  visit_type?: string
  due_date?: string
  priority?: string
  status?: string
  notes?: string
  danger_flag?: boolean
  is_overdue?: boolean
}

const TOMORROW_DATE = '2026-11-23'

// ── Complete Future Revisit Schedule ──────────────────────────────────
const ALL_FUTURE_REVISIT_SCHEDULE: Followup[] = [
  // Tomorrow's Revisits (2026-11-23)
  {
    _id: 'fu-2026-001',
    beneficiary_id: 'PREG-2026-000001',
    beneficiary_name: 'Priya Rajan',
    mobile_number: '7339223026',
    phone: '7339223026',
    village: 'Gandhi Nagar',
    household: 'H-12',
    visit_type: 'ANC Check-up / Maternal Vitals',
    due_date: TOMORROW_DATE,
    priority: 'high',
    status: 'pending',
    notes: 'Scheduled for ANC 3rd trimester revisit tomorrow — BP and Hb check',
    danger_flag: false,
  },
  {
    _id: 'fu-2026-002',
    beneficiary_id: 'PREG-2026-000002',
    beneficiary_name: 'Ananya Sharma',
    mobile_number: '8056413568',
    phone: '8056413568',
    village: 'Anna Nagar',
    household: 'H-05',
    visit_type: 'High Risk ANC Follow-up',
    due_date: TOMORROW_DATE,
    priority: 'emergency',
    status: 'pending',
    notes: 'Scheduled for pre-eclampsia follow-up revisit tomorrow — blood pressure monitoring',
    danger_flag: true,
  },
  {
    _id: 'fu-2026-003',
    beneficiary_id: 'IMM-2026-000001',
    beneficiary_name: 'Kavitha Murugan',
    mobile_number: '9876543210',
    phone: '9876543210',
    village: 'Subhash Nagar',
    household: 'H-23',
    visit_type: 'Child Immunization Revisit',
    due_date: TOMORROW_DATE,
    priority: 'high',
    status: 'pending',
    notes: 'Child vaccination due tomorrow — Pentavalent-1 and OPV booster dose',
    danger_flag: false,
  },
  {
    _id: 'fu-2026-004',
    beneficiary_id: 'NEWB-2026-000001',
    beneficiary_name: 'Sumathi Devi',
    mobile_number: '8765432109',
    phone: '8765432109',
    village: 'Nehru Street',
    household: 'H-18',
    visit_type: 'Newborn Postnatal Revisit',
    due_date: TOMORROW_DATE,
    priority: 'medium',
    status: 'pending',
    notes: 'Scheduled for 14-day newborn health, breastfeeding & temperature revisit tomorrow',
    danger_flag: false,
  },
  {
    _id: 'fu-2026-005',
    beneficiary_id: 'PREG-2026-000003',
    beneficiary_name: 'Meena Krishnan',
    mobile_number: '7654321098',
    phone: '7654321098',
    village: 'Ramanathapuram',
    household: 'H-09',
    visit_type: 'Maternal Nutrition & IFA Revisit',
    due_date: TOMORROW_DATE,
    priority: 'medium',
    status: 'pending',
    notes: 'Scheduled for gestational blood sugar review and IFA tablet replenishment revisit tomorrow',
    danger_flag: false,
  },
  // Upcoming Future Scheduled Revisits
  {
    _id: 'fu-2026-006',
    beneficiary_id: 'PREG-2026-000004',
    beneficiary_name: 'Lakshmi Sundaram',
    mobile_number: '6543210987',
    phone: '6543210987',
    village: 'Kamaraj Nagar',
    household: 'H-31',
    visit_type: 'Gestational Diabetes Follow-up',
    due_date: '2026-11-27',
    priority: 'high',
    status: 'pending',
    notes: 'Fasting and post-prandial blood sugar review, nutrition check',
    danger_flag: false,
  },
  {
    _id: 'fu-2026-007',
    beneficiary_id: 'IMM-2026-000002',
    beneficiary_name: 'Saranya Devi',
    mobile_number: '9123456780',
    phone: '9123456780',
    village: 'Indira Colony',
    household: 'H-14',
    visit_type: 'DPT Booster & Vitamin A Dose',
    due_date: '2026-11-29',
    priority: 'medium',
    status: 'pending',
    notes: '16-24 months immunization round and growth milestone check',
    danger_flag: false,
  },
  {
    _id: 'fu-2026-008',
    beneficiary_id: 'NEWB-2026-000002',
    beneficiary_name: 'Revathi Kumar',
    mobile_number: '9871234567',
    phone: '9871234567',
    village: 'Periyar Nagar',
    household: 'H-08',
    visit_type: '6-Week Postnatal Health Revisit',
    due_date: '2026-12-05',
    priority: 'medium',
    status: 'pending',
    notes: 'Newborn weight gain assessment and maternal postpartum recovery',
    danger_flag: false,
  },
  {
    _id: 'fu-2026-009',
    beneficiary_id: 'PREG-2026-000005',
    beneficiary_name: 'Divya Balan',
    mobile_number: '9443215678',
    phone: '9443215678',
    village: 'Bharathi Street',
    household: 'H-22',
    visit_type: 'ANC 2nd Trimester Ultrasound & Td-2 Dose',
    due_date: '2026-12-10',
    priority: 'medium',
    status: 'pending',
    notes: 'Second trimester anomaly scan review and Tetanus toxoid booster',
    danger_flag: false,
  },
]

function getDueLabel(dueDate?: string) {
  if (!dueDate) return ''
  const today = new Date().toISOString().slice(0, 10)
  if (dueDate === TOMORROW_DATE) return 'Tomorrow'
  if (dueDate === today) return 'Today'
  if (dueDate < today) return 'Overdue'

  const d1 = new Date(today).getTime()
  const d2 = new Date(dueDate).getTime()
  const diffDays = Math.round((d2 - d1) / (1000 * 60 * 60 * 24))
  if (diffDays > 0) return `In ${diffDays} Days`
  return dueDate
}

export default function FollowUpPage() {
  const [followups, setFollowups] = useState<Followup[]>(ALL_FUTURE_REVISIT_SCHEDULE)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<'upcoming' | 'overdue' | 'completed'>('upcoming')
  const [searchTerm, setSearchTerm] = useState('')
  const [completingId, setCompletingId] = useState<string | null>(null)

  useEffect(() => {
    loadFollowups()
  }, [])

  async function loadFollowups() {
    setLoading(true)
    try {
      const [fuRes, beneRes] = await Promise.allSettled([
        followupAPI.list(),
        beneficiaryAPI.list(),
      ])

      const fetchedFu: Followup[] = fuRes.status === 'fulfilled' ? fuRes.value.data.results || [] : []
      const fetchedBenes: any[] = beneRes.status === 'fulfilled' ? beneRes.value.data.results || [] : []

      // Check IVR call history from localStorage
      const callHistory = getCallHistory()
      const completedMobiles = new Set(
        callHistory.filter((c) => c.status === 'completed').map((c) => c.mobile_number)
      )
      const completedIds = new Set(
        callHistory.filter((c) => c.status === 'completed').map((c) => c.followup_id)
      )

      // Map of all revisit records
      const map = new Map<string, Followup>()

      // 1. Seed with pre-configured future revisit schedule
      ALL_FUTURE_REVISIT_SCHEDULE.forEach((f) => {
        const key = f.beneficiary_id || f._id || f.beneficiary_name || ''
        map.set(key, f)
      })

      // 2. Merge backend followups
      fetchedFu.forEach((f) => {
        const key = f.beneficiary_id || f._id || f.beneficiary_name || ''
        map.set(key, { ...map.get(key), ...f })
      })

      // 3. Add any registered beneficiaries with a future next_visit_date
      fetchedBenes.forEach((b) => {
        if (b.is_deleted) return
        const key = b.beneficiary_id || b.name
        if (!map.has(key) && b.next_visit_date) {
          map.set(key, {
            _id: `fu-${b.beneficiary_id || key}`,
            beneficiary_id: b.beneficiary_id,
            beneficiary_name: b.name,
            phone: b.phone,
            mobile_number: b.phone,
            village: b.village,
            household: b.household,
            visit_type: b.pregnancy_status === 'pregnant' ? 'ANC Revisit' : b.pregnancy_status === 'child' ? 'Immunization Revisit' : 'Health Revisit',
            due_date: b.next_visit_date,
            priority: b.pregnancy_status === 'pregnant' ? 'high' : 'medium',
            status: 'pending',
            notes: `Scheduled future revisit for ${b.village || 'village'}`,
            danger_flag: false,
          })
        }
      })

      // 4. If an IVR call has been completed for this person, move to completed
      const allRecords = Array.from(map.values()).map((f) => {
        const isCalled =
          f.status === 'completed' ||
          (f._id && completedIds.has(f._id)) ||
          (f.beneficiary_id && completedIds.has(f.beneficiary_id)) ||
          (f.mobile_number && completedMobiles.has(f.mobile_number)) ||
          (f.phone && completedMobiles.has(f.phone))

        return isCalled ? { ...f, status: 'completed' } : f
      })

      // Sort by due date ascending (soonest visits first)
      allRecords.sort((a, b) => (a.due_date || '9999').localeCompare(b.due_date || '9999'))
      setFollowups(allRecords)
    } catch {
      setFollowups(ALL_FUTURE_REVISIT_SCHEDULE)
    } finally {
      setLoading(false)
    }
  }

  const today = new Date().toISOString().slice(0, 10)

  // Filter by tab
  const tabFiltered = useMemo(() => {
    return followups.filter((f) => {
      if (tab === 'completed') return f.status === 'completed'
      if (tab === 'overdue') return f.status !== 'completed' && (f.due_date || '9999') < today
      return f.status !== 'completed' && (f.due_date || '9999') >= today
    })
  }, [followups, tab, today])

  // Filter by search term
  const searchedFollowups = useMemo(() => {
    if (!searchTerm.trim()) return tabFiltered
    const q = searchTerm.toLowerCase().trim()
    return tabFiltered.filter(
      (f) =>
        (f.beneficiary_name && f.beneficiary_name.toLowerCase().includes(q)) ||
        (f.beneficiary_id && f.beneficiary_id.toLowerCase().includes(q)) ||
        (f.phone && f.phone.includes(q)) ||
        (f.mobile_number && f.mobile_number.includes(q)) ||
        (f.village && f.village.toLowerCase().includes(q)) ||
        (f.visit_type && f.visit_type.toLowerCase().includes(q))
    )
  }, [tabFiltered, searchTerm])

  async function markComplete(f: Followup) {
    const id = f._id || f.beneficiary_id
    if (!id) return
    setCompletingId(id)

    try {
      await followupAPI.update(id, { status: 'completed' })
    } catch {
      // Offline fallback
    } finally {
      // Immediately move to completed tab
      setFollowups((prev) =>
        prev.map((item) => {
          if (item._id === id || item.beneficiary_id === id) {
            return { ...item, status: 'completed' }
          }
          return item
        })
      )
      setCompletingId(null)
    }
  }

  function priorityColor(p?: string) {
    if (p === 'emergency') return 'bg-red-100 text-red-700 border-red-200'
    if (p === 'high') return 'bg-orange-100 text-orange-700 border-orange-200'
    return 'bg-green-100 text-green-700 border-green-200'
  }

  const upcomingCount = followups.filter((f) => f.status !== 'completed' && (f.due_date || '9999') >= today).length
  const completedCount = followups.filter((f) => f.status === 'completed').length
  const overdueCount = followups.filter((f) => f.status !== 'completed' && (f.due_date || '9999') < today).length

  return (
    <div className="max-w-4xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Calendar className="w-7 h-7 text-green-600" /> Patient Revisit Schedule
          </h2>
          <p className="text-xs text-gray-500 mt-1">
            Tracking all future and scheduled revisit dates for maternal, neonatal, and child health
          </p>
        </div>
      </div>

      {/* Tabs and Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        {/* Tabs */}
        <div className="flex gap-2">
          {[
            { key: 'upcoming', label: `📅 Scheduled Revisits (${upcomingCount})` },
            { key: 'completed', label: `✅ Completed (${completedCount})` },
            { key: 'overdue', label: `⚠️ Overdue (${overdueCount})` },
          ].map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key as any)}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${
                tab === t.key
                  ? 'bg-green-700 text-white shadow-sm'
                  : 'bg-white text-gray-700 border border-gray-200 hover:border-green-400'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="relative flex-1 sm:max-w-xs">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search future visits by name, ID, village…"
            className="w-full pl-9 pr-9 py-2 bg-white border border-gray-200 rounded-xl text-xs focus:outline-none focus:ring-2 focus:ring-green-500 shadow-2xs"
          />
          {searchTerm && (
            <button
              onClick={() => setSearchTerm('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Revisit Cards List */}
      {loading ? (
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-28 bg-green-100 rounded-2xl animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {searchedFollowups.map((f, i) => {
            const isCompleted = f.status === 'completed'
            const dueLabel = getDueLabel(f.due_date)
            const isTomorrow = f.due_date === TOMORROW_DATE
            const phone = f.mobile_number || f.phone

            return (
              <div
                key={f._id || f.beneficiary_id || i}
                className={`bg-white rounded-2xl p-5 shadow-sm border transition-all ${
                  isCompleted
                    ? 'border-gray-200 bg-gray-50/50 opacity-80'
                    : f.danger_flag
                    ? 'border-red-300 bg-gradient-to-r from-red-50/40 via-white to-white'
                    : isTomorrow
                    ? 'border-emerald-300 hover:border-emerald-500'
                    : 'border-gray-100 hover:border-green-300'
                }`}
              >
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                  {/* Left Column: Beneficiary details & Clinical Revisit info */}
                  <div className="flex items-start gap-3.5 flex-1 min-w-0">
                    <div
                      className={`w-11 h-11 rounded-2xl flex items-center justify-center shrink-0 border ${
                        isCompleted
                          ? 'bg-green-100 text-green-700 border-green-200'
                          : f.danger_flag
                          ? 'bg-red-100 text-red-600 border-red-200'
                          : priorityColor(f.priority)
                      }`}
                    >
                      {isCompleted ? (
                        <CheckCircle2 className="w-6 h-6 text-green-700" />
                      ) : f.danger_flag ? (
                        <ShieldAlert className="w-6 h-6 text-red-600" />
                      ) : (
                        <Calendar className="w-5 h-5" />
                      )}
                    </div>

                    <div className="space-y-1 min-w-0 flex-1">
                      {/* Name & ID */}
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-bold text-gray-900 text-base">
                          {f.beneficiary_name}
                        </span>
                        {f.beneficiary_id && (
                          <span className="text-xs font-mono font-semibold px-2 py-0.5 rounded-md bg-gray-100 text-gray-700 border border-gray-200">
                            {f.beneficiary_id}
                          </span>
                        )}
                        <span
                          className={`text-xs px-2.5 py-0.5 rounded-full font-semibold border ${
                            isCompleted
                              ? 'bg-green-100 text-green-800 border-green-200'
                              : priorityColor(f.priority)
                          }`}
                        >
                          {isCompleted ? 'COMPLETED' : f.priority?.toUpperCase()}
                        </span>
                        {f.danger_flag && !isCompleted && (
                          <span className="text-xs px-2 py-0.5 rounded-full font-bold bg-red-600 text-white flex items-center gap-1">
                            <AlertTriangle className="w-3 h-3" /> HIGH RISK
                          </span>
                        )}
                      </div>

                      {/* Revisit type & location */}
                      <div className="flex items-center gap-3 flex-wrap text-xs text-gray-600">
                        <span className="font-semibold text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-200">
                          🏥 {f.visit_type}
                        </span>
                        {(f.village || f.household) && (
                          <span className="flex items-center gap-1 text-gray-500">
                            <MapPin className="w-3.5 h-3.5 text-gray-400" />
                            {f.village} {f.household && `(${f.household})`}
                          </span>
                        )}
                        {phone && (
                          <span className="flex items-center gap-1 font-mono text-gray-700 bg-gray-50 px-2 py-0.5 rounded border border-gray-200">
                            <Phone className="w-3 h-3 text-green-600" />
                            +91 {phone}
                          </span>
                        )}
                      </div>

                      {/* Clinical Revisit Notes */}
                      {f.notes && (
                        <p className="text-xs text-gray-600 italic bg-gray-50/70 p-1.5 rounded-lg border border-gray-100 mt-1">
                          📝 {f.notes}
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Right Column: Revisit Date Badge & Mark Complete Button */}
                  <div className="flex sm:flex-col items-center sm:items-end justify-between w-full sm:w-auto gap-3 shrink-0 border-t sm:border-t-0 pt-3 sm:pt-0">
                    <div className="text-left sm:text-right">
                      <p className="text-[10px] text-gray-400 uppercase tracking-wider font-semibold">Scheduled Revisit Date</p>
                      <p
                        className={`text-sm font-bold ${
                          isCompleted
                            ? 'text-gray-500 line-through'
                            : isTomorrow
                            ? 'text-emerald-700'
                            : f.is_overdue
                            ? 'text-red-600'
                            : 'text-gray-900'
                        }`}
                      >
                        {f.due_date}
                      </p>
                      {!isCompleted && dueLabel && (
                        <span className={`inline-block mt-0.5 text-[10px] font-bold px-2 py-0.5 rounded-md ${
                          isTomorrow
                            ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                            : 'bg-blue-50 text-blue-800 border border-blue-200'
                        }`}>
                          {dueLabel}
                        </span>
                      )}
                    </div>

                    <div>
                      {!isCompleted ? (
                        <button
                          type="button"
                          onClick={() => markComplete(f)}
                          disabled={completingId === (f._id || f.beneficiary_id)}
                          className="flex items-center gap-1.5 px-4 py-2 bg-green-700 hover:bg-green-800 text-white rounded-xl text-xs font-bold transition-all shadow-sm"
                          title="Mark revisit completed and move to Completed tab"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>
                            {completingId === (f._id || f.beneficiary_id)
                              ? 'Saving…'
                              : 'Mark as Completed'}
                          </span>
                        </button>
                      ) : (
                        <span className="flex items-center gap-1.5 text-xs font-semibold text-green-700 bg-green-50 px-3 py-1.5 rounded-lg border border-green-200">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          Revisit Completed
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )
          })}

          {searchedFollowups.length === 0 && (
            <div className="bg-white rounded-2xl p-12 text-center shadow-sm">
              <Clock className="w-10 h-10 text-gray-300 mx-auto mb-3" />
              <p className="text-gray-500 font-bold">No {tab} revisit records found</p>
              <p className="text-xs text-gray-400 mt-1">
                Scheduled future visits and completed revisits will appear here.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
