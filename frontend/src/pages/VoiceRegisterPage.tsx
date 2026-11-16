import { useState, useRef, useEffect, useCallback } from 'react'
import { Mic, Square, Volume2, VolumeX, CheckCircle2, AlertTriangle, RefreshCw, Loader2, FileCheck } from 'lucide-react'
import { voiceAPI, visitAPI, beneficiaryAPI } from '../services/api'

type WorkflowState = 'idle' | 'recording' | 'processing' | 'extracted' | 'reading' | 'correcting' | 'confirmed'

const VISIT_TYPES = [
  { value: 'pregnancy', label: 'Pregnancy Visit' },
  { value: 'newborn', label: 'Newborn Visit' },
  { value: 'postnatal', label: 'Postnatal Visit' },
  { value: 'immunisation', label: 'Immunisation Visit' },
  { value: 'household', label: 'General Household' },
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
  danger_detection_results?: {detected: boolean; name: string; referral_message_en: string; referral_message_ta: string}[]
}

interface Beneficiary {
  beneficiary_id: string
  name: string
  pregnancy_status?: string
  pregnancy_month?: number
}

export default function VoiceRegisterPage() {
  const [state, setState] = useState<WorkflowState>('idle')
  const [visitType, setVisitType] = useState('pregnancy')
  const [language, setLanguage] = useState('ta')
  const [transcript, setTranscript] = useState('')
  const [extracted, setExtracted] = useState<ExtractedRecord | null>(null)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [recordingTime, setRecordingTime] = useState(0)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  const [beneficiaries, setBeneficiaries] = useState<Beneficiary[]>([])
  const [selectedBeneficiary, setSelectedBeneficiary] = useState<Beneficiary | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [audioLevel, setAudioLevel] = useState(0)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<BlobPart[]>([])
  const timerRef = useRef<number | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const animFrameRef = useRef<number | null>(null)
  const streamRef = useRef<MediaStream | null>(null)

  // Load beneficiaries
  useEffect(() => {
    beneficiaryAPI.list().then(r => setBeneficiaries(r.data.results || [])).catch(() => {})
  }, [])

  const filteredBeneficiaries = beneficiaries.filter(b =>
    b.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    b.beneficiary_id.toLowerCase().includes(searchQuery.toLowerCase())
  )

  // Audio level visualizer
  const startVisualizer = useCallback((stream: MediaStream) => {
    const ctx = new AudioContext()
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

  async function startRecording() {
    setError('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      startVisualizer(stream)

      const mr = new MediaRecorder(stream, { mimeType: MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/mp4' })
      chunksRef.current = []
      mr.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data) }
      mr.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: mr.mimeType })
        await processAudio(blob, mr.mimeType)
      }
      mr.start(500)
      mediaRecorderRef.current = mr
      setState('recording')

      // Timer
      setRecordingTime(0)
      timerRef.current = window.setInterval(() => setRecordingTime(t => t + 1), 1000)
    } catch (err) {
      setError('Microphone access denied. Please allow microphone permission and try again.')
    }
  }

  function stopRecording() {
    if (timerRef.current) clearInterval(timerRef.current)
    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
    if (mediaRecorderRef.current?.state !== 'inactive') mediaRecorderRef.current?.stop()
    streamRef.current?.getTracks().forEach(t => t.stop())
    setState('processing')
    setAudioLevel(0)
  }

  async function processAudio(blob: Blob, mimeType: string) {
    setState('processing')
    try {
      const fd = new FormData()
      const ext = mimeType.includes('webm') ? 'webm' : 'mp4'
      fd.append('audio', blob, `recording.${ext}`)
      fd.append('language', language)
      fd.append('visit_type', visitType)
      const tr = await voiceAPI.transcribe(fd)
      const t = tr.data.transcript || ''
      setTranscript(t)

      if (!t) { setError('No speech detected. Please try again.'); setState('idle'); return }

      // Extract via AI
      const ex = await visitAPI.extract(t, visitType)
      const rec: ExtractedRecord = ex.data
      if (selectedBeneficiary) {
        rec.beneficiary_name = rec.beneficiary_name || selectedBeneficiary.name
      }
      setExtracted(rec)
      setState('extracted')
    } catch {
      setError('Processing failed. Check your API connection and try again.')
      setState('idle')
    }
  }

  function speakText(text: string) {
    window.speechSynthesis.cancel()
    const u = new SpeechSynthesisUtterance(text)
    u.lang = language === 'ta' ? 'ta-IN' : language === 'hi' ? 'hi-IN' : 'en-IN'
    u.rate = 0.85
    u.onstart = () => setIsSpeaking(true)
    u.onend = () => setIsSpeaking(false)
    u.onerror = () => setIsSpeaking(false)
    window.speechSynthesis.speak(u)
    setState('reading')
  }

  function buildReadbackText(r: ExtractedRecord) {
    const lines = [`Visit record for ${r.beneficiary_name || 'beneficiary'}.`]
    if (r.visit_type) lines.push(`Visit type: ${r.visit_type}.`)
    if (r.pregnancy_month) lines.push(`Pregnancy: ${r.pregnancy_month} months.`)
    if (r.weight_kg) lines.push(`Weight: ${r.weight_kg} kilograms.`)
    if (r.anc_completed === true) lines.push('ANC checkup completed.')
    if (r.ifa_given === true) lines.push('IFA tablet given.')
    if (r.vaccinations?.length) lines.push(`Vaccinations: ${r.vaccinations.join(', ')}.`)
    if (r.next_visit_date) lines.push(`Next visit: ${r.next_visit_date}.`)
    if (r.missing_fields?.length) lines.push(`Missing: ${r.missing_fields.join(', ')}.`)
    lines.push('Is this correct?')
    return lines.join(' ')
  }

  function stopSpeaking() {
    window.speechSynthesis.cancel()
    setIsSpeaking(false)
    setState('extracted')
  }

  async function confirmRecord() {
    if (!extracted?._id && !extracted?.id) { setError('No record to save'); return }
    const id = extracted._id || extracted.id!
    setState('processing')
    try {
      await visitAPI.confirm(id)
      setSaved(true)
      setState('confirmed')
    } catch {
      setError('Save failed. Please try again.')
      setState('extracted')
    }
  }

  function reset() {
    window.speechSynthesis.cancel()
    setState('idle')
    setTranscript('')
    setExtracted(null)
    setError('')
    setSaved(false)
    setRecordingTime(0)
    setAudioLevel(0)
  }

  const dangerResults = extracted?.danger_detection_results?.filter(r => r.detected) || []
  const hasDanger = extracted?.danger_flag || dangerResults.length > 0

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

      {/* Microphone */}
      <div className="bg-white rounded-2xl p-8 shadow-sm flex flex-col items-center">
        <div className="relative mb-6">
          {state === 'recording' && (
            <>
              <div className="absolute inset-0 bg-red-200 rounded-full pulse-ring scale-125" />
              <div className="absolute inset-0 bg-red-100 rounded-full pulse-ring scale-150" style={{animationDelay:'0.5s'}} />
            </>
          )}
          <button
            onClick={state === 'idle' || state === 'extracted' || state === 'confirmed' ? startRecording : stopRecording}
            disabled={state === 'processing' || state === 'reading'}
            className={`w-32 h-32 rounded-full flex items-center justify-center transition-all shadow-lg relative z-10 ${
              state === 'recording' ? 'bg-red-600 hover:bg-red-700' :
              state === 'processing' ? 'bg-gray-200 cursor-not-allowed' :
              'bg-green-700 hover:bg-green-800 hover:scale-105'
            }`}
          >
            {state === 'processing' ? <Loader2 className="w-12 h-12 text-white animate-spin" /> :
             state === 'recording' ? <Square className="w-12 h-12 text-white" fill="white" /> :
             state === 'confirmed' ? <CheckCircle2 className="w-12 h-12 text-white" /> :
             <Mic className="w-12 h-12 text-white" />}
          </button>
        </div>

        {/* Audio visualizer */}
        {state === 'recording' && (
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

        <p className="text-sm text-gray-600 font-medium">
          {state === 'idle' && 'Tap to start recording'}
          {state === 'recording' && `🔴 Recording… ${recordingTime}s — Tap to stop`}
          {state === 'processing' && 'AI processing your speech…'}
          {state === 'extracted' && 'Record extracted — review below'}
          {state === 'reading' && 'Reading record aloud…'}
          {state === 'correcting' && 'Say your correction…'}
          {state === 'confirmed' && '✅ Record saved to MongoDB'}
        </p>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-2xl p-4 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
          <p className="text-red-700 text-sm">{error}</p>
        </div>
      )}

      {/* Danger Alert */}
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
      {extracted && (
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
              { label: 'Beneficiary', value: extracted.beneficiary_name },
              { label: 'Visit Type', value: extracted.visit_type },
              { label: 'Visit Date', value: extracted.visit_date },
              { label: 'Pregnancy Month', value: extracted.pregnancy_month },
              { label: 'Weight (kg)', value: extracted.weight_kg },
              { label: 'ANC Completed', value: extracted.anc_completed === null ? null : extracted.anc_completed ? 'Yes' : 'No' },
              { label: 'IFA Given', value: extracted.ifa_given === null ? null : extracted.ifa_given ? 'Yes' : 'No' },
              { label: 'Next Visit', value: extracted.next_visit_date },
            ].filter(f => f.value !== null && f.value !== undefined).map(f => (
              <div key={f.label} className={`bg-gray-50 rounded-xl p-3 ${extracted.uncertain_fields?.includes(f.label.toLowerCase().replace(' ','_')) ? 'border border-orange-200' : ''}`}>
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
          {extracted.missing_fields && extracted.missing_fields.length > 0 && (
            <div className="mt-3 bg-orange-50 border border-orange-200 rounded-xl p-3">
              <p className="text-xs text-orange-600 font-medium mb-1">Missing fields</p>
              <p className="text-sm text-orange-800">{extracted.missing_fields.join(', ')}</p>
            </div>
          )}

          {/* Actions */}
          <div className="flex flex-wrap gap-3 mt-5">
            <button onClick={() => speakText(buildReadbackText(extracted))} disabled={isSpeaking} className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50">
              <Volume2 className="w-4 h-4" /> Read Aloud
            </button>
            {isSpeaking && (
              <button onClick={stopSpeaking} className="flex items-center gap-2 px-4 py-2.5 bg-gray-200 text-gray-700 rounded-xl text-sm font-medium hover:bg-gray-300 transition-colors">
                <VolumeX className="w-4 h-4" /> Stop
              </button>
            )}
            <button onClick={startRecording} className="flex items-center gap-2 px-4 py-2.5 bg-orange-100 text-orange-700 rounded-xl text-sm font-medium hover:bg-orange-200 transition-colors">
              <Mic className="w-4 h-4" /> Correct via Voice
            </button>
            <button onClick={confirmRecord} disabled={state === 'processing' || saved} className="flex items-center gap-2 px-4 py-2.5 bg-green-700 text-white rounded-xl text-sm font-semibold hover:bg-green-800 transition-colors disabled:opacity-50">
              <CheckCircle2 className="w-4 h-4" /> Confirm & Save
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
