/**
 * GnaniRevisitBar.tsx
 *
 * Exact UI mirror of RevisitPage (Existing Voice AI mode).
 * Only difference: audio is captured at 16 kHz PCM and sent to
 * Gnani Prisma v3.0 STT instead of Whisper/Groq.
 * All stages, mandatory fields, ML advisory, danger signs, and
 * save flow are 100% identical to the existing revisit bar.
 */

import { useState, useRef } from 'react'
import {
  Mic, Square, UserCheck, AlertTriangle, CheckCircle2,
  Loader2, Search, ArrowRight, ShieldAlert,
  Stethoscope, Brain,
} from 'lucide-react'
import { gnaniAPI, revisitAPI, visitAPI, beneficiaryAPI, mlAPI, alertAPI } from '../../services/api'
import { Link } from 'react-router-dom'

type Stage = 'identify' | 'verify' | 'clinical' | 'review' | 'saved'

interface BeneficiaryRecord {
  beneficiary_id: string
  name: string
  village?: string
  household?: string
  phone?: string
  pregnancy_status?: string
  pregnancy_month?: number
  beneficiary_type?: string
  category?: string
  last_visit_date?: string
  next_visit_date?: string
}

interface IdentityResult {
  found: boolean
  beneficiary_id?: string
  spoken_id?: string
  spoken_name?: string
  name_match: boolean
  name_match_quality: string
  existing_beneficiary?: BeneficiaryRecord
  warning_message?: string
}

function getBeneficiaryCategory(b?: BeneficiaryRecord | null): 'pregnant_woman' | 'newborn' | 'immunization_child' {
  if (!b) return 'pregnant_woman'
  const cat = (b.category || b.beneficiary_type || '').toLowerCase()
  if (cat.includes('preg') || cat.includes('maternal')) return 'pregnant_woman'
  if (cat.includes('newb') || cat.includes('infant')) return 'newborn'
  if (cat.includes('imm') || cat.includes('child')) return 'immunization_child'
  const bid = (b.beneficiary_id || '').toUpperCase()
  if (bid.startsWith('PREG')) return 'pregnant_woman'
  if (bid.startsWith('NEWB')) return 'newborn'
  if (bid.startsWith('IMM')) return 'immunization_child'
  if (b.pregnancy_status === 'pregnant') return 'pregnant_woman'
  return 'pregnant_woman'
}

const FIELD_LABELS: Record<string, string> = {
  // Pregnant Woman
  weight_kg: 'Current Weight (kg)',
  blood_pressure: 'Blood Pressure (mmHg)',
  blood_pressure_systolic: 'BP Systolic (mmHg)',
  blood_pressure_diastolic: 'BP Diastolic (mmHg)',
  hb_level: 'Haemoglobin Level (g/dL)',
  blood_sugar_level: 'Blood Sugar Level (mg/dL)',
  vaginal_bleeding: 'Vaginal Bleeding',
  severe_headache_blurred_vision: 'Severe Headache or Blurred Vision',
  fetal_movement: 'Fetal Movement',
  ifa_calcium_consumption: 'IFA and Calcium Tablet Consumption',
  pregnancy_month: 'Pregnancy Month',
  visit_date: 'Visit Date',
  next_visit_date: 'Next Visit Date',

  // Newborn
  temperature_celsius: 'Body Temperature (°C)',
  respiratory_rate: 'Respiratory Rate (breaths/min)',
  breastfeeding_status: 'Breastfeeding Status',
  difficulty_in_feeding: 'Difficulty in Feeding',
  difficulty_in_breathing: 'Difficulty in Breathing',
  yellowing_skin_eyes: 'Yellowing of Skin or Eyes',
  umbilical_cord_condition: 'Umbilical Cord Condition',
  age_days: 'Age in Days',

  // Immunization
  height_cm: 'Current Height / Length (cm)',
  general_health_condition: 'General Health Condition',
  vaccines_due_today: 'Vaccines Due Today',
  vaccines_given_today: 'Vaccines Given Today',
  missed_vaccination_doses: 'Missed Vaccination Doses',
  previous_aefi: 'Previous AEFI',
  next_vaccination_due_date: 'Next Vaccination Due Date',
}

// ── Encode captured PCM float chunks into a WAV blob ─────────────────────────
function encodeWav(samples: Float32Array[], sampleRate: number): Blob {
  const totalLength = samples.reduce((acc, s) => acc + s.length, 0)
  const buffer = new ArrayBuffer(44 + totalLength * 2)
  const view = new DataView(buffer)

  function writeStr(offset: number, str: string) {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i))
  }

  writeStr(0, 'RIFF')
  view.setUint32(4, 36 + totalLength * 2, true)
  writeStr(8, 'WAVE')
  writeStr(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)         // PCM
  view.setUint16(22, 1, true)         // Mono
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeStr(36, 'data')
  view.setUint32(40, totalLength * 2, true)

  let offset = 44
  for (const s of samples) {
    for (let i = 0; i < s.length; i++) {
      const v = Math.max(-1, Math.min(1, s[i]))
      view.setInt16(offset, v < 0 ? v * 0x8000 : v * 0x7fff, true)
      offset += 2
    }
  }

  return new Blob([view], { type: 'audio/wav' })
}

