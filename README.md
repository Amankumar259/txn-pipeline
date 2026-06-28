# AI-Powered Transaction Processing Pipeline

A backend API that accepts a CSV of raw financial transactions, processes it asynchronously through a job queue, uses an LLM to classify transactions and flag anomalies, and generates a structured summary report.

## Tech Stack

- **API**: FastAPI
- **Database**: PostgreSQL
- **Job Queue**: Celery + Redis
- **LLM**: Gemini 1.5 Flash
- **Containerisation**: Docker + Docker Compose

## Architecture
Client → POST /jobs/upload → FastAPI → PostgreSQL (job record)

↓

Redis (enqueue)

↓

Celery Worker

↓

Clean → Anomaly → LLM (Gemini)

↓

PostgreSQL (results)

↑

Client → GET /jobs/{id}/results → FastAPI

## Setup

### 1. Clone the repo
```bash
git clone https://github.com/Amankumar259/txn-pipeline.git
cd txn-pipeline
```

### 2. Configure environment
```bash
cp .env.example .env
```
Open `.env` and add your Gemini API key:
GEMINI_API_KEY=your_gemini_api_key_here
Get a free key at https://aistudio.google.com

### 3. Start all services
```bash
docker compose up --build
```
This starts PostgreSQL, Redis, FastAPI, and the Celery worker in one command. Wait for:
- `Uvicorn running on http://0.0.0.0:8000`
- `celery@... ready`

## API Endpoints

### Upload CSV
```bash
curl -X POST http://localhost:8000/jobs/upload \
  -F "file=@transactions.csv"
```
Response:
```json
{"job_id": "abc-123", "status": "pending", "message": "Job enqueued."}
```

### Poll job status
```bash
curl http://localhost:8000/jobs/{job_id}/status
```
Response:
```json
{"job_id": "abc-123", "status": "completed", "summary": {...}}
```

### Get full results
```bash
curl http://localhost:8000/jobs/{job_id}/results
```
Response includes:
- `transactions` — full cleaned transaction list
- `anomalies` — flagged transactions with reasons
- `category_spend` — spend breakdown per category
- `summary` — LLM narrative, risk level, top merchants

### List all jobs
```bash
curl http://localhost:8000/jobs
```

### Filter jobs by status
```bash
curl "http://localhost:8000/jobs?status=completed"
```

## Processing Pipeline

When a job is dequeued the worker runs these steps in order:

1. **Data Cleaning** — normalises date formats to ISO 8601, strips currency symbols, uppercases status values, fills missing categories with Uncategorised, removes exact duplicate rows
2. **Anomaly Detection** — flags transactions where amount exceeds 3x the account median, flags USD transactions on domestic-only merchants like Swiggy, Ola, IRCTC
3. **LLM Classification** — batches uncategorised transactions and calls Gemini to assign a category from: Food, Shopping, Travel, Transport, Utilities, Cash Withdrawal, Entertainment, Other
4. **LLM Narrative** — single Gemini call to produce total spend by currency, top 3 merchants, anomaly count, 2-3 sentence narrative, and a risk level of low/medium/high
5. **Retry Logic** — failed LLM calls are retried up to 3 times with exponential backoff. If all retries fail the batch is marked llm_failed and processing continues

## Windows (PowerShell) curl commands

```powershell
# Upload
curl.exe -X POST http://localhost:8000/jobs/upload -F "file=@transactions.csv"

# Status
curl.exe http://localhost:8000/jobs/{job_id}/status

# Results
curl.exe http://localhost:8000/jobs/{job_id}/results

# List all
curl.exe http://localhost:8000/jobs

# Filter
curl.exe "http://localhost:8000/jobs?status=completed"
```

## Project Structure
txn-pipeline/

├── docker-compose.yml

├── .env.example

├── README.md

├── api/

│   ├── Dockerfile

│   ├── requirements.txt

│   ├── main.py

│   ├── database.py

│   ├── schemas.py

│   └── routers/

│       └── jobs.py

├── shared/

│   ├── models.py

│   └── celery_app.py

└── worker/

├── Dockerfile

├── requirements.txt

└── tasks/

├── init.py

├── cleaning.py

├── anomaly.py

└── llm.py

## Architecture Diagram
in the repo
