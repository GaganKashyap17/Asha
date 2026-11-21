import React, { useState } from 'react'
import type { IVRCallRecord } from './ivrTypes'
import { clearCallHistory } from './ivrService'

interface IVRCallHistoryProps {
  records: IVRCallRecord[]
  onRefresh: () => void
}

const STATUS_BADGES: Record<string, string> = {
  completed: 'bg-green-100 text-green-700 border-green-200',
  busy: 'bg-amber-100 text-amber-700 border-amber-200',
  no_answer: 'bg-gray-100 text-gray-600 border-gray-200',
  failed: 'bg-red-100 text-red-700 border-red-200',
  calling: 'bg-blue-100 text-blue-700 border-blue-200',
  ringing: 'bg-blue-100 text-blue-700 border-blue-200',
  playing: 'bg-blue-100 text-blue-700 border-blue-200',
  answered: 'bg-green-100 text-green-600 border-green-200',
  initiating: 'bg-blue-100 text-blue-600 border-blue-200',
  idle: 'bg-gray-100 text-gray-500 border-gray-200',
}

const STATUS_ICONS: Record<string, string> = {
  completed: '✅',
  busy: '🔴',
  no_answer: '📵',
  failed: '❌',
  calling: '📡',
  ringing: '🔔',
  playing: '🔊',
  answered: '☎️',
  initiating: '📡',
  idle: '⏸️',
}

const LANG_FLAGS: Record<string, string> = {
  en: '🇬🇧 English',
  hi: '🇮🇳 हिंदी',
  ta: '🌺 தமிழ்',
  kn: '🌸 ಕನ್ನಡ',
}

function maskMobile(num: string): string {
  const digits = num.replace(/\D/g, '')
  if (digits.length >= 5) return `+91 ${digits.slice(0, 5)} XXXXX`
  return `+91 ${num.slice(0, 5)}XXXXX`
}

