// IVR Subsystem — Integrated Service
// Handles client-side audio playback via Web Speech API,
// syncs with the unified Django backend /api/ivr/ APIs, and caches in localStorage.

import type { CallStatus, Language, IVRBeneficiary, IVRCallRecord } from './ivrTypes'
import { ivrAPI } from '../../services/api'

const STORAGE_KEY = 'ivr_call_history'

// ── ID Generation ────────────────────────────────────────────────────
export function generateCallId(): string {
  const timestamp = Date.now().toString(36)
  const random = Math.random().toString(36).substring(2, 9)
  return `ivr-${timestamp}-${random}`
}

// ── Multilingual Reminder Messages ───────────────────────────────────
export function getReminderMessage(
  lang: Language,
  beneficiary_name: string,
  visit_date: string,
  visit_type: string
): string {
  const nameGreeting =
    beneficiary_name && beneficiary_name !== 'Citizen Beneficiary'
      ? `${beneficiary_name} அவர்களே`
      : ''
  const enName =
    beneficiary_name && beneficiary_name !== 'Citizen Beneficiary'
      ? `${beneficiary_name}, `
      : ''
  const hiName =
    beneficiary_name && beneficiary_name !== 'Citizen Beneficiary'
      ? `${beneficiary_name} जी, `
      : ''
  const knName =
    beneficiary_name && beneficiary_name !== 'Citizen Beneficiary'
      ? `${beneficiary_name} ಅವರೇ, `
      : ''

  const templates: Record<Language, string> = {
    en: `Hello! ${enName}This is a reminder from your local ASHA worker. Your ASHA worker is scheduled to visit you on ${visit_date} for ${visit_type}. Please be available at home. Thank you.`,
    hi: `नमस्ते! ${hiName}यह आपके स्थानीय ASHA कार्यकर्ता की ओर से एक अनुस्मारक है। आपकी ASHA कार्यकर्ता ${visit_date} को ${visit_type} के लिए आपसे मिलने आएंगी। कृपया घर पर उपलब्ध रहें। धन्यवाद।`,
    ta: `வணக்கம்! ${nameGreeting} இது உங்கள் உள்ளூர் ASHA பணியாளரிடமிருந்து ஒரு நினைவூட்டல். உங்கள் ASHA பணியாளர் ${visit_date} அன்று ${visit_type} க்காக உங்களை சந்திக்க வருவார்கள். தயவுசெய்து வீட்டில் இருங்கள். நன்றி.`,
    kn: `ನಮಸ್ಕಾರ! ${knName}ಇದು ನಿಮ್ಮ ಸ್ಥಳೀಯ ASHA ಕಾರ್ಯಕರ್ತೆಯಿಂದ ಒಂದು ನೆನಪೋಲೆ. ನಿಮ್ಮ ASHA ಕಾರ್ಯಕರ್ತೆ ${visit_date} ರಂದು ${visit_type} ಗಾಗಿ ನಿಮ್ಮನ್ನು ಭೇಟಿ ಮಾಡಲು ಬರುತ್ತಾರೆ. ದಯವಿಟ್ಟು ಮನೆಯಲ್ಲಿ ಇರಿ. ಧನ್ಯವಾದ.`,
  }

  return templates[lang] ?? templates['en']
}

// ── LocalStorage & Backend Sync ──────────────────────────────────────
export function getCallHistory(): IVRCallRecord[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    return JSON.parse(raw) as IVRCallRecord[]
  } catch {
    return []
  }
}

