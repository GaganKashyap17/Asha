import { useEffect, useState } from 'react'
import { Settings, Wifi, WifiOff, CheckCircle2, AlertTriangle } from 'lucide-react'
import { analyticsAPI } from '../services/api'
import { useAuth } from '../contexts/AuthContext'

interface Health { groq?: {connected: boolean; model?: string; latency_ms?: number; error?: string}; mongodb?: {connected: boolean; mode?: string} }

export default function SettingsPage() {
  const { user } = useAuth()
  const [health, setHealth] = useState<Health | null>(null)
  const [checking, setChecking] = useState(false)

  async function checkHealth() {
    setChecking(true)
    try { const r = await analyticsAPI.health(); setHealth(r.data) } catch { setHealth(null) } finally { setChecking(false) }
  }

  useEffect(() => { checkHealth() }, [])

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2"><Settings className="w-7 h-7 text-green-600" /> Settings</h2>

      {/* Profile */}
      <div className="bg-white rounded-2xl p-5 shadow-sm">
        <h3 className="font-semibold text-gray-800 mb-4">Worker Profile</h3>
        <div className="grid grid-cols-2 gap-3 text-sm">
          {[['Worker ID', user?.worker_id],['Name', user?.name],['District', user?.district],['PHC', user?.phc],['Language', user?.language],['Role', user?.role]].map(([k,v]) => (
            <div key={k} className="bg-gray-50 rounded-xl p-3">
              <p className="text-xs text-gray-500 mb-0.5">{k}</p>
              <p className="font-medium text-gray-900">{v || '—'}</p>
            </div>
          ))}
        </div>
      </div>

      {/* API Health */}
      <div className="bg-white rounded-2xl p-5 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-gray-800">API Connection Status</h3>
          <button onClick={checkHealth} disabled={checking} className="text-sm text-green-700 hover:underline disabled:opacity-50">
            {checking ? 'Checking…' : 'Refresh'}
          </button>
        </div>
        {health ? (
          <div className="space-y-3">
            <div className={`flex items-center gap-3 p-3 rounded-xl ${health.groq?.connected ? 'bg-green-50' : 'bg-red-50'}`}>
              {health.groq?.connected ? <CheckCircle2 className="w-5 h-5 text-green-600" /> : <AlertTriangle className="w-5 h-5 text-red-500" />}
              <div>
                <p className="font-medium text-sm">Groq AI</p>
                <p className="text-xs text-gray-500">{health.groq?.connected ? `${health.groq.model} · ${health.groq.latency_ms}ms` : health.groq?.error || 'Not connected'}</p>
              </div>
            </div>
            <div className={`flex items-center gap-3 p-3 rounded-xl ${health.mongodb?.connected ? 'bg-green-50' : 'bg-orange-50'}`}>
              {health.mongodb?.connected ? <Wifi className="w-5 h-5 text-green-600" /> : <WifiOff className="w-5 h-5 text-orange-500" />}
              <div>
                <p className="font-medium text-sm">MongoDB Atlas</p>
                <p className="text-xs text-gray-500">{health.mongodb?.mode || 'Unknown'}</p>
              </div>
            </div>
          </div>
        ) : <p className="text-gray-400 text-sm">{checking ? 'Checking connections…' : 'Could not reach backend'}</p>}
      </div>

      {/* Voice */}
      <div className="bg-white rounded-2xl p-5 shadow-sm">
        <h3 className="font-semibold text-gray-800 mb-3">Speech Provider</h3>
        <div className="space-y-2 text-sm">
          <div className="flex items-center gap-2 text-green-700"><CheckCircle2 className="w-4 h-4" /> Groq Whisper (chunked upload) — Active</div>
          <div className="flex items-center gap-2 text-gray-400"><AlertTriangle className="w-4 h-4" /> Gnani Streaming STT — Adapter ready, awaiting credentials</div>
          <div className="flex items-center gap-2 text-blue-600"><CheckCircle2 className="w-4 h-4" /> Browser SpeechSynthesis TTS — Active (fallback)</div>
        </div>
      </div>

      {/* Privacy */}
      <div className="bg-green-50 rounded-2xl p-5">
        <h3 className="font-semibold text-gray-800 mb-3">Privacy & Safety</h3>
        <ul className="space-y-2 text-sm text-gray-700">
          {['All data in this demo is synthetic — no real patient records','API keys stored server-side only — never sent to browser','Session tokens expire when browser tab is closed','Voice recordings are processed and immediately deleted','Danger sign detection is deterministic — not AI-only'].map(p => (
            <li key={p} className="flex items-start gap-2"><CheckCircle2 className="w-4 h-4 text-green-600 mt-0.5 shrink-0" />{p}</li>
          ))}
        </ul>
      </div>
    </div>
  )
}
