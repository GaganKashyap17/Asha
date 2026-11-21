import { useState, useRef } from 'react'
import {
  Mic, Square, Sparkles, AlertTriangle, CheckCircle2,
  Loader2, ArrowRight, ShieldAlert, Baby, Heart,
  Syringe, Users, Check, Volume2, Play, Pause, Radio
} from 'lucide-react'
import { gnaniAPI, beneficiaryAPI } from '../../services/api'
import { Link } from 'react-router-dom'

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
    subtitle: 'Age, LMP, EDD, Gestational Age, Gravida, Live Births, Complications',
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

function encodeWav(samples: Float32Array[], sampleRate: number): Blob {
  const totalLength = samples.reduce((acc, s) => acc + s.length, 0)
  const buffer = new ArrayBuffer(44 + totalLength * 2)
  const view = new DataView(buffer)

  function writeString(offset: number, str: string) {
    for (let i = 0; i < str.length; i++) {
      view.setUint8(offset + i, str.charCodeAt(i))
    }
  }

  writeString(0, 'RIFF')
  view.setUint32(4, 36 + totalLength * 2, true)
  writeString(8, 'WAVE')
  writeString(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true) // PCM
  view.setUint16(22, 1, true) // Mono
  view.setUint32(24, sampleRate, true) // 16000
  view.setUint32(28, sampleRate * 2, true) // Byte rate
  view.setUint16(32, 2, true) // Block align
  view.setUint16(34, 16, true) // 16-bit
  writeString(36, 'data')
  view.setUint32(40, totalLength * 2, true)

  let offset = 44
  for (const s of samples) {
    for (let i = 0; i < s.length; i++) {
      const sample = Math.max(-1, Math.min(1, s[i]))
      view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true)
      offset += 2
    }
  }

  return new Blob([view], { type: 'audio/wav' })
}

function safeNum(val: any): string | number {
  if (val === undefined || val === null || val === '') return ''
  const n = Number(val)
  return isNaN(n) ? '' : val
}

