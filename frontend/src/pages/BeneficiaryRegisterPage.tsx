import { useState, useRef, useEffect } from 'react'
import {
  Mic, Square, UserPlus, AlertTriangle, CheckCircle2,
  RefreshCw, Loader2, ArrowRight, ShieldAlert, Baby, Heart,
  Syringe, Users, Calendar, Phone, MapPin, Activity, HelpCircle,
  Check, X, Sparkles
} from 'lucide-react'
import { voiceAPI, beneficiaryAPI } from '../services/api'
import { Link, useSearchParams } from 'react-router-dom'
import GnaniBeneficiaryBar from '../components/beneficiaries/GnaniBeneficiaryBar'

export type BeneficiaryCategory = 'pregnant_woman' | 'newborn' | 'immunization_child' | 'other'

interface ExtractedData {
  beneficiary_id?: string | null
  name?: string
  baby_name?: string
  child_name?: string
  age?: number | string
  gender?: string
  address?: string
  village?: string
  household?: string
  phone?: string
  dob?: string

  // Pregnant Woman specific
  pregnancy_registration_status?: string
  lmp?: string
  edd?: string
  expected_delivery_date?: string
  gestational_age_weeks?: number | string
  gravida?: number | string
  previous_live_births?: number | string
  previous_complications?: string

  // Newborn & Immunization specific
  mother_name?: string
  mother_beneficiary_id?: string
  place_of_delivery?: string
  birth_weight_kg?: number | string

  // Immunization specific
  immunization_card_status?: string
  vaccination_status?: string
  vaccinations_received?: string[]
  vaccinations_pending?: string[]

  // Other Beneficiary specific
  beneficiary_category?: string
  emergency_contact?: string
  blood_group?: string
}

interface DuplicateWarning {
  existing_id: string
  existing_name: string
  existing_village?: string
  existing_category?: string
  phone_match: boolean
  message: string
}

const CATEGORIES: {
  id: BeneficiaryCategory
  title: string
  subtitle: string
  icon: typeof Heart
  color: string
  badge: string
}[] = [
  {
    id: 'pregnant_woman',
    title: 'Pregnant Woman',
    subtitle: 'LMP, EDD, Gestational Age, Gravida, Live Births, Complications',
    icon: Heart,
    color: 'text-rose-600 bg-rose-50 border-rose-200',
    badge: 'PREG-xxxxxx',
  },
  {
    id: 'newborn',
    title: 'Newborn Baby',
    subtitle: 'DOB, Gender, Mother Reference, Place of Delivery, Birth Weight',
    icon: Baby,
    color: 'text-blue-600 bg-blue-50 border-blue-200',
    badge: 'NEWB-xxxxxx',
  },
  {
    id: 'immunization_child',
    title: 'Immunization / Child',
    subtitle: 'DOB, Gender, Maternal Link, Card Status, Vaccine Doses',
    icon: Syringe,
    color: 'text-emerald-600 bg-emerald-50 border-emerald-200',
    badge: 'IMM-xxxxxx',
  },
  {
    id: 'other',
    title: 'Other Beneficiary',
    subtitle: 'Elderly / Adolescent / General Adult, Emergency Contact, Blood Group',
    icon: Users,
    color: 'text-purple-600 bg-purple-50 border-purple-200',
    badge: 'BEN-xxxxxx',
  },
]

const BLOOD_GROUPS = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-', 'Unknown']
const OTHER_CATEGORIES = ['Elderly Care', 'Adolescent Health', 'General Adult', 'Chronic Illness / NCD', 'Palliative Care']

function FieldLabel({
  label,
  field,
  required = false,
  isRecording,
  recordingField,
  recordingTime,
  onStart,
  onStop,
}: {
  label: string
  field: string
  required?: boolean
  isRecording: boolean
  recordingField: string | null
  recordingTime: number
  onStart: (field: string) => void
  onStop: () => void
}) {
  const isCurrent = isRecording && recordingField === field
  return (
    <div className="flex items-center justify-between mb-1">
      <label className="text-xs font-semibold text-gray-700">
        {label} {required && <span className="text-red-500">*</span>}
      </label>
      <button
        type="button"
        onClick={isCurrent ? onStop : () => onStart(field)}
        disabled={isRecording && !isCurrent}
        className={`flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-md font-medium transition ${
          isCurrent
            ? 'bg-red-600 text-white animate-pulse'
            : isRecording
            ? 'text-gray-300 cursor-not-allowed'
            : 'text-green-700 hover:bg-green-50 border border-green-200'
        }`}
      >
        {isCurrent ? (
          <>
            <Square className="w-3 h-3" /> Stop ({recordingTime}s)
          </>
        ) : (
          <>
            <Mic className="w-3 h-3" /> Speak
          </>
        )}
      </button>
    </div>
  )
}

