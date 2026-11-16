import { useEffect, useState } from 'react'
import { Calendar, CheckCircle2, AlertTriangle, Clock } from 'lucide-react'
import { followupAPI } from '../services/api'

interface Followup {
  _id?: string; beneficiary_name?: string; visit_type?: string
  due_date?: string; priority?: string; status?: string
  notes?: string; danger_flag?: boolean; is_overdue?: boolean
}

export default function FollowUpPage() {
  const [followups, setFollowups] = useState<Followup[]>([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<'upcoming'|'overdue'|'completed'>('upcoming')

  useEffect(() => {
    followupAPI.list().then(r => setFollowups(r.data.results || [])).finally(() => setLoading(false))
  }, [])

  const today = new Date().toISOString().slice(0,10)
  const filtered = followups.filter(f => {
    if (tab === 'completed') return f.status === 'completed'
    if (tab === 'overdue') return f.status === 'pending' && (f.due_date || '9999') < today
    return f.status === 'pending' && (f.due_date || '9999') >= today
  })

  async function markComplete(id?: string) {
    if (!id) return
    await followupAPI.update(id, { status: 'completed' })
    setFollowups(fs => fs.map(f => f._id === id ? {...f, status: 'completed'} : f))
  }

  function priorityColor(p?: string) {
    if (p === 'emergency') return 'bg-red-100 text-red-700'
    if (p === 'high') return 'bg-orange-100 text-orange-700'
    return 'bg-green-100 text-green-700'
  }

  return (
    <div className="max-w-3xl mx-auto space-y-5">
      <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2"><Calendar className="w-7 h-7 text-green-600" /> Follow-ups</h2>
      <div className="flex gap-2">
        {(['upcoming','overdue','completed'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} className={`px-4 py-2 rounded-xl text-sm font-medium capitalize transition-colors ${tab === t ? 'bg-green-700 text-white' : 'bg-white text-gray-600 border border-gray-200 hover:border-green-400'}`}>{t}</button>
        ))}
      </div>
      {loading ? <div className="space-y-3">{[...Array(4)].map((_,i) => <div key={i} className="h-20 bg-green-100 rounded-2xl animate-pulse" />)}</div> : (
        <div className="space-y-3">
          {filtered.map((f, i) => (
            <div key={f._id || i} className={`bg-white rounded-2xl p-5 shadow-sm flex items-start gap-4 ${f.is_overdue ? 'border border-red-200' : ''}`}>
              <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${priorityColor(f.priority)}`}>
                {f.danger_flag ? <AlertTriangle className="w-5 h-5" /> : <Calendar className="w-5 h-5" />}
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium text-gray-900">{f.beneficiary_name}</p>
                <p className="text-sm text-gray-500 capitalize">{f.visit_type}</p>
                <p className="text-xs text-gray-400 mt-0.5">{f.notes}</p>
              </div>
              <div className="text-right shrink-0">
                <p className={`text-sm font-semibold ${f.is_overdue ? 'text-red-600' : 'text-gray-800'}`}>{f.due_date}</p>
                <span className={`text-xs px-2 py-0.5 rounded-full ${priorityColor(f.priority)}`}>{f.priority}</span>
                {f.status !== 'completed' && (
                  <button onClick={() => markComplete(f._id)} className="block mt-2 text-xs text-green-700 hover:underline">
                    <CheckCircle2 className="inline w-3 h-3 mr-1" />Mark done
                  </button>
                )}
              </div>
            </div>
          ))}
          {filtered.length === 0 && (
            <div className="bg-white rounded-2xl p-12 text-center shadow-sm">
              <Clock className="w-10 h-10 text-gray-300 mx-auto mb-3" />
              <p className="text-gray-400">No {tab} follow-ups</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
