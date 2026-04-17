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
- **6 LLM providers** — OpenAI, Azure OpenAI, Anthropic Claude, Google Gemini, Mistral, AWS Bedrock
- **Provider Settings UI** — configure, test, and manage LLM credentials from the browser (gear icon in top bar)
- **Encrypted credential vault** — AES-256-GCM encrypted storage for API keys, synced to the ProviderRegistry at startup
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
| **AI Orchestration** | LangGraph (multi-agent pipelines), mars_cmbagent ProviderRegistry |
| **LLM Providers** | OpenAI, Azure OpenAI, Anthropic, Google Gemini, Mistral, AWS Bedrock |
| **Credentials** | AES-256-GCM encrypted vault (cryptography >= 42.0) |
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
│   │   ├── useProviders.ts       # Provider CRUD + cache invalidation
│   │   └── useModelConfig.ts     # Provider-filtered model dropdowns
│   ├── contexts/                 # Theme, WebSocket providers
│   ├── types/                    # TypeScript definitions
│   │   └── providers.ts          # Provider system interfaces
│   └── lib/                      # Config, API utilities
│
├── backend/                      # FastAPI application
│   ├── main.py                   # Entry point + WebSocket endpoint
│   ├── routers/                  # API routes
│   │   ├── deepresearch.py       # Core wizard endpoints
│   │   ├── files.py              # File management
│   │   ├── credentials.py        # API key management
│   │   ├── models.py             # Model availability
│   │   └── providers.py          # Multi-provider credential management (7 endpoints)
│   ├── services/
│   │   ├── credential_vault.py   # AES-256-GCM encrypted credential storage
│   │   └── config_bridge.py      # Syncs vault + .env -> ProviderRegistry
│   ├── models/
│   │   └── provider_schemas.py   # Pydantic models for provider API
│   ├── task_framework/
│   │   ├── phases/               # Stage execution logic
│   │   ├── paper_agents/         # LangGraph paper generation pipeline
│   │   ├── langgraph_agents/     # Multi-agent orchestration
│   │   └── prompts/              # Structured prompts per stage
│   ├── core/                     # App factory, config, logging
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
git clone https://github.com//MARS-PaperPulse.git
cd MARS-PaperPulse
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and add your API keys (you only need one provider to get started):

```env
# At least one provider required
OPENAI_API_KEY="your-key-here"
ANTHROPIC_API_KEY="your-key-here"        # optional
GEMINI_API_KEY="your-key-here"           # optional
MISTRAL_API_KEY="your-key-here"          # optional

# Azure OpenAI (optional — overrides OpenAI for gpt-* models)
AZURE_OPENAI_API_KEY="your-azure-key"
AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com"

# AWS Bedrock (optional)
AWS_ACCESS_KEY_ID="AKIA..."
AWS_SECRET_ACCESS_KEY="your-secret"
AWS_DEFAULT_REGION="us-east-1"

# Credential vault encryption key (recommended for production)
MARS_CREDENTIAL_KEY="generate-with-openssl-rand-base64-32"
```

> **Alternative:** Skip `.env` entirely and configure providers via the Settings UI (gear icon in the top bar). Credentials are encrypted and persisted locally.

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

### Deep Research

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/deepresearch/create` | Create a new research task |
| `POST` | `/api/deepresearch/{id}/stages/{n}/execute` | Execute a stage |
| `GET` | `/api/deepresearch/{id}/stages/{n}/content` | Get stage output |
| `PUT` | `/api/deepresearch/{id}/stages/{n}/content` | Update stage content |
| `POST` | `/api/deepresearch/{id}/stages/{n}/refine` | AI refinement |
| `GET` | `/api/deepresearch/recent` | Recent tasks |
| `DELETE` | `/api/deepresearch/{id}` | Delete task |

### Provider Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/providers` | List all 6 providers with status + credential schema |
| `GET` | `/api/providers/{id}` | Single provider detail |
| `POST` | `/api/providers/{id}/credentials` | Store credentials (encrypted vault + registry sync) |
| `POST` | `/api/providers/{id}/test` | Test credentials without storing |
| `DELETE` | `/api/providers/{id}/credentials` | Remove stored credentials |
| `GET` | `/api/providers/models/available` | Models from all configured providers |
| `POST` | `/api/providers/sync` | Force re-sync .env + vault to registry |

### Model Configuration

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/models/config` | Full model config (defaults, workflow overrides) |
| `GET` | `/api/models/available` | Available model list |
| `POST` | `/api/models/reload` | Hot-reload model config from YAML |

Full interactive docs available at `http://localhost:8000/docs` when the backend is running.

## Configuration

See [.env.example](.env.example) for all available configuration options including:

- **LLM Provider API keys** — OpenAI, Anthropic, Gemini, Mistral, Azure OpenAI, AWS Bedrock
- **Credential vault encryption** — `MARS_CREDENTIAL_KEY` for portable AES-256-GCM encryption
- **Work directory paths** — where task outputs, logs, and credentials are stored
- **CORS settings** — allowed origins for frontend
- **Database URL** — SQLite (default), PostgreSQL, MySQL
- **Logging level and format**
- **File upload size limits**

### Provider Priority

Credentials are loaded in this order (highest priority wins):

1. **Settings UI** (stored in encrypted vault)
2. **`.env` file** (loaded on startup)
3. **System environment variables**

### Adding a New Provider

To add a new LLM provider (e.g., Cohere):

1. Create `cmbagent/providers/cohere_provider.py` implementing `LLMProviderAdapter`
2. Register it in `registry.py:_register_builtins()`

That's it. The backend API auto-discovers it, the frontend auto-renders the credential form, and model dropdowns auto-include its models.

## License

This project is part of the MARS research framework.
