# Property Rental Management System

An AI-powered property rental management system for landlords and property managers.

## Overview

This project combines:

- **LangChain / LangGraph** for stateful AI agents
- **n8n** for real-world workflow automation

Together, the platform can answer tenant questions, track rent payments, manage
maintenance requests, forecast rental income, and trigger automated actions
across communication, scheduling, and finance tools.

## Core AI Capabilities

The AI layer is designed around stateful rental support agents that can:

1. **Answer tenant questions**
   - Availability
   - Pricing
   - Amenities
2. **Track rent payments**
   - Payment status
   - Late-payment detection
   - Reminder generation
3. **Handle maintenance requests**
   - Log issues by tenant and property
   - Suggest repair scheduling
   - Maintain request history
4. **Forecast rental income**
   - Estimate expected income
   - Track repayment timelines for financing
   - Support landlord decision-making with historical context

Because the agents are stateful, they can retain tenant and property context for
personalized, ongoing interactions.

## Automation Capabilities

The automation layer is designed for n8n workflows that connect the agents to
external tools and business processes:

- Send **WhatsApp** or **email** responses automatically
- Sync maintenance schedules with **Google Calendar**
- Log rent payments to **spreadsheets** or **accounting software**
- Trigger alerts for:
  - Late payments
  - Vacant rooms
  - Follow-up actions

## Target End-to-End Flows

### 1. Tenant communication

Tenant asks about a unit → AI agent checks property context → response is sent
through WhatsApp or email via n8n.

### 2. Rent collection

Payment data is received → AI agent updates payment status → n8n logs the
payment and sends reminders or late-payment alerts when needed.

### 3. Maintenance management

Tenant reports an issue → AI agent records the request and suggests next steps →
n8n creates a calendar event and notifies the responsible party.

### 4. Financial forecasting

Rental and payment history is analyzed → AI agent forecasts expected income and
repayment timelines for financing decisions.

## Suggested System Components

- **AI Orchestration**
  - LangChain tools for business actions
  - LangGraph for stateful multi-step flows
- **Data Context**
  - Tenant history
  - Property inventory
  - Payment records
  - Maintenance logs
- **Automation Layer**
  - n8n workflows for messaging, scheduling, alerts, and bookkeeping
- **Integrations**
  - WhatsApp
  - Email
  - Google Calendar
  - Spreadsheets / accounting systems

## Project Goal

The goal of this system is not only to provide intelligent answers, but also to
take action automatically so landlords spend less time on repetitive operational
work while tenants receive faster and more accurate support.

## Local database setup

The project expects the app's PostgreSQL container on **localhost:5433** to
avoid colliding with an existing local PostgreSQL instance on port 5432.

- Local app connection: `postgresql+psycopg://postgres:postgres@localhost:5433/rental_ai`
- Container-to-container connection: `postgresql+psycopg://postgres:postgres@db:5432/rental_ai`

## Run the project

### With Docker

```bash
docker compose up --build db api ui
```

- API: http://localhost:8000
- UI: http://localhost:8501
- Database: localhost:5433
- For document ingestion and semantic search, make sure Ollama is reachable at the configured `OLLAMA_BASE_URL`.

### Locally

1. Create and activate a virtual environment, then install dependencies:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   python -m pip install -e .
   ```

2. Start PostgreSQL/pgvector on port 5433 or set `DATABASE_URL` in `.env`.
3. Set a Groq API key in `.env` as `GROQ_API_KEY` (the app also accepts the legacy `GROK_API_KEY` name).
4. Optional: set `GROQ_MODEL` in `.env` if your Groq account uses a different model. The default is `openai/gpt-oss-120b`.
5. Optional: if you change `EMBEDDING_MODEL`, also set `EMBEDDING_DIMENSIONS` to the matching vector size. The default `nomic-embed-text` uses `768`.
6. Start the API:

   ```bash
   python main.py
   ```

7. Start the UI in another terminal:

   ```bash
   .venv\Scripts\streamlit.exe run src/ui/app.py
   ```

8. Verify the services:

   - API health: `http://localhost:8000/health`
   - UI: `http://localhost:8501`

`python main.py` starts the FastAPI backend. It is not just a database bootstrap script.

## n8n chat orchestration workflow

An import-ready n8n workflow is available for the Streamlit chat orchestration mode:

- Workflow JSON: `n8n/workflows/rentalai-chat-orchestrator.json`
- Setup guide: `docs/n8n-chat-workflow.md`

This workflow receives chat requests from Streamlit, calls the backend `/chat` API,
and returns a JSON response containing `response` for the UI.

## Telegram -> n8n -> backend workflow

An import-ready n8n workflow is also available for a direct Telegram integration:

- Workflow JSON: `n8n/workflows/rentalai-telegram-bridge.json`
- Setup guide: `docs/telegram-n8n-backend.md`

This flow removes Streamlit from the user chat path. Telegram sends updates to n8n,
n8n calls the backend `/chat` API, and n8n replies back to Telegram.
