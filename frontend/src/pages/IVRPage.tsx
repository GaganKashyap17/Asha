import { useState, useEffect, useMemo, useRef } from 'react'
import { useLocation, useSearchParams, Link } from 'react-router-dom'
import {
  PhoneCall,
  Calendar,
  MapPin,
  Phone,
  Search,
  CheckCircle2,
  Sparkles,
  ArrowLeft,
  Users,
} from 'lucide-react'
import type { IVRBeneficiary, IVRCallRecord, CallStatus, Language } from '../components/ivr/ivrTypes'
import {
  getCallHistory,
  fetchCallHistoryFromBackend,
  saveCallRecord,
  isDuplicateCall,
  simulateCall,
  cancelSpeech,
} from '../components/ivr/ivrService'
import IVRConfirmModal from '../components/ivr/IVRConfirmModal'
import IVRCallProgress from '../components/ivr/IVRCallProgress'
import IVRCallHistory from '../components/ivr/IVRCallHistory'
import { ivrAPI, beneficiaryAPI, followupAPI } from '../services/api'

const TOMORROW_DATE = '2026-11-23'

const DEFAULT_DATABASE_BENEFICIARIES: IVRBeneficiary[] = [
  {
    _id: 'PREG-2026-000001',
    beneficiary_id: 'PREG-2026-000001',
    beneficiary_name: 'Priya Rajan',
    mobile_number: '7339223026',
    visit_date: TOMORROW_DATE,
    visit_type: 'ANC Check-up / Maternal Vitals',
    priority: 'high',
    notes: 'Scheduled for ANC 3rd trimester revisit tomorrow — BP and Hb check',
    village: 'Gandhi Nagar',
    household: 'H-12',
  },
  {
    _id: 'PREG-2026-000002',
    beneficiary_id: 'PREG-2026-000002',
    beneficiary_name: 'Ananya Sharma',
    mobile_number: '8056413568',
    visit_date: TOMORROW_DATE,
    visit_type: 'High Risk ANC Follow-up',
    priority: 'emergency',
    notes: 'Scheduled for pre-eclampsia follow-up revisit tomorrow — blood pressure monitoring',
    village: 'Anna Nagar',
    household: 'H-05',
  },
  {
    _id: 'IMM-2026-000001',
    beneficiary_id: 'IMM-2026-000001',
    beneficiary_name: 'Kavitha Murugan',
    mobile_number: '9876543210',
    visit_date: TOMORROW_DATE,
    visit_type: 'Child Immunization Revisit',
    priority: 'high',
    notes: 'Child vaccination due tomorrow — Pentavalent-1 and OPV booster dose',
    village: 'Subhash Nagar',
    household: 'H-23',
  },
  {
    _id: 'NEWB-2026-000001',
    beneficiary_id: 'NEWB-2026-000001',
    beneficiary_name: 'Sumathi Devi',
    mobile_number: '8765432109',
    visit_date: TOMORROW_DATE,
    visit_type: 'Newborn Postnatal Revisit',
    priority: 'medium',
    notes: 'Scheduled for 14-day newborn health, breastfeeding & temperature revisit tomorrow',
    village: 'Nehru Street',
    household: 'H-18',
  },
  {
    _id: 'PREG-2026-000003',
    beneficiary_id: 'PREG-2026-000003',
    beneficiary_name: 'Meena Krishnan',
    mobile_number: '7654321098',
    visit_date: TOMORROW_DATE,
    visit_type: 'Maternal Nutrition & IFA Revisit',
    priority: 'medium',
    notes: 'Scheduled for gestational blood sugar review and IFA tablet replenishment revisit tomorrow',
    village: 'Ramanathapuram',
    household: 'H-09',
  },
]