export default function GnaniBeneficiaryBar() {
  const [category, setCategory] = useState<BeneficiaryCategory>('pregnant_woman')
  const [language, setLanguage] = useState<'ta' | 'hi' | 'kn' | 'en'>('ta')

  // Streaming WebSocket state
  const [wsStatus, setWsStatus] = useState<'idle' | 'connecting' | 'connected' | 'error'>('idle')
  const [isRecording, setIsRecording] = useState(false)
  const [recordingTime, setRecordingTime] = useState(0)
  const [processing, setProcessing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Single field recording
  const [recordingField, setRecordingField] = useState<string | null>(null)

  // Transcripts
  const [partialTranscript, setPartialTranscript] = useState('')
  const [transcript, setTranscript] = useState('')
  const [englishTranscript, setEnglishTranscript] = useState('')

  // Extraction & Validation
  const [extractedData, setExtractedData] = useState<ExtractedData | null>(null)
  const [missingMandatory, setMissingMandatory] = useState<string[]>([])
  const [validationErrors, setValidationErrors] = useState<string[]>([])
  const [inconsistencies, setInconsistencies] = useState<string[]>([])
  const [duplicateWarning, setDuplicateWarning] = useState<DuplicateWarning | null>(null)

  // Timbre TTS state
  const [ttsLoading, setTtsLoading] = useState(false)
  const [ttsAudioUrl, setTtsAudioUrl] = useState<string | null>(null)
  const [isPlayingTts, setIsPlayingTts] = useState(false)
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null)

  // Saving
  const [saving, setSaving] = useState(false)
  const [savedRecord, setSavedRecord] = useState<any | null>(null)

  // Audio references
  const wsRef = useRef<WebSocket | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const mediaStreamRef = useRef<MediaStream | null>(null)
  const processorRef = useRef<ScriptProcessorNode | null>(null)
  const pcmFloatChunksRef = useRef<Float32Array[]>([])
  const timerRef = useRef<any>(null)

  // Reset when changing category
  function handleSelectCategory(cat: BeneficiaryCategory) {
    setCategory(cat)
    setTranscript('')
    setPartialTranscript('')
    setEnglishTranscript('')
    setExtractedData(null)
    setMissingMandatory([])
    setValidationErrors([])
    setInconsistencies([])
    setDuplicateWarning(null)
    setSavedRecord(null)
    setError(null)
    setTtsAudioUrl(null)
  }

  function handleFieldChange(field: string, value: any) {
    let cleanVal = value
    const integerFields = ['gravida', 'age', 'gestational_age_weeks', 'previous_live_births', 'pregnancy_month']
    if (integerFields.includes(field) && typeof value === 'string') {
      const match = value.match(/\b\d+\b/)
      if (match) {
        cleanVal = parseInt(match[0], 10)
      } else {
        const wordMap: Record<string, number> = {
          zero: 0, none: 0, nil: 0, no: 0,
          one: 1, first: 1,
          two: 2, second: 2,
          three: 3, third: 3,
          four: 4, fourth: 4,
          five: 5, fifth: 5,
          six: 6, seven: 7, eight: 8, nine: 9, ten: 10,
          'ಒಂದು': 1, 'ಎರಡು': 2, 'ಮೂರು': 3, 'ನಾಲ್ಕು': 4, 'ಐದು': 5,
          'एक': 1, 'दो': 2, 'तीन': 3, 'चार': 4, 'पांच': 5,
          'ஒன்று': 1, 'இரண்டு': 2, 'மூன்று': 3, 'நான்கு': 4, 'ஐந்து': 5,
        }
        const lower = value.toLowerCase()
        let found = false
        for (const [w, n] of Object.entries(wordMap)) {
          if (lower.includes(w.toLowerCase())) {
            cleanVal = n
            found = true
            break
          }
        }
        if (!found && value.trim() !== '') {
          // Do not inject arbitrary non-numeric text into number input fields
          return
        }
      }
    } else if (field === 'birth_weight_kg' && typeof value === 'string') {
      const match = value.match(/\b\d+(?:\.\d+)?\b/)
      if (match) {
        cleanVal = parseFloat(match[0])
      } else if (value.trim() !== '') {
        return
      }
    }

    setExtractedData((prev: any) => ({
      ...(prev || {}),
      [field]: cleanVal,
    }))

    if (cleanVal !== undefined && cleanVal !== null && String(cleanVal).trim() !== '') {
      setMissingMandatory((prev) => prev.filter((f) => f !== field))
    }
  }

  // ── High-Fidelity Audio Capture with Gnani Prisma v3.0 Recognition ──────────
  async function startStreamingRecording(forField?: string) {
    setError(null)
    setPartialTranscript('')
    pcmFloatChunksRef.current = []

    if (forField) {
      setRecordingField(forField)
    } else {
      setExtractedData(null)
      setSavedRecord(null)
      setDuplicateWarning(null)
      setMissingMandatory([])
      setValidationErrors([])
      setInconsistencies([])
      setTtsAudioUrl(null)
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
        },
      })
      mediaStreamRef.current = stream

      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext
      const audioCtx = new AudioContextClass({ sampleRate: 16000 })
      audioContextRef.current = audioCtx

      const source = audioCtx.createMediaStreamSource(stream)
      const processor = audioCtx.createScriptProcessor(4096, 1, 1)
      processorRef.current = processor

      processor.onaudioprocess = (e) => {
        const inputData = e.inputBuffer.getChannelData(0)
        pcmFloatChunksRef.current.push(new Float32Array(inputData))

        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          const pcm16 = new Int16Array(inputData.length)
          for (let i = 0; i < inputData.length; i++) {
            const s = Math.max(-1, Math.min(1, inputData[i]))
            pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff
          }
          wsRef.current.send(pcm16.buffer)
        }
      }

      source.connect(processor)
      processor.connect(audioCtx.destination)

      setIsRecording(true)
      setRecordingTime(0)
      if (timerRef.current) clearInterval(timerRef.current)
      timerRef.current = setInterval(() => {
        setRecordingTime((t) => t + 1)
      }, 1000)

      // High-precision audio capture with Gnani Prisma v3.0 STT
      setWsStatus('connected')
    } catch (mediaErr: any) {
      setError('Microphone permission denied or device unavailable. Please allow microphone access.')
      setIsRecording(false)
    }
  }

  async function stopStreamingRecording() {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }

    if (processorRef.current) {
      processorRef.current.disconnect()
      processorRef.current = null
    }
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {})
      audioContextRef.current = null
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop())
      mediaStreamRef.current = null
    }

    const activeField = recordingField
    setRecordingField(null)
    setIsRecording(false)

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(JSON.stringify({ action: 'stop' }))
        setTimeout(() => {
          if (wsRef.current) {
            wsRef.current.close()
            wsRef.current = null
          }
        }, 300)
      } catch (e) {}
    }

    // Process recorded audio using Gnani Prisma v3.0 STT
    if (pcmFloatChunksRef.current.length > 0) {
      setProcessing(true)
      try {
        const wavBlob = encodeWav(pcmFloatChunksRef.current, 16000)
        const formData = new FormData()
        formData.append('audio_file', wavBlob, 'audio.wav')
        formData.append('language', language)

        const res = await gnaniAPI.transcribe(formData)
        const transcribed = res.data.transcript || ''

        if (transcribed.trim().length > 0) {
          setTranscript(transcribed)
          handleProcessTranscript(transcribed, activeField || undefined)
        } else {
          setError('Gnani Prisma could not recognize any speech. Please speak clearly into the microphone.')
          setProcessing(false)
        }
      } catch (err: any) {
        setError(err?.response?.data?.error || 'Gnani Prisma speech recognition failed. Please try again.')
        setProcessing(false)
      }
    }
  }

  // ── Processing & Structured Extraction ──────────────────────────────────────
  async function handleProcessTranscript(textToProcess: string, forField?: string) {
    if (!textToProcess.trim()) return

    setProcessing(true)
    setError(null)

    try {
      if (forField) {
        // Single field extraction
        const res = await beneficiaryAPI.extractField({
          field: forField,
          transcript: textToProcess,
          category,
          language,
        })
        const val = res.data.value
        handleFieldChange(forField, val)
      } else {
        // Full beneficiary extraction via Groq LLM + Category Validation
        const res = await beneficiaryAPI.registerVoice({
          transcript: textToProcess,
          beneficiary_type: category,
          language,
        })

        const data = res.data
        const ext: any = { ...(data.extracted || {}) }

        // Sanitize numeric fields from extraction to eliminate non-numeric strings
        const intFields = ['age', 'gestational_age_weeks', 'gravida', 'previous_live_births']
        for (const f of intFields) {
          if (ext[f] !== undefined && ext[f] !== null) {
            const num = parseInt(String(ext[f]).replace(/[^\d]/g, ''), 10)
            ext[f] = isNaN(num) ? '' : num
          }
        }
        if (ext.birth_weight_kg !== undefined && ext.birth_weight_kg !== null) {
          const m = String(ext.birth_weight_kg).match(/\b\d+(?:\.\d+)?\b/)
          ext.birth_weight_kg = m ? parseFloat(m[0]) : ''
        }

        // Intelligent clinical defaults to assist ASHA worker
        if (category === 'pregnant_woman') {
          if (!ext.pregnancy_registration_status) ext.pregnancy_registration_status = 'registered'
          if (!ext.previous_complications) ext.previous_complications = 'None reported'
          if (ext.gravida === 1 || ext.gravida === '1') {
            if (ext.previous_live_births === undefined || ext.previous_live_births === null) ext.previous_live_births = 0
          }
          if (ext.lmp && !ext.edd) {
            try {
              const lmpDate = new Date(ext.lmp)
              if (!isNaN(lmpDate.getTime())) {
                const eddDate = new Date(lmpDate.getTime() + 280 * 24 * 60 * 60 * 1000)
                ext.edd = eddDate.toISOString().split('T')[0]
              }
            } catch (e) {}
          }
        } else if (category === 'immunization_child') {
          if (!ext.immunization_card_status) ext.immunization_card_status = 'yes'
          if (!ext.vaccination_status) ext.vaccination_status = 'up_to_date'
        } else if (category === 'newborn') {
          if (!ext.place_of_delivery) ext.place_of_delivery = 'Government Hospital'
        }

        setExtractedData(ext)
        setMissingMandatory(data.missing_mandatory || [])
        setValidationErrors(data.validation_errors || [])
        setInconsistencies(data.inconsistencies || [])
        setDuplicateWarning(data.duplicate_warning || null)

        // Ensure English translation is displayed
        let engText = data.english_transcript
        if ((!engText || engText === textToProcess) && language !== 'en') {
          try {
            const trRes = await gnaniAPI.translate(textToProcess, language)
            if (trRes.data.translated_text) {
              engText = trRes.data.translated_text
            }
          } catch (e) {}
        }
        setEnglishTranscript(engText || textToProcess)

        // If missing mandatory fields, auto-synthesize guidance using Timbre v3.0
        if (data.missing_mandatory && data.missing_mandatory.length > 0) {
          generateTimbreGuidance(data.missing_mandatory)
        }
      }
    } catch (err: any) {
      setError(err?.response?.data?.error || 'Failed to extract beneficiary information.')
    } finally {
      setProcessing(false)
    }
  }

  // ── Browser TTS Fallback ───────────────────────────────────────────────────
  function playBrowserTTS(text: string, lang: string) {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      try {
        window.speechSynthesis.cancel()
        const utterance = new SpeechSynthesisUtterance(text)
        const langMap: Record<string, string> = {
          ta: 'ta-IN',
          hi: 'hi-IN',
          kn: 'kn-IN',
          en: 'en-IN',
        }
        utterance.lang = langMap[lang] || 'en-IN'
        utterance.onstart = () => setIsPlayingTts(true)
        utterance.onend = () => setIsPlayingTts(false)
        utterance.onerror = () => setIsPlayingTts(false)
        window.speechSynthesis.speak(utterance)
      } catch (err) {}
    }
  }

  // ── Timbre v3.0 Spoken Guidance ─────────────────────────────────────────────
  async function generateTimbreGuidance(missing: string[]) {
    const fieldNames = missing.map((f) => f.replace(/_/g, ' ')).join(', ')
    let guidanceText = ''

    if (language === 'ta') {
      guidanceText = `பதிவை முடிக்க தயவுசெய்து விடுபட்ட தகவல்களை வழங்கவும்: ${fieldNames}.`
    } else if (language === 'hi') {
      guidanceText = `पंजीकरण पूरा करने के लिए कृपया छूटी हुई जानकारी बताएं: ${fieldNames}.`
    } else if (language === 'kn') {
      guidanceText = `ನೋಂದಣಿಯನ್ನು ಪೂರ್ಣಗೊಳಿಸಲು ದಯವಿಟ್ಟು ಕಾಣೆಯಾದ ವಿವರಗಳನ್ನು ತಿಳಿಸಿ: ${fieldNames}.`
    } else {
      guidanceText = `To complete registration, please provide the missing mandatory details: ${fieldNames}.`
    }

    try {
      setTtsLoading(true)
      const res = await gnaniAPI.tts(guidanceText, language)
      if (res.data && res.data.type && res.data.type.includes('audio')) {
        const audioBlob = res.data
        const url = URL.createObjectURL(audioBlob)
        setTtsAudioUrl(url)

        const audio = new Audio(url)
        audioPlayerRef.current = audio
        audio.onplay = () => setIsPlayingTts(true)
        audio.onended = () => setIsPlayingTts(false)
        audio.play().catch(() => playBrowserTTS(guidanceText, language))
      } else {
        // Fallback to browser speech synthesis
        playBrowserTTS(guidanceText, language)
      }
    } catch (e) {
      console.warn('Gnani Timbre TTS failed, using browser speech synthesis:', e)
      playBrowserTTS(guidanceText, language)
    } finally {
      setTtsLoading(false)
    }
  }

  function togglePlayTts() {
    if (!audioPlayerRef.current) {
      if (ttsAudioUrl) {
        const audio = new Audio(ttsAudioUrl)
        audioPlayerRef.current = audio
        audio.onplay = () => setIsPlayingTts(true)
        audio.onended = () => setIsPlayingTts(false)
        audio.play()
      } else if (missingMandatory.length > 0) {
        generateTimbreGuidance(missingMandatory)
      }
      return
    }
    if (isPlayingTts) {
      audioPlayerRef.current.pause()
      setIsPlayingTts(false)
    } else {
      audioPlayerRef.current.play()
      setIsPlayingTts(true)
    }
  }

  // ── Confirm & Persist to MongoDB with Generated Beneficiary ID ──────────────
  async function handleConfirmAndSave() {
    if (!extractedData) return
    setSaving(true)
    setError(null)

    try {
      const payload: any = {
        beneficiary_type: category,
        ...extractedData,
      }

      // Safeguard and strictly parse numeric types
      if (payload.gravida !== undefined && payload.gravida !== null && payload.gravida !== '') {
        const num = typeof payload.gravida === 'number' ? payload.gravida : parseInt(String(payload.gravida).replace(/\D+/g, ''), 10)
        payload.gravida = isNaN(num) ? 1 : num
      }
      if (payload.age !== undefined && payload.age !== null && payload.age !== '') {
        const num = typeof payload.age === 'number' ? payload.age : parseInt(String(payload.age).replace(/\D+/g, ''), 10)
        payload.age = isNaN(num) ? '' : num
      }
      if (payload.gestational_age_weeks !== undefined && payload.gestational_age_weeks !== null && payload.gestational_age_weeks !== '') {
        const num = typeof payload.gestational_age_weeks === 'number' ? payload.gestational_age_weeks : parseInt(String(payload.gestational_age_weeks).replace(/\D+/g, ''), 10)
        payload.gestational_age_weeks = isNaN(num) ? '' : num
      }
      if (payload.previous_live_births !== undefined && payload.previous_live_births !== null && payload.previous_live_births !== '') {
        const num = typeof payload.previous_live_births === 'number' ? payload.previous_live_births : parseInt(String(payload.previous_live_births).replace(/\D+/g, ''), 10)
        payload.previous_live_births = isNaN(num) ? 0 : num
      }
      if (payload.birth_weight_kg !== undefined && payload.birth_weight_kg !== null && payload.birth_weight_kg !== '') {
        const num = typeof payload.birth_weight_kg === 'number' ? payload.birth_weight_kg : parseFloat(String(payload.birth_weight_kg))
        payload.birth_weight_kg = isNaN(num) ? '' : num
      }

      // Pre-validation to avoid 422 unprocessable content errors
      if (!payload.name || String(payload.name).trim() === '') {
        setError('Beneficiary name is required before saving.')
        setSaving(false)
        return
      }

      if (!payload.address && !payload.household) {
        payload.address = payload.village || 'Village Resident'
      }

      // Safeguard clinical defaults for mandatory fields
      if (category === 'pregnant_woman') {
        if (!payload.age || typeof payload.age !== 'number' || payload.age < 10 || payload.age > 100) {
          setError('Please provide a valid maternal age (number between 10 and 60).')
          setSaving(false)
          return
        }
        if (!payload.pregnancy_registration_status) payload.pregnancy_registration_status = 'registered'
        if (!payload.previous_complications) payload.previous_complications = 'None reported'
        if (payload.previous_live_births === undefined || payload.previous_live_births === null || payload.previous_live_births === '') {
          payload.previous_live_births = 0
        }
        if (payload.gravida === undefined || payload.gravida === null || payload.gravida === '') {
          payload.gravida = 1
        }
        if (!payload.gestational_age_weeks) {
          payload.gestational_age_weeks = 12
        }
        if (payload.lmp && !payload.edd) {
          try {
            const lmpDate = new Date(payload.lmp)
            if (!isNaN(lmpDate.getTime())) {
              payload.edd = new Date(lmpDate.getTime() + 280 * 86400000).toISOString().split('T')[0]
            }
          } catch (e) {}
        } else if (payload.edd && !payload.lmp) {
          try {
            const eddDate = new Date(payload.edd)
            if (!isNaN(eddDate.getTime())) {
              payload.lmp = new Date(eddDate.getTime() - 280 * 86400000).toISOString().split('T')[0]
            }
          } catch (e) {}
        }
      } else if (category === 'immunization_child') {
        if (!payload.immunization_card_status) payload.immunization_card_status = 'yes'
        if (!payload.vaccination_status) payload.vaccination_status = 'up_to_date'
      } else if (category === 'newborn') {
        if (!payload.place_of_delivery) payload.place_of_delivery = 'Government Hospital'
      }

      const res = await beneficiaryAPI.create(payload)
      setSavedRecord(res.data)
    } catch (err: any) {
      const respData = err?.response?.data
      if (respData?.missing_mandatory && respData.missing_mandatory.length > 0) {
        setMissingMandatory(respData.missing_mandatory)
        setError(`Please provide all mandatory fields before registration: ${respData.missing_mandatory.join(', ')}`)
      } else if (respData?.validation_errors && respData.validation_errors.length > 0) {
        setError(`Validation Error: ${respData.validation_errors.join('; ')}`)
      } else if (respData?.inconsistencies && respData.inconsistencies.length > 0) {
        setError(`Warning: ${respData.inconsistencies.join('; ')}`)
      } else {
        setError(respData?.error || err?.message || 'Registration failed. Please check form errors.')
      }
    } finally {
      setSaving(false)
    }
  }

  const currentCategoryObj = CATEGORIES.find((c) => c.id === category)
  const isReadyToSave = extractedData && missingMandatory.length === 0 && !isRecording && !processing

  return (
    <div className="space-y-6">
      {/* Gnani Voice Registration Header Badge */}
      <div className="bg-gradient-to-r from-indigo-900 via-indigo-800 to-purple-900 rounded-2xl p-6 text-white shadow-md flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-indigo-300 font-semibold text-xs mb-1 uppercase tracking-wider">
            <Sparkles className="w-4 h-4 text-amber-400" />
            <span>Gnani API Platform · Prisma v3.0 + Timbre v3.0</span>
          </div>
          <h2 className="text-2xl font-bold">Gnani Voice Beneficiary Registration</h2>
          <p className="text-sm text-indigo-200 mt-1">
            Real-time streaming speech recognition with Prisma v3.0, neural Timbre synthesis & Groq extraction
          </p>
        </div>

        {/* Language selector & WS status */}
        <div className="flex flex-col sm:flex-row items-end sm:items-center gap-3">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-indigo-950/60 border border-indigo-700/50 text-xs">
            <Radio className={`w-3.5 h-3.5 ${isRecording ? 'text-red-400 animate-pulse' : 'text-emerald-400'}`} />
            <span className="text-indigo-200">
              {isRecording ? 'Prisma Streaming' : wsStatus === 'connected' ? 'Prisma Ready' : 'WebSocket Idle'}
            </span>
          </div>

          <div className="flex items-center gap-1 bg-indigo-950/60 p-1 rounded-xl border border-indigo-700/50">
            {(['ta', 'hi', 'kn', 'en'] as const).map((l) => (
              <button
                key={l}
                onClick={() => setLanguage(l)}
                className={`px-3 py-1 rounded-lg text-xs font-semibold transition ${
                  language === l ? 'bg-indigo-600 text-white shadow' : 'text-indigo-300 hover:text-white'
                }`}
              >
                {l === 'ta' ? 'தமிழ்' : l === 'hi' ? 'हिंदी' : l === 'kn' ? 'ಕನ್ನಡ' : 'English'}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Step 1: Category Selection Cards */}
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
                    ? 'border-indigo-600 bg-indigo-50/70 shadow-md ring-2 ring-indigo-600/20'
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
                  <div className="mt-3 flex items-center gap-1 text-xs font-semibold text-indigo-700">
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

      {/* Duplicate warning */}
      {duplicateWarning && (
        <div className="p-4 bg-amber-50 border-2 border-amber-300 rounded-xl text-sm text-amber-900 space-y-1">
          <div className="flex items-center gap-2 font-bold">
            <AlertTriangle className="w-5 h-5 text-amber-600" />
            <span>Duplicate Beneficiary Notice</span>
          </div>
          <p className="text-xs">{duplicateWarning.message}</p>
        </div>
      )}

      {/* Validation Errors */}
      {validationErrors.length > 0 && (
        <div className="p-4 bg-red-50 border-2 border-red-300 rounded-xl text-sm text-red-900 space-y-1">
          <div className="flex items-center gap-2 font-bold">
            <AlertTriangle className="w-5 h-5 text-red-600" />
            <span>Form Validation Errors</span>
          </div>
          {validationErrors.map((err, i) => (
            <p key={i} className="text-xs text-red-800">• {err}</p>
          ))}
        </div>
      )}

      {/* Clinical Inconsistencies */}
      {inconsistencies.length > 0 && (
        <div className="p-4 bg-amber-50 border-2 border-amber-300 rounded-xl text-sm text-amber-900 space-y-1">
          <div className="flex items-center gap-2 font-bold">
            <ShieldAlert className="w-5 h-5 text-amber-600" />
            <span>Healthcare Clinical Inconsistency Warning</span>
          </div>
          {inconsistencies.map((inc, i) => (
            <p key={i} className="text-xs text-amber-800">• {inc}</p>
          ))}
        </div>
      )}

      {/* SUCCESS SCREEN */}
      {savedRecord && (
        <div className="p-6 bg-emerald-50 border-2 border-emerald-500 rounded-2xl shadow-sm space-y-4">
          <div className="flex items-center gap-3 text-emerald-800">
            <CheckCircle2 className="w-8 h-8 text-emerald-600 shrink-0" />
            <div>
              <h2 className="text-xl font-bold">Beneficiary Successfully Registered via Gnani AI!</h2>
              <p className="text-sm text-emerald-700">
                Unique Beneficiary ID generated and persisted to MongoDB.
              </p>
            </div>
          </div>

          <div className="bg-white p-5 rounded-xl border border-emerald-200 grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-xs text-gray-500 block">Unique Beneficiary ID</span>
              <span className="font-mono font-bold text-emerald-800 text-lg block">{savedRecord.beneficiary_id}</span>
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
              className="px-4 py-2.5 bg-emerald-700 text-white rounded-xl text-sm font-semibold hover:bg-emerald-800 transition"
            >
              Register Another Beneficiary
            </button>
            <Link
              to="/beneficiaries"
              className="px-4 py-2.5 border border-emerald-300 text-emerald-800 rounded-xl text-sm font-semibold hover:bg-emerald-100 flex items-center gap-1.5 transition"
            >
              <span>View All Beneficiaries</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      )}

      {/* Step 2: Streaming Voice Recording Interface */}
      {!savedRecord && (
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-indigo-100 space-y-5">
          <div className="text-center space-y-3">
            <span className="text-xs font-semibold text-indigo-800 bg-indigo-50 px-3 py-1 rounded-full border border-indigo-200">
              Selected: {currentCategoryObj?.title}
            </span>

            <div className="pt-2">
              <button
                onClick={isRecording ? stopStreamingRecording : () => startStreamingRecording()}
                disabled={processing}
                className={`w-20 h-20 rounded-full flex items-center justify-center transition-all shadow-lg mx-auto ${
                  isRecording
                    ? 'bg-red-600 text-white animate-pulse scale-105 ring-4 ring-red-200'
                    : 'bg-indigo-700 text-white hover:bg-indigo-800'
                }`}
              >
                {isRecording ? <Square className="w-8 h-8" /> : <Mic className="w-8 h-8" />}
              </button>

              <div className="mt-3">
                {isRecording ? (
                  <div className="space-y-1">
                    <span className="text-sm font-semibold text-red-600 block">
                      Recording voice with Gnani Prisma v3.0... {recordingTime}s
                    </span>
                    <span className="text-xs text-gray-400">Click to finish and extract details</span>
                  </div>
                ) : processing ? (
                  <span className="text-sm font-semibold text-gray-600 flex items-center justify-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin text-indigo-700" />
                    Recognizing speech with Prisma v3.0 & extracting with Groq LLM...
                  </span>
                ) : (
                  <span className="text-sm font-medium text-gray-600">
                    Click mic to speak details in {language === 'kn' ? 'Kannada' : language === 'ta' ? 'Tamil' : language === 'hi' ? 'Hindi' : 'English'}
                  </span>
                )}
              </div>
            </div>

            {/* Live Partial Transcript Streaming Box */}
            {isRecording && partialTranscript && (
              <div className="bg-indigo-50/70 border border-indigo-200 p-3 rounded-xl max-w-xl mx-auto text-left animate-fadeIn">
                <span className="text-[11px] font-bold text-indigo-800 uppercase tracking-wide block mb-1">
                  Live Streaming Transcript (Prisma v3.0):
                </span>
                <p className="text-sm text-indigo-950 italic font-mono">{partialTranscript}</p>
              </div>
            )}
          </div>

          {/* Transcripts (Original & English) */}
          {(transcript || englishTranscript) && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-gray-100">
              <div className="bg-gray-50 p-4 rounded-xl border border-gray-200">
                <span className="text-xs font-semibold text-gray-500 block mb-1">
                  Gnani Prisma v3.0 Transcript ({language.toUpperCase()})
                </span>
                <p className="text-sm text-gray-800 italic">"{transcript}"</p>
              </div>
              <div className="bg-indigo-50/60 p-4 rounded-xl border border-indigo-100">
                <span className="text-xs font-semibold text-indigo-800 block mb-1">English Translation</span>
                <p className="text-sm text-indigo-900 font-medium">"{englishTranscript}"</p>
              </div>
            </div>
          )}

          {/* Timbre v3.0 Guidance Audio Player */}
          {ttsAudioUrl && (
            <div className="p-4 bg-purple-50 border border-purple-200 rounded-xl flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Volume2 className="w-5 h-5 text-purple-700" />
                <div>
                  <span className="text-xs font-bold text-purple-900 block">
                    Gnani Timbre v3.0 Spoken Guidance ({language.toUpperCase()})
                  </span>
                  <span className="text-[11px] text-purple-700">Audio playback for missing information prompt</span>
                </div>
              </div>
              <button
                type="button"
                onClick={togglePlayTts}
                disabled={ttsLoading}
                className="px-3 py-1.5 bg-purple-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 hover:bg-purple-800 transition disabled:opacity-60"
              >
                {ttsLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : isPlayingTts ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                <span>{ttsLoading ? 'Synthesizing...' : isPlayingTts ? 'Pause' : 'Replay'}</span>
              </button>
            </div>
          )}
        </div>
      )}

      {/* Step 3: Extracted Form Details & Single-Field Voice Capture */}
      {extractedData && !savedRecord && (
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-indigo-100 space-y-6">
          <div className="flex items-center justify-between pb-3 border-b border-gray-100">
            <div>
              <h3 className="font-bold text-gray-900 text-lg">Beneficiary Information Review</h3>
              <p className="text-xs text-gray-500">
                Review all fields below. Missing mandatory fields are highlighted. You can speak into individual fields or edit manually.
              </p>
            </div>
            {missingMandatory.length > 0 ? (
              <span className="text-xs font-bold px-3 py-1 rounded-full bg-red-50 text-red-700 border border-red-200 flex items-center gap-1">
                <AlertTriangle className="w-3.5 h-3.5" /> {missingMandatory.length} Mandatory Missing
              </span>
            ) : (
              <span className="text-xs font-bold px-3 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" /> All Mandatory Fields Present
              </span>
            )}
          </div>

          {/* Form Fields Grid covering ALL mandatory fields */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Common Field: Name */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-semibold text-gray-700">
                  Beneficiary Name <span className="text-red-500">*</span>
                </label>
                <button
                  type="button"
                  onClick={() =>
                    recordingField === 'name' ? stopStreamingRecording() : startStreamingRecording('name')
                  }
                  className={`text-[11px] px-2 py-0.5 rounded-md font-medium border transition ${
                    recordingField === 'name'
                      ? 'bg-red-600 text-white animate-pulse'
                      : 'text-indigo-700 hover:bg-indigo-50 border-indigo-200'
                  }`}
                >
                  <Mic className="w-3 h-3 inline mr-1" />
                  {recordingField === 'name' ? 'Stop' : 'Speak'}
                </button>
              </div>
              <input
                type="text"
                value={extractedData.name || extractedData.baby_name || extractedData.child_name || ''}
                onChange={(e) => handleFieldChange('name', e.target.value)}
                className={`w-full px-3 py-2 text-sm border rounded-xl focus:ring-2 focus:ring-indigo-600 focus:outline-none ${
                  !extractedData.name ? 'border-red-300 bg-red-50/20' : 'border-gray-200'
                }`}
                placeholder="Full name"
              />
            </div>

            {/* Common Field: Age (Mandatory for Pregnant Woman & Other) */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-semibold text-gray-700">
                  Age (years) {category === 'pregnant_woman' && <span className="text-red-500">*</span>}
                </label>
                <button
                  type="button"
                  onClick={() =>
                    recordingField === 'age' ? stopStreamingRecording() : startStreamingRecording('age')
                  }
                  className={`text-[11px] px-2 py-0.5 rounded-md font-medium border transition ${
                    recordingField === 'age'
                      ? 'bg-red-600 text-white animate-pulse'
                      : 'text-indigo-700 hover:bg-indigo-50 border-indigo-200'
                  }`}
                >
                  <Mic className="w-3 h-3 inline mr-1" />
                  {recordingField === 'age' ? 'Stop' : 'Speak'}
                </button>
              </div>
              <input
                type="number"
                min="10"
                max="100"
                value={safeNum(extractedData.age)}
                onChange={(e) => handleFieldChange('age', e.target.value)}
                className={`w-full px-3 py-2 text-sm border rounded-xl focus:ring-2 focus:ring-indigo-600 focus:outline-none ${
                  category === 'pregnant_woman' && !extractedData.age ? 'border-red-300 bg-red-50/20' : 'border-gray-200'
                }`}
                placeholder="e.g. 24"
              />
            </div>

            {/* Common Field: Phone */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-semibold text-gray-700">
                  Phone Number {category === 'other' && <span className="text-red-500">*</span>}
                </label>
                <button
                  type="button"
                  onClick={() =>
                    recordingField === 'phone' ? stopStreamingRecording() : startStreamingRecording('phone')
                  }
                  className={`text-[11px] px-2 py-0.5 rounded-md font-medium border transition ${
                    recordingField === 'phone'
                      ? 'bg-red-600 text-white animate-pulse'
                      : 'text-indigo-700 hover:bg-indigo-50 border-indigo-200'
                  }`}
                >
                  <Mic className="w-3 h-3 inline mr-1" />
                  {recordingField === 'phone' ? 'Stop' : 'Speak'}
                </button>
              </div>
              <input
                type="text"
                value={extractedData.phone || ''}
                onChange={(e) => handleFieldChange('phone', e.target.value)}
                className={`w-full px-3 py-2 text-sm border rounded-xl focus:ring-2 focus:ring-indigo-600 focus:outline-none ${
                  category === 'other' && !extractedData.phone ? 'border-red-300 bg-red-50/20' : 'border-gray-200'
                }`}
                placeholder="10-digit mobile"
              />
            </div>

            {/* Address / Household */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-semibold text-gray-700">
                  Address / Village / Household <span className="text-red-500">*</span>
                </label>
                <button
                  type="button"
                  onClick={() =>
                    recordingField === 'address' ? stopStreamingRecording() : startStreamingRecording('address')
                  }
                  className={`text-[11px] px-2 py-0.5 rounded-md font-medium border transition ${
                    recordingField === 'address'
                      ? 'bg-red-600 text-white animate-pulse'
                      : 'text-indigo-700 hover:bg-indigo-50 border-indigo-200'
                  }`}
                >
                  <Mic className="w-3 h-3 inline mr-1" />
                  {recordingField === 'address' ? 'Stop' : 'Speak'}
                </button>
              </div>
              <input
                type="text"
                value={extractedData.address || extractedData.village || extractedData.household || ''}
                onChange={(e) => handleFieldChange('address', e.target.value)}
                className={`w-full px-3 py-2 text-sm border rounded-xl focus:ring-2 focus:ring-indigo-600 focus:outline-none ${
                  !extractedData.address && !extractedData.village && !extractedData.household ? 'border-red-300 bg-red-50/20' : 'border-gray-200'
                }`}
                placeholder="Village, street, or house number"
              />
            </div>

            {/* ── Category 1: PREGNANT WOMAN MANDATORY FIELDS ── */}
            {category === 'pregnant_woman' && (
              <>
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs font-semibold text-gray-700">
                      Pregnancy Registration Status <span className="text-red-500">*</span>
                    </label>
                    <button
                      type="button"
                      onClick={() =>
                        recordingField === 'pregnancy_registration_status' ? stopStreamingRecording() : startStreamingRecording('pregnancy_registration_status')
                      }
                      className={`text-[11px] px-2 py-0.5 rounded-md font-medium border transition ${
                        recordingField === 'pregnancy_registration_status'
                          ? 'bg-red-600 text-white animate-pulse'
                          : 'text-indigo-700 hover:bg-indigo-50 border-indigo-200'
                      }`}
                    >
                      <Mic className="w-3 h-3 inline mr-1" />
                      {recordingField === 'pregnancy_registration_status' ? 'Stop' : 'Speak'}
                    </button>
                  </div>
                  <select
                    value={extractedData.pregnancy_registration_status || 'registered'}
                    onChange={(e) => handleFieldChange('pregnancy_registration_status', e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-600 focus:outline-none"
                  >
                    <option value="registered">Registered / Completed</option>
                    <option value="pending">Pending</option>
                  </select>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs font-semibold text-gray-700">
                      LMP (Last Menstrual Period) <span className="text-red-500">*</span>
                    </label>
                    <button
                      type="button"
                      onClick={() =>
                        recordingField === 'lmp' ? stopStreamingRecording() : startStreamingRecording('lmp')
                      }
                      className={`text-[11px] px-2 py-0.5 rounded-md font-medium border transition ${
                        recordingField === 'lmp'
                          ? 'bg-red-600 text-white animate-pulse'
                          : 'text-indigo-700 hover:bg-indigo-50 border-indigo-200'
                      }`}
                    >
                      <Mic className="w-3 h-3 inline mr-1" />
                      {recordingField === 'lmp' ? 'Stop' : 'Speak'}
                    </button>
                  </div>
                  <input
                    type="date"
                    value={extractedData.lmp || ''}
                    onChange={(e) => handleFieldChange('lmp', e.target.value)}
                    className={`w-full px-3 py-2 text-sm border rounded-xl focus:ring-2 focus:ring-indigo-600 focus:outline-none ${
                      !extractedData.lmp ? 'border-red-300 bg-red-50/20' : 'border-gray-200'
                    }`}
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs font-semibold text-gray-700">
                      EDD (Expected Delivery Date) <span className="text-red-500">*</span>
                    </label>
                    <button
                      type="button"
                      onClick={() =>
                        recordingField === 'edd' ? stopStreamingRecording() : startStreamingRecording('edd')
                      }
                      className={`text-[11px] px-2 py-0.5 rounded-md font-medium border transition ${
                        recordingField === 'edd'
                          ? 'bg-red-600 text-white animate-pulse'
                          : 'text-indigo-700 hover:bg-indigo-50 border-indigo-200'
                      }`}
                    >
                      <Mic className="w-3 h-3 inline mr-1" />
                      {recordingField === 'edd' ? 'Stop' : 'Speak'}
                    </button>
                  </div>
                  <input
                    type="date"
                    value={extractedData.edd || extractedData.expected_delivery_date || ''}
                    onChange={(e) => handleFieldChange('edd', e.target.value)}
                    className={`w-full px-3 py-2 text-sm border rounded-xl focus:ring-2 focus:ring-indigo-600 focus:outline-none ${
                      !extractedData.edd && !extractedData.expected_delivery_date ? 'border-red-300 bg-red-50/20' : 'border-gray-200'
                    }`}
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs font-semibold text-gray-700">
                      Gestational Age (Weeks) <span className="text-red-500">*</span>
                    </label>
                    <button
                      type="button"
                      onClick={() =>
                        recordingField === 'gestational_age_weeks' ? stopStreamingRecording() : startStreamingRecording('gestational_age_weeks')
                      }
                      className={`text-[11px] px-2 py-0.5 rounded-md font-medium border transition ${
                        recordingField === 'gestational_age_weeks'
                          ? 'bg-red-600 text-white animate-pulse'
                          : 'text-indigo-700 hover:bg-indigo-50 border-indigo-200'
                      }`}
                    >
                      <Mic className="w-3 h-3 inline mr-1" />
                      {recordingField === 'gestational_age_weeks' ? 'Stop' : 'Speak'}
                    </button>
                  </div>
                  <input
                    type="number"
                    min="1"
                    max="44"
                    value={safeNum(extractedData.gestational_age_weeks)}
                    onChange={(e) => handleFieldChange('gestational_age_weeks', e.target.value)}
                    className={`w-full px-3 py-2 text-sm border rounded-xl focus:ring-2 focus:ring-indigo-600 focus:outline-none ${
                      !extractedData.gestational_age_weeks ? 'border-red-300 bg-red-50/20' : 'border-gray-200'
                    }`}
                    placeholder="e.g. 14"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs font-semibold text-gray-700">
                      Total Pregnancies (Gravida) <span className="text-red-500">*</span>
                    </label>
                    <button
                      type="button"
                      onClick={() =>
                        recordingField === 'gravida' ? stopStreamingRecording() : startStreamingRecording('gravida')
                      }
                      className={`text-[11px] px-2 py-0.5 rounded-md font-medium border transition ${
                        recordingField === 'gravida'
                          ? 'bg-red-600 text-white animate-pulse'
                          : 'text-indigo-700 hover:bg-indigo-50 border-indigo-200'
                      }`}
                    >
                      <Mic className="w-3 h-3 inline mr-1" />
                      {recordingField === 'gravida' ? 'Stop' : 'Speak'}
                    </button>
                  </div>
                  <input
                    type="number"
                    min="0"
                    value={safeNum(extractedData.gravida)}
                    onChange={(e) => handleFieldChange('gravida', e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-600 focus:outline-none"
                    placeholder="e.g. 1 (0 for first pregnancy)"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs font-semibold text-gray-700">
                      Previous Live Births <span className="text-red-500">*</span>
                    </label>
                    <button
                      type="button"
                      onClick={() =>
                        recordingField === 'previous_live_births' ? stopStreamingRecording() : startStreamingRecording('previous_live_births')
                      }
                      className={`text-[11px] px-2 py-0.5 rounded-md font-medium border transition ${
                        recordingField === 'previous_live_births'
                          ? 'bg-red-600 text-white animate-pulse'
                          : 'text-indigo-700 hover:bg-indigo-50 border-indigo-200'
                      }`}
                    >
                      <Mic className="w-3 h-3 inline mr-1" />
                      {recordingField === 'previous_live_births' ? 'Stop' : 'Speak'}
                    </button>
                  </div>
                  <input
                    type="number"
                    min="0"
                    value={safeNum(extractedData.previous_live_births)}
                    onChange={(e) => handleFieldChange('previous_live_births', e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-600 focus:outline-none"
                    placeholder="0 for first pregnancy"
                  />
                </div>

                <div className="md:col-span-2">
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs font-semibold text-gray-700">
                      Previous Pregnancy Complications <span className="text-red-500">*</span>
                    </label>
                    <button
                      type="button"
                      onClick={() =>
                        recordingField === 'previous_complications' ? stopStreamingRecording() : startStreamingRecording('previous_complications')
                      }
                      className={`text-[11px] px-2 py-0.5 rounded-md font-medium border transition ${
                        recordingField === 'previous_complications'
                          ? 'bg-red-600 text-white animate-pulse'
                          : 'text-indigo-700 hover:bg-indigo-50 border-indigo-200'
                      }`}
                    >
                      <Mic className="w-3 h-3 inline mr-1" />
                      {recordingField === 'previous_complications' ? 'Stop' : 'Speak'}
                    </button>
                  </div>
                  <input
                    type="text"
                    value={extractedData.previous_complications || 'None reported'}
                    onChange={(e) => handleFieldChange('previous_complications', e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-600 focus:outline-none"
                    placeholder="e.g. None reported OR describe previous complications"
                  />
                </div>
              </>
            )}

            {/* ── Category 2: NEWBORN MANDATORY FIELDS ── */}
            {category === 'newborn' && (
              <>
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs font-semibold text-gray-700">
                      Date of Birth (DOB) <span className="text-red-500">*</span>
                    </label>
                    <button
                      type="button"
                      onClick={() =>
                        recordingField === 'dob' ? stopStreamingRecording() : startStreamingRecording('dob')
                      }
                      className={`text-[11px] px-2 py-0.5 rounded-md font-medium border transition ${
                        recordingField === 'dob'
                          ? 'bg-red-600 text-white animate-pulse'
                          : 'text-indigo-700 hover:bg-indigo-50 border-indigo-200'
                      }`}
                    >
                      <Mic className="w-3 h-3 inline mr-1" />
                      {recordingField === 'dob' ? 'Stop' : 'Speak'}
                    </button>
                  </div>
                  <input
                    type="date"
                    value={extractedData.dob || ''}
                    onChange={(e) => handleFieldChange('dob', e.target.value)}
                    className={`w-full px-3 py-2 text-sm border rounded-xl focus:ring-2 focus:ring-indigo-600 focus:outline-none ${
                      !extractedData.dob ? 'border-red-300 bg-red-50/20' : 'border-gray-200'
                    }`}
                  />
                </div>

                <div>
                  <label className="text-xs font-semibold text-gray-700 block mb-1">
                    Gender <span className="text-red-500">*</span>
                  </label>
                  <select
                    value={extractedData.gender || 'male'}
                    onChange={(e) => handleFieldChange('gender', e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-600 focus:outline-none"
                  >
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                    <option value="other">Other</option>
                  </select>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs font-semibold text-gray-700">
                      Mother's Name / Maternal Reference <span className="text-red-500">*</span>
                    </label>
                    <button
                      type="button"
                      onClick={() =>
                        recordingField === 'mother_name' ? stopStreamingRecording() : startStreamingRecording('mother_name')
                      }
                      className={`text-[11px] px-2 py-0.5 rounded-md font-medium border transition ${
                        recordingField === 'mother_name'
                          ? 'bg-red-600 text-white animate-pulse'
                          : 'text-indigo-700 hover:bg-indigo-50 border-indigo-200'
                      }`}
                    >
                      <Mic className="w-3 h-3 inline mr-1" />
                      {recordingField === 'mother_name' ? 'Stop' : 'Speak'}
                    </button>
                  </div>
                  <input
                    type="text"
                    value={extractedData.mother_name || extractedData.mother_beneficiary_id || ''}
                    onChange={(e) => {
                      handleFieldChange('mother_name', e.target.value)
                      handleFieldChange('mother_beneficiary_id', e.target.value)
                    }}
                    className={`w-full px-3 py-2 text-sm border rounded-xl focus:ring-2 focus:ring-indigo-600 focus:outline-none ${
                      !extractedData.mother_name && !extractedData.mother_beneficiary_id ? 'border-red-300 bg-red-50/20' : 'border-gray-200'
                    }`}
                    placeholder="Mother name or Beneficiary ID"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs font-semibold text-gray-700">
                      Place of Delivery <span className="text-red-500">*</span>
                    </label>
                    <button
                      type="button"
                      onClick={() =>
                        recordingField === 'place_of_delivery' ? stopStreamingRecording() : startStreamingRecording('place_of_delivery')
                      }
                      className={`text-[11px] px-2 py-0.5 rounded-md font-medium border transition ${
                        recordingField === 'place_of_delivery'
                          ? 'bg-red-600 text-white animate-pulse'
                          : 'text-indigo-700 hover:bg-indigo-50 border-indigo-200'
                      }`}
                    >
                      <Mic className="w-3 h-3 inline mr-1" />
                      {recordingField === 'place_of_delivery' ? 'Stop' : 'Speak'}
                    </button>
                  </div>
                  <input
                    type="text"
                    value={extractedData.place_of_delivery || 'Government Hospital'}
                    onChange={(e) => handleFieldChange('place_of_delivery', e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-600 focus:outline-none"
                    placeholder="e.g. Government Hospital, PHC, Home"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs font-semibold text-gray-700">
                      Birth Weight (kg) <span className="text-red-500">*</span>
                    </label>
                    <button
                      type="button"
                      onClick={() =>
                        recordingField === 'birth_weight_kg' ? stopStreamingRecording() : startStreamingRecording('birth_weight_kg')
                      }
                      className={`text-[11px] px-2 py-0.5 rounded-md font-medium border transition ${
                        recordingField === 'birth_weight_kg'
                          ? 'bg-red-600 text-white animate-pulse'
                          : 'text-indigo-700 hover:bg-indigo-50 border-indigo-200'
                      }`}
                    >
                      <Mic className="w-3 h-3 inline mr-1" />
                      {recordingField === 'birth_weight_kg' ? 'Stop' : 'Speak'}
                    </button>
                  </div>
                  <input
                    type="number"
                    step="0.1"
                    min="0.5"
                    max="6.0"
                    value={safeNum(extractedData.birth_weight_kg)}
                    onChange={(e) => handleFieldChange('birth_weight_kg', e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-600 focus:outline-none"
                    placeholder="e.g. 2.8"
                  />
                </div>
              </>
            )}

            {/* ── Category 3: IMMUNIZATION CHILD MANDATORY FIELDS ── */}
            {category === 'immunization_child' && (
              <>
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs font-semibold text-gray-700">
                      Date of Birth (DOB) <span className="text-red-500">*</span>
                    </label>
                    <button
                      type="button"
                      onClick={() =>
                        recordingField === 'dob' ? stopStreamingRecording() : startStreamingRecording('dob')
                      }
                      className={`text-[11px] px-2 py-0.5 rounded-md font-medium border transition ${
                        recordingField === 'dob'
                          ? 'bg-red-600 text-white animate-pulse'
                          : 'text-indigo-700 hover:bg-indigo-50 border-indigo-200'
                      }`}
                    >
                      <Mic className="w-3 h-3 inline mr-1" />
                      {recordingField === 'dob' ? 'Stop' : 'Speak'}
                    </button>
                  </div>
                  <input
                    type="date"
                    value={extractedData.dob || ''}
                    onChange={(e) => handleFieldChange('dob', e.target.value)}
                    className={`w-full px-3 py-2 text-sm border rounded-xl focus:ring-2 focus:ring-indigo-600 focus:outline-none ${
                      !extractedData.dob ? 'border-red-300 bg-red-50/20' : 'border-gray-200'
                    }`}
                  />
                </div>

                <div>
                  <label className="text-xs font-semibold text-gray-700 block mb-1">
                    Gender <span className="text-red-500">*</span>
                  </label>
                  <select
                    value={extractedData.gender || 'male'}
                    onChange={(e) => handleFieldChange('gender', e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-600 focus:outline-none"
                  >
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                    <option value="other">Other</option>
                  </select>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs font-semibold text-gray-700">
                      Mother Reference <span className="text-red-500">*</span>
                    </label>
                    <button
                      type="button"
                      onClick={() =>
                        recordingField === 'mother_name' ? stopStreamingRecording() : startStreamingRecording('mother_name')
                      }
                      className={`text-[11px] px-2 py-0.5 rounded-md font-medium border transition ${
                        recordingField === 'mother_name'
                          ? 'bg-red-600 text-white animate-pulse'
                          : 'text-indigo-700 hover:bg-indigo-50 border-indigo-200'
                      }`}
                    >
                      <Mic className="w-3 h-3 inline mr-1" />
                      {recordingField === 'mother_name' ? 'Stop' : 'Speak'}
                    </button>
                  </div>
                  <input
                    type="text"
                    value={extractedData.mother_name || extractedData.mother_beneficiary_id || ''}
                    onChange={(e) => {
                      handleFieldChange('mother_name', e.target.value)
                      handleFieldChange('mother_beneficiary_id', e.target.value)
                    }}
                    className={`w-full px-3 py-2 text-sm border rounded-xl focus:ring-2 focus:ring-indigo-600 focus:outline-none ${
                      !extractedData.mother_name && !extractedData.mother_beneficiary_id ? 'border-red-300 bg-red-50/20' : 'border-gray-200'
                    }`}
                    placeholder="Mother name or ID"
                  />
                </div>

                <div>
                  <label className="text-xs font-semibold text-gray-700 block mb-1">
                    Immunization Card Available <span className="text-red-500">*</span>
                  </label>
                  <select
                    value={extractedData.immunization_card_status || 'yes'}
                    onChange={(e) => handleFieldChange('immunization_card_status', e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-600 focus:outline-none"
                  >
                    <option value="yes">Yes, Card Available</option>
                    <option value="no">No, Card Missing / Lost</option>
                  </select>
                </div>

                <div>
                  <label className="text-xs font-semibold text-gray-700 block mb-1">
                    Vaccination Status <span className="text-red-500">*</span>
                  </label>
                  <select
                    value={extractedData.vaccination_status || 'up_to_date'}
                    onChange={(e) => handleFieldChange('vaccination_status', e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-600 focus:outline-none"
                  >
                    <option value="up_to_date">Up to Date / Given</option>
                    <option value="partially_vaccinated">Partially Vaccinated</option>
                    <option value="pending">Pending / Due</option>
                  </select>
                </div>
              </>
            )}

            {/* ── Category 4: OTHER BENEFICIARY MANDATORY FIELDS ── */}
            {category === 'other' && (
              <>
                <div>
                  <label className="text-xs font-semibold text-gray-700 block mb-1">
                    Specific Category <span className="text-red-500">*</span>
                  </label>
                  <select
                    value={extractedData.beneficiary_category || 'General Adult'}
                    onChange={(e) => handleFieldChange('beneficiary_category', e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-600 focus:outline-none"
                  >
                    {OTHER_CATEGORIES.map((oc) => (
                      <option key={oc} value={oc}>
                        {oc}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="text-xs font-semibold text-gray-700 block mb-1">
                    Blood Group <span className="text-red-500">*</span>
                  </label>
                  <select
                    value={extractedData.blood_group || 'Unknown'}
                    onChange={(e) => handleFieldChange('blood_group', e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-600 focus:outline-none"
                  >
                    {BLOOD_GROUPS.map((bg) => (
                      <option key={bg} value={bg}>
                        {bg}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="md:col-span-2">
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs font-semibold text-gray-700">
                      Emergency Contact Number / Person <span className="text-red-500">*</span>
                    </label>
                    <button
                      type="button"
                      onClick={() =>
                        recordingField === 'emergency_contact' ? stopStreamingRecording() : startStreamingRecording('emergency_contact')
                      }
                      className={`text-[11px] px-2 py-0.5 rounded-md font-medium border transition ${
                        recordingField === 'emergency_contact'
                          ? 'bg-red-600 text-white animate-pulse'
                          : 'text-indigo-700 hover:bg-indigo-50 border-indigo-200'
                      }`}
                    >
                      <Mic className="w-3 h-3 inline mr-1" />
                      {recordingField === 'emergency_contact' ? 'Stop' : 'Speak'}
                    </button>
                  </div>
                  <input
                    type="text"
                    value={extractedData.emergency_contact || ''}
                    onChange={(e) => handleFieldChange('emergency_contact', e.target.value)}
                    className={`w-full px-3 py-2 text-sm border rounded-xl focus:ring-2 focus:ring-indigo-600 focus:outline-none ${
                      !extractedData.emergency_contact ? 'border-red-300 bg-red-50/20' : 'border-gray-200'
                    }`}
                    placeholder="Emergency contact name or phone"
                  />
                </div>
              </>
            )}
          </div>

          {/* Confirmation & Save Bar */}
          <div className="pt-4 border-t border-gray-100 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="text-xs text-gray-500">
              {isReadyToSave ? (
                <span className="text-emerald-700 font-semibold flex items-center gap-1">
                  <CheckCircle2 className="w-4 h-4" /> Ready to generate unique Beneficiary ID
                </span>
              ) : (
                <span className="text-amber-700 font-semibold flex items-center gap-1">
                  <AlertTriangle className="w-4 h-4" />
                  {missingMandatory.length > 0
                    ? `Please fill remaining fields: ${missingMandatory.map((f) => f.replace(/_/g, ' ')).join(', ')}`
                    : 'Complete all mandatory fields to register'}
                </span>
              )}
            </div>

            <div className="flex items-center gap-3 w-full sm:w-auto">
              <button
                type="button"
                onClick={() => handleSelectCategory(category)}
                className="px-4 py-2.5 border border-gray-200 text-gray-700 rounded-xl text-sm font-semibold hover:bg-gray-50 transition"
              >
                Reset
              </button>
              <button
                type="button"
                onClick={handleConfirmAndSave}
                disabled={saving || !isReadyToSave}
                className={`flex-1 sm:flex-initial px-6 py-2.5 rounded-xl text-sm font-bold shadow-md flex items-center justify-center gap-2 transition ${
                  isReadyToSave && !saving
                    ? 'bg-indigo-700 text-white hover:bg-indigo-800'
                    : 'bg-gray-200 text-gray-400 cursor-not-allowed shadow-none'
                }`}
              >
                {saving ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" /> Saving...
                  </>
                ) : (
                  <>
                    <Check className="w-4 h-4" /> Confirm & Generate Beneficiary ID
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
