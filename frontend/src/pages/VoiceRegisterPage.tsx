import { useState, useRef, useEffect, useCallback } from 'react'
import {
  Mic, Square, Volume2, VolumeX, CheckCircle2, AlertTriangle,
  RefreshCw, Loader2, FileCheck, HelpCircle, Edit3
} from 'lucide-react'
import { voiceAPI, visitAPI, beneficiaryAPI } from '../services/api'

// ─────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────

type WorkflowState =
  | 'idle'
  | 'recording'
  | 'processing'
  | 'extracted'          // draft returned, may be incomplete
  | 'collecting_field'   // asking for a missing field
  | 'collecting_recording' // recording answer to missing-field prompt
  | 'collecting_processing'// transcribing/extracting field value
  | 'reading'            // TTS read-back
  | 'awaiting_confirm'   // read-back done, waiting for yes/no
  | 'correcting'         // voice correction in progress
  | 'confirmed'          // saved to MongoDB

const VISIT_TYPES = [
  { value: 'pregnancy',    label: 'Pregnancy Visit' },
  { value: 'newborn',      label: 'Newborn Visit' },
  { value: 'postnatal',    label: 'Postnatal Visit' },
  { value: 'immunisation', label: 'Immunisation Visit' },
  { value: 'household',    label: 'General Household' },
]

const LANGUAGES = [
  { value: 'ta', label: 'Tamil' },
  { value: 'hi', label: 'Hindi' },
  { value: 'en', label: 'English' },
  { value: 'kn', label: 'Kannada' },
  { value: 'te', label: 'Telugu' },
]

interface ExtractedRecord {
  _id?: string
  id?: string
  beneficiary_name?: string
  visit_type?: string
  visit_date?: string
  pregnancy_month?: number
  weight_kg?: number
  anc_completed?: boolean
  ifa_given?: boolean
  vaccinations?: string[]
  danger_signs?: string[]
  danger_flag?: boolean
  next_visit_date?: string
  missing_fields?: string[]
  uncertain_fields?: string[]
  confirmation_status?: string
  confidence_score?: number
  validation_errors?: string[]
  danger_detection_results?: {
    detected: boolean
    name: string
    referral_message_en: string
    referral_message_ta: string
  }[]
}

interface ExtractResponse {
  draft_id: string
  record: ExtractedRecord
  missing_fields: string[]
  is_complete: boolean
  validation_errors: string[]
  next_prompt: string | null
  readback_text: string | null
  danger_flag: boolean
  danger_alert_created: boolean
}

interface Beneficiary {
  beneficiary_id: string
  name: string
  pregnancy_status?: string
  pregnancy_month?: number
}

// ─────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────

function buildReadbackText(r: ExtractedRecord): string {
  const lines = [`Visit record for ${r.beneficiary_name || 'beneficiary'}.`]
  if (r.visit_type)       lines.push(`Visit type: ${r.visit_type}.`)
  if (r.pregnancy_month)  lines.push(`Pregnancy: ${r.pregnancy_month} months.`)
  if (r.weight_kg)        lines.push(`Weight: ${r.weight_kg} kilograms.`)
  if (r.anc_completed === true)  lines.push('ANC checkup completed.')
  if (r.ifa_given === true)      lines.push('IFA tablet given.')
  if (r.vaccinations?.length)    lines.push(`Vaccinations: ${r.vaccinations.join(', ')}.`)
  if (r.next_visit_date)  lines.push(`Next visit: ${r.next_visit_date}.`)
  lines.push('Is this correct? Say yes to save or no to correct.')
  return lines.join(' ')
}

// ─────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────

