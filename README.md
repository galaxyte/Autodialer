# Autodialer

Autodialer is an AI-assisted calling automation platform that lets teams queue Twilio test calls, monitor their status in real time, and drive calls from natural-language prompts powered by OpenAI.

🔗 **Live Demo:** [https://autodialer-72pc.onrender.com/](https://autodialer-72pc.onrender.com/)

## Features

- Upload up to 100 Twilio test numbers via text or CSV and fire a controlled call campaign.
- Enforce Twilio test mode-only dialing with per-call status tracking.
- AI prompt box that understands “Call +15005550006 and tell them about our product launch” and schedules the call automatically.
- Real-time dashboard summarising success, failure, and skipped calls.
- CSV export of the call log for audits or post-run analysis.

## Tech Stack

- **Backend:** FastAPI (Python 3.11)
- **Database:** SQLite (SQLAlchemy 2.x + `aiosqlite`)
- **Voice:** Twilio Voice API (test credentials only)
- **AI:** OpenAI `gpt-4o-mini`
- **Frontend:** Jinja2 templates + Tailwind (CDN) + custom CSS
- **Environment:** `.env`-driven configuration loaded via `python-dotenv`

## Folder Structure

```
autodialer/
├── app/
│   ├── main.py
│   ├── models/
│   │   └── call_log.py
│   ├── routes/
│   │   ├── ai_prompt.py
│   │   └── calls.py
│   ├── services/
│   │   ├── ai_service.py
│   │   ├── call_manager.py
│   │   └── twilio_service.py
│   ├── static/
│   │   └── style.css
│   ├── templates/
│   │   ├── dashboard.html
│   │   └── index.html
│   └── utils.py
├── env.example
├── requirements.txt
└── README.md
```

> ℹ️ `.env.example` files are blocked in this environment, so the template lives at `env.example`. Rename it to `.env` before running the app.

## Getting Started

### 1. Clone & create a virtual environment

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy the template and fill in your credentials:

```bash
copy env.example .env
```

`.env` contents:

```env
DATABASE_URL=sqlite+aiosqlite:///./autodialer.db
TWILIO_ACCOUNT_SID=ACXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
TWILIO_AUTH_TOKEN=your_twilio_test_auth_token
TWILIO_FROM_NUMBER=+15005550006
OPENAI_API_KEY=sk-your-openai-key
```

### 4. Run the app

```bash
uvicorn app.main:app --reload
```

The app listens on <http://127.0.0.1:8000/>.

## Usage Walkthrough

1. Navigate to the home page and upload Twilio test numbers (e.g. `+15005550006, +15005550009`) via text area or CSV.
2. Submit the form – calls are queued and executed sequentially with a safety delay.
3. Watch the dashboard update in real time (status, timestamp, duration, errors).
4. Export the CSV log if you need to share or archive the run.
5. Optionally, instruct the AI assistant with messages like:
   > “Call +15005550006 and tell them about the AeroLeads demo tomorrow.”
6. The AI extracts the number, validates it, and schedules the call automatically.

### Call Flow (Command Sequence)

| Step | Action | Result |
|------|--------|--------|
| 1 | `Queue Calls` | Writes queued entries to SQLite |
| 2 | Background worker | Calls Twilio API with speech message |
| 3 | Twilio response | Updates call status (`success`, `failed`, `skipped`) |
| 4 | Dashboard refresh | Reflects totals and individual call outcomes |

## Twilio Test Mode

- Only numbers beginning with `+1500` are accepted, aligning with Twilio’s test sandbox.
- Recommended test pair: `TWILIO_FROM_NUMBER = +15005550006` and destination `+15005550009`.
- Calls play `Hello from Autodialer test system` (or the AI-generated prompt) via TwiML `<Say>`.
- Failure cases (invalid number, missing credentials, Twilio exceptions) are logged with details.

## AI Prompt Tips

- Reference the destination number explicitly: `Call +15005550009 and let them know that onboarding starts Monday`.
- Keep prompts short and specific; the AI returns a concise message for the Twilio voice call.
- If a number cannot be parsed or is not a Twilio test number, the app warns and skips the call.


