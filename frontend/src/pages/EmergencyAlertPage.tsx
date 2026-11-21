import { useEffect, useState, useMemo } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  MapPin,
  Phone,
  Search,
  X,
  Clock,
  ShieldAlert,
  Hospital,
} from 'lucide-react'
import { alertAPI, visitAPI, beneficiaryAPI } from '../services/api'

export interface Alert {
  _id?: string
  id?: string
  visit_id?: string
  draft_id?: string
  beneficiary_name?: string
  beneficiary_id?: string
  phone?: string
  mobile_number?: string
  village?: string
  household?: string
  visit_type?: string
  danger_signs?: string[]
  referral_status?: string
  resolved?: boolean
  created_at?: string
  danger_details?: { rule_id?: string; name?: string; severity?: string }[]
}

export default function EmergencyAlertPage() {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [loading, setLoading] = useState(true)
  const [filterTab, setFilterTab] = useState<'active' | 'referred' | 'all'>('active')
  const [searchTerm, setSearchTerm] = useState('')
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  useEffect(() => {
    loadAlerts()
  }, [])

  async function loadAlerts() {
    setLoading(true)
    try {
      const [alertsRes, visitsRes, beneRes] = await Promise.allSettled([
        alertAPI.list(),
        visitAPI.list(),
        beneficiaryAPI.list(),
      ])

      const rawAlerts: Alert[] =
        alertsRes.status === 'fulfilled' ? alertsRes.value.data.results || [] : []
      const rawVisits: any[] =
        visitsRes.status === 'fulfilled' ? visitsRes.value.data.results || [] : []
      const rawBenes: any[] =
        beneRes.status === 'fulfilled' ? beneRes.value.data.results || [] : []

      // Build lookup maps
      const beneMap = new Map<string, any>()
      rawBenes.forEach((b) => {
        if (b.beneficiary_id) beneMap.set(b.beneficiary_id, b)
        if (b.name) beneMap.set(b.name.toLowerCase().trim(), b)
        if (b.phone) beneMap.set(b.phone, b)
      })

      const alertsMap = new Map<string, Alert>()

      // 1. Add all backend alerts
      rawAlerts.forEach((a) => {
        const key = a._id || a.visit_id || a.draft_id || `${a.beneficiary_name}-${a.created_at}`
        
        // Enrich beneficiary details
        const b =
          (a.beneficiary_id && beneMap.get(a.beneficiary_id)) ||
          (a.beneficiary_name && beneMap.get(a.beneficiary_name.toLowerCase().trim())) ||
          (a.phone && beneMap.get(a.phone))

        alertsMap.set(key, {
          ...a,
          _id: a._id || a.id || key,
          beneficiary_id: a.beneficiary_id || b?.beneficiary_id,
          beneficiary_name: a.beneficiary_name || b?.name || 'Citizen Beneficiary',
          phone: a.phone || a.mobile_number || b?.phone,
          village: a.village || b?.village,
          household: a.household || b?.household,
          visit_type: a.visit_type || (b?.pregnancy_status === 'pregnant' ? 'High Risk ANC Revisit' : 'Clinical Revisit'),
        })
      })

      // 2. Cross-reference visits collection: Any visit flagged as emergency MUST appear here
      rawVisits.forEach((v) => {
        if (v.danger_flag || (v.danger_signs && v.danger_signs.length > 0) || v.priority === 'emergency') {
          const vId = v._id || v.id || ''
          const dId = v.draft_id || ''

          // Check if already in alerts
          const alreadyLinked = Array.from(alertsMap.values()).some(
            (a) =>
              (vId && (a.visit_id === vId || a._id === vId)) ||
              (dId && a.draft_id === dId) ||
              (v.beneficiary_id && a.beneficiary_id === v.beneficiary_id && (a.created_at || '').slice(0, 10) === (v.created_at || v.visit_date || '').slice(0, 10))
          )

          if (!alreadyLinked) {
            const b =
              (v.beneficiary_id && beneMap.get(v.beneficiary_id)) ||
              (v.beneficiary_name && beneMap.get(v.beneficiary_name.toLowerCase().trim())) ||
              (v.phone && beneMap.get(v.phone))

            const alertKey = `visit-alert-${vId || Math.random().toString(36).substring(2)}`
            alertsMap.set(alertKey, {
              _id: alertKey,
              visit_id: vId,
              draft_id: dId || undefined,
              beneficiary_id: v.beneficiary_id || b?.beneficiary_id,
              beneficiary_name: v.beneficiary_name || b?.name || 'Citizen Beneficiary',
              phone: v.phone || b?.phone,
              village: v.village || b?.village,
              household: v.household || b?.household,
              visit_type: v.visit_type || 'Patient Revisit',
              danger_signs: v.danger_signs && v.danger_signs.length > 0 ? v.danger_signs : ['Clinical Danger Sign Flagged in Revisit History'],
              danger_details: v.danger_details || v.danger_detection_results || [],
              referral_status: v.referral_status || 'pending',
              resolved: v.resolved || false,
              created_at: v.created_at || v.visit_date || new Date().toISOString(),
            })
          }
        }
      })

      const combined = Array.from(alertsMap.values())
      // Sort newest first
      combined.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''))
      setAlerts(combined)
    } catch (err) {
      console.error('Failed to load emergency alerts:', err)
    } finally {
      setLoading(false)
    }
  }

  async function markReferred(alert: Alert) {
    const id = alert._id || alert.visit_id
    if (!id) return
    setActionLoading(id)
    try {
      await alertAPI.update(id, { referral_status: 'referred', resolved: true })
    } catch {
      // offline fallback
    } finally {
      setAlerts((prev) =>
        prev.map((a) =>
          a._id === id || a.visit_id === id
            ? { ...a, referral_status: 'referred', resolved: true }
            : a
        )
      )
      setActionLoading(null)
    }
  }

  // Filter by tab
  const filteredByTab = useMemo(() => {
    return alerts.filter((a) => {
      const isResolved = a.resolved || a.referral_status === 'referred'
      if (filterTab === 'active') return !isResolved
      if (filterTab === 'referred') return isResolved
      return true
    })
  }, [alerts, filterTab])

  // Filter by search query
  const filteredAlerts = useMemo(() => {
    if (!searchTerm.trim()) return filteredByTab
    const q = searchTerm.toLowerCase().trim()
    return filteredByTab.filter(
      (a) =>
        (a.beneficiary_name && a.beneficiary_name.toLowerCase().includes(q)) ||
        (a.beneficiary_id && a.beneficiary_id.toLowerCase().includes(q)) ||
        (a.phone && a.phone.includes(q)) ||
        (a.village && a.village.toLowerCase().includes(q)) ||
        (a.danger_signs && a.danger_signs.some((s) => s.toLowerCase().includes(q)))
    )
  }, [filteredByTab, searchTerm])

  const activeCount = alerts.filter((a) => !a.resolved && a.referral_status !== 'referred').length

  return (
    <div className="max-w-4xl mx-auto space-y-5">
      {/* Emergency Header Banner */}
      <div className="bg-gradient-to-r from-red-600 to-rose-700 text-white rounded-2xl p-6 shadow-md flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 bg-white/20 backdrop-blur-md rounded-2xl flex items-center justify-center shrink-0 border border-white/30 animate-pulse">
            <ShieldAlert className="w-8 h-8 text-white" />
          </div>
          <div>
            <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
              Emergency Alerts & Danger Cases
            </h2>
            <p className="text-red-100 text-sm mt-0.5">
              {activeCount} active emergency case{activeCount !== 1 ? 's' : ''} requiring immediate hospital referral
            </p>
          </div>
        </div>

        <div className="bg-white/10 backdrop-blur-md px-4 py-2 rounded-xl border border-white/20 text-right shrink-0">
          <span className="text-xs uppercase tracking-wider text-red-200 block font-semibold">Priority Protocol</span>
          <span className="text-sm font-bold text-white flex items-center gap-1">
            <Hospital className="w-4 h-4" /> Immediate PHC Referral
          </span>
        </div>
      </div>

      {/* Clinical Disclaimer */}
      <div className="bg-orange-50 border border-orange-200 rounded-2xl p-4 text-xs text-orange-900 flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-orange-600 shrink-0 mt-0.5" />
        <div className="leading-relaxed">
          <strong>Clinical Safety Protocol:</strong> These emergency alerts are automatically generated whenever maternal or neonatal danger signs are detected during speech-to-text or structured clinical revisits (based on WHO and IMNCI emergency guidelines). Immediate Primary Health Centre (PHC) referral and follow-up contact is mandatory.
        </div>
      </div>

      {/* Tabs and Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        {/* Tabs */}
        <div className="flex gap-2">
          {[
            { key: 'active', label: `🚨 Active Alerts (${activeCount})` },
            { key: 'referred', label: `✅ Referred to PHC` },
            { key: 'all', label: `📋 All (${alerts.length})` },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setFilterTab(tab.key as any)}
              className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all ${
                filterTab === tab.key
                  ? 'bg-red-600 text-white shadow-sm'
                  : 'bg-white text-gray-700 border border-gray-200 hover:border-red-300'
              }`}
            >
              {tab.label}
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
            placeholder="Search by name, ID, phone, symptom…"
            className="w-full pl-9 pr-9 py-2 bg-white border border-gray-200 rounded-xl text-xs focus:outline-none focus:ring-2 focus:ring-red-500 shadow-2xs"
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

      {/* Alert Cards List */}
      {loading ? (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-36 bg-red-50/70 rounded-2xl animate-pulse border border-red-100" />
          ))}
        </div>
      ) : (
        <div className="space-y-4">
          {filteredAlerts.map((a, i) => {
            const isReferred = a.resolved || a.referral_status === 'referred'
            const phone = a.phone || a.mobile_number

            return (
              <div
                key={a._id || a.visit_id || i}
                className={`bg-white rounded-2xl p-5 shadow-sm border transition-all ${
                  isReferred
                    ? 'border-gray-200 bg-gray-50/40 opacity-90'
                    : 'border-2 border-red-300 hover:border-red-500 hover:shadow-md'
                }`}
              >
                {/* Header row: Beneficiary Name & Status Badge */}
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pb-3 border-b border-gray-100">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2.5 flex-wrap">
                      <span className="font-bold text-gray-900 text-lg">
                        {a.beneficiary_name}
                      </span>
                      {a.beneficiary_id && (
                        <span className="text-xs font-mono font-semibold px-2 py-0.5 rounded-md bg-gray-100 text-gray-800 border border-gray-200">
                          {a.beneficiary_id}
                        </span>
                      )}
                      {!isReferred && (
                        <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-red-600 text-white tracking-wider uppercase flex items-center gap-1 shadow-2xs">
                          <AlertTriangle className="w-3 h-3" /> Emergency Case
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-3 text-xs text-gray-500 flex-wrap">
                      <span className="font-semibold text-gray-700">🏥 {a.visit_type}</span>
                      <span>&bull;</span>
                      <span className="flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5 text-gray-400" />
                        Detected: {(a.created_at || '').slice(0, 10) || 'Recently'}
                      </span>
                    </div>
                  </div>

                  <span
                    className={`text-xs px-3 py-1 rounded-full font-bold flex items-center gap-1.5 ${
                      isReferred
                        ? 'bg-green-100 text-green-800 border border-green-300'
                        : 'bg-red-100 text-red-700 border border-red-300 animate-pulse'
                    }`}
                  >
                    {isReferred ? (
                      <>
                        <CheckCircle2 className="w-3.5 h-3.5 text-green-700" />
                        Referred to PHC
                      </>
                    ) : (
                      <>
                        <AlertTriangle className="w-3.5 h-3.5 text-red-600" />
                        Pending Referral
                      </>
                    )}
                  </span>
                </div>

                {/* Beneficiary Clinical Details Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 py-3 text-xs text-gray-700">
                  {(a.village || a.household) && (
                    <div className="flex items-center gap-2 bg-gray-50 p-2.5 rounded-xl border border-gray-200/60">
                      <MapPin className="w-4 h-4 text-gray-500 shrink-0" />
                      <div>
                        <p className="text-[10px] text-gray-400 font-medium">Household Location</p>
                        <p className="font-semibold text-gray-800">
                          {a.village} {a.household && `(${a.household})`}
                        </p>
                      </div>
                    </div>
                  )}

                  {phone && (
                    <div className="flex items-center gap-2 bg-gray-50 p-2.5 rounded-xl border border-gray-200/60">
                      <Phone className="w-4 h-4 text-green-600 shrink-0" />
                      <div>
                        <p className="text-[10px] text-gray-400 font-medium">Citizen Contact</p>
                        <p className="font-mono font-bold text-gray-800">+91 {phone}</p>
                      </div>
                    </div>
                  )}
                </div>

                {/* Detected Danger Signs List Box */}
                <div className="bg-red-50/80 border border-red-200 rounded-xl p-3.5 mb-4 space-y-1.5">
                  <p className="text-xs font-bold text-red-900 flex items-center gap-1.5 uppercase tracking-wide">
                    <ShieldAlert className="w-4 h-4 text-red-600" />
                    Detected Danger Signs (Immediate Referral Required):
                  </p>
                  <ul className="space-y-1 pl-1">
                    {(a.danger_signs && a.danger_signs.length > 0
                      ? a.danger_signs
                      : ['Critical clinical observation flagged during patient visit']
                    ).map((s, j) => (
                      <li key={j} className="text-xs font-medium text-red-800 flex items-start gap-1.5">
                        <span className="text-red-500 font-bold shrink-0 mt-0.5">•</span>
                        <span>{s}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Action Button: Refer to PHC */}
                <div className="flex items-center justify-end pt-1">
                  {!isReferred ? (
                    <button
                      onClick={() => markReferred(a)}
                      disabled={actionLoading === a._id}
                      className="flex items-center gap-2 px-5 py-2.5 bg-green-700 hover:bg-green-800 text-white rounded-xl text-xs font-bold transition-all shadow-sm"
                    >
                      <CheckCircle2 className="w-4 h-4" />
                      <span>{actionLoading === a._id ? 'Updating…' : 'Mark as Referred to PHC'}</span>
                    </button>
                  ) : (
                    <span className="flex items-center gap-1.5 text-xs font-semibold text-green-700 bg-green-50 px-3 py-1.5 rounded-lg border border-green-200">
                      <CheckCircle2 className="w-4 h-4" />
                      Referred to Primary Health Centre
                    </span>
                  )}
                </div>
              </div>
            )
          })}

          {filteredAlerts.length === 0 && (
            <div className="bg-white rounded-2xl p-12 text-center shadow-sm border border-gray-100">
              <CheckCircle2 className="w-12 h-12 text-green-500 mx-auto mb-3" />
              <p className="text-gray-700 font-bold text-base">No {filterTab} emergency alerts</p>
              <p className="text-xs text-gray-400 mt-1">
                Any clinical danger signs detected during patient visits or revisits will automatically appear here.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
