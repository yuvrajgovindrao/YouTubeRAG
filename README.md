# YouTube RAG Assistant

<div align="center">

[![CI](https://github.com/yuvrajgovindrao/YouTubeRAG/actions/workflows/ci.yml/badge.svg)](https://github.com/yuvrajgovindrao/YouTubeRAG/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL + pgvector](https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Google Gemini](https://img.shields.io/badge/Google_Gemini-8E75B2?logo=googlegemini&logoColor=white)](https://ai.google.dev/)
[![React 18](https://img.shields.io/badge/React_18-20232A?logo=react&logoColor=61DAFB)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-646CFF?logo=vite&logoColor=white)](https://vitejs.dev/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)

<br />

**A multi-video RAG system that ingests YouTube playlists, retrieves timestamp-grounded answers across sources, and deploys via a single config-driven codebase to both a local dev profile and a rate-limited public demo on Azure.**

</div>

---

## Tech Stack

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                               TECH STACK                                    │
├───────────────────┬─────────────────────────┬───────────────────────────────┤
│ Layer             │ Technology              │ Purpose                       │
├───────────────────┼─────────────────────────┼───────────────────────────────┤
│ Frontend UI       │ React 18, Vite          │ Interactive Player & Sources  │
│ Styling           │ Vanilla CSS & Glassmorphism │ Modern Dark Mode UI       │
│ Video Player      │ YouTube IFrame API      │ Exact Timestamp Seeking       │
│ Backend API       │ FastAPI (Python 3.12+)  │ Async Endpoints & Pipeline    │
│ Task Queue        │ FastAPI BackgroundTasks │ Asynchronous Ingestion Jobs   │
│ Vector Database   │ PostgreSQL 16 + pgvector│ Hybrid Metadata + Vectors     │
│ Caption Extract   │ youtube-transcript-api  │ Zero-cost Captions Parsing    │
│ Video Metadata    │ yt-dlp                  │ Fast ID/Playlist Resolution   │
│ Embeddings        │ Gemini gemini-embedding-001 │ 768-dim Vector Embeddings │
│ LLM Synthesis     │ Gemini 1.5 Flash        │ Context-Grounded Answer RAG   │
│ Session Cleanup   │ APScheduler             │ Sliding-Expiry TTL Job        │
│ Rate Limiting     │ SlowAPI (Limits)        │ Per-session & IP Throttling   │
│ Containerization  │ Docker & Docker Compose │ One-command clone-and-run     │
│ CI/CD Automation  │ GitHub Actions          │ Automated Tests & Builds      │
└───────────────────┴─────────────────────────┴───────────────────────────────┘
```

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

## Quick Start (Docker Compose)

### 1. Clone & Configure Environment

```bash
git clone https://github.com/yuvrajgovindrao/YouTubeRAG.git
cd YouTubeRAG

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

---

## License

This project is licensed under the MIT License - see the LICENSE file for details.
