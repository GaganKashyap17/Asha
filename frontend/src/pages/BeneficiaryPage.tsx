import { useEffect, useState } from 'react'
import { Users, Search, Plus, Eye, Calendar, Baby } from 'lucide-react'
import { beneficiaryAPI } from '../services/api'

interface Beneficiary {
  beneficiary_id: string; name: string; age?: number; village?: string
  household?: string; pregnancy_status?: string; pregnancy_month?: number
  expected_delivery_date?: string; newborn_age_days?: number
  last_visit_date?: string; next_visit_date?: string
}

export default function BeneficiaryPage() {
  const [beneficiaries, setBeneficiaries] = useState<Beneficiary[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<Beneficiary | null>(null)

  useEffect(() => {
    beneficiaryAPI.list().then(r => setBeneficiaries(r.data.results || [])).finally(() => setLoading(false))
  }, [])

  function statusColor(s?: string) {
    if (s === 'pregnant') return 'bg-blue-100 text-blue-700'
    if (s === 'postnatal') return 'bg-purple-100 text-purple-700'
    return 'bg-gray-100 text-gray-600'
  }

  const filtered = beneficiaries.filter(b =>
    b.name.toLowerCase().includes(search.toLowerCase()) ||
    b.beneficiary_id.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="max-w-4xl mx-auto space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2"><Users className="w-7 h-7 text-green-600" /> Beneficiaries</h2>
        <button className="flex items-center gap-2 px-4 py-2.5 bg-green-700 text-white rounded-xl text-sm font-semibold hover:bg-green-800 transition-colors">
          <Plus className="w-4 h-4" /> Add Beneficiary
        </button>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search by name or ID…"
          className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-2xl text-sm focus:outline-none focus:ring-2 focus:ring-green-500 bg-white" />
      </div>

      {loading ? (
        <div className="grid sm:grid-cols-2 gap-4">{[...Array(6)].map((_,i) => <div key={i} className="h-32 bg-green-100 rounded-2xl animate-pulse" />)}</div>
      ) : (
        <div className="grid sm:grid-cols-2 gap-4">
          {filtered.map(b => (
            <div key={b.beneficiary_id} className="bg-white rounded-2xl p-5 shadow-sm hover:shadow-md transition-shadow cursor-pointer" onClick={() => setSelected(selected?.beneficiary_id === b.beneficiary_id ? null : b)}>
              <div className="flex items-start justify-between mb-3">
                <div>
                  <p className="font-semibold text-gray-900">{b.name}</p>
                  <p className="text-xs text-gray-500">{b.beneficiary_id} · Age {b.age}</p>
                </div>
                <span className={`text-xs px-2 py-1 rounded-full font-medium capitalize ${statusColor(b.pregnancy_status)}`}>
                  {b.pregnancy_status?.replace('_', ' ')}
                </span>
              </div>
              <div className="text-sm text-gray-600 space-y-1">
                <p>📍 {b.village} · {b.household}</p>
                {b.pregnancy_month && <p><Baby className="inline w-3 h-3 mr-1" />Month {b.pregnancy_month}</p>}
                {b.newborn_age_days !== undefined && <p><Baby className="inline w-3 h-3 mr-1" />Newborn — {b.newborn_age_days} days old</p>}
                {b.last_visit_date && <p><Calendar className="inline w-3 h-3 mr-1" />Last visit: {b.last_visit_date}</p>}
                {b.next_visit_date && <p className="text-green-700">📅 Next: {b.next_visit_date}</p>}
              </div>
              {selected?.beneficiary_id === b.beneficiary_id && (
                <div className="mt-4 pt-4 border-t border-gray-100 flex gap-2">
                  <button className="flex items-center gap-1 px-3 py-1.5 bg-green-100 text-green-700 rounded-lg text-xs font-medium hover:bg-green-200 transition-colors">
                    <Eye className="w-3 h-3" /> View History
                  </button>
                </div>
              )}
            </div>
          ))}
          {filtered.length === 0 && <p className="text-gray-400 text-center py-10 col-span-2">No beneficiaries found</p>}
        </div>
      )}
    </div>
  )
}
