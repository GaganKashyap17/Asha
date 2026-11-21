import { useEffect, useState } from 'react'
import { ClipboardList, AlertTriangle, CheckCircle2, Clock, Search, X } from 'lucide-react'
import { visitAPI } from '../services/api'

interface Visit {
  _id?: string; id?: string; beneficiary_name?: string; visit_type?: string
  visit_date?: string; confirmation_status?: string; danger_flag?: boolean
  weight_kg?: number; pregnancy_month?: number; anc_completed?: boolean
}

export default function VisitHistoryPage() {
  const [visits, setVisits] = useState<Visit[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')
  const [search, setSearch] = useState('')

  useEffect(() => {
    visitAPI.list().then(r => setVisits(r.data.results || [])).finally(() => setLoading(false))
  }, [])

  const filtered = visits.filter(v => {
    const matchesFilter = !filter || v.visit_type === filter || v.confirmation_status === filter
    const q = search.toLowerCase().trim()
    const matchesSearch = !q ||
      (v.beneficiary_name && v.beneficiary_name.toLowerCase().includes(q)) ||
      (v.visit_type && v.visit_type.toLowerCase().includes(q)) ||
      (v.visit_date && v.visit_date.includes(q))
    return matchesFilter && matchesSearch
  })

  return (
    <div className="max-w-4xl mx-auto space-y-5">
      <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2"><ClipboardList className="w-7 h-7 text-green-600" /> Visit History</h2>

      {/* Search Bar */}
      <div className="relative">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search visit history by beneficiary name, visit type, or date…"
          className="w-full pl-10 pr-10 py-3 bg-white border border-gray-300 rounded-2xl text-sm focus:outline-none focus:ring-2 focus:ring-green-500 shadow-xs"
        />
        {search && (
          <button
            onClick={() => setSearch('')}
            className="absolute right-3.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      <div className="flex gap-2 flex-wrap">
        {['', 'pregnancy','newborn','postnatal','immunisation','household','confirmed','pending'].map(f => (
          <button key={f} onClick={() => setFilter(f)} className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${filter === f ? 'bg-green-700 text-white' : 'bg-white text-gray-600 border border-gray-200 hover:border-green-400'}`}>
            {f || 'All'}
          </button>
        ))}
      </div>
      {loading ? <div className="space-y-3">{[...Array(5)].map((_,i) => <div key={i} className="h-16 bg-green-100 rounded-2xl animate-pulse" />)}</div> : (
        <div className="bg-white rounded-2xl shadow-sm overflow-hidden">
          {filtered.map((v, i) => (
            <div key={v._id || i} className={`flex items-center gap-4 px-5 py-4 ${i < filtered.length-1 ? 'border-b border-gray-100' : ''}`}>
              <div className="w-9 h-9 bg-green-100 rounded-full flex items-center justify-center text-green-700 font-bold text-sm shrink-0">
                {v.beneficiary_name?.[0] || 'B'}
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium text-gray-900 truncate">{v.beneficiary_name || 'Unknown'}</p>
                <p className="text-xs text-gray-500 capitalize">{v.visit_type} · {v.visit_date}</p>
              </div>
              {v.danger_flag && <AlertTriangle className="w-4 h-4 text-red-500 shrink-0" />}
              <span className={`text-xs px-2 py-1 rounded-full shrink-0 ${v.confirmation_status === 'confirmed' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}`}>
                {v.confirmation_status === 'confirmed' ? <><CheckCircle2 className="inline w-3 h-3 mr-1" />Confirmed</> : <><Clock className="inline w-3 h-3 mr-1" />Pending</>}
              </span>
            </div>
          ))}
          {filtered.length === 0 && <p className="text-center py-12 text-gray-400">No visits found</p>}
        </div>
      )}
    </div>
  )
}
