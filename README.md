# YouTube RAG Assistant

> **"Built a multi-video RAG system that ingests YouTube playlists, retrieves timestamp-grounded answers across sources, and deploys via a single config-driven codebase to both a local dev profile and a rate-limited public demo on Azure."**

---

## Architecture Overview

```
┌─────────────────┐           ┌────────────────────────────┐           ┌──────────────────────┐
│  Vite + React   │   HTTP    │      FastAPI Backend       │   SQL     │ PostgreSQL + pgvector│
│  Frontend       │◄─────────►│  - Session Middleware      │◄─────────►│  sessions /          │
│                 │           │  - URL Parser & Ingestion  │           │  collections /       │
│  YouTube Player │           │  - Retrieval & Gemini RAG  │           │  videos / chunks /   │
│  (IFrame API)   │           │  - BackgroundTasks & Clean │           │  jobs                │
└─────────────────┘           └──────────────┬─────────────┘           └──────────────────────┘
                                             │
                          ┌──────────────────┼───────────────────┐
                          ▼                  ▼                   ▼
                   ┌─────────────┐   ┌───────────────┐   ┌────────────────┐
                   │   yt-dlp    │   │   youtube-    │   │   Gemini API   │
                   │  (metadata) │   │ transcript-api│   │  (Embed & Chat)│
                   └─────────────┘   └───────────────┘   └────────────────┘
```

---

## Core Features

- **Mixed Link Ingestion:** Paste single video links, multiple links, or entire YouTube playlists in one input. Deduplicates by `video_id` automatically.
- **Configurable 5-Video Cap:** Enforces a priority-based cap (explicit individual links take priority, remainder filled in native playlist order).
- **Free Transcript Ingestion:** Extracts captions via `youtube-transcript-api` without audio downloads or paid ASR APIs.
- **Sentence-Aware Chunking:** Segments captions into ~30–60 second speech windows while strictly preserving the initial `start_time` for timestamp seeking.
- **pgvector Cosine Search:** Fast vector similarity retrieval scoped to the user's active session collection.
- **Gemini Flash Synthesis:** Answers are synthesized solely from retrieved chunks (preventing hallucinations).
- **Interactive Single Player:** Embedded YouTube Player API loads the video and seeks to the exact second when a source card is clicked.
- **Sliding-Expiry Auto-Cleanup:** APScheduler deletes inactive sessions and cascades deletions to collections, videos, chunks, and jobs.
- **Dual Deployment Profiles:** Run locally without caps via Docker Compose, or deploy to Azure Container Apps with rate limits and session TTL enabled.

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Backend** | FastAPI (Python 3.12+) | Async REST API & BackgroundTasks |
| **Database** | PostgreSQL 16 + pgvector | Relational metadata + vector embedding storage |
| **Captions** | `youtube-transcript-api` | Zero-cost subtitle extraction |
| **Metadata** | `yt-dlp` | Fast playlist and video ID resolution (no audio download) |
| **Embeddings** | Gemini (`gemini-embedding-001`) | 768-dimension semantic vector embeddings |
| **Generation** | Gemini (`gemini-1.5-flash`) | Context-grounded synthesis |
| **Frontend** | React 18 + Vite | Dark mode, glassmorphism UI, YouTube IFrame API |
| **Containers** | Docker & Docker Compose | Containerized local and cloud deployment |

---

## Quick Start (Docker Compose)

### 1. Clone & Configure Environment

```bash
git clone <repository-url>
cd youtube-rag

# Configure your Gemini API key in backend/.env
cp backend/.env.example backend/.env
```

Open `backend/.env` and add your Google Gemini API key:
```env
GEMINI_API_KEY=AIzaSy...
```

### 2. Start Full Stack

```bash
docker compose up --build
```

- **Frontend:** [http://localhost:3000](http://localhost:3000)
- **Backend API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Database (PostgreSQL + pgvector):** `localhost:5432`

---

## Running Locally for Development

### 1. Start Database Container Only

```bash
docker compose up -d db
```

### 2. Run Backend

```bash
# In project root
python -m venv .venv
.\.venv\Scripts\activate  # Windows (or source .venv/bin/activate on Linux/Mac)
pip install -r backend/requirements.txt

# Run FastAPI dev server
$env:PYTHONPATH="backend"
uvicorn app.main:app --reload --port 8000
```

### 3. Run Frontend

```bash
cd frontend
npm install
npm run dev
```

Visit [http://localhost:3000](http://localhost:3000).

---

## Running Automated Tests

Run the test suite covering URL parsing, sentence-aware chunking, session handling, and API endpoints:

```bash
$env:PYTHONPATH="backend"
pytest backend/tests -v
```

---

## Configuration Profiles

| Variable | Local (`.env.example`) | Hosted (`.env.production`) |
|---|---|---|
| `ENVIRONMENT` | `development` | `production` |
| `MAX_VIDEOS_PER_COLLECTION` | `999` (unlimited) | `5` (hard cap) |
| `SESSION_TTL_SECONDS` | `0` (disabled) | `7200` (2 hours) |
| `RATE_LIMIT_ENABLED` | `false` | `true` |
| `RATE_LIMIT_PER_HOUR` | `60` | `10` |
| `GEMINI_EMBEDDING_MODEL` | `gemini-embedding-001` | `gemini-embedding-001` |
| `GEMINI_CHAT_MODEL` | `gemini-1.5-flash` | `gemini-1.5-flash` |
| `SIMILARITY_THRESHOLD` | `0.55` | `0.55` |
| `MAX_SOURCES_RETURNED` | `4` | `4` |

---

## Azure Deployment (Azure Container Apps)

1. **Azure Database for PostgreSQL Flexible Server:**
   - Deploy PostgreSQL 16 on Azure.
   - Run `CREATE EXTENSION vector;`.
2. **Container Apps:**
   - Build and push backend image to Azure Container Registry (ACR).
   - Set environment variables matching `.env.production`.
   - Scale rule: Scale down to 0 replicas when idle to protect Azure credits.
3. **Frontend:**
   - Deploy the Nginx container or static bundle to Azure Static Web Apps.
