# AirDesk HVAC AI Platform

AirDesk combines a frontend web experience with a FastAPI backend that handles Twilio SMS webhooks and generates AI responses for missed HVAC calls.

## Project Structure

- `index.html` + `assets/`: frontend static site
- `backend/main.py`: FastAPI app for Twilio webhook handling
- `backend/requirements.txt`: backend Python dependencies
- `backend/.env.example`: required environment variables template

## Backend Setup (FastAPI + Twilio + OpenAI)

### 1) Create and activate a virtual environment

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

### 3) Configure environment variables

```bash
cp .env.example .env
```

Set the values in `backend/.env`:

- `OPENAI_API_KEY`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_PHONE_NUMBER`

### 4) Run the backend server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"ok"}
```

## Twilio Webhook

Point your Twilio incoming message webhook to:

`POST /webhook/twilio`

For local testing, use a tunnel (for example ngrok) and configure Twilio with the public URL:

`https://<your-public-url>/webhook/twilio`

## Frontend

The frontend is currently stored as static built assets in the repository root:

- `index.html`
- `assets/`

You can open `index.html` directly in a browser or serve the folder with any static file server.

## Security Notes

- Never commit real `.env` files or API keys.
- `.gitignore` is configured to exclude backend env and virtual environment files.