export async function fetchCallHistoryFromBackend(): Promise<IVRCallRecord[]> {
  try {
    const res = await ivrAPI.getHistory(100)
    const backendCalls: IVRCallRecord[] = res.data.results || []
    if (backendCalls.length > 0) {
      // Merge with local storage
      const local = getCallHistory()
      const mergedMap = new Map<string, IVRCallRecord>()
      // Backend first
      backendCalls.forEach((c) => mergedMap.set(c.call_id || c.mobile_number, c))
      // Add local if missing
      local.forEach((c) => {
        const key = c.call_id || c.mobile_number
        if (!mergedMap.has(key)) mergedMap.set(key, c)
      })
      const merged = Array.from(mergedMap.values()).sort(
        (a, b) => new Date(b.initiated_at).getTime() - new Date(a.initiated_at).getTime()
      )
      localStorage.setItem(STORAGE_KEY, JSON.stringify(merged))
      return merged
    }
  } catch (err) {
    console.warn('[IVR] Could not fetch call history from backend:', err)
  }
  return getCallHistory()
}

export function saveCallRecord(record: IVRCallRecord): void {
  const history = getCallHistory()
  const terminalStatuses: CallStatus[] = ['completed', 'busy', 'no_answer', 'failed']
  if (record.followup_id) {
    const existing = history.findIndex(
      (r) =>
        r.followup_id === record.followup_id &&
        !terminalStatuses.includes(r.status)
    )
    if (existing !== -1) {
      history[existing] = record
      localStorage.setItem(STORAGE_KEY, JSON.stringify(history))
      return
    }
  }

  history.unshift(record) // newest first
  localStorage.setItem(STORAGE_KEY, JSON.stringify(history))
}

export function clearCallHistory(): void {
  localStorage.removeItem(STORAGE_KEY)
}

// ── Duplicate Call Detection ─────────────────────────────────────────
export function isDuplicateCall(followup_id?: string, mobile_number?: string): boolean {
  const history = getCallHistory()
  const cutoff = Date.now() - 24 * 60 * 60 * 1000 // 24 hours ago

  return history.some((record) => {
    const matchesId = followup_id && record.followup_id === followup_id
    const matchesMobile = mobile_number && record.mobile_number === mobile_number
    if (!matchesId && !matchesMobile) return false
    if (!['completed', 'busy', 'no_answer'].includes(record.status)) return false
    const initiatedAt = new Date(record.initiated_at).getTime()
    return initiatedAt > cutoff
  })
}

// ── BCP-47 Language Code Map ─────────────────────────────────────────
const LANG_TO_BCP47: Record<Language, string> = {
  en: 'en-IN',
  hi: 'hi-IN',
  ta: 'ta-IN',
  kn: 'kn-IN',
}

let keepAliveTimer: ReturnType<typeof setInterval> | null = null

// ── Web Speech API with Full Voice Playback & Keep-Alive ─────────────
export function speakReminder(message: string, language: Language): Promise<void> {
  return new Promise((resolve) => {
    if (typeof window === 'undefined' || !window.speechSynthesis) {
      resolve()
      return
    }

    // Cancel any previous voice
    cancelSpeech()

    const utterance = new SpeechSynthesisUtterance(message)
    if (typeof window !== 'undefined') {
      (window as any).__ivrUtterance = utterance
    }

    const bcp47 = LANG_TO_BCP47[language] ?? 'en-IN'
    utterance.lang = bcp47
    utterance.rate = 0.88 // Clear, measured pace suitable for healthcare reminders
    utterance.pitch = 1.0
    utterance.volume = 1.0

    let finished = false
    const cleanupAndResolve = () => {
      if (finished) return
      finished = true
      if (keepAliveTimer) {
        clearInterval(keepAliveTimer)
        keepAliveTimer = null
      }
      if (typeof window !== 'undefined') {
        (window as any).__ivrUtterance = null
      }
      resolve()
    }

    utterance.onend = () => {
      cleanupAndResolve()
    }

    utterance.onerror = (e) => {
      console.warn('[IVR] Speech synthesis error or interrupted:', e.error)
      cleanupAndResolve()
    }

    // Keep-alive timer prevents browser from pausing speech mid-sentence
    keepAliveTimer = setInterval(() => {
      if (window.speechSynthesis && window.speechSynthesis.speaking) {
        window.speechSynthesis.pause()
        window.speechSynthesis.resume()
      }
    }, 4000)

    const triggerSpeech = () => {
      try {
        const voices = window.speechSynthesis.getVoices()
        const langPrefix = bcp47.split('-')[0]
        const matchedVoice = voices.find(
          (v) => v.lang === bcp47 || v.lang.startsWith(langPrefix)
        )
        if (matchedVoice) {
          utterance.voice = matchedVoice
        }
        window.speechSynthesis.speak(utterance)
      } catch (err) {
        console.warn('[IVR] Failed to speak utterance:', err)
        cleanupAndResolve()
      }
    }

    const availableVoices = window.speechSynthesis.getVoices()
    if (availableVoices && availableVoices.length > 0) {
      triggerSpeech()
    } else {
      let fired = false
      window.speechSynthesis.onvoiceschanged = () => {
        if (!fired) {
          fired = true
          triggerSpeech()
        }
      }
      setTimeout(() => {
        if (!fired && !finished) {
          fired = true
          triggerSpeech()
        }
      }, 500)
    }

    // Generous 60-second safety fallback timeout so flow never hangs permanently
    setTimeout(() => {
      if (!finished) {
        cleanupAndResolve()
      }
    }, 60000)
  })
}

