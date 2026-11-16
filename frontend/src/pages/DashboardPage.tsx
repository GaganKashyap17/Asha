import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Users, Calendar, AlertTriangle, CheckCircle2, Mic, TrendingUp, Clock } from 'lucide-react'
import { BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { analyticsAPI } from '../services/api'
import { useAuth } from '../contexts/AuthContext'

const PIE_COLORS = ['#166534','#16a34a','#4ade80','#86efac','#0f766e']

function StatCard({ icon: Icon, label, value, color }: { icon: typeof Users; label: string; value: number | string; color: string }) {
  return (
    <div className="bg-white rounded-2xl p-5 shadow-sm flex items-center gap-4">
      <div className={`w-12 h-12 ${color} rounded-xl flex items-center justify-center`}>
        <Icon className="w-6 h-6" />
      </div>
      <div>
        <p className="text-2xl font-bold text-gray-900">{value}</p>
        <p className="text-sm text-gray-500">{label}</p>
      </div>
    </div>
  )
}

interface DashboardData {
  total_beneficiaries?: number
  total_visits?: number
  pending_followups?: number
  active_danger_alerts?: number
  confirmed_visits?: number
  weekly_visits?: {date: string; count: number}[]
  visit_type_breakdown?: Record<string,number>
  recent_visits?: {beneficiary_name?: string; visit_type?: string; visit_date?: string; confirmation_status?: string; danger_flag?: boolean}[]
  upcoming_followups?: {beneficiary_name?: string; visit_type?: string; due_date?: string; priority?: string}[]
  active_alerts?: {beneficiary_name?: string; danger_signs?: string[]}[]
}

export default function DashboardPage() {
  const { user } = useAuth()
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const today = new Date().toLocaleDateString('en-IN', { weekday:'long', year:'numeric', month:'long', day:'numeric' })

  useEffect(() => {
    analyticsAPI.dashboard().then(r => setData(r.data)).catch(() => {}).finally(() => setLoading(false))
  }, [])

  const weeklyData = data?.weekly_visits || []
  const pieData = Object.entries(data?.visit_type_breakdown || {}).map(([name, value]) => ({ name, value }))

  if (loading) return (
    <div className="space-y-4">
      {[...Array(4)].map((_,i) => <div key={i} className="h-24 bg-green-100 rounded-2xl animate-pulse" />)}
    </div>
  )

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Welcome, {user?.name?.split(' ')[0]} 👋</h2>
          <p className="text-gray-500 text-sm mt-1">{today}</p>
        </div>
        <Link to="/voice" className="flex items-center gap-2 px-5 py-3 bg-green-700 text-white rounded-xl font-semibold hover:bg-green-800 transition-colors shadow-md">
          <Mic className="w-5 h-5" />
          New Voice Entry
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Users} label="Beneficiaries" value={data?.total_beneficiaries ?? 0} color="bg-green-100 text-green-700" />
        <StatCard icon={CheckCircle2} label="Total Visits" value={data?.total_visits ?? 0} color="bg-blue-100 text-blue-700" />
        <StatCard icon={Calendar} label="Pending Follow-ups" value={data?.pending_followups ?? 0} color="bg-orange-100 text-orange-700" />
        <StatCard icon={AlertTriangle} label="Active Alerts" value={data?.active_danger_alerts ?? 0} color="bg-red-100 text-red-700" />
      </div>

      {/* Alert banner */}
      {(data?.active_danger_alerts ?? 0) > 0 && (
        <Link to="/alerts" className="flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-2xl hover:bg-red-100 transition-colors">
          <AlertTriangle className="w-6 h-6 text-red-600 shrink-0" />
          <div className="flex-1">
            <p className="font-semibold text-red-800">⚠️ {data?.active_danger_alerts} Active Emergency Alert{(data?.active_danger_alerts ?? 0) > 1 ? 's' : ''}</p>
            <p className="text-sm text-red-600">Immediate attention required — tap to view</p>
          </div>
        </Link>
      )}

      {/* Charts */}
      <div className="grid lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-2xl p-5 shadow-sm">
          <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-green-600" /> Weekly Visits
          </h3>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={weeklyData}>
              <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={d => d.slice(5)} />
              <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="count" fill="#166534" radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-2xl p-5 shadow-sm">
          <h3 className="font-semibold text-gray-900 mb-4">Visit Types</h3>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" innerRadius={45} outerRadius={75} paddingAngle={4} dataKey="value" label={({ name }) => name}>
                  {pieData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          ) : <p className="text-gray-400 text-sm text-center py-12">No visit data yet</p>}
        </div>
      </div>

      {/* Recent visits + follow-ups */}
      <div className="grid lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-2xl p-5 shadow-sm">
          <h3 className="font-semibold text-gray-900 mb-4">Recent Visits</h3>
          <div className="space-y-3">
            {(data?.recent_visits || []).slice(0,6).map((v, i) => (
              <div key={i} className="flex items-center gap-3">
                <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center text-green-700 font-bold text-xs">
                  {v.beneficiary_name?.[0] || 'B'}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{v.beneficiary_name || 'Unknown'}</p>
                  <p className="text-xs text-gray-500 capitalize">{v.visit_type} · {v.visit_date}</p>
                </div>
                {v.danger_flag && <AlertTriangle className="w-4 h-4 text-red-500 shrink-0" />}
                <span className={`text-xs px-2 py-1 rounded-full ${v.confirmation_status === 'confirmed' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}`}>
                  {v.confirmation_status}
                </span>
              </div>
            ))}
            {(!data?.recent_visits || data.recent_visits.length === 0) && <p className="text-gray-400 text-sm">No visits recorded yet</p>}
          </div>
        </div>

        <div className="bg-white rounded-2xl p-5 shadow-sm">
          <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Clock className="w-4 h-4 text-orange-500" /> Upcoming Follow-ups
          </h3>
          <div className="space-y-3">
            {(data?.upcoming_followups || []).slice(0,5).map((f, i) => (
              <div key={i} className="flex items-center gap-3">
                <div className={`w-2 h-2 rounded-full shrink-0 ${f.priority === 'emergency' ? 'bg-red-500' : f.priority === 'high' ? 'bg-orange-400' : 'bg-green-400'}`} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900">{f.beneficiary_name}</p>
                  <p className="text-xs text-gray-500 capitalize">{f.visit_type} · Due {f.due_date}</p>
                </div>
              </div>
            ))}
            {(!data?.upcoming_followups || data.upcoming_followups.length === 0) && <p className="text-gray-400 text-sm">No upcoming follow-ups</p>}
          </div>
          <Link to="/followups" className="block mt-4 text-sm text-green-700 font-medium hover:underline text-center">View all follow-ups →</Link>
        </div>
      </div>

      <p className="text-xs text-gray-400 text-center">Data from MongoDB Atlas · Synthetic demo records</p>
    </div>
  )
}