export default function BeneficiaryRegisterPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialMode = searchParams.get('mode') === 'gnani' ? 'gnani' : 'existing'
  const [registrationMode, setRegistrationMode] = useState<'existing' | 'gnani'>(initialMode)

  function switchMode(mode: 'existing' | 'gnani') {
    setRegistrationMode(mode)
    setSearchParams(mode === 'gnani' ? { mode: 'gnani' } : {})
  }

  const [category, setCategory] = useState<BeneficiaryCategory>('pregnant_woman')
  const [language, setLanguage] = useState<'ta' | 'hi' | 'en'>('ta')

  // Recording state
  const [isRecording, setIsRecording] = useState(false)
  const [recordingTime, setRecordingTime] = useState(0)
  const [processing, setProcessing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Single-field voice recording
  const [recordingField, setRecordingField] = useState<string | null>(null)

  // Transcripts & Extraction
  const [transcript, setTranscript] = useState('')
  const [englishTranscript, setEnglishTranscript] = useState('')
  const [extractedData, setExtractedData] = useState<ExtractedData | null>(null)

  // Validation
  const [missingMandatory, setMissingMandatory] = useState<string[]>([])
  const [validationErrors, setValidationErrors] = useState<string[]>([])
  const [inconsistencies, setInconsistencies] = useState<string[]>([])
  const [duplicateWarning, setDuplicateWarning] = useState<DuplicateWarning | null>(null)

  // Saving
  const [saving, setSaving] = useState(false)
  const [savedRecord, setSavedRecord] = useState<any | null>(null)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const timerRef = useRef<any>(null)

  // Reset form when changing category
  function handleSelectCategory(cat: BeneficiaryCategory) {
    setCategory(cat)
    setTranscript('')
    setEnglishTranscript('')
    setExtractedData(null)
    setMissingMandatory([])
    setValidationErrors([])
    setInconsistencies([])
    setDuplicateWarning(null)
    setSavedRecord(null)
    setError(null)
  }

  // ── Audio Recording ────────────────────────────────────────────────────────
  async function startRecording(forField?: string) {
    setError(null)
    audioChunksRef.current = []
    if (forField) {
      setRecordingField(forField)
    } else {
      setExtractedData(null)
      setSavedRecord(null)
      setDuplicateWarning(null)
      setMissingMandatory([])
      setValidationErrors([])
      setInconsistencies([])
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      mediaRecorderRef.current = recorder

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data)
      }

      recorder.onstop = () => {
        if (forField) {
          handleFieldAudioReady(forField)
        } else {
          handleFullAudioReady()
        }
      }

      recorder.start()
      setIsRecording(true)
      setRecordingTime(0)

      timerRef.current = setInterval(() => {
        setRecordingTime((t) => t + 1)
      }, 1000)
    } catch (err: any) {
      setError('Microphone access denied or not available. Please allow mic permissions.')
    }
  }

  function stopRecording() {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop()
      mediaRecorderRef.current.stream.getTracks().forEach((track) => track.stop())
      setIsRecording(false)
      clearInterval(timerRef.current)
    }
  }

  // ── Full Registration Speech ───────────────────────────────────────────────
  async function handleFullAudioReady() {
    if (audioChunksRef.current.length === 0) return
    setProcessing(true)
    setError(null)

    try {
      const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' })
      const formData = new FormData()
      formData.append('audio', audioBlob, 'category_voice.webm')
      formData.append('language', language)

      // 1. Transcribe
      const transRes = await voiceAPI.transcribe(formData)
      const spokenText = transRes.data?.transcript || ''
      setTranscript(spokenText)

      // 2. Extract structured data
      await processFullTranscript(spokenText)
    } catch (err: any) {
      setError(err?.response?.data?.error || err.message || 'Speech processing failed.')
    } finally {
      setProcessing(false)
    }
  }

  async function processFullTranscript(text: string) {
    if (!text.trim()) return
    setProcessing(true)
    setError(null)

    try {
      const res = await beneficiaryAPI.registerVoice({
        transcript: text,
        beneficiary_type: category,
        language: language,
      })

      const data = res.data
      setEnglishTranscript(data.english_transcript || text)
      setExtractedData(data.extracted || {})
      setMissingMandatory(data.missing_mandatory || [])
      setValidationErrors(data.validation_errors || [])
      setInconsistencies(data.inconsistencies || [])
      setDuplicateWarning(data.duplicate_warning || null)
    } catch (err: any) {
      setError(err?.response?.data?.error || 'Extraction failed. Please try again.')
    } finally {
      setProcessing(false)
    }
  }

  // ── Single-field voice collection ──────────────────────────────────────────
  async function handleFieldAudioReady(fieldName: string) {
    if (audioChunksRef.current.length === 0) return
    setProcessing(true)
    setError(null)

    try {
      const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' })
      const formData = new FormData()
      formData.append('audio', audioBlob, 'field_voice.webm')
      formData.append('language', language)

      // 1. Transcribe audio
      const transRes = await voiceAPI.transcribe(formData)
      const spoken = (transRes.data?.transcript || '').trim()

      if (spoken) {
        // 2. Extract and normalize the specific field value
        try {
          const extRes = await beneficiaryAPI.extractField({
            field: fieldName,
            transcript: spoken,
            category: category,
            language: language,
          })
          const resolvedField = extRes.data?.field || fieldName
          const extractedValue = extRes.data?.value

          if (extractedValue !== null && extractedValue !== undefined && extractedValue !== '') {
            handleFieldChange(resolvedField as keyof ExtractedData, extractedValue)
            if (resolvedField === 'mother_name' || resolvedField === 'mother_beneficiary_id') {
              setMissingMandatory((prev) => prev.filter((f) => f !== 'maternal_reference' && f !== resolvedField))
            }
          } else {
            setError(`Could not extract a valid value for ${fieldName.replace(/_/g, ' ')} from "${spoken}". Please try speaking again or enter it manually.`)
          }
        } catch {
          // If extract endpoint fails, fall back only if not a date field
          if (!['lmp', 'edd', 'dob'].includes(fieldName)) {
            handleFieldChange(fieldName as keyof ExtractedData, spoken)
          } else {
            setError(`Could not determine date for ${fieldName} from "${spoken}". Please enter a valid date.`)
          }
        }
      }
    } catch (err: any) {
      setError(`Failed to capture answer for ${fieldName}.`)
    } finally {
      setProcessing(false)
      setRecordingField(null)
    }
  }

  // ── Manual Field Updates & Dynamic Validation ──────────────────────────────
  function handleFieldChange(field: keyof ExtractedData, value: any) {
    setExtractedData((prev) => {
      const updated = { ...(prev || {}), [field]: value }

      // Clear from missing list if value is present
      if (value !== '' && value !== null && value !== undefined) {
        setMissingMandatory((cur) =>
          cur.filter((f) => {
            if (f === field) return false
            if (f === 'maternal_reference' && (field === 'mother_name' || field === 'mother_beneficiary_id')) return false
            if (f === 'address' && (field === 'household' || field === 'village')) return false
            if (f === 'edd' && field === 'expected_delivery_date') return false
            return true
          })
        )
      }

      // Inconsistency check for LMP vs EDD
      if (field === 'lmp' || field === 'edd' || field === 'expected_delivery_date') {
        const lmpVal = field === 'lmp' ? value : updated.lmp
        const eddVal =
          field === 'edd' || field === 'expected_delivery_date' ? value : updated.edd || updated.expected_delivery_date
        if (lmpVal && eddVal) {
          const d1 = new Date(lmpVal)
          const d2 = new Date(eddVal)
          if (!isNaN(d1.getTime()) && !isNaN(d2.getTime())) {
            if (d2 <= d1) {
              setInconsistencies(['EDD cannot be on or before LMP date.'])
            } else {
              setInconsistencies([])
            }
          }
        }
      }

      return updated
    })
  }

  // ── Final Confirm & Save (Backend Generates ID) ─────────────────────────────
  async function handleConfirmAndSave() {
    if (!extractedData) return
    setSaving(true)
    setError(null)

    try {
      const payload: any = {
        beneficiary_type: category,
        name: extractedData.name || extractedData.baby_name || extractedData.child_name || '',
        phone: extractedData.phone || '',
        address: extractedData.address || extractedData.household || extractedData.village || '',
        village: extractedData.village || '',
        household: extractedData.household || '',
        gender: extractedData.gender || (category === 'pregnant_woman' ? 'female' : ''),
        original_transcript: transcript,
        english_translation: englishTranscript,
        ...extractedData,
      }

      // Ensure maternal reference fields are set
      if (extractedData.mother_name) payload.mother_name = extractedData.mother_name
      if (extractedData.mother_beneficiary_id) payload.mother_beneficiary_id = extractedData.mother_beneficiary_id

      // Provide clinical defaults & sanitize types for pregnant woman
      if (category === 'pregnant_woman') {
        if (!payload.pregnancy_registration_status) {
          payload.pregnancy_registration_status = 'registered'
        }
        if (!payload.previous_complications) {
          payload.previous_complications = 'None reported'
        }
        if (payload.age !== undefined && payload.age !== '') {
          payload.age = Number(payload.age)
        }
        if (payload.gestational_age_weeks !== undefined && payload.gestational_age_weeks !== '') {
          payload.gestational_age_weeks = Number(payload.gestational_age_weeks)
        }
        payload.gravida = payload.gravida !== undefined && payload.gravida !== '' ? Number(payload.gravida) : 0
        payload.previous_live_births =
          payload.previous_live_births !== undefined && payload.previous_live_births !== ''
            ? Number(payload.previous_live_births)
            : 0
        if (payload.edd && !payload.expected_delivery_date) {
          payload.expected_delivery_date = payload.edd
        }
      } else if (category === 'newborn') {
        if (payload.birth_weight_kg !== undefined && payload.birth_weight_kg !== '') {
          payload.birth_weight_kg = Number(payload.birth_weight_kg)
        }
      }

      const res = await beneficiaryAPI.create(payload)
      setSavedRecord(res.data)
      setExtractedData(null)
    } catch (err: any) {
      const respData = err?.response?.data
      const missingList = respData?.missing_mandatory?.length
        ? `Missing fields: ${respData.missing_mandatory.map((f: string) => f.replace(/_/g, ' ')).join(', ')}`
        : ''
      const errorList = respData?.validation_errors?.length ? respData.validation_errors.join('; ') : ''
      const incList = respData?.inconsistencies?.length ? respData.inconsistencies.join('; ') : ''

      const combined =
        [respData?.error, missingList, errorList, incList].filter(Boolean).join(' — ') ||
        'Failed to save beneficiary record.'
      setError(combined)

      if (respData?.missing_mandatory) {
        setMissingMandatory(respData.missing_mandatory)
      }
      if (respData?.validation_errors) {
        setValidationErrors(respData.validation_errors)
      }
      if (respData?.inconsistencies) {
        setInconsistencies(respData.inconsistencies)
      }
    } finally {
      setSaving(false)
    }
  }

  // Step state determination
  const currentStep = savedRecord
    ? 6
    : duplicateWarning
    ? 5
    : extractedData
    ? missingMandatory.length > 0
      ? 3
      : 4
    : isRecording
    ? 2
    : 1

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Registration Mode Selector Bar: Existing Voice AI vs Gnani API Platform */}
      <div className="bg-white p-2 rounded-2xl shadow-sm border border-gray-200 flex flex-col sm:flex-row gap-2">
        <button
          type="button"
          onClick={() => switchMode('existing')}
          className={`flex-1 py-3 px-4 rounded-xl font-bold text-sm flex items-center justify-center gap-2.5 transition-all ${
            registrationMode === 'existing'
              ? 'bg-green-700 text-white shadow-sm ring-2 ring-green-600/20'
              : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
          }`}
        >
          <Mic className="w-4 h-4" />
          <span>Beneficiary Registration – Existing Voice AI</span>
          <span className={`text-[10px] px-2 py-0.5 rounded-full font-mono ${
            registrationMode === 'existing' ? 'bg-green-800 text-green-100' : 'bg-gray-100 text-gray-600'
          }`}>
            Whisper + Groq
          </span>
        </button>

        <button
          type="button"
          onClick={() => switchMode('gnani')}
          className={`flex-1 py-3 px-4 rounded-xl font-bold text-sm flex items-center justify-center gap-2.5 transition-all ${
            registrationMode === 'gnani'
              ? 'bg-gradient-to-r from-indigo-700 to-purple-700 text-white shadow-sm ring-2 ring-indigo-600/20'
              : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
          }`}
        >
          <Sparkles className="w-4 h-4 text-amber-300" />
          <span>Gnani Voice Registration – Prisma + Timbre</span>
          <span className={`text-[10px] px-2 py-0.5 rounded-full font-mono ${
            registrationMode === 'gnani' ? 'bg-indigo-900/60 text-indigo-100' : 'bg-gray-100 text-gray-600'
          }`}>
            Prisma v3.0 + Timbre
          </span>
        </button>
      </div>

      {registrationMode === 'gnani' ? (
        <GnaniBeneficiaryBar />
      ) : (
        <>
          {/* Top Header */}
          <div className="bg-white rounded-2xl p-6 shadow-sm border border-green-100 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-green-700 font-semibold text-sm mb-1">
            <UserPlus className="w-5 h-5" />
            <span>Category-Based Registration</span>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Beneficiary Voice Registration</h1>
          <p className="text-sm text-gray-500">
            Select category, speak naturally, validate mandatory fields, and generate unique Beneficiary ID
          </p>
        </div>

        {/* Voice Language Selector */}
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

      {/* Progress Steps Indicator */}
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 text-center text-xs font-semibold">
        {[
          { num: 1, label: '1. Category' },
          { num: 2, label: '2. Voice' },
          { num: 3, label: '3. Validate' },
          { num: 4, label: '4. Review' },
          { num: 5, label: '5. Duplicates' },
          { num: 6, label: '6. ID & Save' },
        ].map((s) => (
          <div
            key={s.num}
            className={`p-2 rounded-xl border transition-all ${
              currentStep === s.num
                ? 'bg-green-700 text-white border-green-700 shadow-sm'
                : currentStep > s.num
                ? 'bg-green-100 text-green-800 border-green-200'
                : 'bg-white text-gray-400 border-gray-200'
            }`}
          >
            {s.label}
          </div>
        ))}
      </div>

      {/* STEP 1: CATEGORY SELECTION CARDS */}
      <div className="space-y-3">
        <label className="block text-sm font-bold text-gray-800">
          Step 1: Select Beneficiary Category <span className="text-red-500">*</span>
        </label>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {CATEGORIES.map((c) => {
            const Icon = c.icon
            const isSelected = category === c.id
            return (
              <button
                key={c.id}
                type="button"
                onClick={() => handleSelectCategory(c.id)}
                className={`p-4 rounded-2xl border-2 text-left transition-all relative flex flex-col justify-between ${
                  isSelected
                    ? 'border-green-600 bg-green-50/70 shadow-md ring-2 ring-green-600/20'
                    : 'border-gray-200 bg-white hover:border-gray-300'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${c.color}`}>
                      <Icon className="w-5 h-5" />
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-gray-100 text-gray-600 border border-gray-200">
                      {c.badge}
                    </span>
                  </div>
                  <h3 className="font-bold text-gray-900 text-sm leading-tight">{c.title}</h3>
                  <p className="text-xs text-gray-500 mt-1 line-clamp-2">{c.subtitle}</p>
                </div>
                {isSelected && (
                  <div className="mt-3 flex items-center gap-1 text-xs font-semibold text-green-700">
                    <Check className="w-3.5 h-3.5" /> Selected
                  </div>
                )}
              </button>
            )
          })}
        </div>
      </div>

      {/* Error alert */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700 flex items-start gap-2">
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
          <div className="flex-1">{error}</div>
        </div>
      )}

      {/* Inconsistencies alert */}
      {inconsistencies.length > 0 && (
        <div className="p-4 bg-amber-50 border-2 border-amber-300 rounded-xl text-sm text-amber-900 space-y-1">
          <div className="flex items-center gap-2 font-bold">
            <ShieldAlert className="w-5 h-5 text-amber-600" />
            <span>Healthcare Clinical Inconsistency Warning</span>
          </div>
          {inconsistencies.map((inc, i) => (
            <p key={i} className="text-xs text-amber-800">
              • {inc}
            </p>
          ))}
        </div>
      )}

      {/* STEP 6: SUCCESS SCREEN */}
      {savedRecord && (
        <div className="p-6 bg-green-50 border-2 border-green-500 rounded-2xl shadow-sm space-y-4">
          <div className="flex items-center gap-3 text-green-800">
            <CheckCircle2 className="w-8 h-8 text-green-600 shrink-0" />
            <div>
              <h2 className="text-xl font-bold">Beneficiary Successfully Registered!</h2>
              <p className="text-sm text-green-700">
                Unique Beneficiary ID generated and persisted to MongoDB.
              </p>
            </div>
          </div>

          <div className="bg-white p-5 rounded-xl border border-green-200 grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-xs text-gray-500 block">Unique Beneficiary ID</span>
              <span className="font-mono font-bold text-green-800 text-lg block">{savedRecord.beneficiary_id}</span>
            </div>
            <div>
              <span className="text-xs text-gray-500 block">Name</span>
              <span className="font-semibold text-gray-900 block">{savedRecord.name}</span>
            </div>
            <div>
              <span className="text-xs text-gray-500 block">Category</span>
              <span className="capitalize text-gray-800 block font-medium">
                {savedRecord.beneficiary_type?.replace('_', ' ')}
              </span>
            </div>
            <div>
              <span className="text-xs text-gray-500 block">Registration Date</span>
              <span className="text-gray-800 block">{savedRecord.registration_date}</span>
            </div>
          </div>

          <div className="flex items-center gap-3 pt-2">
            <button
              onClick={() => handleSelectCategory(category)}
              className="px-4 py-2.5 bg-green-700 text-white rounded-xl text-sm font-semibold hover:bg-green-800 transition"
            >
              Register Another Beneficiary
            </button>
            <Link
              to="/beneficiaries"
              className="px-4 py-2.5 border border-green-300 text-green-800 rounded-xl text-sm font-semibold hover:bg-green-100 flex items-center gap-1.5 transition"
            >
              <span>View All Beneficiaries</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      )}

      {/* STEP 2: VOICE RECORDING INTERFACE */}
      {!savedRecord && (
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-green-100 space-y-5">
          <div className="text-center space-y-3">
            <span className="text-xs font-semibold text-green-800 bg-green-50 px-3 py-1 rounded-full border border-green-200">
              Selected: {CATEGORIES.find((c) => c.id === category)?.title}
            </span>

            <div className="pt-2">
              <button
                onClick={isRecording ? stopRecording : () => startRecording()}
                disabled={processing}
                className={`w-20 h-20 rounded-full flex items-center justify-center transition-all shadow-lg mx-auto ${
                  isRecording
                    ? 'bg-red-600 text-white animate-pulse scale-105'
                    : 'bg-green-700 text-white hover:bg-green-800'
                }`}
              >
                {isRecording ? <Square className="w-8 h-8" /> : <Mic className="w-8 h-8" />}
              </button>

              <div className="mt-3">
                {isRecording ? (
                  <span className="text-sm font-semibold text-red-600">
                    Recording... {recordingTime}s (Click to stop)
                  </span>
                ) : processing ? (
                  <span className="text-sm font-semibold text-gray-600 flex items-center justify-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin text-green-700" />
                    Transcribing & extracting structured {category.replace('_', ' ')} data...
                  </span>
                ) : (
                  <span className="text-sm font-medium text-gray-600">
                    Click mic and speak details in {language === 'ta' ? 'Tamil' : language === 'hi' ? 'Hindi' : 'English'}
                  </span>
                )}
              </div>
            </div>

            {/* Category-Specific Speech Guide */}
            <div className="text-xs text-gray-500 bg-gray-50 p-3 rounded-xl border border-gray-100 max-w-xl mx-auto text-left">
              <span className="font-semibold text-gray-700 block mb-1">Recommended Speech Pattern:</span>
              {category === 'pregnant_woman' && (
                <p>
                  "Her name is Lakshmi, 25 years old, household H102. Pregnancy registration is completed. LMP was 10
                  August 2026. She is 14 weeks pregnant. Two previous pregnancies and one live birth. No complications."
                </p>
              )}
              {category === 'newborn' && (
                <p>
                  "Register a newborn baby. Baby name is Arjun, born 15 November 2026, male. Mother's name is Lakshmi.
                  Delivered at Government Hospital, Coimbatore. Birth weight is 2.8 kilograms."
                </p>
              )}
              {category === 'immunization_child' && (
                <p>
                  "Child name is Kavin, born 10 January 2026, male. Mother's name is Meena. Immunization card is
                  available. Received BCG and HepB, OPV-1 is pending."
                </p>
              )}
              {category === 'other' && (
                <p>
                  "Register a new beneficiary. Name is Ravi Kumar, phone 9876543210. Category is Elderly Care, address
                  Coimbatore. Emergency contact is 9876501234. Blood group is O positive."
                </p>
              )}
            </div>
          </div>

          {/* Transcript Previews */}
          {(transcript || englishTranscript) && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-gray-100">
              <div className="bg-gray-50 p-4 rounded-xl">
                <span className="text-xs font-semibold text-gray-500 block mb-1">Original Voice Transcript</span>
                <p className="text-sm text-gray-800 italic">"{transcript}"</p>
              </div>
              <div className="bg-green-50/60 p-4 rounded-xl border border-green-100">
                <span className="text-xs font-semibold text-green-800 block mb-1">English Translation</span>
                <p className="text-sm text-gray-800 italic">"{englishTranscript || transcript}"</p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* DUPLICATE WARNING BANNER */}
      {duplicateWarning && !savedRecord && (
        <div className="bg-amber-50 border-2 border-amber-300 rounded-2xl p-5 shadow-sm space-y-2">
          <div className="flex items-center gap-2 text-amber-900 font-bold">
            <ShieldAlert className="w-5 h-5 text-amber-600" />
            <span>Possible Duplicate Beneficiary Detected</span>
          </div>
          <p className="text-sm text-amber-800">{duplicateWarning.message}</p>
          <div className="text-xs text-amber-900 bg-white/80 p-3 rounded-lg border border-amber-200 flex items-center justify-between">
            <div>
              Existing Record: <strong>{duplicateWarning.existing_name}</strong> (ID: {duplicateWarning.existing_id})
              {duplicateWarning.existing_village && ` · Village: ${duplicateWarning.existing_village}`}
            </div>
            <button
              onClick={() => setDuplicateWarning(null)}
              className="px-3 py-1 bg-amber-200 text-amber-900 rounded font-semibold text-xs hover:bg-amber-300 transition"
            >
              Acknowledge & Continue
            </button>
          </div>
        </div>
      )}

      {/* STEP 3 & 4: DYNAMIC CATEGORY-BASED FORM & MISSING INFO COLLECTION */}
      {extractedData && !savedRecord && (
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-green-100 space-y-6">
          <div className="flex items-center justify-between border-b border-gray-100 pb-4 flex-wrap gap-2">
            <div>
              <h2 className="text-lg font-bold text-gray-900">
                Step 4: Review & Complete {CATEGORIES.find((c) => c.id === category)?.title} Details
              </h2>
              <p className="text-xs text-gray-500">
                Mandatory fields must be completed. Unique ID will be generated upon confirmation.
              </p>
            </div>
            <span className="text-xs font-mono px-3 py-1 rounded-full bg-gray-100 text-gray-600 border border-gray-200">
              ID: Generated on Confirmation
            </span>
          </div>

          {/* Missing mandatory fields banner */}
          {missingMandatory.length > 0 && (
            <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl space-y-3">
              <div className="flex items-center gap-2 text-rose-800 font-bold text-xs">
                <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
                <span>Some mandatory details are missing. Click Speak on any field to provide it:</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {missingMandatory.map((field) => {
                  const isCurrent = isRecording && recordingField === field
                  return (
                    <button
                      key={field}
                      type="button"
                      onClick={isCurrent ? stopRecording : () => startRecording(field)}
                      disabled={isRecording && !isCurrent}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition shadow-sm ${
                        isCurrent
                          ? 'bg-red-600 text-white animate-pulse border border-red-600'
                          : isRecording
                          ? 'bg-gray-100 text-gray-400 border border-gray-200 cursor-not-allowed'
                          : 'bg-white border border-rose-300 text-rose-700 hover:bg-rose-100'
                      }`}
                    >
                      {isCurrent ? <Square className="w-3.5 h-3.5" /> : <Mic className="w-3.5 h-3.5 text-rose-600" />}
                      <span>{isCurrent ? `Stop recording (${recordingTime}s)` : `Speak ${field.replace(/_/g, ' ')}`}</span>
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          {/* DYNAMIC FORM PER CATEGORY */}

          {/* ── 1. PREGNANT WOMAN FORM ── */}
          {category === 'pregnant_woman' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <FieldLabel
                  label="Name"
                  field="name"
                  required
                  isRecording={isRecording}
                  recordingField={recordingField}
                  recordingTime={recordingTime}
                  onStart={startRecording}
                  onStop={stopRecording}
                />
                <input
                  type="text"
                  value={extractedData.name || ''}
                  onChange={(e) => handleFieldChange('name', e.target.value)}
                  placeholder="Full name"
                  className={`w-full px-3 py-2 border rounded-xl text-sm ${
                    !extractedData.name ? 'border-rose-300 bg-rose-50/20' : 'border-gray-200 focus:border-green-600'
                  }`}
                />
              </div>

              <div>
                <FieldLabel
                  label="Age"
                  field="age"
                  required
                  isRecording={isRecording}
                  recordingField={recordingField}
                  recordingTime={recordingTime}
                  onStart={startRecording}
                  onStop={stopRecording}
                />
                <input
                  type="number"
                  min="10"
                  max="60"
                  value={extractedData.age || ''}
                  onChange={(e) => handleFieldChange('age', e.target.value)}
                  placeholder="e.g. 25"
                  className={`w-full px-3 py-2 border rounded-xl text-sm ${
                    !extractedData.age ? 'border-rose-300 bg-rose-50/20' : 'border-gray-200 focus:border-green-600'
                  }`}
                />
              </div>

              <div>
                <FieldLabel
                  label="Address / Household ID"
                  field="address"
                  required
                  isRecording={isRecording}
                  recordingField={recordingField}
                  recordingTime={recordingTime}
                  onStart={startRecording}
                  onStop={stopRecording}
                />
                <input
                  type="text"
                  value={extractedData.address || extractedData.household || ''}
                  onChange={(e) => handleFieldChange('address', e.target.value)}
                  placeholder="e.g. H102, Coimbatore"
                  className={`w-full px-3 py-2 border rounded-xl text-sm ${
                    !extractedData.address && !extractedData.household
                      ? 'border-rose-300 bg-rose-50/20'
                      : 'border-gray-200 focus:border-green-600'
                  }`}
                />
              </div>

              <div>
                <FieldLabel
                  label="Pregnancy Registration Status"
                  field="pregnancy_registration_status"
                  required
                  isRecording={isRecording}
                  recordingField={recordingField}
                  recordingTime={recordingTime}
                  onStart={startRecording}
                  onStop={stopRecording}
                />
                <select
                  value={extractedData.pregnancy_registration_status || 'registered'}
                  onChange={(e) => handleFieldChange('pregnancy_registration_status', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:border-green-600"
                >
                  <option value="registered">Registered / Completed</option>
                  <option value="pending">Pending</option>
                </select>
              </div>

              <div>
                <FieldLabel
                  label="Last Menstrual Period (LMP)"
                  field="lmp"
                  required
                  isRecording={isRecording}
                  recordingField={recordingField}
                  recordingTime={recordingTime}
                  onStart={startRecording}
                  onStop={stopRecording}
                />
                <input
                  type="date"
                  value={extractedData.lmp || ''}
                  onChange={(e) => handleFieldChange('lmp', e.target.value)}
                  className={`w-full px-3 py-2 border rounded-xl text-sm ${
                    !extractedData.lmp ? 'border-rose-300 bg-rose-50/20' : 'border-gray-200 focus:border-green-600'
                  }`}
                />
              </div>

              <div>
                <FieldLabel
                  label="Expected Date of Delivery (EDD)"
                  field="edd"
                  required
                  isRecording={isRecording}
                  recordingField={recordingField}
                  recordingTime={recordingTime}
                  onStart={startRecording}
                  onStop={stopRecording}
                />
                <input
                  type="date"
                  value={extractedData.edd || extractedData.expected_delivery_date || ''}
                  onChange={(e) => handleFieldChange('edd', e.target.value)}
                  className={`w-full px-3 py-2 border rounded-xl text-sm ${
                    !extractedData.edd && !extractedData.expected_delivery_date
                      ? 'border-rose-300 bg-rose-50/20'
                      : 'border-gray-200 focus:border-green-600'
                  }`}
                />
              </div>

              <div>
                <FieldLabel
                  label="Gestational Age (weeks)"
                  field="gestational_age_weeks"
                  required
                  isRecording={isRecording}
                  recordingField={recordingField}
                  recordingTime={recordingTime}
                  onStart={startRecording}
                  onStop={stopRecording}
                />
                <input
                  type="number"
                  min="1"
                  max="44"
                  value={extractedData.gestational_age_weeks || ''}
                  onChange={(e) => handleFieldChange('gestational_age_weeks', e.target.value)}
                  placeholder="e.g. 14"
                  className={`w-full px-3 py-2 border rounded-xl text-sm ${
                    !extractedData.gestational_age_weeks
                      ? 'border-rose-300 bg-rose-50/20'
                      : 'border-gray-200 focus:border-green-600'
                  }`}
                />
              </div>

              <div>
                <FieldLabel
                  label="Previous Pregnancies (Gravida)"
                  field="gravida"
                  required
                  isRecording={isRecording}
                  recordingField={recordingField}
                  recordingTime={recordingTime}
                  onStart={startRecording}
                  onStop={stopRecording}
                />
                <input
                  type="number"
                  min="0"
                  value={extractedData.gravida ?? ''}
                  onChange={(e) => handleFieldChange('gravida', e.target.value)}
                  placeholder="0 for first pregnancy"
                  className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:border-green-600"
                />
              </div>

              <div>
                <FieldLabel
                  label="Previous Live Births"
                  field="previous_live_births"
                  required
                  isRecording={isRecording}
                  recordingField={recordingField}
                  recordingTime={recordingTime}
                  onStart={startRecording}
                  onStop={stopRecording}
                />
                <input
                  type="number"
                  min="0"
                  value={extractedData.previous_live_births ?? ''}
                  onChange={(e) => handleFieldChange('previous_live_births', e.target.value)}
                  placeholder="0 for first pregnancy"
                  className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:border-green-600"
                />
              </div>

              <div>
                <FieldLabel
                  label="Previous Pregnancy Complications"
                  field="previous_complications"
                  required
                  isRecording={isRecording}
                  recordingField={recordingField}
                  recordingTime={recordingTime}
                  onStart={startRecording}
                  onStop={stopRecording}
                />
                <input
                  type="text"
                  value={extractedData.previous_complications || ''}
                  onChange={(e) => handleFieldChange('previous_complications', e.target.value)}
                  placeholder="e.g. None reported OR specify complications"
                  className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:border-green-600"
                />
              </div>
            </div>
          )}

          {/* ── 2. NEWBORN FORM ── */}
          {category === 'newborn' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <FieldLabel
                  label="Baby's Name"
                  field="name"
                  required
                  isRecording={isRecording}
                  recordingField={recordingField}
                  recordingTime={recordingTime}
                  onStart={startRecording}
                  onStop={stopRecording}
                />
                <input
                  type="text"
                  value={extractedData.name || extractedData.baby_name || ''}
                  onChange={(e) => handleFieldChange('name', e.target.value)}
                  placeholder="Baby's name"
                  className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:border-green-600"
                />
              </div>

              <div>
                <FieldLabel
                  label="Date of Birth"
                  field="dob"
                  required
                  isRecording={isRecording}
                  recordingField={recordingField}
                  recordingTime={recordingTime}
                  onStart={startRecording}
                  onStop={stopRecording}
                />
                <input
                  type="date"
                  value={extractedData.dob || ''}
                  onChange={(e) => handleFieldChange('dob', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:border-green-600"
                />
              </div>

              <div>
                <FieldLabel
                  label="Gender"
                  field="gender"
                  required
                  isRecording={isRecording}
                  recordingField={recordingField}
                  recordingTime={recordingTime}
                  onStart={startRecording}
                  onStop={stopRecording}
                />
                <select
                  value={extractedData.gender || ''}
                  onChange={(e) => handleFieldChange('gender', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:border-green-600"
                >
                  <option value="">Select gender</option>
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                  <option value="other">Other</option>
                </select>
              </div>

              <div>
                <FieldLabel
                  label="Birth Weight (kg)"
                  field="birth_weight_kg"
                  required
                  isRecording={isRecording}
                  recordingField={recordingField}
                  recordingTime={recordingTime}
                  onStart={startRecording}
                  onStop={stopRecording}
                />
                <input
                  type="number"
                  step="0.01"
                  min="0.5"
                  max="10"
                  value={extractedData.birth_weight_kg || ''}
                  onChange={(e) => handleFieldChange('birth_weight_kg', e.target.value)}
                  placeholder="e.g. 2.8"
                  className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:border-green-600"
                />
              </div>

              <div>
                <FieldLabel
                  label="Mother's Name"
                  field="mother_name"
                  required
                  isRecording={isRecording}
                  recordingField={recordingField}
                  recordingTime={recordingTime}
                  onStart={startRecording}
                  onStop={stopRecording}
                />
                <input
                  type="text"
                  value={extractedData.mother_name || ''}
                  onChange={(e) => handleFieldChange('mother_name', e.target.value)}
                  placeholder="Mother's name"
                  className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:border-green-600"
                />
              </div>

              <div>
                <FieldLabel
                  label="Mother's Beneficiary ID"
                  field="mother_beneficiary_id"
                  isRecording={isRecording}
                  recordingField={recordingField}
                  recordingTime={recordingTime}
                  onStart={startRecording}
                  onStop={stopRecording}
                />
                <input
                  type="text"
                  value={extractedData.mother_beneficiary_id || ''}
                  onChange={(e) => handleFieldChange('mother_beneficiary_id', e.target.value.toUpperCase())}
                  placeholder="e.g. PREG-000001 or BEN001"
                  className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm uppercase focus:border-green-600"
                />
              </div>

              <div className="md:col-span-2">
                <FieldLabel
                  label="Place of Delivery"
                  field="place_of_delivery"
                  required
                  isRecording={isRecording}
                  recordingField={recordingField}
                  recordingTime={recordingTime}
                  onStart={startRecording}
                  onStop={stopRecording}
                />
                <input
                  type="text"
                  value={extractedData.place_of_delivery || ''}
                  onChange={(e) => handleFieldChange('place_of_delivery', e.target.value)}
                  placeholder="e.g. Government Hospital, Coimbatore"
                  className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:border-green-600"
                />
              </div>
            </div>
          )}

          {/* ── 3. IMMUNIZATION / CHILD FORM ── */}
          {category === 'immunization_child' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <FieldLabel
                  label="Child's Name"
                  field="name"
                  required
                  isRecording={isRecording}
                  recordingField={recordingField}
                  recordingTime={recordingTime}
                  onStart={startRecording}
                  onStop={stopRecording}
                />
                <input
                  type="text"
                  value={extractedData.name || extractedData.child_name || ''}
                  onChange={(e) => handleFieldChange('name', e.target.value)}
                  placeholder="Child's full name"
                  className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:border-green-600"
                />
              </div>

              <div>
                <FieldLabel
                  label="Date of Birth"
                  field="dob"
                  required
                  isRecording={isRecording}
                  recordingField={recordingField}
                  recordingTime={recordingTime}
                  onStart={startRecording}
                  onStop={stopRecording}
                />
                <input
                  type="date"
                  value={extractedData.dob || ''}
                  onChange={(e) => handleFieldChange('dob', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:border-green-600"
                />
              </div>

              <div>
                <FieldLabel
                  label="Gender"
                  field="gender"
                  required
                  isRecording={isRecording}
                  recordingField={recordingField}
                  recordingTime={recordingTime}
                  onStart={startRecording}
                  onStop={stopRecording}
                />
                <select
                  value={extractedData.gender || ''}
                  onChange={(e) => handleFieldChange('gender', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:border-green-600"
                >
                  <option value="">Select gender</option>
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                  <option value="other">Other</option>
                </select>
              </div>

              <div>
                <FieldLabel
                  label="Mother's Name"
                  field="mother_name"
                  required
                  isRecording={isRecording}
                  recordingField={recordingField}
                  recordingTime={recordingTime}
                  onStart={startRecording}
                  onStop={stopRecording}
                />
                <input
                  type="text"
                  value={extractedData.mother_name || ''}
                  onChange={(e) => handleFieldChange('mother_name', e.target.value)}
                  placeholder="Mother's name"
                  className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:border-green-600"
                />
              </div>

              <div>
                <FieldLabel
                  label="Immunization Card Status"
                  field="immunization_card_status"
                  required
                  isRecording={isRecording}
                  recordingField={recordingField}
                  recordingTime={recordingTime}
                  onStart={startRecording}
                  onStop={stopRecording}
                />
                <select
                  value={extractedData.immunization_card_status || 'yes'}
                  onChange={(e) => handleFieldChange('immunization_card_status', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:border-green-600"
                >
                  <option value="yes">Yes (Available)</option>
                  <option value="no">No (Not available)</option>
                  <option value="unknown">Unknown</option>
                </select>
              </div>

              <div>
                <FieldLabel
                  label="Vaccination Status"
                  field="vaccination_status"
                  required
                  isRecording={isRecording}
                  recordingField={recordingField}
                  recordingTime={recordingTime}
                  onStart={startRecording}
                  onStop={stopRecording}
                />
                <input
                  type="text"
                  value={extractedData.vaccination_status || ''}
                  onChange={(e) => handleFieldChange('vaccination_status', e.target.value)}
                  placeholder="e.g. Received BCG, HepB; OPV-1 pending"
                  className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:border-green-600"
                />
              </div>
            </div>
          )}

          {/* ── 4. OTHER BENEFICIARY FORM ── */}
          {category === 'other' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <FieldLabel
                  label="Full Name"
                  field="name"
                  required
                  isRecording={isRecording}
                  recordingField={recordingField}
                  recordingTime={recordingTime}
                  onStart={startRecording}
                  onStop={stopRecording}
                />
                <input
                  type="text"
                  value={extractedData.name || ''}
                  onChange={(e) => handleFieldChange('name', e.target.value)}
                  placeholder="Full name"
                  className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:border-green-600"
                />
              </div>

              <div>
                <FieldLabel
                  label="Phone Number"
                  field="phone"
                  required
                  isRecording={isRecording}
                  recordingField={recordingField}
                  recordingTime={recordingTime}
                  onStart={startRecording}
                  onStop={stopRecording}
                />
                <input
                  type="tel"
                  maxLength={10}
                  value={extractedData.phone || ''}
                  onChange={(e) => handleFieldChange('phone', e.target.value)}
                  placeholder="10-digit mobile number"
                  className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:border-green-600"
                />
              </div>

              <div>
                <FieldLabel
                  label="Beneficiary Category"
                  field="beneficiary_category"
                  required
                  isRecording={isRecording}
                  recordingField={recordingField}
                  recordingTime={recordingTime}
                  onStart={startRecording}
                  onStop={stopRecording}
                />
                <select
                  value={extractedData.beneficiary_category || ''}
                  onChange={(e) => handleFieldChange('beneficiary_category', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:border-green-600"
                >
                  <option value="">Select specific category</option>
                  {OTHER_CATEGORIES.map((cat) => (
                    <option key={cat} value={cat}>
                      {cat}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <FieldLabel
                  label="Blood Group"
                  field="blood_group"
                  required
                  isRecording={isRecording}
                  recordingField={recordingField}
                  recordingTime={recordingTime}
                  onStart={startRecording}
                  onStop={stopRecording}
                />
                <select
                  value={extractedData.blood_group || ''}
                  onChange={(e) => handleFieldChange('blood_group', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:border-green-600"
                >
                  <option value="">Select blood group</option>
                  {BLOOD_GROUPS.map((bg) => (
                    <option key={bg} value={bg}>
                      {bg}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <FieldLabel
                  label="Address"
                  field="address"
                  required
                  isRecording={isRecording}
                  recordingField={recordingField}
                  recordingTime={recordingTime}
                  onStart={startRecording}
                  onStop={stopRecording}
                />
                <input
                  type="text"
                  value={extractedData.address || ''}
                  onChange={(e) => handleFieldChange('address', e.target.value)}
                  placeholder="Address or location"
                  className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:border-green-600"
                />
              </div>

              <div>
                <FieldLabel
                  label="Emergency / Alternate Contact"
                  field="emergency_contact"
                  required
                  isRecording={isRecording}
                  recordingField={recordingField}
                  recordingTime={recordingTime}
                  onStart={startRecording}
                  onStop={stopRecording}
                />
                <input
                  type="text"
                  value={extractedData.emergency_contact || ''}
                  onChange={(e) => handleFieldChange('emergency_contact', e.target.value)}
                  placeholder="Emergency contact name / phone"
                  className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:border-green-600"
                />
              </div>
            </div>
          )}

          {/* Form Actions */}
          <div className="flex items-center justify-between pt-4 border-t border-gray-100 flex-wrap gap-3">
            <button
              type="button"
              onClick={() => handleSelectCategory(category)}
              className="px-4 py-2 border border-gray-200 text-gray-600 rounded-xl text-sm font-semibold hover:bg-gray-50 transition"
            >
              Reset / Change Category
            </button>

            <button
              type="button"
              onClick={handleConfirmAndSave}
              disabled={saving}
              className="px-6 py-2.5 bg-green-700 text-white rounded-xl text-sm font-semibold hover:bg-green-800 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 shadow-sm transition"
            >
              {saving ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Generating ID & Saving...
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  Confirm & Generate Beneficiary ID
                </>
              )}
            </button>
          </div>
        </div>
      )}
        </>
      )}
    </div>
  )
}
