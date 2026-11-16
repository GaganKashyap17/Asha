import { Link } from 'react-router-dom'
import { Mic, Brain, AlertTriangle, Volume2, BarChart3, Globe, Shield, CheckCircle2 } from 'lucide-react'

function AshaWorkerSVG() {
  return (
    <svg viewBox="0 0 320 280" className="w-full max-w-sm mx-auto" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="160" cy="240" r="40" fill="#dcfce7" />
      <rect x="100" y="130" width="120" height="140" rx="20" fill="#166534" />
      <circle cx="160" cy="90" r="45" fill="#fde68a" />
      <ellipse cx="140" cy="88" rx="8" ry="6" fill="#78716c" />
      <ellipse cx="180" cy="88" rx="8" ry="6" fill="#78716c" />
      <path d="M145 108 Q160 120 175 108" stroke="#78716c" strokeWidth="2.5" strokeLinecap="round" fill="none"/>
      <path d="M115 90 Q110 60 130 50 Q160 35 190 50 Q210 60 205 90" fill="#1a5c38" />
      <rect x="130" y="150" width="60" height="40" rx="10" fill="#dcfce7" />
      <rect x="135" y="155" width="50" height="30" rx="8" fill="white" />
      <line x1="140" y1="162" x2="180" y2="162" stroke="#166534" strokeWidth="2" strokeLinecap="round"/>
      <line x1="140" y1="168" x2="175" y2="168" stroke="#166534" strokeWidth="1.5" strokeLinecap="round"/>
      <line x1="140" y1="174" x2="170" y2="174" stroke="#16a34a" strokeWidth="1.5" strokeLinecap="round"/>
      <circle cx="210" cy="145" r="20" fill="#16a34a" opacity="0.9"/>
      <path d="M201 145 L207 151 L219 139" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
      <circle cx="90" cy="160" r="15" fill="#f0faf4" stroke="#166534" strokeWidth="2"/>
      <path d="M82 160 Q87 153 90 160 Q93 167 98 160" stroke="#166534" strokeWidth="2" strokeLinecap="round" fill="none"/>
      <text x="145" y="240" fontSize="12" fill="#166534" fontWeight="600">ASHA Worker</text>
    </svg>
  )
}

const FEATURES = [
  { icon: Mic, title: 'Multilingual Voice', desc: 'Speak Tamil, Hindi, Kannada naturally with English medical terms mixed in', color: 'bg-green-100 text-green-700' },
  { icon: Brain, title: 'AI Extraction', desc: 'Groq LLM automatically extracts structured health data from your speech', color: 'bg-blue-100 text-blue-700' },
  { icon: AlertTriangle, title: 'Danger Detection', desc: 'Independent deterministic engine flags bleeding, fever and other emergencies instantly', color: 'bg-red-100 text-red-700' },
  { icon: Volume2, title: 'Voice Read-back', desc: 'Hear your record read aloud and correct mistakes using your voice', color: 'bg-purple-100 text-purple-700' },
  { icon: BarChart3, title: 'Live Dashboard', desc: 'Real-time analytics of visits, follow-ups and beneficiary health status', color: 'bg-orange-100 text-orange-700' },
  { icon: Globe, title: 'Offline-ready', desc: 'Designed for areas with limited connectivity — mobile-first and lightweight', color: 'bg-teal-100 text-teal-700' },
]

