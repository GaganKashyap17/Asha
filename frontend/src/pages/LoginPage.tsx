import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { Mic, Eye, EyeOff, AlertCircle, KeyRound, UserCheck } from 'lucide-react'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!identifier.trim() || !password) {
      setError('Please enter your Email ID or Worker ID and password.')
      return
    }
    setLoading(true)
    setError('')
    try {
      await login(identifier.trim(), password)
      navigate('/dashboard')
    } catch (err: unknown) {
      const resp = (err as { response?: { data?: { error?: string; detail?: string } } })?.response?.data
      const msg = resp?.error || resp?.detail || 'Login failed. Please verify your credentials and try again.'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  function fillDemo() {
    setIdentifier('ASHA001')
    setPassword('demo123')
    setError('')
  }

  function fillPrimary() {
    setIdentifier('prakajayavel1994@gmail.com')
    setPassword('123456')
    setError('')
  }

  return (
    <div className="min-h-screen bg-green-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <Link to="/" className="flex items-center justify-center gap-2 mb-8">
          <div className="w-12 h-12 bg-green-700 rounded-2xl flex items-center justify-center shadow-lg">
            <Mic className="w-6 h-6 text-white" />
          </div>
          <div className="text-left">
            <h1 className="font-bold text-green-900 text-2xl leading-none">ASHA Voice</h1>
            <p className="text-green-600 text-sm">Healthcare AI</p>
          </div>
        </Link>

        <div className="bg-white rounded-2xl shadow-md p-6 sm:p-8">
          <h2 className="text-xl font-bold text-gray-900 mb-1">Worker Sign In</h2>
          <p className="text-gray-500 text-sm mb-6">Enter your registered Email ID or Worker ID</p>

          {error && (
            <div className="flex items-start gap-2 bg-red-50 border border-red-200 text-red-700 rounded-xl p-3 mb-4 text-sm animate-shake">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email ID or Worker ID</label>
              <input
                type="text"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                placeholder="e.g. asha001@ashavoice.in or ASHA001"
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
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  className="w-full border border-gray-300 rounded-xl px-4 py-3 pr-11 text-sm focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPw(!showPw)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-green-700 text-white rounded-xl font-semibold hover:bg-green-800 transition-colors shadow disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Signing in…' : 'Sign In'}
            </button>
          </form>

          {/* Demo & Primary Account Access */}
          <div className="mt-6 pt-5 border-t border-gray-100">
            <div className="bg-emerald-50/70 border border-emerald-200/60 rounded-xl p-3.5 mb-3">
              <div className="flex items-center gap-2 text-emerald-800 text-xs font-semibold mb-1">
                <KeyRound className="w-3.5 h-3.5 text-emerald-600" />
                <span>Quick Access Accounts</span>
              </div>
              <p className="text-xs text-emerald-700 leading-relaxed mb-2.5">
                Primary (Existing Database): <strong className="font-mono">prakajayavel1994@gmail.com</strong> / <strong className="font-mono">123456</strong>
              </p>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={fillPrimary}
                  className="w-full py-2 bg-emerald-700 hover:bg-emerald-800 text-white rounded-lg font-medium transition-colors text-xs flex items-center justify-center gap-1 shadow-sm"
                >
                  <UserCheck className="w-3 h-3" />
                  Primary Account
                </button>
                <button
                  type="button"
                  onClick={fillDemo}
                  className="w-full py-2 border border-emerald-600 text-emerald-800 hover:bg-emerald-100/60 rounded-lg font-medium transition-colors text-xs flex items-center justify-center gap-1 shadow-sm"
                >
                  <KeyRound className="w-3 h-3" />
                  Demo (ASHA001)
                </button>
              </div>
              <p className="text-[11px] text-gray-500 mt-2">
                ✨ New accounts registered via Sign Up start with a fresh, clean database.
              </p>
            </div>
          </div>

          {/* Link to Signup */}
          <div className="text-center text-sm text-gray-600 mt-4">
            Don&apos;t have an account?{' '}
            <Link to="/signup" className="text-green-700 font-semibold hover:underline">
              Sign Up as ASHA Worker
            </Link>
          </div>
        </div>

        <div className="mt-4 text-center text-xs text-gray-500">
          Demo Accounts: ASHA001–ASHA005 (Password: demo123)
        </div>
      </div>
    </div>
  )
}
