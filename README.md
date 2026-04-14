# MARS-PaperPulse

An AI-powered scientific research paper generation platform that guides researchers through a structured, interactive workflow — from initial idea to publication-ready LaTeX manuscript.

## Overview

PaperPulse is a standalone deep-research application built on the MARS framework. It orchestrates multiple AI agents through a 4-stage pipeline to collaboratively produce complete academic papers, with human-in-the-loop review at every stage.

### The 4-Stage Pipeline

| Stage | Description |
|-------|-------------|
| **1. Idea Generation** | AI brainstorms novel research directions based on your description and uploaded data |
| **2. Method Development** | Develops research methodologies grounded in the generated ideas |
| **3. Experiment Execution** | Simulates experiments and generates results with supporting analysis |
| **4. Paper Generation** | Synthesizes all stages into a complete LaTeX manuscript with citations |

Each stage builds on the previous one. Researchers can review, refine, and iterate on AI-generated content before advancing.

## Key Features

- **Interactive 4-stage research pipeline** with human review at each step
- **Multi-LLM support** — OpenAI (GPT-4, GPT-4o), Google Gemini, Anthropic Claude, Azure OpenAI
- **Real-time console streaming** via WebSocket during stage execution
- **AI-powered refinement chat** for iterating on generated content
- **File upload and context analysis** — upload datasets, papers, or notes for AI to incorporate
- **LaTeX paper generation** with AI-assisted editing and PDF compilation
- **Journal-specific formatting** presets (AAS, JHEP, ICML, NeurIPS, PASJ)
- **Cost tracking** per stage and per task
- **Task history** — resume previous research sessions

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 16, React 18, TypeScript, Tailwind CSS |
| **Backend** | FastAPI, Python 3.12+, Uvicorn |
| **AI Orchestration** | LangGraph (multi-agent pipelines) |
| **Real-time** | Socket.IO / WebSocket |
| **Database** | SQLite (default), PostgreSQL/MySQL (configurable) |
| **PDF** | LaTeX compilation, html2pdf.js |

## Project Structure

```
MARS-PaperPulse/
├── frontend/                     # Next.js application
│   ├── app/                      # Pages and layouts
│   ├── components/
│   │   ├── deepresearch/         # 4-stage wizard UI
│   │   ├── workflow/             # Workflow dashboard & timeline
│   │   ├── console/              # Live console output
│   │   ├── files/                # File preview & upload
│   │   ├── core/                 # Design system (Button, Modal, Tabs...)
│   │   └── layout/               # App shell, nav, top bar
│   ├── hooks/                    # React hooks (task state, models, events)
│   ├── contexts/                 # Theme, WebSocket providers
│   ├── types/                    # TypeScript definitions
│   └── lib/                      # Config, API utilities
│
├── backend/                      # FastAPI application
│   ├── main.py                   # Entry point + WebSocket endpoint
│   ├── routers/                  # API routes
│   │   ├── deepresearch.py       # Core wizard endpoints
│   │   ├── files.py              # File management
│   │   ├── credentials.py        # API key management
│   │   └── models.py             # Model availability
│   ├── task_framework/
│   │   ├── phases/               # Stage execution logic
│   │   ├── paper_agents/         # LangGraph paper generation pipeline
│   │   ├── langgraph_agents/     # Multi-agent orchestration
│   │   └── prompts/              # Structured prompts per stage
│   ├── core/                     # App factory, config, logging
│   ├── services/                 # Session management, PDF extraction
│   └── websocket/                # Event handling
│
├── .env.example                  # Environment config template
└── .gitignore
```

## Getting Started

### Prerequisites

- **Python 3.12+**
- **Node.js 18+**
- **npm**
- At least one AI provider API key (OpenAI, Anthropic, Google, or Azure OpenAI)

### 1. Clone the repository

```bash
git clone https://github.com/UJ2202/MARS-PaperPulse.git
cd MARS-PaperPulse
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:

```env
OPENAI_API_KEY="your-key-here"
ANTHROPIC_API_KEY="your-key-here"      # optional
GEMINI_API_KEY="your-key-here"          # optional
```

### 3. Backend setup

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Backend runs at `http://localhost:8000` (API docs at `/docs`).

### 4. Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:3000`.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/deepresearch/create` | Create a new research task |
| `POST` | `/api/deepresearch/{id}/stages/{n}/execute` | Execute a stage |
| `GET` | `/api/deepresearch/{id}/stages/{n}/content` | Get stage output |
| `PUT` | `/api/deepresearch/{id}/stages/{n}/content` | Update stage content |
| `POST` | `/api/deepresearch/{id}/stages/{n}/refine` | AI refinement |
| `GET` | `/api/deepresearch/recent` | Recent tasks |
| `DELETE` | `/api/deepresearch/{id}` | Delete task |

Full interactive docs available at `http://localhost:8000/docs` when the backend is running.

## Configuration

See [.env.example](.env.example) for all available configuration options including:

- AI provider API keys
- Work directory paths
- CORS settings
- Database URL (SQLite, PostgreSQL, MySQL)
- Logging level and format
- File upload size limits

## License

This project is part of the MARS research framework.