function formatTimestamp(iso: string): string {
  try {
    return new Date(iso).toLocaleString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

const IVRCallHistory: React.FC<IVRCallHistoryProps> = ({ records, onRefresh }) => {
  const [expanded, setExpanded] = useState(true)
  const [confirmClear, setConfirmClear] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | 'completed' | 'busy' | 'no_answer' | 'failed'>('all')

  const handleClear = () => {
    clearCallHistory()
    onRefresh()
    setConfirmClear(false)
  }

  // Filter records based on search query and status filter
  const filteredRecords = records.filter((r) => {
    const q = searchQuery.toLowerCase().trim()
    const matchesQuery =
      !q ||
      r.beneficiary_name.toLowerCase().includes(q) ||
      r.mobile_number.includes(q) ||
      r.visit_type.toLowerCase().includes(q) ||
      r.visit_date.includes(q) ||
      r.status.toLowerCase().includes(q) ||
      r.outcome.toLowerCase().includes(q) ||
      r.call_id.toLowerCase().includes(q)

    const matchesStatus = statusFilter === 'all' || r.status === statusFilter
    return matchesQuery && matchesStatus
  })

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
      {/* Header toggle */}
      <button
        onClick={() => setExpanded((p) => !p)}
        className="w-full flex items-center justify-between p-5 hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="text-lg">📋</span>
          <span className="font-semibold text-gray-800">
            IVR Call History{' '}
            <span className="text-sm font-normal text-gray-400 ml-1">(Integrated)</span>
          </span>
          <span className="bg-gray-100 text-gray-600 text-xs font-bold px-2.5 py-0.5 rounded-full">
            {records.length} {records.length === 1 ? 'call' : 'calls'}
          </span>
        </div>
        <svg
          className={`w-5 h-5 text-gray-400 transition-transform ${expanded ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {expanded && (
        <div className="border-t border-gray-100">
          {/* Search bar & Filter bar */}
          <div className="p-4 bg-gray-50/60 border-b border-gray-100 space-y-3">
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
              {/* Search Input Bar */}
              <div className="relative flex-1">
                <svg
                  className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 1114 0z"
                  />
                </svg>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search by name, phone (e.g. 8056413568), visit type, or status…"
                  className="w-full pl-10 pr-9 py-2.5 text-sm bg-white border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-green-500 shadow-xs"
                />
                {searchQuery && (
                  <button
                    onClick={() => setSearchQuery('')}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 text-sm font-bold w-5 h-5 flex items-center justify-center rounded-full hover:bg-gray-100"
                    title="Clear search"
                  >
                    ×
                  </button>
                )}
              </div>

              {/* Clear History Button */}
              {records.length > 0 && (
                <div className="flex items-center justify-end">
                  {confirmClear ? (
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-gray-600">Clear all?</span>
                      <button
                        onClick={handleClear}
                        className="bg-red-600 text-white px-2.5 py-1.5 rounded-lg hover:bg-red-700 transition-colors font-semibold"
                      >
                        Yes, Clear
                      </button>
                      <button
                        onClick={() => setConfirmClear(false)}
                        className="text-gray-500 px-2.5 py-1.5 rounded-lg border bg-white hover:bg-gray-50"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setConfirmClear(true)}
                      className="text-xs text-red-500 hover:text-red-700 font-medium transition-colors flex items-center gap-1 px-2.5 py-1.5 rounded-lg hover:bg-red-50 shrink-0"
                    >
                      🗑️ Clear History
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* Quick Filter Chips */}
            <div className="flex items-center justify-between flex-wrap gap-2 pt-1 text-xs">
              <div className="flex items-center gap-1.5 flex-wrap">
                {(['all', 'completed', 'busy', 'no_answer', 'failed'] as const).map((st) => (
                  <button
                    key={st}
                    onClick={() => setStatusFilter(st)}
                    className={`px-3 py-1 rounded-full font-medium capitalize transition-colors ${
                      statusFilter === st
                        ? 'bg-green-700 text-white shadow-xs'
                        : 'bg-white text-gray-600 border border-gray-200 hover:border-green-400'
                    }`}
                  >
                    {st === 'all' ? 'All Calls' : st.replace('_', ' ')}
                  </button>
                ))}
              </div>

              <div className="text-gray-400 text-xs">
                Showing {filteredRecords.length} of {records.length}
              </div>
            </div>
          </div>

          {/* Records List */}
          <div className="divide-y divide-gray-50 max-h-[480px] overflow-y-auto">
            {records.length === 0 ? (
              <div className="p-10 text-center text-gray-400">
                <span className="text-4xl block mb-3">📭</span>
                <p className="text-sm font-medium">No calls logged yet</p>
                <p className="text-xs mt-1">Use the &quot;Send IVR Reminder&quot; buttons above to start</p>
              </div>
            ) : filteredRecords.length === 0 ? (
              <div className="p-10 text-center text-gray-400">
                <span className="text-3xl block mb-2">🔍</span>
                <p className="text-sm font-medium text-gray-600">No matching call records found</p>
                <p className="text-xs text-gray-400 mt-1">
                  No records match &quot;{searchQuery}&quot; {statusFilter !== 'all' ? `with status ${statusFilter}` : ''}
                </p>
                <button
                  onClick={() => {
                    setSearchQuery('')
                    setStatusFilter('all')
                  }}
                  className="mt-3 text-xs text-green-700 hover:underline font-semibold"
                >
                  Clear search and filters
                </button>
              </div>
            ) : (
              filteredRecords.map((r) => (
                <div key={r.call_id} className="p-4 hover:bg-gray-50/70 transition-colors">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0 space-y-1">
                      {/* Name + Status badge */}
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-bold text-gray-900">
                          {r.beneficiary_name}
                        </span>
                        <span
                          className={`text-xs px-2.5 py-0.5 rounded-full border font-semibold flex items-center gap-1 ${
                            STATUS_BADGES[r.status] ?? 'bg-gray-100 text-gray-600'
                          }`}
                        >
                          <span>{STATUS_ICONS[r.status] ?? '📞'}</span>
                          <span className="capitalize">{r.status.replace('_', ' ')}</span>
                        </span>
                      </div>

                      {/* Phone + Language */}
                      <div className="flex items-center gap-3 text-xs text-gray-500 font-mono">
                        <span>📱 {maskMobile(r.mobile_number)}</span>
                        <span>{LANG_FLAGS[r.language] ?? r.language}</span>
                      </div>

                      {/* Visit Details */}
                      <div className="flex items-center gap-2 text-xs text-gray-600 flex-wrap">
                        <span>📅 Visit: {r.visit_date}</span>
                        <span>&bull;</span>
                        <span className="font-medium text-gray-700">{r.visit_type}</span>
                      </div>

                      {/* Outcome note */}
                      <p className="text-xs text-gray-500 italic mt-0.5">{r.outcome}</p>
                    </div>

                    {/* Right side: Duration + Time */}
                    <div className="text-right flex-shrink-0 space-y-1">
                      {r.duration_seconds !== undefined && r.duration_seconds > 0 && (
                        <span className="text-xs font-semibold text-green-700 bg-green-50 px-2 py-0.5 rounded-full border border-green-200">
                          ⏱ {r.duration_seconds}s
                        </span>
                      )}
                      <p className="text-xs text-gray-400">{formatTimestamp(r.initiated_at)}</p>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default IVRCallHistory