export function cancelSpeech(): void {
  if (keepAliveTimer) {
    clearInterval(keepAliveTimer)
    keepAliveTimer = null
  }
  if (typeof window !== 'undefined') {
    (window as any).__ivrUtterance = null
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel()
    }
  }
}

// ── Simulated Call ───────────────────────────────────────────────────
function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export async function simulateCall(
  beneficiary: IVRBeneficiary,
  language: Language,
  followup_id?: string,
  onProgress: (status: CallStatus) => void = () => {}
): Promise<IVRCallRecord> {
  const callId = generateCallId()
  const initiatedAt = new Date().toISOString()
  const reminderMessage = getReminderMessage(
    language,
    beneficiary.beneficiary_name,
    beneficiary.visit_date,
    beneficiary.visit_type
  )

  // Stage 1 — Initiating
  onProgress('initiating')
  await delay(600)

  // Stage 2 — Dialing / Calling
  onProgress('calling')
  await delay(1200)

  // Stage 3 — Ringing
  onProgress('ringing')
  await delay(1600)

  // Stage 4 — Citizen Answers
  onProgress('answered')
  await delay(1000)

  // Stage 5 — Playing IVR Voice Reminder
  // Speaks the FULL message in the selected language without early termination
  onProgress('playing')
  const startTime = Date.now()
  await speakReminder(reminderMessage, language)

  // Comfortable natural pause after speech finishes
  await delay(2000)

  // Stage 6 — Call Completed
  onProgress('completed')
  const completedAt = new Date().toISOString()
  const durationSeconds = Math.max(15, Math.round((Date.now() - startTime) / 1000) + 4)

  const record: IVRCallRecord = {
    call_id: callId,
    beneficiary_id: beneficiary.beneficiary_id,
    beneficiary_name: beneficiary.beneficiary_name,
    mobile_number: beneficiary.mobile_number,
    visit_date: beneficiary.visit_date,
    visit_type: beneficiary.visit_type,
    language,
    reminder_message: reminderMessage,
    status: 'completed',
    outcome: 'Reminder played successfully in full',
    initiated_at: initiatedAt,
    completed_at: completedAt,
    duration_seconds: durationSeconds,
    followup_id,
    is_demo: true,
  }

  // Save to local cache
  saveCallRecord(record)

  // Sync to unified Django backend asynchronously
  try {
    await ivrAPI.initiate({
      beneficiary_name: beneficiary.beneficiary_name,
      mobile_number: beneficiary.mobile_number,
      visit_date: beneficiary.visit_date,
      visit_type: beneficiary.visit_type,
      language,
      followup_id,
      beneficiary_id: beneficiary.beneficiary_id,
      notes: beneficiary.notes,
    })
  } catch (backendErr) {
    console.warn('[IVR] Backend call logging notification:', backendErr)
  }

  return record
}