const INITIAL_DEMO_RECORDS: IVRCallRecord[] = [
  {
    call_id: 'call-2026-002',
    beneficiary_name: 'Ananya Sharma',
    mobile_number: '8056413568',
    visit_date: TOMORROW_DATE,
    visit_type: 'High Risk ANC Follow-up',
    language: 'en',
    reminder_message:
      'Hello! This is a reminder from your local ASHA worker. Your ASHA worker is scheduled to visit you on 2026-11-23 for High Risk ANC Follow-up. Please be available at home. Thank you.',
    status: 'completed',
    outcome: 'Reminder played successfully',
    initiated_at: new Date().toISOString(),
    completed_at: new Date().toISOString(),
    duration_seconds: 28,
    followup_id: 'PREG-2026-000002',
  },
  {
    call_id: 'call-2026-001',
    beneficiary_name: 'Priya Rajan',
    mobile_number: '7339223026',
    visit_date: TOMORROW_DATE,
    visit_type: 'ANC Check-up / Maternal Vitals',
    language: 'ta',
    reminder_message:
      'வணக்கம்! இது உங்கள் உள்ளூர் ASHA பணியாளரிடமிருந்து ஒரு நினைவூட்டல். உங்கள் ASHA பணியாளர் 2026-11-23 அன்று ANC Check-up க்காக உங்களை சந்திக்க வருவார்கள். தயவுசெய்து வீட்டில் இருங்கள். நன்றி.',
    status: 'completed',
    outcome: 'Reminder played successfully',
    initiated_at: new Date(Date.now() - 3600000).toISOString(),
    completed_at: new Date(Date.now() - 3600000 + 32000).toISOString(),
    duration_seconds: 32,
    followup_id: 'PREG-2026-000001',
  },
]

const PRIORITY_STYLES: Record<string, string> = {
  emergency: 'bg-red-50 border-red-200 text-red-700',
  high: 'bg-orange-50 border-orange-200 text-orange-700',
  medium: 'bg-amber-50 border-amber-200 text-amber-700',
  low: 'bg-green-50 border-green-200 text-green-700',
}

function maskMobile(num: string): string {
  const digits = num.replace(/\D/g, '')
  if (digits.length >= 5) return `${digits.slice(0, 5)} XXXXX`
  return num
}

