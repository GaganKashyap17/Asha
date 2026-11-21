import React, { useEffect, useRef, useState } from 'react'
import type { CallStatus, Language, IVRBeneficiary, IVRCallRecord } from './ivrTypes'
import { getReminderMessage, speakReminder } from './ivrService'
import { Volume2, RefreshCw } from 'lucide-react'

interface IVRCallProgressProps {
  beneficiary: IVRBeneficiary
  status: CallStatus
  language: Language
  onCancel: () => void
  onComplete: (record: IVRCallRecord) => void
}

const TERMINAL_STATUSES: CallStatus[] = ['completed', 'busy', 'no_answer', 'failed']

function maskMobile(num: string): string {
  const digits = num.replace(/\D/g, '')
  if (digits.length >= 5) {
    return `+91 ${digits.slice(0, 5)} XXXXX`
  }
  return `+91 ${num.slice(0, 5)}XXXXX`
}

interface StatusDisplay {
  icon: string
  label: string
  color: string
  animation: 'pulse-green' | 'dots-amber' | 'wave-green' | 'none' | 'confetti' | 'red' | 'gray'
}

function getStatusDisplay(status: CallStatus): StatusDisplay {
  switch (status) {
    case 'initiating':
      return { icon: '📡', label: 'Initiating Call...', color: 'text-blue-600', animation: 'pulse-green' }
    case 'calling':
      return { icon: '📡', label: 'Dialing...', color: 'text-green-600', animation: 'pulse-green' }
    case 'ringing':
      return { icon: '🔔', label: 'Ringing Phone...', color: 'text-amber-600', animation: 'dots-amber' }
    case 'answered':
      return { icon: '✅', label: 'Citizen Answered', color: 'text-green-600', animation: 'none' }
    case 'playing':
      return { icon: '🔊', label: 'Playing Full Reminder...', color: 'text-green-700', animation: 'wave-green' }
    case 'completed':
      return { icon: '🎉', label: 'Reminder Completed', color: 'text-green-700', animation: 'confetti' }
    case 'busy':
      return { icon: '🔴', label: 'Line Busy', color: 'text-red-600', animation: 'red' }
    case 'no_answer':
      return { icon: '📵', label: 'No Answer', color: 'text-gray-500', animation: 'gray' }
    case 'failed':
      return { icon: '❌', label: 'Call Failed', color: 'text-red-600', animation: 'red' }
    default:
      return { icon: '📞', label: 'Connecting...', color: 'text-gray-500', animation: 'none' }
  }
}

const LANG_LABELS: Record<Language, string> = {
  en: '🇬🇧 English',
  hi: '🇮🇳 हिंदी',
  ta: '🌺 தமிழ்',
  kn: '🌸 ಕನ್ನಡ',
}

