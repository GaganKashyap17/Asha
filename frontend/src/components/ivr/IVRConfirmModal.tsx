import React, { useState } from 'react'
import { Phone, X, Globe, Info, User, Calendar } from 'lucide-react'
import type { IVRBeneficiary, Language } from './ivrTypes'
import { getReminderMessage } from './ivrService'

interface IVRConfirmModalProps {
  beneficiary: IVRBeneficiary
  onConfirm: (lang: Language) => void
  onCancel: () => void
}

const LANGUAGES: { code: Language; label: string; flag: string }[] = [
  { code: 'en', label: 'English', flag: '🇬🇧' },
  { code: 'hi', label: 'हिंदी', flag: '🇮🇳' },
  { code: 'ta', label: 'தமிழ்', flag: '🌺' },
  { code: 'kn', label: 'ಕನ್ನಡ', flag: '🌸' },
]

const PRIORITY_COLORS: Record<string, string> = {
  emergency: 'bg-red-100 text-red-700 border-red-200',
  high: 'bg-orange-100 text-orange-700 border-orange-200',
  medium: 'bg-amber-100 text-amber-700 border-amber-200',
  low: 'bg-green-100 text-green-700 border-green-200',
}

function formatMobile(num: string): string {
  const digits = num.replace(/\D/g, '')
  if (digits.length === 10) {
    return `+91 ${digits.slice(0, 5)} ${digits.slice(5)}`
  }
  return `+91 ${num}`
}

const IVRConfirmModal: React.FC<IVRConfirmModalProps> = ({
  beneficiary,
  onConfirm,
  onCancel,
}) => {
  const [selectedLang, setSelectedLang] = useState<Language>('en')

  const previewMessage = getReminderMessage(
    selectedLang,
    beneficiary.beneficiary_name,
    beneficiary.visit_date,
    beneficiary.visit_type
  )

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-3xl shadow-2xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="bg-gradient-to-r from-green-700 to-green-600 p-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="bg-white/20 rounded-full p-2">
                <Phone className="w-5 h-5 text-white" />
              </div>
              <h2 className="text-white font-bold text-lg">Send IVR Reminder</h2>
            </div>
            <button
              onClick={onCancel}
              className="text-white/80 hover:text-white transition-colors"
              aria-label="Close"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          {/* Demo badge */}
          <div className="mt-3 inline-flex items-center gap-2 bg-amber-400/90 text-amber-900 text-xs font-semibold px-3 py-1.5 rounded-full">
            🎭 SIMULATED DEMO — No real phone call will be placed
          </div>
        </div>

        <div className="p-6 space-y-5">
          {/* Beneficiary Info */}
          <div className="bg-gray-50 rounded-2xl p-4 space-y-3">
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <User className="w-4 h-4 text-green-700" />
              <span className="font-medium text-gray-800">
                {beneficiary.beneficiary_name}
              </span>
              {beneficiary.priority && (
                <span
                  className={`ml-auto text-xs font-semibold px-2 py-0.5 rounded-full border ${
                    PRIORITY_COLORS[beneficiary.priority] ?? 'bg-gray-100 text-gray-600'
                  }`}
                >
                  {beneficiary.priority.toUpperCase()}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <Phone className="w-4 h-4 text-green-700" />
              <span className="font-mono">{formatMobile(beneficiary.mobile_number)}</span>
            </div>
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <Calendar className="w-4 h-4 text-green-700" />
              <span>
                {beneficiary.visit_date} &mdash;{' '}
                <span className="font-medium">{beneficiary.visit_type}</span>
              </span>
            </div>
          </div>

          {/* Language Selector */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Globe className="w-4 h-4 text-green-700" />
              <span className="text-sm font-semibold text-gray-700">
                Select Reminder Language
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {LANGUAGES.map((lang) => (
                <button
                  key={lang.code}
                  onClick={() => setSelectedLang(lang.code)}
                  className={`flex items-center gap-2 px-3 py-2.5 rounded-xl border-2 text-sm font-medium transition-all ${
                    selectedLang === lang.code
                      ? 'border-green-700 bg-green-700 text-white shadow-md'
                      : 'border-gray-200 bg-white text-gray-700 hover:border-green-300 hover:bg-green-50'
                  }`}
                >
                  <span className="text-base">{lang.flag}</span>
                  <span>{lang.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Message Preview */}
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-2">
              Reminder Message Preview
            </label>
            <textarea
              readOnly
              value={previewMessage}
              rows={4}
              className="w-full text-sm text-gray-600 bg-gray-50 border border-gray-200 rounded-xl p-3 resize-none focus:outline-none cursor-default leading-relaxed"
            />
          </div>

          {/* Warning Box */}
          <div className="flex items-start gap-3 bg-blue-50 border border-blue-200 rounded-xl p-3">
            <Info className="w-4 h-4 text-blue-600 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-blue-700 leading-relaxed">
              This will play audio on <strong>this device</strong> using the Web
              Speech API. No actual phone call will be placed to{' '}
              <span className="font-mono font-bold">
                {formatMobile(beneficiary.mobile_number)}
              </span>{' '}
              or any telephone network.
            </p>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3 pt-1">
            <button
              onClick={onCancel}
              className="flex-1 px-4 py-3 rounded-xl border-2 border-gray-200 text-gray-600 font-medium hover:bg-gray-50 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={() => onConfirm(selectedLang)}
              className="flex-1 px-4 py-3 rounded-xl bg-green-700 text-white font-semibold hover:bg-green-800 transition-colors flex items-center justify-center gap-2 shadow-md"
            >
              <Phone className="w-4 h-4" />
              Initiate Simulated Call
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default IVRConfirmModal