export default function IVRPage() {
  const location = useLocation()
  const [searchParams] = useSearchParams()

  const [activeTab, setActiveTab] = useState<'reminders' | 'history'>('reminders')
  const [beneficiaries, setBeneficiaries] = useState<IVRBeneficiary[]>(DEFAULT_DATABASE_BENEFICIARIES)
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [confirmBeneficiary, setConfirmBeneficiary] = useState<IVRBeneficiary | null>(null)
  const [activeCall, setActiveCall] = useState<{
    beneficiary: IVRBeneficiary
    language: Language
  } | null>(null)
  const [callStatus, setCallStatus] = useState<CallStatus>('idle')
  const [callHistory, setCallHistory] = useState<IVRCallRecord[]>([])
  const [quickMobile, setQuickMobile] = useState('8056413568')
  const [highlightedId, setHighlightedId] = useState<string | null>(null)

  const autoCallHandledRef = useRef(false)

  // ── Seed history records and sync with backend on mount ─────────────
  useEffect(() => {
    async function initHistory() {
      const existing = getCallHistory()
      let updated = false
      INITIAL_DEMO_RECORDS.forEach((rec) => {
        if (!existing.some((e) => e.mobile_number === rec.mobile_number)) {
          saveCallRecord(rec)
          updated = true
        }
      })
      if (updated || existing.length === 0) {
        setCallHistory(getCallHistory())
      } else {
        setCallHistory(existing)
      }

      // Sync with unified backend /api/ivr/history/
      const synced = await fetchCallHistoryFromBackend()
      if (synced && synced.length > 0) {
        setCallHistory(synced)
      }
    }

    initHistory()
  }, [])

  // ── Load Real Database Beneficiaries via integrated ivrAPI ──────────
  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true)

        // Try integrated IVR backend endpoint first
        let loadedFromBackend = false
        try {
          const ivrRes = await ivrAPI.getBeneficiaries(true)
          if (ivrRes.data?.results && ivrRes.data.results.length > 0) {
            setBeneficiaries(ivrRes.data.results)
            loadedFromBackend = true
          }
        } catch (ivrErr) {
          console.warn('Fallback to direct beneficiaryAPI/followupAPI:', ivrErr)
        }

        if (!loadedFromBackend) {
          const [bRes, fRes] = await Promise.allSettled([
            beneficiaryAPI.list(),
            followupAPI.list(),
          ])

          const bList: any[] = bRes.status === 'fulfilled' ? bRes.value.data.results || [] : []
          const fList: any[] = fRes.status === 'fulfilled' ? fRes.value.data.results || [] : []

          const followupMap = new Map<string, any>()
          fList.forEach((f) => {
            if (f.beneficiary_id) followupMap.set(f.beneficiary_id, f)
            if (f.beneficiary_name) followupMap.set(f.beneficiary_name.toLowerCase(), f)
            if (f.mobile_number) followupMap.set(f.mobile_number, f)
          })

          const combinedMap = new Map<string, IVRBeneficiary>()

          // 1. Seed with default 5 database beneficiaries
          DEFAULT_DATABASE_BENEFICIARIES.forEach((b) => {
            combinedMap.set(b.beneficiary_id || b.beneficiary_name, b)
          })

          // 2. Merge all beneficiaries from the database / Beneficiary Bar
          bList.forEach((b) => {
            if (b.is_deleted) return
            const key = b.beneficiary_id || b.name
            const matchedFu =
              followupMap.get(b.beneficiary_id) ||
              followupMap.get((b.name || '').toLowerCase()) ||
              followupMap.get(b.phone)

            const phone = b.phone || matchedFu?.mobile_number || matchedFu?.phone || '8056413568'
            const visitDate = matchedFu?.due_date || b.next_visit_date || TOMORROW_DATE
            const visitType =
              matchedFu?.visit_type ||
              b.visit_type ||
              (b.pregnancy_status === 'pregnant'
                ? 'ANC Revisit'
                : b.pregnancy_status === 'child'
                ? 'Immunization Revisit'
                : 'Health Revisit')
            const priority = matchedFu?.priority || b.priority || (b.pregnancy_status === 'pregnant' ? 'high' : 'medium')
            const notes =
              matchedFu?.notes ||
              b.notes ||
              `Scheduled revisit for ${b.village || 'village'} (${b.household || 'household'})`

            combinedMap.set(key, {
              _id: b.beneficiary_id || b._id || `b-${key}`,
              beneficiary_id: b.beneficiary_id,
              beneficiary_name: b.name || key,
              mobile_number: phone,
              visit_date: visitDate,
              visit_type: visitType,
              priority,
              notes,
              village: b.village,
              household: b.household,
            })
          })

          const tomorrowCallsOnly = Array.from(combinedMap.values()).filter(
            (b) => b.visit_date === TOMORROW_DATE
          )
          setBeneficiaries(tomorrowCallsOnly.length > 0 ? tomorrowCallsOnly : DEFAULT_DATABASE_BENEFICIARIES)
        }
      } catch (err) {
        console.error('Error fetching beneficiaries for IVR:', err)
        setBeneficiaries(DEFAULT_DATABASE_BENEFICIARIES)
      } finally {
        setLoading(false)
      }
    }

    loadData()
  }, [])

  // ── Auto-call Trigger from Follow-Up Bar Click ──────────────────────
  useEffect(() => {
    if (autoCallHandledRef.current) return

    const navState = location.state as { autoCall?: boolean; beneficiary?: IVRBeneficiary } | undefined
    const isAutoCall = navState?.autoCall || searchParams.get('auto_call') === 'true'

    if (isAutoCall) {
      autoCallHandledRef.current = true
      let target: IVRBeneficiary | null = null

      if (navState?.beneficiary) {
        target = navState.beneficiary
      } else {
        const phone = searchParams.get('phone')
        const name = searchParams.get('name')
        const type = searchParams.get('type')
        const date = searchParams.get('date')
        const id = searchParams.get('id')

        if (phone || name) {
          target = {
            _id: id || `auto-${phone}`,
            beneficiary_id: id || undefined,
            beneficiary_name: name || 'Citizen Beneficiary',
            mobile_number: phone || '8056413568',
            visit_date: date || TOMORROW_DATE,
            visit_type: type || 'Upcoming Follow-up Revisit',
            priority: 'high',
            notes: 'Automated call triggered from Follow-up Bar',
          }
        }
      }

      if (target) {
        setQuickMobile(target.mobile_number)
        setHighlightedId(target.beneficiary_id || target._id || null)
        setActiveTab('reminders')
        // Automatically open confirmation modal
        setConfirmBeneficiary(target)
      }
    }
  }, [location.state, searchParams])

  const refreshHistory = async () => {
    const list = await fetchCallHistoryFromBackend()
    setCallHistory(list)
  }

  // ── Handle confirm → start call ────────────────────────────────────
  const handleConfirm = (lang: Language) => {
    if (!confirmBeneficiary) return
    const beneficiary = confirmBeneficiary
    setConfirmBeneficiary(null)
    setActiveCall({ beneficiary, language: lang })
    setCallStatus('initiating')

    simulateCall(beneficiary, lang, beneficiary.beneficiary_id || beneficiary._id, (status) => {
      setCallStatus(status)
    })
      .then(async (rec) => {
        // When IVR call finishes, update followup status so it moves to Completed tab!
        if (rec.status === 'completed') {
          const fid = beneficiary.beneficiary_id || beneficiary._id
          if (fid) {
            try {
              await followupAPI.update(fid, { status: 'completed' })
            } catch {
              // ignore offline error
            }
          }
        }
        await refreshHistory()
      })
      .catch(console.error)
  }

  // ── Handle cancel / close of progress modal ─────────────────────────
  const handleProgressClose = () => {
    cancelSpeech()
    setActiveCall(null)
    setCallStatus('idle')
    refreshHistory()
  }

  // Filter beneficiaries: strictly tomorrow's calls only + search term
  const filteredBeneficiaries = useMemo(() => {
    const tomorrowOnly = beneficiaries.filter((b) => b.visit_date === TOMORROW_DATE)
    if (!searchTerm.trim()) return tomorrowOnly
    const term = searchTerm.toLowerCase()
    return tomorrowOnly.filter(
      (b) =>
        b.beneficiary_name.toLowerCase().includes(term) ||
        (b.beneficiary_id && b.beneficiary_id.toLowerCase().includes(term)) ||
        b.mobile_number.includes(term) ||
        (b.village && b.village.toLowerCase().includes(term))
    )
  }, [beneficiaries, searchTerm])

  return (
    <div className="min-h-screen bg-gray-50 pb-12">
      {/* Page Header */}
      <div className="bg-white border-b border-gray-100 shadow-xs sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              to="/followups"
              className="p-2 text-gray-500 hover:text-green-700 hover:bg-green-50 rounded-xl transition-colors"
              title="Back to Follow-ups"
            >
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <div className="bg-green-700 rounded-xl p-2.5 shadow-xs">
              <PhoneCall className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900">IVR Reminder Bar</h1>
              <p className="text-xs text-gray-400">
                Connected to Stored Beneficiaries &amp; Revisit Schedule
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link
              to="/beneficiaries"
              className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-gray-600 bg-gray-100 hover:bg-gray-200 rounded-xl transition-colors"
            >
              <Users className="w-3.5 h-3.5" /> Beneficiary Bar
            </Link>
            <div className="flex items-center gap-2 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-bold px-3 py-1.5 rounded-full">
              ⚡ LIVE SIMULATOR
            </div>
          </div>
        </div>

        {/* Tab Nav */}
        <div className="max-w-4xl mx-auto px-4 flex gap-1 pb-0">
          {[
            {
              key: 'reminders',
              label: `📅 Tomorrow Revisit Reminders (${beneficiaries.length})`,
            },
            {
              key: 'history',
              label: `📋 Call History (${callHistory.length})`,
            },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as 'reminders' | 'history')}
              className={`px-4 py-3 text-sm font-semibold border-b-2 transition-colors ${
                activeTab === tab.key
                  ? 'border-green-700 text-green-700'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 py-6 space-y-5">
        {/* Banner */}
        {activeTab === 'reminders' && (
          <div className="bg-blue-50 border border-blue-200 rounded-2xl p-4 flex items-start gap-3">
            <Sparkles className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-bold text-blue-900">
                Synchronized with Stored Beneficiary Data
              </p>
              <p className="text-xs text-blue-700 leading-relaxed mt-0.5">
                Every citizen shown here is registered in your Beneficiary Bar. Triggering an IVR
                call will play an automated multilingual voice reminder (Tamil, English, Hindi,
                Kannada) through your device's audio speaker via the Web Speech API.
              </p>
            </div>
          </div>
        )}

        {/* ── REMINDERS TAB ────────────────────────────────────────── */}
        {activeTab === 'reminders' && (
          <div className="space-y-4">
            {/* Quick Call by Mobile Number */}
            <div className="bg-white rounded-2xl shadow-xs border border-green-300 p-4 bg-gradient-to-r from-green-50/70 to-emerald-50/40">
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-bold text-gray-900 flex items-center gap-1.5">
                    <span>⚡ Quick Call by Mobile Number</span>
                  </h3>
                  <p className="text-xs text-gray-500">
                    Directly initiate a simulated reminder call to any citizen's mobile.
                  </p>
                </div>
                <div className="flex items-center gap-2 w-full sm:w-auto">
                  <input
                    type="tel"
                    value={quickMobile}
                    onChange={(e) => setQuickMobile(e.target.value)}
                    placeholder="e.g. 8056413568"
                    className="border border-gray-300 rounded-xl px-3 py-2 text-sm font-mono w-full sm:w-44 focus:outline-none focus:ring-2 focus:ring-green-500 bg-white"
                  />
                  <button
                    onClick={() => {
                      const num = quickMobile.trim() || '8056413568'
                      const matched = beneficiaries.find(
                        (b) => b.mobile_number === num || b.mobile_number.endsWith(num)
                      )
                      setConfirmBeneficiary({
                        _id: matched?._id || `custom-${num}`,
                        beneficiary_id: matched?.beneficiary_id,
                        beneficiary_name: matched?.beneficiary_name || 'Citizen Beneficiary',
                        mobile_number: num,
                        visit_date: matched?.visit_date || TOMORROW_DATE,
                        visit_type: matched?.visit_type || 'Upcoming Follow-up Visit',
                        priority: matched?.priority || 'high',
                        notes:
                          matched?.notes ||
                          'Direct IVR reminder call initiated from portal',
                        village: matched?.village,
                        household: matched?.household,
                      })
                    }}
                    className="flex items-center gap-1.5 bg-green-700 hover:bg-green-800 text-white text-xs font-bold px-4 py-2.5 rounded-xl transition-colors shrink-0 shadow-xs"
                  >
                    <Phone className="w-3.5 h-3.5" />
                    <span>Call Now</span>
                  </button>
                </div>
              </div>

              {/* Quick Action Chips for Registered Beneficiaries */}
              <div className="mt-3 flex items-center gap-2 pt-2.5 border-t border-green-200/60 text-xs text-green-900 flex-wrap">
                <span className="font-semibold text-gray-600">Stored Beneficiaries:</span>
                {DEFAULT_DATABASE_BENEFICIARIES.slice(0, 3).map((b) => (
                  <button
                    key={b.mobile_number}
                    type="button"
                    onClick={() => {
                      setQuickMobile(b.mobile_number)
                      setConfirmBeneficiary(b)
                      setHighlightedId(b.beneficiary_id || b._id || null)
                    }}
                    className="bg-white hover:bg-green-100 text-green-900 font-semibold px-2.5 py-1 rounded-lg transition-colors flex items-center gap-1 border border-green-300 shadow-2xs"
                  >
                    <span>📱 {b.beneficiary_name}</span>
                    <span className="font-mono text-[10px] text-gray-500">
                      ({b.mobile_number})
                    </span>
                  </button>
                ))}
              </div>
            </div>

            {/* Search Filter Bar */}
            <div className="relative">
              <Search className="w-4 h-4 text-gray-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search stored beneficiaries by name, ID, phone, or village..."
                className="w-full pl-10 pr-4 py-2.5 bg-white border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-green-500 shadow-xs"
              />
            </div>

            {/* Beneficiaries List */}
            {loading ? (
              <div className="space-y-3">
                {[...Array(4)].map((_, i) => (
                  <div key={i} className="h-28 bg-green-100 rounded-2xl animate-pulse" />
                ))}
              </div>
            ) : (
              <div className="space-y-3">
                {filteredBeneficiaries.map((b) => {
                  const alreadyCalled = isDuplicateCall(b.beneficiary_id ?? b._id, b.mobile_number)
                  const isHighlighted =
                    highlightedId &&
                    (b.beneficiary_id === highlightedId || b._id === highlightedId)
                  const isTomorrow = b.visit_date === TOMORROW_DATE

                  return (
                    <div
                      key={b.beneficiary_id || b._id}
                      className={`bg-white rounded-2xl shadow-xs border p-5 hover:shadow-md transition-all relative overflow-hidden ${
                        isHighlighted
                          ? 'border-green-500 ring-2 ring-green-400/40 bg-gradient-to-r from-green-50/50 to-white'
                          : 'border-gray-100'
                      }`}
                    >
                      {/* Highlight Pill if arrived from Follow Up Bar */}
                      {isHighlighted && (
                        <div className="absolute top-0 right-0 bg-green-600 text-white text-[10px] font-bold px-3 py-0.5 rounded-bl-lg uppercase tracking-wider">
                          Selected for Follow-Up Call
                        </div>
                      )}

                      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                        <div className="flex-1 min-w-0 space-y-2">
                          {/* Name + Beneficiary ID + Priority */}
                          <div className="flex items-center gap-2.5 flex-wrap">
                            <h3 className="text-base font-bold text-gray-900">
                              {b.beneficiary_name}
                            </h3>
                            {b.beneficiary_id && (
                              <span className="text-xs font-mono font-semibold px-2 py-0.5 rounded-md bg-gray-100 text-gray-700 border border-gray-200">
                                {b.beneficiary_id}
                              </span>
                            )}
                            {b.priority && (
                              <span
                                className={`text-xs font-semibold px-2.5 py-0.5 rounded-full border ${
                                  PRIORITY_STYLES[b.priority] ?? 'bg-gray-100 text-gray-600'
                                }`}
                              >
                                {b.priority.toUpperCase()}
                              </span>
                            )}
                          </div>

                          {/* Mobile and Location */}
                          <div className="flex items-center gap-3 flex-wrap text-xs text-gray-600">
                            <span className="font-mono text-gray-800 bg-gray-50 px-2 py-0.5 rounded border border-gray-200 flex items-center gap-1">
                              <Phone className="w-3 h-3 text-green-600" />
                              +91 {maskMobile(b.mobile_number)}
                            </span>
                            {(b.village || b.household) && (
                              <span className="flex items-center gap-1 text-gray-500">
                                <MapPin className="w-3.5 h-3.5 text-gray-400" />
                                {b.village} {b.household && `(${b.household})`}
                              </span>
                            )}
                          </div>

                          {/* Revisit Date & Visit Type */}
                          <div className="flex items-center gap-3 flex-wrap text-xs text-gray-700">
                            <span className="font-semibold text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                              🏥 {b.visit_type}
                            </span>
                            <span className="flex items-center gap-1 font-medium text-gray-600">
                              <Calendar className="w-3.5 h-3.5 text-green-600" />
                              Revisit Due: {b.visit_date} {isTomorrow && ' (Tomorrow)'}
                            </span>
                          </div>

                          {/* Notes */}
                          {b.notes && (
                            <p className="text-xs text-gray-500 italic bg-gray-50/60 p-1.5 rounded-lg border border-gray-100">
                              📝 {b.notes}
                            </p>
                          )}
                        </div>

                        {/* CTA Button */}
                        <div className="flex-shrink-0 w-full sm:w-auto flex justify-end">
                          {alreadyCalled ? (
                            <button
                              disabled
                              className="flex items-center gap-1.5 bg-gray-100 text-gray-400 text-xs font-semibold px-4 py-2.5 rounded-xl cursor-not-allowed border border-gray-200"
                            >
                              <CheckCircle2 className="w-4 h-4 text-green-600" />
                              <span>Reminded Today</span>
                            </button>
                          ) : (
                            <button
                              onClick={() => {
                                setHighlightedId(b.beneficiary_id || b._id || null)
                                setConfirmBeneficiary(b)
                              }}
                              className="flex items-center gap-2 bg-green-700 hover:bg-green-800 text-white text-xs font-bold px-4 py-2.5 rounded-xl transition-all shadow-xs hover:shadow hover:scale-102"
                            >
                              <PhoneCall className="w-4 h-4" />
                              <span>Send IVR Reminder</span>
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}

                {filteredBeneficiaries.length === 0 && (
                  <div className="bg-white rounded-2xl p-12 text-center shadow-xs">
                    <Users className="w-10 h-10 text-gray-300 mx-auto mb-3" />
                    <p className="text-gray-500 font-medium">No matching beneficiaries found</p>
                    <p className="text-xs text-gray-400 mt-1">
                      Check your search query or register new beneficiaries in the Beneficiary Bar.
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ── HISTORY TAB ────────────────────────────────────────── */}
        {activeTab === 'history' && (
          <IVRCallHistory records={callHistory} onRefresh={refreshHistory} />
        )}
      </div>

      {/* ── Modals ─────────────────────────────────────────────────── */}
      {confirmBeneficiary && (
        <IVRConfirmModal
          beneficiary={confirmBeneficiary}
          onConfirm={handleConfirm}
          onCancel={() => setConfirmBeneficiary(null)}
        />
      )}

      {activeCall && (
        <IVRCallProgress
          beneficiary={activeCall.beneficiary}
          status={callStatus}
          language={activeCall.language}
          onCancel={handleProgressClose}
          onComplete={(_record) => {
            handleProgressClose()
          }}
        />
      )}
    </div>
  )
}