const IVRCallProgress: React.FC<IVRCallProgressProps> = ({
  beneficiary,
  status,
  language,
  onCancel,
  onComplete: _onComplete,
}) => {
  const display = getStatusDisplay(status)
  const isTerminal = TERMINAL_STATUSES.includes(status)
  const autoCloseTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [isReplaying, setIsReplaying] = useState(false)

  const reminderText = getReminderMessage(
    language,
    beneficiary.beneficiary_name,
    beneficiary.visit_date,
    beneficiary.visit_type
  )

  // Auto-close timer after speech completes so user can read everything comfortably
  useEffect(() => {
    if (isTerminal && !isReplaying) {
      autoCloseTimer.current = setTimeout(() => {
        onCancel()
      }, 8000)
    }
    return () => {
      if (autoCloseTimer.current) clearTimeout(autoCloseTimer.current)
    }
  }, [isTerminal, isReplaying, onCancel])

  const handleReplay = async () => {
    if (autoCloseTimer.current) clearTimeout(autoCloseTimer.current)
    setIsReplaying(true)
    await speakReminder(reminderText, language)
    setIsReplaying(false)
  }

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-md z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-3xl shadow-2xl w-full max-w-md overflow-hidden max-h-[90vh] flex flex-col animate-in fade-in zoom-in-95 duration-150">
        {/* Demo Banner */}
        <div className="bg-gradient-to-r from-emerald-600 to-green-700 py-2 px-4 text-center text-white shrink-0">
          <span className="text-xs font-bold tracking-wide flex items-center justify-center gap-1.5">
            <span>📞</span> LIVE IVR CALL SIMULATOR (Device Speaker)
          </span>
        </div>

        <div className="p-6 overflow-y-auto flex flex-col items-center gap-5">
          {/* Animated Phone Icon */}
          <div className="relative flex items-center justify-center">
            {(status === 'calling' || status === 'ringing' || status === 'initiating') && (
              <>
                <span className="absolute inline-flex h-24 w-24 rounded-full bg-green-400 opacity-20 animate-ping" />
                <span className="absolute inline-flex h-20 w-20 rounded-full bg-green-400 opacity-30 animate-ping [animation-delay:0.3s]" />
              </>
            )}
            <div
              className={`relative z-10 w-20 h-20 rounded-full flex items-center justify-center text-4xl shadow-lg ${
                isTerminal
                  ? status === 'completed'
                    ? 'bg-green-50 border-2 border-green-400'
                    : 'bg-red-50 border-2 border-red-200'
                  : 'bg-green-700 text-white'
              }`}
            >
              {display.icon}
            </div>
          </div>

          {/* Status Label */}
          <div className="text-center space-y-1">
            <p className={`text-xl font-bold ${display.color}`}>{display.label}</p>
            <p className="text-sm text-gray-500 font-mono">
              📱 {maskMobile(beneficiary.mobile_number)}
            </p>
            <p className="text-xs font-semibold text-gray-700">
              {beneficiary.beneficiary_name} &bull; {beneficiary.visit_type}
            </p>
          </div>

          {/* Wave animation for 'playing' */}
          {(status === 'playing' || isReplaying) && (
            <div className="flex flex-col items-center gap-2 w-full bg-green-50/80 p-3.5 rounded-2xl border border-green-200">
              <div className="flex items-end gap-1.5 h-8">
                {[0, 1, 2, 3, 4, 5, 6].map((i) => (
                  <div
                    key={i}
                    className="w-2 bg-green-600 rounded-full"
                    style={{
                      height: `${14 + (i % 3) * 8}px`,
                      animation: `wave 0.8s ease-in-out infinite`,
                      animationDelay: `${i * 0.12}s`,
                    }}
                  />
                ))}
              </div>
              <p className="text-xs font-semibold text-green-800 flex items-center gap-1">
                <Volume2 className="w-3.5 h-3.5 text-green-700 animate-pulse" />
                Voice speaking on speaker — listening to full reminder...
              </p>
            </div>
          )}

          {/* Live Reminder Text Box */}
          <div className="w-full bg-gray-50 border border-gray-200 p-3.5 rounded-xl text-left">
            <div className="flex items-center justify-between text-xs text-gray-400 mb-1">
              <span>Spoken Voice Content:</span>
              <span className="font-semibold text-gray-700">{LANG_LABELS[language]}</span>
            </div>
            <p className="text-xs text-gray-800 leading-relaxed italic">
              "{reminderText}"
            </p>
          </div>

          {/* Ringing dots */}
          {status === 'ringing' && (
            <div className="flex gap-2">
              {[0, 1, 2].map((i) => (
                <span
                  key={i}
                  className="w-3 h-3 rounded-full bg-amber-400 animate-bounce"
                  style={{ animationDelay: `${i * 0.2}s` }}
                />
              ))}
            </div>
          )}

          {/* Calling spinner */}
          {(status === 'calling' || status === 'initiating') && (
            <div className="w-8 h-8 border-4 border-green-700 border-t-transparent rounded-full animate-spin" />
          )}

          {/* Progress Steps */}
          <div className="w-full space-y-2 bg-gray-50/60 p-3 rounded-xl border border-gray-100">
            {(['calling', 'ringing', 'answered', 'playing', 'completed'] as CallStatus[]).map(
              (step, idx) => {
                const stepStatuses: CallStatus[] = [
                  'calling',
                  'ringing',
                  'answered',
                  'playing',
                  'completed',
                ]
                const currentIdx = stepStatuses.indexOf(status)
                const stepIdx = idx
                const isDone = currentIdx > stepIdx
                const isActive = currentIdx === stepIdx

                return (
                  <div key={step} className="flex items-center gap-3">
                    <div
                      className={`w-5 h-5 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold transition-all ${
                        isDone
                          ? 'bg-green-600 text-white'
                          : isActive
                          ? 'bg-green-200 border-2 border-green-600 text-green-700'
                          : 'bg-gray-200 text-gray-400'
                      }`}
                    >
                      {isDone ? '✓' : idx + 1}
                    </div>
                    <span
                      className={`text-xs capitalize ${
                        isDone
                          ? 'text-green-700 font-medium'
                          : isActive
                          ? 'text-gray-900 font-bold'
                          : 'text-gray-400'
                      }`}
                    >
                      {step === 'playing' ? 'Speaking Reminder in Full' : step.replace('_', ' ')}
                    </span>
                  </div>
                )
              }
            )}
          </div>

          {/* Replay Option when Completed */}
          {status === 'completed' && (
            <button
              onClick={handleReplay}
              disabled={isReplaying}
              className="w-full py-2.5 px-4 rounded-xl font-semibold transition-colors text-xs flex items-center justify-center gap-2 border border-green-600 text-green-800 bg-green-50 hover:bg-green-100"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isReplaying ? 'animate-spin' : ''}`} />
              <span>{isReplaying ? 'Speaking again...' : '🔊 Replay Voice Message'}</span>
            </button>
          )}

          {/* Close/Cancel Button */}
          <button
            onClick={onCancel}
            className={`w-full py-3 rounded-xl font-bold transition-colors text-sm shadow-sm ${
              isTerminal
                ? 'bg-green-700 text-white hover:bg-green-800'
                : 'border-2 border-gray-200 text-gray-600 hover:bg-gray-100'
            }`}
          >
            {isTerminal ? 'Done / Close Window' : 'End Call'}
          </button>

          {isTerminal && !isReplaying && (
            <p className="text-[11px] text-gray-400 text-center">
              Auto-closing in 8 seconds (or click Done / Close Window above)
            </p>
          )}
        </div>
      </div>

      <style>{`
        @keyframes wave {
          0%, 100% { transform: scaleY(0.4); }
          50% { transform: scaleY(1.3); }
        }
      `}</style>
    </div>
  )
}

export default IVRCallProgress
