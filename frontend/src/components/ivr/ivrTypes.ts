// IVR Subsystem — TypeScript Interfaces

export type CallStatus =
  | 'idle'
  | 'initiating'
  | 'calling'
  | 'ringing'
  | 'answered'
  | 'playing'
  | 'completed'
  | 'busy'
  | 'no_answer'
  | 'failed'

export type Language = 'en' | 'hi' | 'ta' | 'kn'

export interface IVRBeneficiary {
  _id?: string
  beneficiary_id?: string
  beneficiary_name: string
  mobile_number: string
  visit_date: string
  visit_type: string
  priority?: string
  notes?: string
  village?: string
  household?: string
}

export interface IVRCallRecord {
  call_id: string
  beneficiary_id?: string
  beneficiary_name: string
  mobile_number: string
  visit_date: string
  visit_type: string
  language: Language
  reminder_message: string
  status: CallStatus
  outcome: string
  initiated_at: string
  completed_at?: string
  duration_seconds?: number
  followup_id?: string
  is_demo?: boolean
}