export default function VoiceRegisterPage() {
  const [state, setState]       = useState<WorkflowState>('idle')
  const [visitType, setVisitType] = useState('pregnancy')
  const [language, setLanguage] = useState('ta')
  const [transcript, setTranscript] = useState('')
  const [extracted, setExtracted]   = useState<ExtractedRecord | null>(null)
  const [draftId, setDraftId]       = useState<string | null>(null)
  const [missingFields, setMissingFields] = useState<string[]>([])
  const [currentFieldPrompt, setCurrentFieldPrompt] = useState<string | null>(null)
  const [readbackText, setReadbackText] = useState<string | null>(null)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [recordingTime, setRecordingTime] = useState(0)
  const [error, setError]       = useState('')
  const [saved, setSaved]       = useState(false)
  const [beneficiaries, setBeneficiaries] = useState<Beneficiary[]>([])
  const [selectedBeneficiary, setSelectedBeneficiary] = useState<Beneficiary | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [audioLevel, setAudioLevel]   = useState(0)
  const [validationErrors, setValidationErrors] = useState<string[]>([])
  // For manual field correction form
  const [showCorrectForm, setShowCorrectForm] = useState(false)
  const [correctField, setCorrectField] = useState('')
  const [correctValue, setCorrectValue] = useState('')

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef        = useRef<BlobPart[]>([])
  const timerRef         = useRef<number | null>(null)
  const analyserRef      = useRef<AnalyserNode | null>(null)
  const animFrameRef     = useRef<number | null>(null)
  const streamRef        = useRef<MediaStream | null>(null)
  // tracks whether we're recording for a missing-field answer
  const collectingFieldRef = useRef<string | null>(null)

  // Load beneficiaries
  useEffect(() => {
    beneficiaryAPI.list().then(r => setBeneficiaries(r.data.results || [])).catch(() => {})
  }, [])

  const filteredBeneficiaries = beneficiaries.filter(b =>
    b.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    b.beneficiary_id.toLowerCase().includes(searchQuery.toLowerCase())
  )

  // ── Audio visualizer ───────────────────────────────────────
  const startVisualizer = useCallback((stream: MediaStream) => {
    const ctx    = new AudioContext()
    const source = ctx.createMediaStreamSource(stream)
    const analyser = ctx.createAnalyser()
    analyser.fftSize = 32
    source.connect(analyser)
    analyserRef.current = analyser
    const data = new Uint8Array(analyser.frequencyBinCount)
    function update() {
      analyser.getByteFrequencyData(data)
      const avg = data.reduce((a, b) => a + b, 0) / data.length
      setAudioLevel(avg)
      animFrameRef.current = requestAnimationFrame(update)
    }
    update()
  }, [])

  // ── Core: start recording ──────────────────────────────────
  async function startRecording(forField?: string) {
    setError('')
    collectingFieldRef.current = forField ?? null
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      startVisualizer(stream)

      const mr = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/mp4',
      })
      chunksRef.current = []
      mr.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data) }
      mr.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: mr.mimeType })
        await processAudio(blob, mr.mimeType)
      }
      mr.start(500)
      mediaRecorderRef.current = mr

      setState(forField ? 'collecting_recording' : 'recording')
      setRecordingTime(0)
      timerRef.current = window.setInterval(() => setRecordingTime(t => t + 1), 1000)
    } catch {
      setError('Microphone access denied. Please allow microphone permission and try again.')
    }
  }

  function stopRecording() {
    if (timerRef.current) clearInterval(timerRef.current)
    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
    if (mediaRecorderRef.current?.state !== 'inactive') mediaRecorderRef.current?.stop()
    streamRef.current?.getTracks().forEach(t => t.stop())
    setState(collectingFieldRef.current ? 'collecting_processing' : 'processing')
    setAudioLevel(0)
  }

  // ── Process audio blob ─────────────────────────────────────
  async function processAudio(blob: Blob, mimeType: string) {
    const targetField = collectingFieldRef.current
    try {
      const fd  = new FormData()
      const ext = mimeType.includes('webm') ? 'webm' : 'mp4'
      fd.append('audio', blob, `recording.${ext}`)
      fd.append('language', language)
      fd.append('visit_type', visitType)
      const tr = await voiceAPI.transcribe(fd)
      const t  = tr.data.transcript || ''
      setTranscript(t)

      if (!t) { setError('No speech detected. Please try again.'); setState('idle'); return }

      if (targetField) {
        // ── collecting a specific missing field ──────────────
        await submitFieldAnswer(targetField, t)
      } else {
        // ── initial extraction ───────────────────────────────
        await runExtract(t)
      }
    } catch {
      setError('Processing failed. Check your API connection and try again.')
      setState(targetField ? 'collecting_field' : 'idle')
    }
  }

  // ── Initial extraction ─────────────────────────────────────
  async function runExtract(t: string) {
    setState('processing')
    const payload: Record<string, string> = { transcript: t, visit_type: visitType }
    if (selectedBeneficiary) {
      payload.beneficiary_name = selectedBeneficiary.name
      payload.beneficiary_id   = selectedBeneficiary.beneficiary_id
    }

    const ex   = await visitAPI.extract(t, visitType, payload)
    const data: ExtractResponse = ex.data

    setDraftId(data.draft_id)
    setExtracted(data.record)
    setMissingFields(data.missing_fields)
    setValidationErrors(data.validation_errors || [])

    if (data.is_complete && data.readback_text) {
      setReadbackText(data.readback_text)
      setState('awaiting_confirm')
    } else if (data.missing_fields.length > 0 && data.next_prompt) {
      setCurrentFieldPrompt(data.next_prompt)
      speakText(data.next_prompt)
      setState('collecting_field')
    } else {
      setState('extracted')
    }
  }

  // ── Submit answer for a missing field ──────────────────────
  async function submitFieldAnswer(field: string, fieldTranscript: string) {
    if (!draftId) return
    setState('collecting_processing')
    try {
      const res = await visitAPI.addDraftField(draftId, {
        field,
        transcript: fieldTranscript,
      })
      const data = res.data

      setExtracted(data.record)
      setMissingFields(data.missing_fields || [])

      if (data.is_complete && data.readback_text) {
        setReadbackText(data.readback_text)
        setState('awaiting_confirm')
        speakText(data.readback_text)
      } else if (data.missing_fields?.length > 0 && data.next_prompt) {
        setCurrentFieldPrompt(data.next_prompt)
        speakText(data.next_prompt)
        setState('collecting_field')
      } else {
        setState('extracted')
      }
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { next_prompt?: string; error?: string } } }
      const nextPrompt = axiosErr?.response?.data?.next_prompt
      const errMsg     = axiosErr?.response?.data?.error || 'Field update failed.'
      setError(errMsg)
      if (nextPrompt) {
        setCurrentFieldPrompt(nextPrompt)
        speakText(nextPrompt)
      }
      setState('collecting_field')
    }
  }

  // ── Manual field correction form ───────────────────────────
  async function submitManualCorrection() {
    if (!draftId || !correctField) return
    setState('collecting_processing')
    try {
      const res = await visitAPI.addDraftField(draftId, {
        field: correctField,
        value: correctValue,
      })
      const data = res.data
      setExtracted(data.record)
      setMissingFields(data.missing_fields || [])
      setShowCorrectForm(false)
      setCorrectField('')
      setCorrectValue('')
      setError('')

      if (data.is_complete && data.readback_text) {
        setReadbackText(data.readback_text)
        setState('awaiting_confirm')
      } else if (data.missing_fields?.length > 0 && data.next_prompt) {
        setCurrentFieldPrompt(data.next_prompt)
        speakText(data.next_prompt)
        setState('collecting_field')
      } else {
        setState('extracted')
      }
    } catch {
      setError('Correction failed. Please try again.')
      setState('extracted')
    }
  }

  // ── TTS ────────────────────────────────────────────────────
  function speakText(text: string) {
    window.speechSynthesis.cancel()
    const u  = new SpeechSynthesisUtterance(text)
    u.lang   = language === 'ta' ? 'ta-IN' : language === 'hi' ? 'hi-IN' : 'en-IN'
    u.rate   = 0.85
    u.onstart = () => setIsSpeaking(true)
    u.onend   = () => setIsSpeaking(false)
    u.onerror = () => setIsSpeaking(false)
    window.speechSynthesis.speak(u)
  }

  function stopSpeaking() {
    window.speechSynthesis.cancel()
    setIsSpeaking(false)
  }

  // ── Trigger read-back manually ─────────────────────────────
  function triggerReadback() {
    if (!extracted) return
    const text = readbackText || buildReadbackText(extracted)
    setReadbackText(text)
    speakText(text)
    setState('awaiting_confirm')
  }

  // ── Confirm & save ─────────────────────────────────────────
  async function confirmRecord() {
    if (!draftId) { setError('No draft to save'); return }
    setState('processing')
    try {
      const res = await visitAPI.confirmDraft(draftId)
      setSaved(true)
      setState('confirmed')
      setExtracted(res.data.visit)
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { blocking_reasons?: string[]; missing_fields?: string[]; next_prompt?: string } } }
      const data = axiosErr?.response?.data
      if (data?.blocking_reasons) {
        setValidationErrors(data.blocking_reasons)
        if (data.missing_fields?.length && data.next_prompt) {
          setMissingFields(data.missing_fields)
          setCurrentFieldPrompt(data.next_prompt)
          speakText(data.next_prompt)
          setState('collecting_field')
        } else {
          setState('extracted')
        }
        setError('Cannot save: some required fields are still missing or invalid.')
      } else {
        setError('Save failed. Please try again.')
        setState('extracted')
      }
    }
  }

  // ── Discard / reset ────────────────────────────────────────
  async function reset() {
    window.speechSynthesis.cancel()
    if (draftId && !saved) {
      try { await visitAPI.discardDraft(draftId) } catch { /* ignore */ }
    }
    setState('idle')
    setTranscript('')
    setExtracted(null)
    setDraftId(null)
    setMissingFields([])
    setCurrentFieldPrompt(null)
    setReadbackText(null)
    setError('')
    setSaved(false)
    setRecordingTime(0)
    setAudioLevel(0)
    setValidationErrors([])
    setShowCorrectForm(false)
    collectingFieldRef.current = null
  }

  // ─────────────────────────────────────────────────────────
  // Derived
  // ─────────────────────────────────────────────────────────

  const dangerResults = extracted?.danger_detection_results?.filter(r => r.detected) || []
  const hasDanger = extracted?.danger_flag || dangerResults.length > 0
  const isRecordingState  = state === 'recording' || state === 'collecting_recording'
  const isProcessingState = state === 'processing' || state === 'collecting_processing'

  function micLabel() {
    if (state === 'idle')                return 'Tap to start recording'
    if (state === 'recording')           return `🔴 Recording… ${recordingTime}s — Tap to stop`
    if (state === 'collecting_recording') return `🔴 Answer recording… ${recordingTime}s — Tap to stop`
    if (state === 'processing')          return 'AI processing your speech…'
    if (state === 'collecting_processing') return 'Processing your answer…'
    if (state === 'extracted')           return 'Record extracted — review below'
    if (state === 'collecting_field')    return 'Waiting for your answer…'
    if (state === 'reading')             return 'Reading record aloud…'
    if (state === 'awaiting_confirm')    return 'Please confirm or correct the record'
    if (state === 'confirmed')           return '✅ Record saved to MongoDB'
    return ''
  }

  // ─────────────────────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────────────────────

  return (
    <div className="max-w-2xl mx-auto space-y-5">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Voice Field Register</h2>
        <p className="text-gray-500 text-sm mt-1">Record your visit by speaking naturally in Tamil or English</p>
      </div>

      {/* Beneficiary Search */}
      <div className="bg-white rounded-2xl p-5 shadow-sm">
        <h3 className="font-semibold text-gray-800 mb-3">Select Beneficiary</h3>
        <input
          type="text"
          placeholder="Search by name or ID…"
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          className="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500 mb-3"
        />
        {searchQuery && (
          <div className="border border-gray-200 rounded-xl overflow-hidden max-h-40 overflow-y-auto">
            {filteredBeneficiaries.map(b => (
              <button
                key={b.beneficiary_id}
                onClick={() => { setSelectedBeneficiary(b); setSearchQuery('') }}
                className={`w-full text-left px-4 py-2.5 text-sm hover:bg-green-50 transition-colors flex items-center justify-between ${selectedBeneficiary?.beneficiary_id === b.beneficiary_id ? 'bg-green-50' : ''}`}
              >
                <span className="font-medium">{b.name}</span>
                <span className="text-gray-400 text-xs">{b.beneficiary_id}</span>
              </button>
            ))}
            {filteredBeneficiaries.length === 0 && <p className="px-4 py-3 text-sm text-gray-400">No results</p>}
          </div>
        )}
        {selectedBeneficiary && (
          <div className="flex items-center justify-between bg-green-50 rounded-xl px-4 py-2.5">
            <div>
              <p className="font-medium text-green-900">{selectedBeneficiary.name}</p>
              <p className="text-xs text-green-700">{selectedBeneficiary.beneficiary_id} · {selectedBeneficiary.pregnancy_status}</p>
            </div>
            <button onClick={() => setSelectedBeneficiary(null)} className="text-green-600 hover:text-green-800 text-sm">Change</button>
          </div>
        )}
      </div>

      {/* Controls */}
      <div className="bg-white rounded-2xl p-5 shadow-sm grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1.5">Visit Type</label>
          <select value={visitType} onChange={e => setVisitType(e.target.value)} className="w-full border border-gray-300 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500">
            {VISIT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1.5">Language</label>
          <select value={language} onChange={e => setLanguage(e.target.value)} className="w-full border border-gray-300 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500">
            {LANGUAGES.map(l => <option key={l.value} value={l.value}>{l.label}</option>)}
          </select>
        </div>
      </div>

      {/* Missing Field Prompt Banner */}
      {(state === 'collecting_field' || state === 'collecting_recording' || state === 'collecting_processing') && currentFieldPrompt && (
        <div className="bg-amber-50 border border-amber-300 rounded-2xl p-5 shadow-sm">
          <div className="flex items-start gap-3">
            <HelpCircle className="w-6 h-6 text-amber-600 shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="font-semibold text-amber-900 mb-1">Additional information needed</p>
              <p className="text-amber-800 text-sm">{currentFieldPrompt}</p>
              {missingFields.length > 1 && (
                <p className="text-xs text-amber-600 mt-2">
                  {missingFields.length - 1} more field{missingFields.length > 2 ? 's' : ''} needed after this.
                </p>
              )}
            </div>
          </div>
          {state === 'collecting_field' && (
            <button
              onClick={() => startRecording(missingFields[0])}
              className="mt-3 flex items-center gap-2 px-4 py-2 bg-amber-600 text-white rounded-xl text-sm font-medium hover:bg-amber-700 transition-colors"
            >
              <Mic className="w-4 h-4" /> Record Answer
            </button>
          )}
        </div>
      )}

      {/* Microphone */}
      <div className="bg-white rounded-2xl p-8 shadow-sm flex flex-col items-center">
        <div className="relative mb-6">
          {isRecordingState && (
            <>
              <div className="absolute inset-0 bg-red-200 rounded-full pulse-ring scale-125" />
              <div className="absolute inset-0 bg-red-100 rounded-full pulse-ring scale-150" style={{animationDelay:'0.5s'}} />
            </>
          )}
          <button
            onClick={() => {
              if (isRecordingState) {
                stopRecording()
              } else if (state === 'idle' || state === 'extracted' || state === 'confirmed') {
                startRecording()
              } else if (state === 'collecting_field') {
                startRecording(missingFields[0])
              }
            }}
            disabled={isProcessingState || state === 'reading' || state === 'awaiting_confirm'}
            className={`w-32 h-32 rounded-full flex items-center justify-center transition-all shadow-lg relative z-10 ${
              isRecordingState     ? 'bg-red-600 hover:bg-red-700' :
              isProcessingState    ? 'bg-gray-200 cursor-not-allowed' :
              state === 'confirmed'? 'bg-green-700' :
              'bg-green-700 hover:bg-green-800 hover:scale-105'
            }`}
          >
            {isProcessingState     ? <Loader2 className="w-12 h-12 text-white animate-spin" /> :
             isRecordingState      ? <Square className="w-12 h-12 text-white" fill="white" /> :
             state === 'confirmed' ? <CheckCircle2 className="w-12 h-12 text-white" /> :
             <Mic className="w-12 h-12 text-white" />}
          </button>
        </div>

        {/* Audio visualizer */}
        {isRecordingState && (
          <div className="flex items-center gap-1 mb-4 h-10">
            {[...Array(5)].map((_, i) => (
              <div
                key={i}
                className="w-2 bg-green-500 rounded-full wave-bar transition-all"
                style={{ height: `${Math.max(8, (audioLevel / 255) * 40 + Math.random() * 10)}px` }}
              />
            ))}
          </div>
        )}

        <p className="text-sm text-gray-600 font-medium">{micLabel()}</p>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-2xl p-4 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
          <p className="text-red-700 text-sm">{error}</p>
        </div>
      )}

      {/* Validation errors */}
      {validationErrors.length > 0 && (
        <div className="bg-orange-50 border border-orange-200 rounded-2xl p-4">
          <p className="text-orange-700 text-sm font-semibold mb-1">Validation issues:</p>
          <ul className="list-disc list-inside text-sm text-orange-700 space-y-0.5">
            {validationErrors.map((e, i) => <li key={i}>{e}</li>)}
          </ul>
        </div>
      )}

      {/* Danger Alert — fires immediately regardless of completeness */}
      {hasDanger && extracted && (
        <div className="bg-red-600 text-white rounded-2xl p-5 shadow-lg">
          <div className="flex items-center gap-3 mb-3">
            <AlertTriangle className="w-7 h-7" />
            <h3 className="font-bold text-lg">⚠️ EMERGENCY ALERT</h3>
          </div>
          {dangerResults.map((d, i) => (
            <div key={i} className="bg-red-700 rounded-xl p-4 mb-3">
              <p className="font-semibold mb-1">{d.name}</p>
              <p className="text-sm text-red-100 mb-2">{d.referral_message_en}</p>
              <p className="text-xs text-red-200 italic">{d.referral_message_ta}</p>
            </div>
          ))}
          <p className="text-xs text-red-200 mt-2">⚠️ Referral support tool — not a diagnostic system. Always use clinical judgment.</p>
        </div>
      )}

      {/* Transcript */}
      {transcript && (
        <div className="bg-white rounded-2xl p-5 shadow-sm">
          <h3 className="font-semibold text-gray-800 mb-2 text-sm">Transcript</h3>
          <p className="text-gray-700 text-sm bg-gray-50 rounded-xl p-3 leading-relaxed">{transcript}</p>
        </div>
      )}

      {/* Extracted Record */}
      {extracted && !saved && (
        <div className="bg-white rounded-2xl p-5 shadow-sm">
          <h3 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
            <FileCheck className="w-5 h-5 text-green-600" /> Extracted Visit Record
            {extracted.confidence_score !== undefined && (
              <span className="ml-auto text-xs bg-green-100 text-green-700 px-2 py-1 rounded-full">
                {Math.round(extracted.confidence_score * 100)}% confidence
              </span>
            )}
          </h3>
          <div className="grid grid-cols-2 gap-3 text-sm">
            {[
              { label: 'Beneficiary',     value: extracted.beneficiary_name },
              { label: 'Visit Type',      value: extracted.visit_type },
              { label: 'Visit Date',      value: extracted.visit_date },
              { label: 'Pregnancy Month', value: extracted.pregnancy_month },
              { label: 'Weight (kg)',     value: extracted.weight_kg },
              {
                label: 'ANC Completed',
                value: extracted.anc_completed === null || extracted.anc_completed === undefined
                  ? null
                  : extracted.anc_completed ? 'Yes' : 'No',
              },
              {
                label: 'IFA Given',
                value: extracted.ifa_given === null || extracted.ifa_given === undefined
                  ? null
                  : extracted.ifa_given ? 'Yes' : 'No',
              },
              { label: 'Next Visit',      value: extracted.next_visit_date },
            ].filter(f => f.value !== null && f.value !== undefined).map(f => (
              <div
                key={f.label}
                className={`bg-gray-50 rounded-xl p-3 ${
                  extracted.uncertain_fields?.includes(f.label.toLowerCase().replace(' ', '_'))
                    ? 'border border-orange-200' : ''
                }`}
              >
                <p className="text-xs text-gray-500 mb-0.5">{f.label}</p>
                <p className="font-medium text-gray-900">{String(f.value)}</p>
              </div>
            ))}
          </div>

          {extracted.vaccinations && extracted.vaccinations.length > 0 && (
            <div className="mt-3 bg-gray-50 rounded-xl p-3">
              <p className="text-xs text-gray-500 mb-1">Vaccinations</p>
              <p className="font-medium text-gray-900">{extracted.vaccinations.join(', ')}</p>
            </div>
          )}

          {/* Missing fields warning */}
          {missingFields.length > 0 && (
            <div className="mt-3 bg-orange-50 border border-orange-200 rounded-xl p-3">
              <p className="text-xs text-orange-600 font-semibold mb-1">
                ⚠️ Missing mandatory fields — record cannot be saved yet
              </p>
              <p className="text-sm text-orange-800">{missingFields.join(', ')}</p>
            </div>
          )}

          {/* Manual correction form */}
          {showCorrectForm && (
            <div className="mt-4 border border-gray-200 rounded-xl p-4 bg-gray-50">
              <p className="text-sm font-medium text-gray-700 mb-3">Correct a field</p>
              <div className="grid grid-cols-2 gap-3 mb-3">
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Field</label>
                  <select
                    value={correctField}
                    onChange={e => setCorrectField(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                  >
                    <option value="">Select field…</option>
                    {['beneficiary_name','visit_type','visit_date','pregnancy_month','weight_kg',
                      'anc_completed','ifa_given','next_visit_date'].map(f => (
                      <option key={f} value={f}>{f}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">New value</label>
                  <input
                    type="text"
                    value={correctValue}
                    onChange={e => setCorrectValue(e.target.value)}
                    placeholder="Enter value…"
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                  />
                </div>
              </div>
              <div className="flex gap-2">
                <button onClick={submitManualCorrection} disabled={!correctField} className="px-4 py-2 bg-green-700 text-white rounded-lg text-sm font-medium hover:bg-green-800 disabled:opacity-50">Apply</button>
                <button onClick={() => setShowCorrectForm(false)} className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-300">Cancel</button>
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex flex-wrap gap-3 mt-5">
            {/* Read aloud */}
            <button
              onClick={triggerReadback}
              disabled={isSpeaking}
              className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              <Volume2 className="w-4 h-4" /> Read Aloud
            </button>

            {isSpeaking && (
              <button onClick={stopSpeaking} className="flex items-center gap-2 px-4 py-2.5 bg-gray-200 text-gray-700 rounded-xl text-sm font-medium hover:bg-gray-300 transition-colors">
                <VolumeX className="w-4 h-4" /> Stop
              </button>
            )}

            {/* Voice correction */}
            <button
              onClick={() => startRecording()}
              className="flex items-center gap-2 px-4 py-2.5 bg-orange-100 text-orange-700 rounded-xl text-sm font-medium hover:bg-orange-200 transition-colors"
            >
              <Mic className="w-4 h-4" /> Re-record
            </button>

            {/* Manual correction */}
            <button
              onClick={() => setShowCorrectForm(v => !v)}
              className="flex items-center gap-2 px-4 py-2.5 bg-gray-100 text-gray-700 rounded-xl text-sm font-medium hover:bg-gray-200 transition-colors"
            >
              <Edit3 className="w-4 h-4" /> Correct Field
            </button>

            {/* Confirm & Save — only enabled when complete */}
            <button
              onClick={confirmRecord}
              disabled={
                isProcessingState ||
                saved ||
                missingFields.length > 0
              }
              title={missingFields.length > 0 ? `Missing: ${missingFields.join(', ')}` : 'Save to MongoDB'}
              className="flex items-center gap-2 px-4 py-2.5 bg-green-700 text-white rounded-xl text-sm font-semibold hover:bg-green-800 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <CheckCircle2 className="w-4 h-4" /> Confirm &amp; Save
            </button>
          </div>
        </div>
      )}

      {/* Read-back / awaiting confirm panel */}
      {state === 'awaiting_confirm' && readbackText && !saved && (
        <div className="bg-blue-50 border border-blue-200 rounded-2xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <Volume2 className="w-5 h-5 text-blue-700" />
            <h3 className="font-semibold text-blue-900">Please confirm the record</h3>
          </div>
          <p className="text-sm text-blue-800 leading-relaxed mb-4">{readbackText}</p>
          <div className="flex gap-3">
            <button
              onClick={confirmRecord}
              disabled={isProcessingState}
              className="flex items-center gap-2 px-5 py-2.5 bg-green-700 text-white rounded-xl text-sm font-semibold hover:bg-green-800 disabled:opacity-50"
            >
              <CheckCircle2 className="w-4 h-4" /> Yes, Save
            </button>
            <button
              onClick={() => { setState('extracted'); setShowCorrectForm(true) }}
              className="flex items-center gap-2 px-5 py-2.5 bg-gray-200 text-gray-700 rounded-xl text-sm font-medium hover:bg-gray-300"
            >
              <Edit3 className="w-4 h-4" /> No, Correct
            </button>
          </div>
        </div>
      )}

      {/* Confirmed */}
      {saved && (
        <div className="bg-green-50 border border-green-200 rounded-2xl p-5 text-center">
          <CheckCircle2 className="w-10 h-10 text-green-600 mx-auto mb-2" />
          <p className="font-semibold text-green-800">Visit record saved to MongoDB Atlas</p>
          <p className="text-sm text-green-600 mb-4">Follow-up tasks generated automatically</p>
          <button onClick={reset} className="flex items-center gap-2 px-5 py-2.5 bg-green-700 text-white rounded-xl text-sm font-medium hover:bg-green-800 mx-auto">
            <RefreshCw className="w-4 h-4" /> New Recording
          </button>
        </div>
      )}
    </div>
  )
}