const STEPS = [
  { n: '1', title: 'Record', desc: 'Tap the microphone and speak naturally in Tamil or English about your visit' },
  { n: '2', title: 'Transcribe', desc: 'Groq Whisper AI converts your speech to text, handling code-mixed language' },
  { n: '3', title: 'Extract', desc: 'AI automatically structures weight, ANC status, IFA, vaccinations and more' },
  { n: '4', title: 'Confirm', desc: 'Hear the record read aloud, correct if needed, then confirm to save' },
]

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-white">
      {/* Nav */}
      <nav className="sticky top-0 z-50 bg-white/80 backdrop-blur border-b border-green-100">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center gap-3">
          <div className="w-9 h-9 bg-green-700 rounded-xl flex items-center justify-center">
            <Mic className="w-5 h-5 text-white" />
          </div>
          <span className="font-bold text-green-900 text-xl">ASHA Voice</span>
          <div className="flex-1" />
          <Link to="/login" className="px-5 py-2 bg-green-700 text-white rounded-xl text-sm font-semibold hover:bg-green-800 transition-colors">
            Login
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-6xl mx-auto px-4 py-16 grid md:grid-cols-2 gap-12 items-center">
        <div>
          <div className="inline-flex items-center gap-2 bg-green-100 text-green-800 px-3 py-1 rounded-full text-sm font-medium mb-6">
            <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            Powered by Groq AI
          </div>
          <h1 className="text-4xl md:text-5xl font-bold text-gray-900 leading-tight mb-4">
            Speak Naturally.<br />
            <span className="text-green-700">Record Instantly.</span><br />
            Protect Every Life.
          </h1>
          <p className="text-lg text-gray-600 mb-8 leading-relaxed">
            AI-powered voice assistant for ASHA healthcare workers. Record home visits in Tamil or English — no typing needed.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link to="/login" className="px-6 py-3 bg-green-700 text-white rounded-xl font-semibold hover:bg-green-800 transition-colors shadow-md">
              Get Started →
            </Link>
            <a href="#how-it-works" className="px-6 py-3 border border-green-300 text-green-700 rounded-xl font-semibold hover:bg-green-50 transition-colors">
              How It Works
            </a>
          </div>
        </div>
        <div className="relative">
          <div className="absolute inset-0 bg-green-100 rounded-3xl -rotate-3 scale-95" />
          <div className="relative bg-green-50 rounded-3xl p-6">
            <AshaWorkerSVG />
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="bg-green-50 py-16">
        <div className="max-w-6xl mx-auto px-4">
          <h2 className="text-3xl font-bold text-center text-gray-900 mb-12">Everything ASHA Workers Need</h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {FEATURES.map((f) => (
              <div key={f.title} className="bg-white rounded-2xl p-6 shadow-sm hover:shadow-md transition-shadow">
                <div className={`w-11 h-11 ${f.color} rounded-xl flex items-center justify-center mb-4`}>
                  <f.icon className="w-5 h-5" />
                </div>
                <h3 className="font-semibold text-gray-900 mb-2">{f.title}</h3>
                <p className="text-gray-600 text-sm leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section id="how-it-works" className="py-16 max-w-6xl mx-auto px-4">
        <h2 className="text-3xl font-bold text-center text-gray-900 mb-12">How It Works</h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {STEPS.map((s, i) => (
            <div key={s.n} className="text-center relative">
              {i < STEPS.length - 1 && (
                <div className="hidden lg:block absolute top-6 left-3/4 w-1/2 h-0.5 bg-green-200 z-0" />
              )}
              <div className="w-12 h-12 bg-green-700 text-white rounded-full flex items-center justify-center text-xl font-bold mx-auto mb-4 relative z-10">
                {s.n}
              </div>
              <h3 className="font-semibold text-gray-900 mb-2">{s.title}</h3>
              <p className="text-gray-600 text-sm">{s.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Languages */}
      <section className="bg-green-700 py-12 text-white text-center">
        <div className="max-w-4xl mx-auto px-4">
          <h2 className="text-2xl font-bold mb-4">Supports Indian Languages</h2>
          <p className="text-green-100 mb-6">Natural Tamil + English code-mixing. Architecture supports any Indian language.</p>
          <div className="flex flex-wrap justify-center gap-3">
            {['Tamil · தமிழ்', 'Hindi · हिंदी', 'Kannada · ಕನ್ನಡ', 'Telugu · తెలుగు'].map((l) => (
              <span key={l} className="px-4 py-2 bg-white/20 rounded-full text-sm font-medium">{l}</span>
            ))}
            <span className="px-4 py-2 bg-white/10 rounded-full text-sm text-green-200">+ More planned</span>
          </div>
        </div>
      </section>

      {/* Safety */}
      <section className="py-16 max-w-5xl mx-auto px-4">
        <div className="bg-green-50 rounded-2xl p-8">
          <div className="flex items-center gap-3 mb-6">
            <Shield className="w-7 h-7 text-green-700" />
            <h2 className="text-2xl font-bold text-gray-900">Responsible AI by Design</h2>
          </div>
          <div className="grid sm:grid-cols-2 gap-4">
            {[
              'Synthetic demo data only — no real patient records',
              'API keys stored server-side, never exposed to browser',
              'Deterministic danger sign engine independent of LLM',
              'Referral support tool — never diagnoses or prescribes',
              'Human confirmation required before every record is saved',
              'Auditable correction history for every visit record',
            ].map((point) => (
              <div key={point} className="flex items-start gap-2">
                <CheckCircle2 className="w-5 h-5 text-green-600 mt-0.5 shrink-0" />
                <span className="text-gray-700 text-sm">{point}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-green-100 py-8 text-center text-gray-500 text-sm">
        <p>ASHA Voice · Powered by Groq AI · Built for India's Healthcare Heroes</p>
        <p className="mt-1 text-xs">Demo project — synthetic data only — not for clinical use</p>
      </footer>
    </div>
  )
}
