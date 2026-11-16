# 🏥 ASHA Voice

**Speak Naturally. Record Instantly. Protect Every Life.**

An AI-powered multilingual voice assistant that enables ASHA (Accredited Social Health Activists) workers to record household healthcare visits by speaking naturally in Tamil or Tamil-English code-mixed speech — without typing.

---

## Table of Contents

- [Problem Statement](#problem-statement)
- [Solution](#solution)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Key Features](#key-features)
- [Quick Start](#quick-start)
- [Environment Configuration](#environment-configuration)
- [API Reference](#api-reference)
- [AI Pipeline](#ai-pipeline)
- [Danger Sign Detection](#danger-sign-detection)
- [Demo Accounts & Data](#demo-accounts--data)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Disclaimer](#disclaimer)

---

## Problem Statement

ASHA workers visit pregnant women, newborns, and households for immunisation and healthcare follow-ups across rural India. They currently maintain paper registers or manually enter data into mobile apps. Typing is slow and error-prone, especially while travelling between households.

## Solution

ASHA Voice provides a complete voice-driven healthcare field register:

1. **Speak** naturally in Tamil or Tamil-English code-mix
2. **Transcribe** via Groq Whisper (`whisper-large-v3-turbo`)
3. **Extract** structured healthcare data via Groq LLM (`openai/gpt-oss-120b`)
4. **Detect** danger signs deterministically (independent of LLM)
5. **Read back** the extracted record aloud via browser Speech Synthesis
6. **Correct** using voice if needed
7. **Confirm** and save to MongoDB Atlas
8. **Generate** follow-up actions automatically

---

## Architecture

```
ASHA Worker
    │
    ▼
React Mobile App (port 5173)
    │
    ├─ MediaRecorder API → WebM/OGG audio chunks
    │
    ▼
Django REST API (port 8000)
    │
    ├─ POST /api/voice/transcribe/
    │       └─ Groq Whisper (whisper-large-v3-turbo)
    │               └─ Tamil+English transcript
    │
    ├─ POST /api/visits/extract/
    │       ├─ Groq LLM (openai/gpt-oss-120b)
    │       │       └─ Structured VisitRecord JSON (Pydantic)
    │       └─ Deterministic Danger Sign Engine
    │               └─ DS001–DS004 rule set (WHO / IMNCI)
    │
    ├─ POST /api/visits/{id}/confirm/
    │       ├─ MongoDB Atlas → save VisitRecord
    │       └─ Follow-up Generator
    │
    └─ GET /api/analytics/dashboard/
            └─ Aggregated stats from MongoDB Atlas
```

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite 5, TypeScript, Tailwind CSS |
| UI Components | Lucide React, Framer Motion, Recharts |
| Routing | React Router v6 |
| HTTP Client | Axios |
| Backend | Python 3.13, Django 4.2, Django REST Framework |
| Real-time | Django Channels (WebSocket), Daphne |
| Database | MongoDB Atlas (PyMongo) — no Django ORM |
| AI — STT | Groq Whisper (`whisper-large-v3-turbo`) |
| AI — LLM | Groq (`openai/gpt-oss-120b`) |
| Data Validation | Pydantic v2 |
| Testing | pytest, pytest-django |
| TTS | Browser `speechSynthesis` API (fallback; Gnani adapter interface ready) |

---

## Key Features

- 🎤 **Voice-first workflow** — complete a visit record without typing
- 🌐 **Tamil + English code-mix** — handles natural mixed speech
- 🤖 **Groq AI extraction** — converts free-form speech into structured JSON
- 🚨 **Deterministic danger detection** — bleeding, convulsions, fever (newborn), severe headache — independent of LLM
- 🔊 **TTS read-back** — extracted record read aloud for confirmation
- ✏️ **Voice correction** — correct individual fields by speaking
- 💾 **MongoDB Atlas** — cloud-native storage with real-time sync
- 📅 **Auto follow-ups** — generated based on visit type and clinical rules
- 📊 **Dashboard analytics** — visit trends, immunisation stats, alert summary
- 📱 **Mobile-first design** — optimised for smartphones in field use

---

## Quick Start

### Prerequisites

- Python 3.10+ (tested on 3.13)
- Node.js 18+
- MongoDB Atlas account (URI with database `Hasha`)
- Groq API key

### 1. Clone & configure

```bash
git clone <repo-url>
cd Arogya
```

### 2. Backend setup

```powershell
cd backend
python -m venv venv
venv\Scripts\pip install -r requirements.txt

# Copy and fill in credentials
copy .env.example .env
# Edit backend\.env — see Environment Configuration below
```

### 3. Seed demo data

```powershell
cd backend
venv\Scripts\python.exe manage.py seed_data
```

Expected output:
```
✓ MongoDB Atlas connected
✓ Seeded 5 ASHA users
✓ Seeded 10 beneficiaries
✓ Seeded 20 visits
✓ Seeded 5 follow-ups
✓ Seeded 2 danger alerts
```

### 4. Start backend

```powershell
# Windows — double-click or run:
start_backend.bat

# Or directly:
cd backend
venv\Scripts\python.exe manage.py runserver 8000
```

### 5. Frontend setup & start

```powershell
cd frontend
npm install

# Windows — double-click or run:
..\start_frontend.bat

# Or directly:
npm run dev
```

### 6. Open the app

Navigate to **http://localhost:5173**

Login with demo account: `ASHA001` / `demo123`

---

## Environment Configuration

### `backend/.env`

```env
# Groq AI
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b

# MongoDB Atlas
MONGODB_URI=mongodb+srv://user:password@cluster.mongodb.net/Hasha?retryWrites=true&w=majority
MONGODB_DB_NAME=Hasha

# Django
DJANGO_SECRET_KEY=your-strong-random-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

> **Security:** Never commit `.env` to version control. It is excluded by `.gitignore`.

### `frontend/.env`

```env
VITE_API_URL=http://localhost:8000
```

> Only `VITE_API_URL` is exposed to the frontend. No secrets go into Vite env vars.

---

## API Reference

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/accounts/login/` | Demo login → returns token |
| POST | `/api/accounts/logout/` | Clear session |
| GET | `/api/accounts/me/` | Current user profile |

### Voice & Visits

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/voice/transcribe/` | Upload audio → Whisper transcript |
| POST | `/api/visits/extract/` | Transcript → structured VisitRecord + danger check |
| GET | `/api/visits/` | List all visits (paginated) |
| GET | `/api/visits/{id}/` | Visit detail |
| PATCH | `/api/visits/{id}/correct/` | Correct a field (`{field, value}`) |
| POST | `/api/visits/{id}/confirm/` | Confirm → save to MongoDB + generate follow-ups |

### Beneficiaries

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/beneficiaries/` | List (supports `?search=name`) |
| GET | `/api/beneficiaries/{id}/` | Beneficiary detail + visit history |
| POST | `/api/beneficiaries/` | Add new beneficiary |

### Follow-ups & Alerts

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/followups/` | List follow-ups (supports `?status=pending`) |
| PATCH | `/api/followups/{id}/` | Update status |
| GET | `/api/alerts/` | Active danger alerts |
| PATCH | `/api/alerts/{id}/` | Update referral status / resolve |

### Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/analytics/dashboard/` | Aggregated stats + charts data |
| GET | `/api/analytics/health/` | System health (Groq + MongoDB status) |

---

## AI Pipeline

### Speech-to-Text

```
Audio (WebM/OGG) → multipart upload → Groq Whisper API
                                            ↓
                                   Tamil+English transcript
```

Model: `whisper-large-v3-turbo`

> **Note:** Groq Whisper uses an audio-upload (non-streaming) workflow. For genuine low-latency streaming, the codebase includes a `GnaniSpeechAdapter` interface stub (`services/speech_service.py`) ready for integration when Gnani credentials are available.

### Structured Extraction

The transcript is sent to Groq LLM with a structured JSON schema prompt. The response is validated with Pydantic (`VisitRecord`):

```json
{
  "beneficiary_name": "Lakshmi",
  "visit_type": "pregnancy",
  "pregnancy_month": 7,
  "weight_kg": 62.5,
  "blood_pressure": "120/80",
  "anc_completed": true,
  "ifa_given": true,
  "next_visit_date": "2026-12-02",
  "missing_fields": [],
  "confidence_score": 0.91,
  "raw_transcript": "..."
}
```

---

## Danger Sign Detection

Danger signs are detected **deterministically** using a rule engine (`services/danger_detection_service.py`), **independent of the LLM**.

| Rule ID | Danger Sign | Trigger Keywords | Severity | Reference |
|---------|------------|-----------------|----------|-----------|
| DS001 | Bleeding during pregnancy | bleeding, blood, ரத்தம் | Emergency | WHO ANC 2015 §C1 |
| DS002 | Convulsions / seizures | convulsion, fits, வலிப்பு | Emergency | IMNCI MoHFW 2014 Ch.2 |
| DS003 | Severe headache / blurred vision | severe headache, blurred vision, தலைவலி | Emergency | WHO ANC 2015 §C3 |
| DS004 | Newborn fever (visit context) | fever, காய்ச்சல் + newborn context | Emergency | IMNCI MoHFW 2014 Ch.3 |

**Negation handling:** Phrases like "no bleeding", "did not bleed", "had bleeding last year" are excluded from positive detection.

---

## Demo Accounts & Data

| Worker ID | Name | PHC | Password |
|-----------|------|-----|----------|
| ASHA001 | Priya Sundaram | Tambaram PHC | demo123 |
| ASHA002 | Meenakshi Rajan | Avadi PHC | demo123 |
| ASHA003 | Kavitha Devi | Ambattur PHC | demo123 |
| ASHA004 | Saranya Kumar | Pallavaram PHC | demo123 |
| ASHA005 | Anitha Babu | Chromepet PHC | demo123 |

**Key demo beneficiary:** BEN001 — Lakshmi, pregnancy 7 months (use for voice demo)

> All accounts and data are **synthetic** for demonstration only. This is not production-grade identity verification.

### Demo Voice Script (Tamil-English)

Speak this into the microphone on the Voice Register page (BEN001, Pregnancy Visit):

> *"Lakshmi madam visited today. She is in seventh month pregnancy. Weight is 62.5 kg. Blood pressure normal. ANC completed. IFA tablets given. Next visit December two."*

Expected extraction:
- Name: Lakshmi | Month: 7 | Weight: 62.5 kg | ANC: ✓ | IFA: ✓ | Next: 2026-12-02

### Danger Sign Demo

> *"Patient is experiencing bleeding and severe headache during pregnancy."*

Expected: Immediate **DS001 + DS003** emergency alert (red banner), PHC referral reminder.

---

## Testing

```powershell
cd backend
venv\Scripts\python.exe -m pytest tests/ -v
```

**33 tests** covering:
- Danger sign detection (positive, negated, historical, hypothetical, Tamil, code-mix)
- Extraction schema validation (Pydantic)
- Follow-up rule generation
- Groq service key validation

```
33 passed in 0.37s
```

---

## Project Structure

```
Arogya/
├── backend/
│   ├── apps/
│   │   ├── accounts/          # Demo auth (ASHA001-005)
│   │   ├── analytics/         # Dashboard stats, health check, seed_data
│   │   ├── beneficiaries/     # Beneficiary CRUD
│   │   ├── danger_alerts/     # Alert management
│   │   ├── followups/         # Follow-up scheduling
│   │   ├── visits/            # Visit extract/correct/confirm
│   │   └── voice_agent/       # Transcription, WebSocket
│   ├── config/
│   │   ├── settings.py        # Django config (MongoDB, Channels, CORS)
│   │   ├── urls.py            # URL routing
│   │   └── asgi.py            # Channels ASGI
│   ├── services/
│   │   ├── mongodb_service.py # Atlas singleton + in-memory fallback
│   │   ├── groq_service.py    # LLM extraction + validation
│   │   ├── speech_service.py  # Whisper STT + Gnani adapter stub
│   │   ├── danger_detection_service.py  # Deterministic rule engine
│   │   ├── extraction_service.py        # Pydantic VisitRecord schema
│   │   ├── followup_service.py          # Follow-up generation rules
│   │   └── tts_service.py     # TTS interface
│   ├── tests/
│   │   ├── test_danger_detection.py
│   │   ├── test_extraction.py
│   │   ├── test_followups.py
│   │   └── test_groq.py
│   ├── .env                   # 🔒 NOT committed (credentials)
│   ├── .env.example           # Template — safe to commit
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── LandingPage.tsx
│   │   │   ├── LoginPage.tsx
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── VoiceRegisterPage.tsx   # 🎤 Core voice workflow
│   │   │   ├── BeneficiaryPage.tsx
│   │   │   ├── VisitHistoryPage.tsx
│   │   │   ├── FollowUpPage.tsx
│   │   │   ├── EmergencyAlertPage.tsx
│   │   │   └── SettingsPage.tsx
│   │   ├── components/layout/Layout.tsx
│   │   ├── contexts/AuthContext.tsx
│   │   └── services/api.ts
│   ├── .env
│   └── vite.config.ts
├── start_backend.bat
├── start_frontend.bat
├── .gitignore
└── README.md
```

---

## Disclaimer

> **ASHA Voice is a referral-support and record-keeping tool. It is NOT a diagnostic system.**
>
> - All danger sign alerts are reminders to refer to PHC/ANM — not diagnoses.
> - Medical decisions must always be made by qualified healthcare professionals.
> - All demo data is entirely synthetic. No real patient information is used or stored.
> - This application is built for hackathon demonstration purposes.

---

*Built for the AI-powered Healthcare Hackathon — Tamil Nadu, 2026*