export default function GnaniRevisitBar() {
  const [stage, setStage] = useState<Stage>('identify')
  const [language, setLanguage] = useState<'ta' | 'hi' | 'en'>('ta')

  // ── Voice Recording state ─────────────────────────────────────────────────
  const [isRecording, setIsRecording] = useState(false)
  const [recordingField, setRecordingField] = useState<string | null>(null)
  const [recordingTime, setRecordingTime] = useState(0)
  const [processing, setProcessing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Stage 1 & 2: Identity
  const [identityResult, setIdentityResult] = useState<IdentityResult | null>(null)
  const [manualIdInput, setManualIdInput] = useState('')
  const [verifiedBeneficiary, setVerifiedBeneficiary] = useState<BeneficiaryRecord | null>(null)

  // Stage 3 & 4: Clinical
  const [draftId, setDraftId] = useState<string | null>(null)
  const [visitRecord, setVisitRecord] = useState<any | null>(null)
  const [missingFields, setMissingFields] = useState<string[]>([])
  const [dangerFlag, setDangerFlag] = useState(false)
  const [dangerResults, setDangerResults] = useState<any[]>([])
  const [readbackText, setReadbackText] = useState<string | null>(null)
  const [mlAssessment, setMlAssessment] = useState<any | null>(null)
  const [saving, setSaving] = useState(false)
  const [savedVisitId, setSavedVisitId] = useState<string | null>(null)

  // Gnani Prisma audio capture refs (16 kHz PCM)
  const audioContextRef = useRef<AudioContext | null>(null)
  const mediaStreamRef = useRef<MediaStream | null>(null)
  const processorRef = useRef<ScriptProcessorNode | null>(null)
  const pcmChunksRef = useRef<Float32Array[]>([])
  const timerRef = useRef<any>(null)

  // ── Gnani Prisma 16 kHz PCM Recording ──────────────────────────────────────
  async function startRecording(target: 'identity' | 'clinical' | string) {
    setError(null)
    pcmChunksRef.current = []

    if (target !== 'identity' && target !== 'clinical') {
      setRecordingField(target)
    } else {
      setRecordingField(null)
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, sampleRate: 16000, echoCancellation: true, noiseSuppression: true },
      })
      mediaStreamRef.current = stream

      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext
      const audioCtx = new AudioCtx({ sampleRate: 16000 })
      audioContextRef.current = audioCtx

      const source = audioCtx.createMediaStreamSource(stream)
      const processor = audioCtx.createScriptProcessor(4096, 1, 1)
      processorRef.current = processor

      processor.onaudioprocess = (e) => {
        pcmChunksRef.current.push(new Float32Array(e.inputBuffer.getChannelData(0)))
      }

      source.connect(processor)
      processor.connect(audioCtx.destination)

      setIsRecording(true)
      setRecordingTime(0)
      if (timerRef.current) clearInterval(timerRef.current)
      timerRef.current = setInterval(() => setRecordingTime((t) => t + 1), 1000)
    } catch {
      setError('Microphone access denied or unavailable.')
      setRecordingField(null)
    }
  }

  async function stopRecording() {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null }
    if (processorRef.current) { processorRef.current.disconnect(); processorRef.current = null }
    if (audioContextRef.current) { audioContextRef.current.close().catch(() => {}); audioContextRef.current = null }
    if (mediaStreamRef.current) { mediaStreamRef.current.getTracks().forEach((t) => t.stop()); mediaStreamRef.current = null }

    const target = recordingField ?? (isRecording ? '_main' : null)
    setIsRecording(false)
    setRecordingField(null)

    if (pcmChunksRef.current.length === 0) return
    setProcessing(true)
    setError(null)

    try {
      const wavBlob = encodeWav(pcmChunksRef.current, 16000)
      const formData = new FormData()
      formData.append('audio_file', wavBlob, 'audio.wav')
      formData.append('language', language)

      const res = await gnaniAPI.transcribe(formData)
      const transcribed = (res.data?.transcript || '').trim()

      if (!transcribed) {
        setError('Gnani Prisma could not detect speech. Please speak clearly and try again.')
        setProcessing(false)
        return
      }

      if (target === null || target === '_main') {
        // main identity or clinical button — determine from stage
        if (stage === 'identify') {
          await processIdentityTranscript(transcribed)
        } else if (stage === 'clinical') {
          await processClinicalTranscript(transcribed)
        }
      } else if (target === 'identity') {
        await processIdentityTranscript(transcribed)
      } else if (target === 'clinical') {
        await processClinicalTranscript(transcribed)
      } else {
        await handleFieldAudioReady(target, transcribed)
      }
    } catch (err: any) {
      setError(err?.response?.data?.error || err.message || 'Gnani Prisma speech recognition failed.')
      setProcessing(false)
    }
  }

  // ── Identity Speech Processing ───────────────────────────────────────────
  async function processIdentityTranscript(text: string) {
    if (!text.trim()) return
    setProcessing(true)
    setError(null)
    try {
      const res = await revisitAPI.init({ transcript: text, language })
      setIdentityResult(res.data)
      setStage('verify')
    } catch (err: any) {
      setError(err?.response?.data?.error || 'Identity extraction failed.')
    } finally {
      setProcessing(false)
    }
  }

  async function handleManualLookup() {
    if (!manualIdInput.trim()) return
    setProcessing(true)
    setError(null)
    try {
      const res = await beneficiaryAPI.lookup(manualIdInput.trim())
      if (res.data?.found) {
        setIdentityResult({
          found: true,
          beneficiary_id: res.data.beneficiary.beneficiary_id,
          spoken_name: res.data.beneficiary.name,
          name_match: true,
          name_match_quality: 'manual_lookup',
          existing_beneficiary: res.data.beneficiary,
        })
        setStage('verify')
      } else {
        setError(`No active beneficiary found with ID ${manualIdInput}`)
      }
    } catch (err: any) {
      setError(err?.response?.data?.message || 'Beneficiary lookup failed.')
    } finally {
      setProcessing(false)
    }
  }

  function confirmIdentity() {
    if (!identityResult?.existing_beneficiary) return
    setVerifiedBeneficiary(identityResult.existing_beneficiary)
    setStage('clinical')
  }

  // ── Clinical Speech Processing ───────────────────────────────────────────
  async function processClinicalTranscript(text: string) {
    if (!text.trim() || !verifiedBeneficiary) return
    setProcessing(true)
    setError(null)

    try {
      const bCat = getBeneficiaryCategory(verifiedBeneficiary)
      const res = await revisitAPI.extract({
        transcript: text,
        beneficiary_id: verifiedBeneficiary.beneficiary_id,
        beneficiary_type: bCat,
        language,
      })

      const data = res.data
      setDraftId(data.draft_id)
      setVisitRecord(data.record)
      setMissingFields(data.missing_fields || [])
      setDangerFlag(data.danger_flag || false)
      setDangerResults(data.danger_detection_results || [])
      setMlAssessment(data.ml_risk_assessment || null)
      setReadbackText(data.readback_text || null)
      setStage('review')
    } catch (err: any) {
      setError(err?.response?.data?.error || 'Clinical extraction failed.')
    } finally {
      setProcessing(false)
    }
  }

  // ── Single-Field Voice Capture ───────────────────────────────────────────
  async function handleFieldAudioReady(fieldName: string, spoken: string) {
    if (!spoken || !verifiedBeneficiary) {
      setRecordingField(null)
      setProcessing(false)
      return
    }

    try {
      const bCat = getBeneficiaryCategory(verifiedBeneficiary)
      const extRes = await revisitAPI.extractField({
        field: fieldName,
        transcript: spoken,
        category: bCat,
        draft_id: draftId || undefined,
        language,
      })

      const extractedInfo = extRes.data?.extracted_info || {}
      const val = extRes.data?.value ?? extractedInfo?.value

      if (val !== null && val !== undefined && val !== '') {
        const updated = { ...visitRecord, [fieldName]: val }
        for (const [k, v] of Object.entries(extractedInfo)) {
          if (k !== 'field' && k !== 'value' && k !== 'raw_transcript' && v !== null && v !== undefined) {
            updated[k] = v
          }
        }
        setVisitRecord(updated)

        if (extRes.data?.missing_fields) {
          setMissingFields(extRes.data.missing_fields)
        } else {
          setMissingFields((prev) => prev.filter((f) => f !== fieldName))
        }
      } else {
        const numericOrDate = [
          'weight_kg', 'hb_level', 'blood_sugar_level', 'temperature_celsius',
          'respiratory_rate', 'height_cm', 'visit_date', 'next_visit_date', 'next_vaccination_due_date',
        ]
        if (!numericOrDate.includes(fieldName)) {
          handleRecordFieldChange(fieldName, spoken)
        } else {
          setError(`Could not extract a valid value for ${FIELD_LABELS[fieldName] || fieldName} from "${spoken}". Please try again or type manually.`)
        }
      }
    } catch {
      setError(`Failed to capture answer for ${FIELD_LABELS[fieldName] || fieldName}.`)
    } finally {
      setProcessing(false)
      setRecordingField(null)
    }
  }

  function handleRecordFieldChange(field: string, value: any) {
    if (!visitRecord) return
    const updated = { ...visitRecord, [field]: value }
    setVisitRecord(updated)
    setMissingFields((prev) => prev.filter((f) => f !== field))

    const bCat = getBeneficiaryCategory(verifiedBeneficiary)
    mlAPI.predict(bCat, updated, dangerFlag)
      .then((res) => { if (res.data?.success) setMlAssessment(res.data) })
      .catch(() => {})
  }

  // ── Save Confirm ─────────────────────────────────────────────────────────
  async function handleConfirmSave() {
    if (!draftId || !visitRecord) return
    setSaving(true)
    setError(null)

    try {
      const fieldsToSync = [
        'visit_date', 'next_visit_date', 'weight_kg',
        'blood_pressure', 'blood_pressure_systolic', 'blood_pressure_diastolic',
        'hb_level', 'blood_sugar_level', 'vaginal_bleeding', 'severe_headache_blurred_vision',
        'fetal_movement', 'ifa_calcium_consumption', 'pregnancy_month', 'ifa_given', 'calcium_given',
        'temperature_celsius', 'respiratory_rate', 'breastfeeding_status', 'difficulty_in_feeding',
        'difficulty_in_breathing', 'yellowing_skin_eyes', 'umbilical_cord_condition', 'age_days',
        'height_cm', 'general_health_condition', 'vaccines_due_today', 'vaccines_given_today',
        'missed_vaccination_doses', 'previous_aefi', 'next_vaccination_due_date',
      ]

      for (const f of fieldsToSync) {
        if (visitRecord[f] !== undefined && visitRecord[f] !== null && String(visitRecord[f]).trim() !== '') {
          try { await visitAPI.addDraftField(draftId, { field: f, value: visitRecord[f] }) } catch {}
        }
      }

      const res = await visitAPI.confirmDraft(draftId, {
        ...visitRecord,
        beneficiary_id: verifiedBeneficiary?.beneficiary_id,
        beneficiary_name: verifiedBeneficiary?.name,
        revisit_category: category,
      })

      // If clinical emergency / danger signs were flagged, register an emergency alert with full details
      if (dangerFlag || visitRecord.danger_flag || (dangerResults && dangerResults.length > 0)) {
        try {
          const signs = dangerResults?.length
            ? dangerResults.map((d: any) => (typeof d === 'string' ? d : d.name))
            : visitRecord.danger_signs || ['Emergency Clinical Danger Sign Detected']

          await alertAPI.create({
            visit_id: res.data?.visit?._id || res.data?.visit?.id || draftId,
            draft_id: draftId,
            beneficiary_id: verifiedBeneficiary?.beneficiary_id || visitRecord.beneficiary_id,
            beneficiary_name: verifiedBeneficiary?.name || visitRecord.beneficiary_name || 'Citizen Beneficiary',
            phone: verifiedBeneficiary?.phone || visitRecord.phone,
            village: verifiedBeneficiary?.village || visitRecord.village,
            household: verifiedBeneficiary?.household || visitRecord.household,
            visit_type: `Revisit: ${category}`,
            danger_signs: signs,
            danger_details: dangerResults || [],
            referral_status: 'pending',
            resolved: false,
          })
        } catch {
          // Backend draft_confirm handles it as well
        }
      }

      setSavedVisitId(res.data?.visit?._id || res.data?.visit?.id || draftId)
      setStage('saved')
    } catch (err: any) {
      const resp = err?.response?.data
      const reasons = resp?.blocking_reasons?.length ? resp.blocking_reasons.join('; ') : ''
      const missing = resp?.missing_fields?.length ? `Missing: ${resp.missing_fields.join(', ')}` : ''
      const msg = [resp?.error, reasons, missing].filter(Boolean).join(' — ') || 'Failed to save revisit.'
      setError(msg)
    } finally {
      setSaving(false)
    }
  }

  function resetAll() {
    setStage('identify')
    setIdentityResult(null)
    setManualIdInput('')
    setVerifiedBeneficiary(null)
    setDraftId(null)
    setVisitRecord(null)
    setMissingFields([])
    setDangerFlag(false)
    setDangerResults([])
    setMlAssessment(null)
    setReadbackText(null)
    setError(null)
    setSavedVisitId(null)
    setRecordingField(null)
  }

  // ── Field Header Helper Component ────────────────────────────────────────
  function FieldHeader({
    label, fieldKey, required = true,
  }: { label: string; fieldKey: string; required?: boolean }) {
    const isThisFieldRecording = isRecording && recordingField === fieldKey
    return (
      <div className="flex items-center justify-between mb-1.5">
        <label className="text-xs font-semibold text-gray-700 flex items-center gap-1">
          <span>{label}</span>
          {required && <span className="text-red-500 font-bold">*</span>}
        </label>
        <button
          type="button"
          onClick={() => {
            if (isThisFieldRecording) stopRecording()
            else startRecording(fieldKey)
          }}
          disabled={processing || (isRecording && !isThisFieldRecording)}
          title={`Speak ${label}`}
          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium transition ${
            isThisFieldRecording
              ? 'bg-red-600 text-white animate-pulse'
              : 'bg-green-50 text-green-700 hover:bg-green-100 border border-green-200'
          }`}
        >
          {isThisFieldRecording ? (
            <>
              <Square className="w-3 h-3 fill-current" />
              <span>Stop ({recordingTime}s)</span>
            </>
          ) : (
            <>
              <Mic className="w-3 h-3" />
              <span>Speak</span>
            </>
          )}
        </button>
      </div>
    )
  }

  const category = getBeneficiaryCategory(verifiedBeneficiary)
  const isMainRecording = isRecording && recordingField === null

  return (
    <div className="space-y-6">
      {/* ── Top Header ────────────────────────────────────────────────── */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-green-100 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-green-700 font-semibold text-sm mb-1">
            <Stethoscope className="w-5 h-5" />
            <span>Gnani Voice Revisit Bar</span>
            <span className="text-[10px] bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full font-mono font-bold">
              Prisma v3.0 STT
            </span>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Existing Beneficiary Revisit</h1>
          <p className="text-sm text-gray-500">
            Voice-driven identity verification &amp; category-based clinical revisit observations
          </p>
        </div>

        {/* Language selector */}
        <div className="flex items-center gap-2 bg-green-50 p-1.5 rounded-xl border border-green-200">
          <span className="text-xs font-semibold text-green-800 px-2">Voice:</span>
          {(['ta', 'hi', 'en'] as const).map((lang) => (
            <button
              key={lang}
              onClick={() => setLanguage(lang)}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                language === lang ? 'bg-green-700 text-white shadow-sm' : 'text-gray-600 hover:text-green-800'
              }`}
            >
              {lang === 'ta' ? 'தமிழ்' : lang === 'hi' ? 'हिंदी' : 'English'}
            </button>
          ))}
        </div>
      </div>

      {/* ── Progress Steps ────────────────────────────────────────────── */}
      <div className="grid grid-cols-4 gap-2 text-center text-xs font-semibold">
        <div className={`p-2.5 rounded-xl border transition ${stage === 'identify' ? 'bg-green-700 text-white border-green-700 shadow-sm' : 'bg-white text-gray-500 border-gray-200'}`}>
          1. Identity Voice
        </div>
        <div className={`p-2.5 rounded-xl border transition ${stage === 'verify' ? 'bg-green-700 text-white border-green-700 shadow-sm' : 'bg-white text-gray-500 border-gray-200'}`}>
          2. Verify Identity
        </div>
        <div className={`p-2.5 rounded-xl border transition ${stage === 'clinical' ? 'bg-green-700 text-white border-green-700 shadow-sm' : 'bg-white text-gray-500 border-gray-200'}`}>
          3. Clinical Voice
        </div>
        <div className={`p-2.5 rounded-xl border transition ${stage === 'review' || stage === 'saved' ? 'bg-green-700 text-white border-green-700 shadow-sm' : 'bg-white text-gray-500 border-gray-200'}`}>
          4. Review &amp; Save
        </div>
      </div>

      {/* ── Error display ────────────────────────────────────────────── */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700 flex items-start gap-2">
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
          <div className="flex-1">{error}</div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════ */}
      {/* STAGE 1: Identity Voice Lookup                                    */}
      {/* ══════════════════════════════════════════════════════════════════ */}
      {stage === 'identify' && (
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-green-100 space-y-6">
          <div className="text-center space-y-3">
            <h2 className="text-lg font-bold text-gray-900">Step 1: Speak Beneficiary ID or Name</h2>
            <p className="text-sm text-gray-500">
              Speak the beneficiary ID (e.g. "PREG zero one" or "Meena") to look up their record
            </p>

            <div className="pt-2">
              <button
                onClick={isMainRecording ? stopRecording : () => startRecording('identity')}
                disabled={processing}
                className={`w-20 h-20 rounded-full flex items-center justify-center transition-all shadow-lg mx-auto ${
                  isMainRecording ? 'bg-red-600 text-white animate-pulse scale-105' : 'bg-green-700 text-white hover:bg-green-800'
                }`}
              >
                {isMainRecording ? <Square className="w-8 h-8" /> : <Mic className="w-8 h-8" />}
              </button>

              <div className="mt-3">
                {isMainRecording ? (
                  <span className="text-sm font-semibold text-red-600">Recording... {recordingTime}s</span>
                ) : processing ? (
                  <span className="text-sm font-semibold text-gray-600 flex items-center justify-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin text-green-700" />
                    Recognizing beneficiary identity...
                  </span>
                ) : (
                  <span className="text-sm font-medium text-gray-600">
                    Click mic and say: "Revisit for Lakshmi, ID PREG-123456"
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Fallback manual search */}
          <div className="pt-4 border-t border-gray-100 flex items-center gap-3 max-w-md mx-auto">
            <div className="relative flex-1">
              <input
                type="text"
                placeholder="Or type ID (e.g. PREG-123456 or BEN001)"
                value={manualIdInput}
                onChange={(e) => setManualIdInput(e.target.value)}
                className="w-full px-4 py-2 border border-gray-200 rounded-xl text-sm uppercase focus:border-green-600"
              />
            </div>
            <button
              onClick={handleManualLookup}
              disabled={processing || !manualIdInput.trim()}
              className="px-4 py-2 bg-green-700 text-white rounded-xl text-sm font-semibold hover:bg-green-800 disabled:opacity-50 transition flex items-center gap-1.5"
            >
              <Search className="w-4 h-4" />
              <span>Lookup</span>
            </button>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════ */}
      {/* STAGE 2: Verify Identity                                          */}
      {/* ══════════════════════════════════════════════════════════════════ */}
      {stage === 'verify' && identityResult && (
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-green-100 space-y-6">
          <div className="flex items-center justify-between border-b border-gray-100 pb-4">
            <div>
              <h2 className="text-lg font-bold text-gray-900">Step 2: Verify Beneficiary Identity</h2>
              <p className="text-xs text-gray-500">
                Confirm this is the intended patient before recording clinical details
              </p>
            </div>
          </div>

          {/* Case 1: ID NOT FOUND */}
          {!identityResult.found && (
            <div className="p-5 bg-red-50 border-2 border-red-300 rounded-2xl space-y-3">
              <div className="flex items-center gap-2 text-red-800 font-bold">
                <ShieldAlert className="w-6 h-6 text-red-600" />
                <span>Beneficiary Not Found in Database</span>
              </div>
              <p className="text-sm text-red-700">{identityResult.warning_message}</p>
              <div className="flex items-center gap-3 pt-2">
                <button
                  onClick={() => setStage('identify')}
                  className="px-4 py-2 bg-red-700 text-white rounded-xl text-sm font-semibold hover:bg-red-800 transition"
                >
                  Try Again
                </button>
                <Link
                  to="/register"
                  className="px-4 py-2 border border-red-300 text-red-800 rounded-xl text-sm font-semibold hover:bg-red-100 transition"
                >
                  Register as New Beneficiary
                </Link>
              </div>
            </div>
          )}

          {/* Case 2: ID FOUND */}
          {identityResult.found && identityResult.existing_beneficiary && (
            <div className="space-y-4">
              {!identityResult.name_match && (
                <div className="p-4 bg-amber-50 border-2 border-amber-300 rounded-2xl flex items-start gap-3">
                  <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                  <div>
                    <h3 className="font-bold text-amber-900 text-sm">Identity Caution</h3>
                    <p className="text-xs text-amber-800 mt-1">{identityResult.warning_message}</p>
                  </div>
                </div>
              )}

              {/* Beneficiary Card */}
              <div className="bg-green-50/60 p-5 rounded-2xl border border-green-200 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 bg-green-700 text-white rounded-xl flex items-center justify-center font-bold text-lg">
                      {identityResult.existing_beneficiary.name[0]}
                    </div>
                    <div>
                      <h3 className="text-lg font-bold text-gray-900">{identityResult.existing_beneficiary.name}</h3>
                      <span className="text-xs font-mono font-semibold text-green-800 bg-green-100 px-2 py-0.5 rounded-md">
                        {identityResult.existing_beneficiary.beneficiary_id}
                      </span>
                    </div>
                  </div>
                  <span className="px-3 py-1 bg-white border border-green-300 rounded-full text-xs font-semibold text-green-800 capitalize">
                    {getBeneficiaryCategory(identityResult.existing_beneficiary).replace('_', ' ')}
                  </span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs pt-3 border-t border-green-200">
                  <div>
                    <span className="text-gray-500 block">Village</span>
                    <span className="font-semibold text-gray-800">{identityResult.existing_beneficiary.village || '—'}</span>
                  </div>
                  <div>
                    <span className="text-gray-500 block">Phone</span>
                    <span className="font-semibold text-gray-800">{identityResult.existing_beneficiary.phone || '—'}</span>
                  </div>
                  <div>
                    <span className="text-gray-500 block">Pregnancy Status</span>
                    <span className="font-semibold text-gray-800 capitalize">{identityResult.existing_beneficiary.pregnancy_status || '—'}</span>
                  </div>
                  <div>
                    <span className="text-gray-500 block">Last Visit</span>
                    <span className="font-semibold text-gray-800">{identityResult.existing_beneficiary.last_visit_date || 'None'}</span>
                  </div>
                </div>
              </div>

              {/* Confirmation Buttons */}
              <div className="flex items-center justify-end gap-3 pt-3">
                <button
                  onClick={() => setStage('identify')}
                  className="px-4 py-2 border border-gray-200 text-gray-600 rounded-xl text-sm font-semibold hover:bg-gray-50 transition"
                >
                  Wrong Patient / Re-try
                </button>
                <button
                  onClick={confirmIdentity}
                  className="px-6 py-2.5 bg-green-700 text-white rounded-xl text-sm font-semibold hover:bg-green-800 flex items-center gap-2 shadow-sm transition"
                >
                  <UserCheck className="w-4 h-4" />
                  <span>Confirm Identity &amp; Proceed</span>
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════ */}
      {/* STAGE 3: Clinical Voice Capture                                   */}
      {/* ══════════════════════════════════════════════════════════════════ */}
      {stage === 'clinical' && verifiedBeneficiary && (
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-green-100 space-y-6">
          <div className="flex items-center justify-between border-b border-gray-100 pb-3">
            <div>
              <span className="text-xs font-semibold text-green-700 uppercase">Patient Confirmed</span>
              <h2 className="text-lg font-bold text-gray-900">
                {verifiedBeneficiary.name} ({verifiedBeneficiary.beneficiary_id})
              </h2>
            </div>
            <span className="text-xs bg-green-100 text-green-800 font-semibold px-2.5 py-1 rounded-lg capitalize">
              {category.replace('_', ' ')} Revisit
            </span>
          </div>

          <div className="text-center space-y-3 py-4">
            <h3 className="text-base font-bold text-gray-800">Step 3: Speak Clinical Observations</h3>
            <p className="text-xs text-gray-500 max-w-md mx-auto">
              Speak the 8 mandatory observations naturally in {language === 'ta' ? 'Tamil' : language === 'hi' ? 'Hindi' : 'English'}.
            </p>

            <div className="pt-2">
              <button
                onClick={isMainRecording ? stopRecording : () => startRecording('clinical')}
                disabled={processing}
                className={`w-20 h-20 rounded-full flex items-center justify-center transition-all shadow-lg mx-auto ${
                  isMainRecording ? 'bg-red-600 text-white animate-pulse scale-105' : 'bg-green-700 text-white hover:bg-green-800'
                }`}
              >
                {isMainRecording ? <Square className="w-8 h-8" /> : <Mic className="w-8 h-8" />}
              </button>

              <div className="mt-3">
                {isMainRecording ? (
                  <span className="text-sm font-semibold text-red-600">Recording... {recordingTime}s</span>
                ) : processing ? (
                  <span className="text-sm font-semibold text-gray-600 flex items-center justify-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin text-green-700" />
                    Extracting clinical observations &amp; danger signs...
                  </span>
                ) : (
                  <span className="text-sm font-medium text-gray-600">
                    Click mic and speak full visit observations
                  </span>
                )}
              </div>
            </div>

            {/* Category-specific guidance */}
            <div className="text-xs text-gray-600 bg-green-50/70 p-3 rounded-xl border border-green-200 max-w-lg mx-auto text-left">
              <span className="font-bold text-green-900 block mb-1">
                Mandatory Observations for {category === 'pregnant_woman' ? 'Pregnant Woman' : category === 'newborn' ? 'Newborn' : 'Immunization'}:
              </span>
              {category === 'pregnant_woman' && (
                <ol className="list-decimal pl-4 space-y-0.5 text-gray-700">
                  <li>Weight (kg) &bull; 2. Blood Pressure (mmHg)</li>
                  <li>Haemoglobin Level (g/dL) &bull; 4. Blood Sugar Level (mg/dL)</li>
                  <li>Vaginal Bleeding &bull; 6. Severe Headache / Blurred Vision</li>
                  <li>Fetal Movement &bull; 8. IFA and Calcium Consumption</li>
                </ol>
              )}
              {category === 'newborn' && (
                <ol className="list-decimal pl-4 space-y-0.5 text-gray-700">
                  <li>Weight (kg) &bull; 2. Body Temperature (°C)</li>
                  <li>Respiratory Rate (breaths/min) &bull; 4. Breastfeeding Status</li>
                  <li>Difficulty in Feeding &bull; 6. Difficulty in Breathing</li>
                  <li>Yellowing of Skin/Eyes &bull; 8. Umbilical Cord Condition</li>
                </ol>
              )}
              {category === 'immunization_child' && (
                <ol className="list-decimal pl-4 space-y-0.5 text-gray-700">
                  <li>Weight (kg) &bull; 2. Height/Length (cm)</li>
                  <li>General Health Condition &bull; 4. Vaccines Due Today</li>
                  <li>Vaccines Given Today &bull; 6. Missed Vaccination Doses</li>
                  <li>Previous AEFI &bull; 8. Next Vaccination Due Date</li>
                </ol>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════ */}
      {/* STAGE 4: Review Clinical Data & Save                              */}
      {/* ══════════════════════════════════════════════════════════════════ */}
      {stage === 'review' && visitRecord && verifiedBeneficiary && (
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-green-100 space-y-6">
          <div className="flex items-center justify-between border-b border-gray-100 pb-3">
            <div>
              <span className="text-xs font-semibold text-green-700 uppercase">Step 4: Clinical Review &amp; Verification</span>
              <h2 className="text-lg font-bold text-gray-900">
                {verifiedBeneficiary.name} ({verifiedBeneficiary.beneficiary_id}) — {category.replace('_', ' ').toUpperCase()}
              </h2>
            </div>
            <span className="text-xs bg-gray-100 text-gray-700 font-mono px-2 py-1 rounded">
              Draft ID: {draftId?.slice(0, 8)}...
            </span>
          </div>

          {/* Missing Fields Banner */}
          {missingFields.length > 0 && (
            <div className="p-4 bg-amber-50 border-2 border-amber-300 rounded-2xl space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-amber-900 font-bold text-sm">
                  <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0" />
                  <span>Missing Mandatory Information ({missingFields.length} remaining)</span>
                </div>
                <span className="text-xs font-semibold text-amber-800 bg-amber-200/60 px-2 py-0.5 rounded-full">
                  Speak missing field to fill directly
                </span>
              </div>
              <p className="text-xs text-amber-800">
                Please complete the missing mandatory observations. Click <strong>Speak</strong> to speak just that value, or type it into the form below:
              </p>
              <div className="flex flex-wrap gap-2 pt-1">
                {missingFields.map((f) => {
                  const isRec = isRecording && recordingField === f
                  return (
                    <div
                      key={f}
                      className="flex items-center gap-2 bg-white px-3 py-1.5 rounded-xl border border-amber-300 shadow-xs text-xs"
                    >
                      <span className="font-semibold text-gray-800">{FIELD_LABELS[f] || f.replace(/_/g, ' ')}</span>
                      <button
                        type="button"
                        onClick={() => (isRec ? stopRecording() : startRecording(f))}
                        disabled={processing || (isRecording && !isRec)}
                        className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold transition ${
                          isRec
                            ? 'bg-red-600 text-white animate-pulse'
                            : 'bg-green-700 text-white hover:bg-green-800 shadow-xs'
                        }`}
                      >
                        {isRec ? (
                          <>
                            <Square className="w-3 h-3 fill-current" />
                            <span>Stop ({recordingTime}s)</span>
                          </>
                        ) : (
                          <>
                            <Mic className="w-3 h-3" />
                            <span>Speak</span>
                          </>
                        )}
                      </button>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Danger Sign Alert */}
          {dangerFlag && (
            <div className="bg-red-50 border-2 border-red-500 rounded-2xl p-5 space-y-2">
              <div className="flex items-center gap-2 text-red-900 font-bold">
                <AlertTriangle className="w-6 h-6 text-red-600" />
                <span>HIGH PRIORITY CLINICAL DANGER SIGNS DETECTED</span>
              </div>
              <p className="text-xs text-red-800">
                Deterministic clinical rules identified danger signs. Immediate medical referral recommended:
              </p>
              <div className="space-y-1">
                {dangerResults.map((d: any, i: number) => {
                  const label = typeof d === 'string' ? d : (d.name || d.sign || d.rule_id || 'Danger Sign')
                  const message = typeof d === 'object' && d !== null ? (d.referral_message_en || d.referral_message_ta || '') : ''
                  return (
                    <div key={i} className="text-xs font-semibold text-red-900 bg-white/70 p-2 rounded-lg border border-red-200">
                      ⚠ {label} {message && `— ${message}`}
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Readback Banner */}
          {readbackText && (
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-xs text-blue-900">
              <span className="font-bold block mb-1">ASHA Read-back Summary:</span>
              <p className="italic">{readbackText}</p>
            </div>
          )}

          {/* ML Risk Assessment */}
          {mlAssessment && (
            <div className={`rounded-2xl p-4 border shadow-sm transition-all ${
              mlAssessment.prediction === 1 || mlAssessment.severity === 'emergency'
                ? 'bg-amber-50/70 border-amber-300 text-amber-950'
                : 'bg-emerald-50/60 border-emerald-200 text-emerald-950'
            }`}>
              <div className="flex items-start justify-between gap-3 mb-2.5">
                <div className="flex items-center gap-2.5">
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
                    mlAssessment.prediction === 1 || mlAssessment.severity === 'emergency'
                      ? 'bg-amber-200/80 text-amber-800'
                      : 'bg-emerald-200/80 text-emerald-800'
                  }`}>
                    <Brain className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-sm text-gray-900">{mlAssessment.model_name}</span>
                      <span className="text-[10px] bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded font-mono font-bold uppercase tracking-wider">
                        ML Advisory
                      </span>
                    </div>
                    <p className="text-[11px] text-gray-500">
                      Automated screening prediction across clinical, growth &amp; schedule features
                    </p>
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <span className={`inline-block px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wide border ${
                    mlAssessment.prediction === 1
                      ? 'bg-amber-100 text-amber-800 border-amber-300'
                      : 'bg-emerald-100 text-emerald-800 border-emerald-300'
                  }`}>
                    {mlAssessment.prediction_label}
                  </span>
                </div>
              </div>

              {/* Probability Bar */}
              <div className="bg-white/80 rounded-xl p-3 border border-gray-200/70 space-y-2 mb-2.5 text-xs">
                <div className="flex justify-between items-center text-xs font-medium text-gray-700">
                  <span>Clinical Concern Probability:</span>
                  <span className="font-mono font-bold text-gray-900">
                    {(mlAssessment.probability_clinical_concern * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
                  <div
                    className={`h-2.5 rounded-full transition-all duration-500 ${
                      mlAssessment.probability_clinical_concern >= 0.5 ? 'bg-amber-500' : 'bg-emerald-500'
                    }`}
                    style={{ width: `${Math.min(100, Math.max(0, mlAssessment.probability_clinical_concern * 100))}%` }}
                  />
                </div>
                <div className="flex justify-between text-[10px] text-gray-400">
                  <span>Standard Expected Range (0%)</span>
                  <span>Screening Concern Threshold (50%)</span>
                  <span>High Concern (100%)</span>
                </div>
              </div>

              {/* Clinical Explanations */}
              {mlAssessment.clinical_explanations && mlAssessment.clinical_explanations.length > 0 && (
                <div className="space-y-1 mb-2">
                  <span className="text-xs font-semibold text-gray-700 block">Identified Clinical Drivers:</span>
                  <ul className="list-disc list-inside space-y-0.5 text-xs text-gray-600 pl-1">
                    {mlAssessment.clinical_explanations.map((exp: string, idx: number) => (
                      <li key={idx} className="leading-relaxed">{exp}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Disclaimer */}
              <div className="text-[11px] text-gray-500 bg-white/60 p-2 rounded-lg border border-gray-200/60 leading-relaxed italic">
                ⚠️ {mlAssessment.safety_disclaimer}
              </div>
            </div>
          )}

          {/* ══════════════════════════════════════════════════════════════ */}
          {/* CATEGORY 1: PREGNANT WOMAN CLINICAL FORM (8 Mandatory Fields) */}
          {/* ══════════════════════════════════════════════════════════════ */}
          {category === 'pregnant_woman' && (
            <div className="space-y-4">
              <h3 className="text-sm font-bold text-gray-900 flex items-center gap-2 border-b pb-2">
                <span className="w-2.5 h-2.5 bg-green-600 rounded-full"></span>
                <span>Pregnant Woman Revisit Observations (8 Mandatory Fields)</span>
              </h3>

              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                {/* 1. Current Weight */}
                <div className={`p-3 rounded-xl border ${missingFields.includes('weight_kg') ? 'bg-amber-50/50 border-amber-300' : 'bg-gray-50/50 border-gray-200'}`}>
                  <FieldHeader label="1. Current Weight (kg)" fieldKey="weight_kg" />
                  <input
                    type="number"
                    step="0.1"
                    value={visitRecord.weight_kg ?? ''}
                    onChange={(e) => handleRecordFieldChange('weight_kg', parseFloat(e.target.value) || null)}
                    placeholder="e.g. 58.5"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-green-600"
                  />
                </div>

                {/* 2. Blood Pressure */}
                <div className={`p-3 rounded-xl border ${missingFields.includes('blood_pressure') ? 'bg-amber-50/50 border-amber-300' : 'bg-gray-50/50 border-gray-200'}`}>
                  <FieldHeader label="2. Blood Pressure (mmHg)" fieldKey="blood_pressure" />
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      placeholder="Sys (120)"
                      value={visitRecord.blood_pressure_systolic ?? ''}
                      onChange={(e) => {
                        const sys = parseInt(e.target.value) || null
                        handleRecordFieldChange('blood_pressure_systolic', sys)
                        if (sys && visitRecord.blood_pressure_diastolic) {
                          handleRecordFieldChange('blood_pressure', `${sys}/${visitRecord.blood_pressure_diastolic}`)
                        }
                      }}
                      className="w-1/2 px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white"
                    />
                    <span className="text-gray-500 font-bold">/</span>
                    <input
                      type="number"
                      placeholder="Dia (80)"
                      value={visitRecord.blood_pressure_diastolic ?? ''}
                      onChange={(e) => {
                        const dia = parseInt(e.target.value) || null
                        handleRecordFieldChange('blood_pressure_diastolic', dia)
                        if (visitRecord.blood_pressure_systolic && dia) {
                          handleRecordFieldChange('blood_pressure', `${visitRecord.blood_pressure_systolic}/${dia}`)
                        }
                      }}
                      className="w-1/2 px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white"
                    />
                  </div>
                </div>

                {/* 3. Haemoglobin */}
                <div className={`p-3 rounded-xl border ${missingFields.includes('hb_level') ? 'bg-amber-50/50 border-amber-300' : 'bg-gray-50/50 border-gray-200'}`}>
                  <FieldHeader label="3. Haemoglobin (g/dL)" fieldKey="hb_level" />
                  <input
                    type="number"
                    step="0.1"
                    value={visitRecord.hb_level ?? ''}
                    onChange={(e) => handleRecordFieldChange('hb_level', parseFloat(e.target.value) || null)}
                    placeholder="e.g. 11.5"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-green-600"
                  />
                </div>

                {/* 4. Blood Sugar */}
                <div className={`p-3 rounded-xl border ${missingFields.includes('blood_sugar_level') ? 'bg-amber-50/50 border-amber-300' : 'bg-gray-50/50 border-gray-200'}`}>
                  <FieldHeader label="4. Blood Sugar (mg/dL)" fieldKey="blood_sugar_level" />
                  <input
                    type="number"
                    step="1"
                    value={visitRecord.blood_sugar_level ?? ''}
                    onChange={(e) => handleRecordFieldChange('blood_sugar_level', parseFloat(e.target.value) || null)}
                    placeholder="e.g. 95"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-green-600"
                  />
                </div>

                {/* 5. Vaginal Bleeding */}
                <div className={`p-3 rounded-xl border ${missingFields.includes('vaginal_bleeding') ? 'bg-amber-50/50 border-amber-300' : 'bg-gray-50/50 border-gray-200'}`}>
                  <FieldHeader label="5. Vaginal Bleeding" fieldKey="vaginal_bleeding" />
                  <select
                    value={visitRecord.vaginal_bleeding || ''}
                    onChange={(e) => handleRecordFieldChange('vaginal_bleeding', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-green-600"
                  >
                    <option value="">Select status</option>
                    <option value="No">No / None (Normal)</option>
                    <option value="Yes">Yes (High Risk / Danger Sign!)</option>
                    <option value="Spotting">Mild Spotting</option>
                  </select>
                </div>

                {/* 6. Severe Headache / Blurred Vision */}
                <div className={`p-3 rounded-xl border ${missingFields.includes('severe_headache_blurred_vision') ? 'bg-amber-50/50 border-amber-300' : 'bg-gray-50/50 border-gray-200'}`}>
                  <FieldHeader label="6. Severe Headache / Blurred Vision" fieldKey="severe_headache_blurred_vision" />
                  <select
                    value={visitRecord.severe_headache_blurred_vision || ''}
                    onChange={(e) => handleRecordFieldChange('severe_headache_blurred_vision', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-green-600"
                  >
                    <option value="">Select status</option>
                    <option value="No">No (Normal)</option>
                    <option value="Yes">Yes (Danger Sign / Pre-eclampsia risk)</option>
                    <option value="Mild Headache">Mild Headache only</option>
                  </select>
                </div>

                {/* 7. Fetal Movement */}
                <div className={`p-3 rounded-xl border ${missingFields.includes('fetal_movement') ? 'bg-amber-50/50 border-amber-300' : 'bg-gray-50/50 border-gray-200'}`}>
                  <FieldHeader label="7. Fetal Movement" fieldKey="fetal_movement" />
                  <select
                    value={visitRecord.fetal_movement || ''}
                    onChange={(e) => handleRecordFieldChange('fetal_movement', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-green-600"
                  >
                    <option value="">Select movement</option>
                    <option value="Normal">Normal (Active)</option>
                    <option value="Reduced">Reduced (Needs Attention)</option>
                    <option value="Absent">Absent (Emergency Danger Sign!)</option>
                  </select>
                </div>

                {/* 8. IFA & Calcium Consumption */}
                <div className={`p-3 rounded-xl border ${missingFields.includes('ifa_calcium_consumption') ? 'bg-amber-50/50 border-amber-300' : 'bg-gray-50/50 border-gray-200'}`}>
                  <FieldHeader label="8. IFA & Calcium Consumption" fieldKey="ifa_calcium_consumption" />
                  <select
                    value={visitRecord.ifa_calcium_consumption || (visitRecord.ifa_given ? 'Both Consumed Regularly' : '')}
                    onChange={(e) => {
                      const val = e.target.value
                      handleRecordFieldChange('ifa_calcium_consumption', val)
                      if (val.includes('Both') || val.includes('Yes')) {
                        handleRecordFieldChange('ifa_given', true)
                        handleRecordFieldChange('calcium_given', true)
                      }
                    }}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-green-600"
                  >
                    <option value="">Select consumption</option>
                    <option value="Both Consumed Regularly">Both Consumed Regularly (100% compliant)</option>
                    <option value="Only IFA Consumed">Only IFA Consumed</option>
                    <option value="Only Calcium Consumed">Only Calcium Consumed</option>
                    <option value="Irregular / Missed Doses">Irregular / Missed Doses</option>
                    <option value="Not Consumed">Not Consumed</option>
                  </select>
                </div>

                {/* Visit Date */}
                <div className="p-3 rounded-xl border bg-gray-50/50 border-gray-200">
                  <FieldHeader label="Visit Date" fieldKey="visit_date" />
                  <input
                    type="date"
                    value={visitRecord.visit_date || ''}
                    onChange={(e) => handleRecordFieldChange('visit_date', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-green-600"
                  />
                </div>

                {/* Next Visit Date */}
                <div className="p-3 rounded-xl border bg-gray-50/50 border-gray-200">
                  <FieldHeader label="Next Visit Date" fieldKey="next_visit_date" required={false} />
                  <input
                    type="date"
                    value={visitRecord.next_visit_date || ''}
                    onChange={(e) => handleRecordFieldChange('next_visit_date', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-green-600"
                  />
                </div>

                {/* Pregnancy Month */}
                <div className="p-3 rounded-xl border bg-gray-50/50 border-gray-200">
                  <FieldHeader label="Pregnancy Month (1-9)" fieldKey="pregnancy_month" required={false} />
                  <input
                    type="number"
                    min="1"
                    max="9"
                    value={visitRecord.pregnancy_month ?? ''}
                    onChange={(e) => handleRecordFieldChange('pregnancy_month', parseInt(e.target.value) || null)}
                    placeholder="e.g. 7"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-green-600"
                  />
                </div>
              </div>
            </div>
          )}

          {/* ══════════════════════════════════════════════════════════════ */}
          {/* CATEGORY 2: NEWBORN CLINICAL FORM (8 Mandatory Fields)        */}
          {/* ══════════════════════════════════════════════════════════════ */}
          {category === 'newborn' && (
            <div className="space-y-4">
              <h3 className="text-sm font-bold text-gray-900 flex items-center gap-2 border-b pb-2">
                <span className="w-2.5 h-2.5 bg-blue-600 rounded-full"></span>
                <span>Newborn Revisit Observations (8 Mandatory Fields)</span>
              </h3>

              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                {/* 1. Current Weight */}
                <div className={`p-3 rounded-xl border ${missingFields.includes('weight_kg') ? 'bg-amber-50/50 border-amber-300' : 'bg-gray-50/50 border-gray-200'}`}>
                  <FieldHeader label="1. Current Weight (kg)" fieldKey="weight_kg" />
                  <input
                    type="number"
                    step="0.05"
                    value={visitRecord.weight_kg ?? ''}
                    onChange={(e) => handleRecordFieldChange('weight_kg', parseFloat(e.target.value) || null)}
                    placeholder="e.g. 3.2"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-green-600"
                  />
                </div>

                {/* 2. Body Temperature */}
                <div className={`p-3 rounded-xl border ${missingFields.includes('temperature_celsius') ? 'bg-amber-50/50 border-amber-300' : 'bg-gray-50/50 border-gray-200'}`}>
                  <FieldHeader label="2. Body Temperature (°C)" fieldKey="temperature_celsius" />
                  <input
                    type="number"
                    step="0.1"
                    value={visitRecord.temperature_celsius ?? ''}
                    onChange={(e) => handleRecordFieldChange('temperature_celsius', parseFloat(e.target.value) || null)}
                    placeholder="e.g. 36.8"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-green-600"
                  />
                </div>

                {/* 3. Respiratory Rate */}
                <div className={`p-3 rounded-xl border ${missingFields.includes('respiratory_rate') ? 'bg-amber-50/50 border-amber-300' : 'bg-gray-50/50 border-gray-200'}`}>
                  <FieldHeader label="3. Respiratory Rate (breaths/min)" fieldKey="respiratory_rate" />
                  <input
                    type="number"
                    value={visitRecord.respiratory_rate ?? ''}
                    onChange={(e) => handleRecordFieldChange('respiratory_rate', parseInt(e.target.value) || null)}
                    placeholder="e.g. 45"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-green-600"
                  />
                </div>

                {/* 4. Breastfeeding Status */}
                <div className={`p-3 rounded-xl border ${missingFields.includes('breastfeeding_status') ? 'bg-amber-50/50 border-amber-300' : 'bg-gray-50/50 border-gray-200'}`}>
                  <FieldHeader label="4. Breastfeeding Status" fieldKey="breastfeeding_status" />
                  <select
                    value={visitRecord.breastfeeding_status || ''}
                    onChange={(e) => handleRecordFieldChange('breastfeeding_status', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-green-600"
                  >
                    <option value="">Select status</option>
                    <option value="Exclusive Breastfeeding">Exclusive Breastfeeding (Normal)</option>
                    <option value="Partial Breastfeeding">Partial Breastfeeding</option>
                    <option value="Formula / Other Milk">Formula / Other Milk</option>
                    <option value="Not Breastfeeding">Not Breastfeeding</option>
                  </select>
                </div>

                {/* 5. Difficulty in Feeding */}
                <div className={`p-3 rounded-xl border ${missingFields.includes('difficulty_in_feeding') ? 'bg-amber-50/50 border-amber-300' : 'bg-gray-50/50 border-gray-200'}`}>
                  <FieldHeader label="5. Difficulty in Feeding" fieldKey="difficulty_in_feeding" />
                  <select
                    value={visitRecord.difficulty_in_feeding || ''}
                    onChange={(e) => handleRecordFieldChange('difficulty_in_feeding', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-green-600"
                  >
                    <option value="">Select status</option>
                    <option value="No">No (Feeds Well / Normal)</option>
                    <option value="Yes">Yes (Unable to latch / Danger Sign)</option>
                  </select>
                </div>

                {/* 6. Difficulty in Breathing */}
                <div className={`p-3 rounded-xl border ${missingFields.includes('difficulty_in_breathing') ? 'bg-amber-50/50 border-amber-300' : 'bg-gray-50/50 border-gray-200'}`}>
                  <FieldHeader label="6. Difficulty in Breathing" fieldKey="difficulty_in_breathing" />
                  <select
                    value={visitRecord.difficulty_in_breathing || ''}
                    onChange={(e) => handleRecordFieldChange('difficulty_in_breathing', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-green-600"
                  >
                    <option value="">Select status</option>
                    <option value="No">No (Normal Breathing)</option>
                    <option value="Yes">Yes (Chest indrawing / Grunting - Emergency!)</option>
                  </select>
                </div>

                {/* 7. Yellowing of Skin or Eyes */}
                <div className={`p-3 rounded-xl border ${missingFields.includes('yellowing_skin_eyes') ? 'bg-amber-50/50 border-amber-300' : 'bg-gray-50/50 border-gray-200'}`}>
                  <FieldHeader label="7. Yellowing of Skin / Eyes" fieldKey="yellowing_skin_eyes" />
                  <select
                    value={visitRecord.yellowing_skin_eyes || ''}
                    onChange={(e) => handleRecordFieldChange('yellowing_skin_eyes', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-green-600"
                  >
                    <option value="">Select status</option>
                    <option value="No">No (Normal Pinkish Skin)</option>
                    <option value="Yes">Yes (Neonatal Jaundice - Danger Sign)</option>
                  </select>
                </div>

                {/* 8. Umbilical Cord Condition */}
                <div className={`p-3 rounded-xl border ${missingFields.includes('umbilical_cord_condition') ? 'bg-amber-50/50 border-amber-300' : 'bg-gray-50/50 border-gray-200'}`}>
                  <FieldHeader label="8. Umbilical Cord Condition" fieldKey="umbilical_cord_condition" />
                  <select
                    value={visitRecord.umbilical_cord_condition || ''}
                    onChange={(e) => handleRecordFieldChange('umbilical_cord_condition', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-green-600"
                  >
                    <option value="">Select condition</option>
                    <option value="Clean & Dry">Clean &amp; Dry (Normal)</option>
                    <option value="Healed / Fallen Off">Healed / Fallen Off</option>
                    <option value="Redness / Pus / Discharge">Redness / Pus / Discharge (Danger Sign!)</option>
                  </select>
                </div>

                {/* Visit Date */}
                <div className="p-3 rounded-xl border bg-gray-50/50 border-gray-200">
                  <FieldHeader label="Visit Date" fieldKey="visit_date" />
                  <input
                    type="date"
                    value={visitRecord.visit_date || ''}
                    onChange={(e) => handleRecordFieldChange('visit_date', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-green-600"
                  />
                </div>

                {/* Age in Days */}
                <div className="p-3 rounded-xl border bg-gray-50/50 border-gray-200">
                  <FieldHeader label="Age in Days" fieldKey="age_days" required={false} />
                  <input
                    type="number"
                    value={visitRecord.age_days ?? ''}
                    onChange={(e) => handleRecordFieldChange('age_days', parseInt(e.target.value) || null)}
                    placeholder="e.g. 14"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-green-600"
                  />
                </div>

                {/* Next Visit Date */}
                <div className="p-3 rounded-xl border bg-gray-50/50 border-gray-200">
                  <FieldHeader label="Next Visit Date" fieldKey="next_visit_date" required={false} />
                  <input
                    type="date"
                    value={visitRecord.next_visit_date || ''}
                    onChange={(e) => handleRecordFieldChange('next_visit_date', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-green-600"
                  />
                </div>
              </div>
            </div>
          )}

          {/* ══════════════════════════════════════════════════════════════ */}
          {/* CATEGORY 3: IMMUNIZATION CLINICAL FORM (8 Mandatory Fields)   */}
          {/* ══════════════════════════════════════════════════════════════ */}
          {category === 'immunization_child' && (
            <div className="space-y-4">
              <h3 className="text-sm font-bold text-gray-900 flex items-center gap-2 border-b pb-2">
                <span className="w-2.5 h-2.5 bg-purple-600 rounded-full"></span>
                <span>Immunization Beneficiary Revisit Observations (8 Mandatory Fields)</span>
              </h3>

              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                {/* 1. Current Weight */}
                <div className={`p-3 rounded-xl border ${missingFields.includes('weight_kg') ? 'bg-amber-50/50 border-amber-300' : 'bg-gray-50/50 border-gray-200'}`}>
                  <FieldHeader label="1. Current Weight (kg)" fieldKey="weight_kg" />
                  <input
                    type="number"
                    step="0.1"
                    value={visitRecord.weight_kg ?? ''}
                    onChange={(e) => handleRecordFieldChange('weight_kg', parseFloat(e.target.value) || null)}
                    placeholder="e.g. 8.4"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-green-600"
                  />
                </div>

                {/* 2. Height / Length */}
                <div className={`p-3 rounded-xl border ${missingFields.includes('height_cm') ? 'bg-amber-50/50 border-amber-300' : 'bg-gray-50/50 border-gray-200'}`}>
                  <FieldHeader label="2. Current Height / Length (cm)" fieldKey="height_cm" />
                  <input
                    type="number"
                    step="0.5"
                    value={visitRecord.height_cm ?? ''}
                    onChange={(e) => handleRecordFieldChange('height_cm', parseFloat(e.target.value) || null)}
                    placeholder="e.g. 72.0"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-green-600"
                  />
                </div>

                {/* 3. General Health Condition */}
                <div className={`p-3 rounded-xl border ${missingFields.includes('general_health_condition') ? 'bg-amber-50/50 border-amber-300' : 'bg-gray-50/50 border-gray-200'}`}>
                  <FieldHeader label="3. General Health Condition" fieldKey="general_health_condition" />
                  <select
                    value={visitRecord.general_health_condition || ''}
                    onChange={(e) => handleRecordFieldChange('general_health_condition', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-green-600"
                  >
                    <option value="">Select condition</option>
                    <option value="Good / Active">Good / Active (Normal)</option>
                    <option value="Fair">Fair / Alert</option>
                    <option value="Fever / Sick">Fever / Sick (Defer or Review)</option>
                    <option value="Lethargic / High Risk">Lethargic / High Risk (Refer)</option>
                  </select>
                </div>

                {/* 4. Vaccines Due Today */}
                <div className={`p-3 rounded-xl border ${missingFields.includes('vaccines_due_today') ? 'bg-amber-50/50 border-amber-300' : 'bg-gray-50/50 border-gray-200'}`}>
                  <FieldHeader label="4. Vaccines Due Today" fieldKey="vaccines_due_today" />
                  <input
                    type="text"
                    value={visitRecord.vaccines_due_today || ''}
                    onChange={(e) => handleRecordFieldChange('vaccines_due_today', e.target.value)}
                    placeholder="e.g. Pentavalent-1, OPV-1, Rotavirus-1"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-green-600"
                  />
                </div>

                {/* 5. Vaccines Given Today */}
                <div className={`p-3 rounded-xl border ${missingFields.includes('vaccines_given_today') ? 'bg-amber-50/50 border-amber-300' : 'bg-gray-50/50 border-gray-200'}`}>
                  <FieldHeader label="5. Vaccines Given Today" fieldKey="vaccines_given_today" />
                  <input
                    type="text"
                    value={visitRecord.vaccines_given_today || ''}
                    onChange={(e) => handleRecordFieldChange('vaccines_given_today', e.target.value)}
                    placeholder="e.g. Pentavalent-1, OPV-1, Rotavirus-1"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-green-600"
                  />
                </div>

                {/* 6. Missed Vaccination Doses */}
                <div className={`p-3 rounded-xl border ${missingFields.includes('missed_vaccination_doses') ? 'bg-amber-50/50 border-amber-300' : 'bg-gray-50/50 border-gray-200'}`}>
                  <FieldHeader label="6. Missed Vaccination Doses" fieldKey="missed_vaccination_doses" />
                  <input
                    type="text"
                    value={visitRecord.missed_vaccination_doses || ''}
                    onChange={(e) => handleRecordFieldChange('missed_vaccination_doses', e.target.value)}
                    placeholder="e.g. None or BCG overdue"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-green-600"
                  />
                </div>

                {/* 7. Previous AEFI */}
                <div className={`p-3 rounded-xl border ${missingFields.includes('previous_aefi') ? 'bg-amber-50/50 border-amber-300' : 'bg-gray-50/50 border-gray-200'}`}>
                  <FieldHeader label="7. Previous AEFI" fieldKey="previous_aefi" />
                  <select
                    value={visitRecord.previous_aefi || ''}
                    onChange={(e) => handleRecordFieldChange('previous_aefi', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-green-600"
                  >
                    <option value="">Select status</option>
                    <option value="None">None (No Adverse Reaction)</option>
                    <option value="Mild Fever">Mild Fever only</option>
                    <option value="Local Swelling">Local Swelling / Redness</option>
                    <option value="Severe Reaction">Severe Reaction / Anaphylaxis</option>
                  </select>
                </div>

                {/* 8. Next Vaccination Due Date */}
                <div className={`p-3 rounded-xl border ${missingFields.includes('next_vaccination_due_date') ? 'bg-amber-50/50 border-amber-300' : 'bg-gray-50/50 border-gray-200'}`}>
                  <FieldHeader label="8. Next Vaccination Due Date" fieldKey="next_vaccination_due_date" />
                  <input
                    type="date"
                    value={visitRecord.next_vaccination_due_date || visitRecord.next_visit_date || ''}
                    onChange={(e) => {
                      handleRecordFieldChange('next_vaccination_due_date', e.target.value)
                      handleRecordFieldChange('next_visit_date', e.target.value)
                    }}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-green-600"
                  />
                </div>

                {/* Visit Date */}
                <div className="p-3 rounded-xl border bg-gray-50/50 border-gray-200">
                  <FieldHeader label="Visit Date" fieldKey="visit_date" />
                  <input
                    type="date"
                    value={visitRecord.visit_date || ''}
                    onChange={(e) => handleRecordFieldChange('visit_date', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-green-600"
                  />
                </div>
              </div>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex items-center justify-between pt-4 border-t border-gray-100">
            <button
              onClick={() => setStage('clinical')}
              className="px-4 py-2 border border-gray-200 text-gray-600 rounded-xl text-sm font-semibold hover:bg-gray-50 transition"
            >
              Re-speak Full Clinical Data
            </button>
            <button
              onClick={handleConfirmSave}
              disabled={saving}
              className="px-6 py-2.5 bg-green-700 text-white rounded-xl text-sm font-semibold hover:bg-green-800 disabled:opacity-50 flex items-center gap-2 shadow-sm transition"
            >
              {saving ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Saving Revisit Record...
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  Confirm &amp; Save Revisit
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════ */}
      {/* STAGE 5: Saved Successfully                                       */}
      {/* ══════════════════════════════════════════════════════════════════ */}
      {stage === 'saved' && (
        <div className="p-6 bg-green-50 border-2 border-green-500 rounded-2xl shadow-sm space-y-4">
          <div className="flex items-center gap-3 text-green-800">
            <CheckCircle2 className="w-8 h-8 text-green-600" />
            <div>
              <h2 className="text-lg font-bold">Revisit Successfully Recorded!</h2>
              <p className="text-sm text-green-700">
                The visit record has been appended to MongoDB visits collection and patient dates synchronized.
              </p>
            </div>
          </div>

          <div className="bg-white p-4 rounded-xl border border-green-200 grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
            <div>
              <span className="text-xs text-gray-500 block">Beneficiary</span>
              <span className="font-bold text-gray-900">{verifiedBeneficiary?.name}</span>
            </div>
            <div>
              <span className="text-xs text-gray-500 block">Beneficiary ID</span>
              <span className="font-bold text-green-800">{verifiedBeneficiary?.beneficiary_id}</span>
            </div>
            <div>
              <span className="text-xs text-gray-500 block">Visit ID</span>
              <span className="text-xs font-mono text-gray-600 truncate block">{savedVisitId}</span>
            </div>
            <div>
              <span className="text-xs text-gray-500 block">Next Visit</span>
              <span className="font-semibold text-gray-800">
                {visitRecord?.next_visit_date || visitRecord?.next_vaccination_due_date || 'Not scheduled'}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={resetAll}
              className="px-4 py-2 bg-green-700 text-white rounded-xl text-sm font-semibold hover:bg-green-800 transition"
            >
              Record Another Revisit
            </button>
            <Link
              to="/visits"
              className="px-4 py-2 border border-green-300 text-green-800 rounded-xl text-sm font-semibold hover:bg-green-100 flex items-center gap-1 transition"
            >
              <span>View Visit History</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}
