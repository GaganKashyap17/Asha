import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { Mic, Eye, EyeOff, AlertCircle } from 'lucide-react'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [workerId, setWorkerId] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!workerId || !password) { setError('Please enter Worker ID and password'); return }
    setLoading(true)
    setError('')
    try {
      await login(workerId.toUpperCase(), password)
      navigate('/dashboard')
    } catch (err: unknown) {
      const msg = (err as {response?: {data?: {error?: string}}})?.response?.data?.error
      setError(msg || 'Login failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  function fillDemo() {
    setWorkerId('ASHA001')
    setPassword('demo123')
    setError('')
  }

  return (
    <div className="min-h-screen bg-green-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <Link to="/" className="flex items-center justify-center gap-2 mb-8">
          <div className="w-12 h-12 bg-green-700 rounded-2xl flex items-center justify-center shadow-lg">
            <Mic className="w-6 h-6 text-white" />
          </div>
          <div className="text-left">
            <h1 className="font-bold text-green-900 text-2xl leading-none">ASHA Voice</h1>
            <p className="text-green-600 text-sm">Healthcare AI</p>
          </div>
        </Link>

        <div className="bg-white rounded-2xl shadow-md p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-1">Worker Login</h2>
          <p className="text-gray-500 text-sm mb-6">Enter your ASHA worker credentials</p>

          {error && (
            <div className="flex items-start gap-2 bg-red-50 border border-red-200 text-red-700 rounded-xl p-3 mb-4 text-sm">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Worker ID</label>
              <input
                type="text"
                value={workerId}
                onChange={e => setWorkerId(e.target.value)}
                placeholder="e.g. ASHA001"
                className="w-full border border-gray-300 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
                autoComplete="username"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
              <div className="relative">
                <input
                  type={showPw ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="Enter password"
                  className="w-full border border-gray-300 rounded-xl px-4 py-3 pr-11 text-sm focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
                  autoComplete="current-password"
                />
                <button type="button" onClick={() => setShowPw(!showPw)} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                  {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-green-700 text-white rounded-xl font-semibold hover:bg-green-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Logging in…' : 'Login'}
            </button>
            <button
              type="button"
              onClick={fillDemo}
              className="w-full py-3 border border-green-300 text-green-700 rounded-xl font-medium hover:bg-green-50 transition-colors text-sm"
            >
              Use Demo Account (ASHA001)
            </button>
          </form>

          <p className="text-center text-xs text-gray-400 mt-5">
            ⚠️ Demo authentication only — not for production use
          </p>
        </div>

        <div className="mt-4 text-center text-xs text-gray-500">
          Demo accounts: ASHA001–ASHA005 · Password: demo123
        </div>
      </div>
    </div>
  )
}
