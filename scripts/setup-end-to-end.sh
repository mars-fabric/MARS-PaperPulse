#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_ENV_EXAMPLE="$ROOT_DIR/backend/.env.example"
BACKEND_ENV="$ROOT_DIR/backend/.env"
FRONTEND_ENV_LOCAL="$ROOT_DIR/frontend/.env.local"
VENV_DIR=""
VENV_PY=""

if [[ ! -f "$BACKEND_ENV_EXAMPLE" ]]; then
  echo "Error: missing backend/.env.example"
  exit 1
fi

prompt_default() {
  local prompt="$1"
  local default_val="$2"
  local value
  read -r -p "$prompt [$default_val]: " value
  if [[ -z "$value" ]]; then
    value="$default_val"
  fi
  printf '%s' "$value"
}

prompt_secret() {
  local prompt="$1"
  local value
  read -r -s -p "$prompt: " value
  echo
  printf '%s' "$value"
}

gen_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  else
    python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
  fi
}

yes_no() {
  local prompt="$1"
  local default="${2:-y}"
  local answer
  read -r -p "$prompt [y/n] (default: $default): " answer
  answer="${answer:-$default}"
  [[ "$answer" =~ ^[Yy]$ ]]
}

is_port_free() {
  local port="$1"
  python3 - "$port" <<'PY' >/dev/null 2>&1
import socket
import sys

port = int(sys.argv[1])
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.bind(("127.0.0.1", port))
except OSError:
    raise SystemExit(1)
finally:
    s.close()
PY
}

pick_free_port() {
  local candidate
  for candidate in 8000 8001 8002 8003; do
    if is_port_free "$candidate"; then
      printf '%s' "$candidate"
      return
    fi
  done
  printf '8000'
}

to_ws_url() {
  local url="$1"
  if [[ "$url" == https://* ]]; then
    printf 'wss://%s' "${url#https://}"
    return
  fi
  if [[ "$url" == http://* ]]; then
    printf 'ws://%s' "${url#http://}"
    return
  fi
  printf '%s' "$url"
}

ensure_venv() {
  if [[ -d "$BACKEND_DIR/.venv" ]]; then
    VENV_DIR="$BACKEND_DIR/.venv"
  elif [[ -d "$BACKEND_DIR/venv" ]]; then
    VENV_DIR="$BACKEND_DIR/venv"
  else
    if ! command -v python3 >/dev/null 2>&1; then
      echo "Error: python3 not found. Install Python 3 first."
      exit 1
    fi
    VENV_DIR="$BACKEND_DIR/.venv"
    echo "No virtual environment found. Creating: $VENV_DIR"
    python3 -m venv "$VENV_DIR"
  fi

  if [[ ! -f "$VENV_DIR/bin/activate" ]]; then
    echo "Error: invalid virtual environment at $VENV_DIR"
    exit 1
  fi

  # shellcheck disable=SC1090
  source "$VENV_DIR/bin/activate"
  VENV_PY="$VENV_DIR/bin/python"
  echo "Using Python virtual environment: $VENV_DIR"

  if [[ -f "$BACKEND_DIR/requirements.txt" ]]; then
    echo "Installing backend dependencies..."
    "$VENV_PY" -m pip install -r "$BACKEND_DIR/requirements.txt"
  fi
}

ensure_frontend_deps() {
  if ! command -v npm >/dev/null 2>&1; then
    echo "Error: npm not found. Install Node.js and npm first."
    exit 1
  fi

  echo "Installing frontend dependencies..."
  (cd "$FRONTEND_DIR" && npm install)
}

echo "== MARS-PaperPulse Local Setup =="
echo

ensure_venv
ensure_frontend_deps

echo "========================================="
echo "Configuration Defaults"
echo "========================================="
echo "  Backend work dir: ./cmbdir"
echo "  Frontend URL: http://localhost:3000"
echo "  Default Provider: Azure (gpt-4o)"
echo "  Database: SQLite (./cmbdir/database/cmbagent.db)"
echo

auto_port="$(pick_free_port)"
if [[ "$auto_port" != "8000" ]]; then
  echo "⚠ Port 8000 is busy. Using first available: $auto_port"
fi

backend_port="$auto_port"
frontend_url="http://localhost:3000"
api_url="http://localhost:$backend_port"
working_dir="./cmbdir"

echo
echo "========================================="
echo "LLM Provider Selection"
echo "========================================="
echo "  1) Azure OpenAI (default - gpt-4o)"
echo "  2) AWS Bedrock (Claude Sonnet 4.5)"
echo "  3) OpenAI (gpt-4o)"
echo "  4) Anthropic (Claude - direct API)"
echo "  5) Google Gemini"
echo "  6) Mistral"
echo "  7) NVIDIA NIM"
provider_input="$(prompt_default "Select provider [1-7]" "1")"

case "$provider_input" in
  ""|1)
    provider_choice="azure"
    ;;
  2)
    provider_choice="aws_bedrock"
    ;;
  3)
    provider_choice="openai"
    ;;
  4)
    provider_choice="anthropic"
    ;;
  5)
    provider_choice="google"
    ;;
  6)
    provider_choice="mistral"
    ;;
  7)
    provider_choice="nvidia"
    ;;
  *)
    echo "Invalid choice. Using Azure (default)."
    provider_choice="azure"
    ;;
esac

# Initialize all provider variables
openai_key=""
az_key=""
az_endpoint=""
az_deployment=""
az_api_version=""
aws_key=""
aws_secret=""
aws_region=""
aws_session_token=""
anthropic_key=""
gemini_key=""
gcp_project=""
mistral_key=""
nvidia_key=""
nvidia_base_url=""

case "$provider_choice" in
  azure)
    echo
    echo "Azure OpenAI (gpt-4o default):"
    az_key="$(prompt_secret "  AZURE_OPENAI_API_KEY (press Enter to skip)")"
    az_endpoint="$(prompt_default "  AZURE_OPENAI_ENDPOINT" "https://your-resource.openai.azure.com/")"
    az_deployment="$(prompt_default "  AZURE_OPENAI_DEPLOYMENT (optional, press Enter to skip)" "")"
    az_api_version="$(prompt_default "  AZURE_OPENAI_API_VERSION (optional, press Enter to skip)" "")"
    ;;
  aws_bedrock)
    echo
    echo "AWS Bedrock (Claude Sonnet 4.5 default):"
    aws_key="$(prompt_secret "  AWS_ACCESS_KEY_ID (press Enter to skip)")"
    aws_secret="$(prompt_secret "  AWS_SECRET_ACCESS_KEY (press Enter to skip)")"
    aws_region="$(prompt_default "  AWS_DEFAULT_REGION" "us-east-1")"
    aws_session_token="$(prompt_default "  AWS_SESSION_TOKEN (optional, press Enter to skip)" "")"
    ;;
  openai)
    echo
    echo "OpenAI (gpt-4o default):"
    openai_key="$(prompt_secret "  OPENAI_API_KEY (press Enter to skip)")"
    ;;
  anthropic)
    echo
    echo "Anthropic (Claude - direct API):"
    anthropic_key="$(prompt_secret "  ANTHROPIC_API_KEY (press Enter to skip)")"
    ;;
  google)
    echo
    echo "Google Gemini (gemini-2.5-pro default):"
    gemini_key="$(prompt_secret "  GEMINI_API_KEY (press Enter to skip)")"
    gcp_project="$(prompt_default "  GOOGLE_CLOUD_PROJECT (optional, press Enter to skip)" "")"
    ;;
  mistral)
    echo
    echo "Mistral (mistral-large-latest default):"
    mistral_key="$(prompt_secret "  MISTRAL_API_KEY (press Enter to skip)")"
    ;;
  nvidia)
    echo
    echo "NVIDIA NIM (nemotron-3-super-120b-a12b default):"
    nvidia_key="$(prompt_secret "  NVIDIA_API_KEY (press Enter to skip)")"
    nvidia_base_url="$(prompt_default "  NVIDIA_BASE_URL (optional, press Enter to skip)" "")"
    ;;
esac

echo
auto_secret="$(gen_secret)"
jwt_secret="$(prompt_default "JWT secret for auth tokens (auto-generated)" "$auto_secret")"
admin_email="$(prompt_default "Admin email for first-boot" "admin@test.example")"
admin_password="$(prompt_secret "Admin password")"
if [[ -z "$admin_password" ]]; then
  admin_password="Admin@12345"
  echo "(Using fallback admin password: Admin@12345)"
fi

echo
echo "========================================="
echo "Langfuse Tracing (Optional)"
echo "========================================="
echo "  1) None (default)"
echo "  2) Langfuse Local (http://localhost:4000)"
echo "  3) Langfuse Cloud (https://cloud.langfuse.com)"
langfuse_input="$(prompt_default "Langfuse mode [1-3]" "1")"

langfuse_mode=""
langfuse_host=""
langfuse_public=""
langfuse_secret=""

case "$langfuse_input" in
  ""|1)
    langfuse_mode="none"
    ;;
  2)
    langfuse_mode="local"
    langfuse_host="http://localhost:4000"
    echo "Langfuse Local:"
    langfuse_public="$(prompt_default "  LANGFUSE_PUBLIC_KEY (press Enter to skip)" "")"
    langfuse_secret="$(prompt_default "  LANGFUSE_SECRET_KEY (press Enter to skip)" "")"
    ;;
  3)
    langfuse_mode="cloud"
    langfuse_host="$(prompt_default "  LANGFUSE_HOST" "https://cloud.langfuse.com")"
    langfuse_public="$(prompt_secret "  LANGFUSE_PUBLIC_KEY (press Enter to skip)")"
    langfuse_secret="$(prompt_secret "  LANGFUSE_SECRET_KEY (press Enter to skip)")"
    ;;
  *)
    langfuse_mode="none"
    ;;
esac

cp "$BACKEND_ENV_EXAMPLE" "$BACKEND_ENV"

{
  echo
  echo "# ============================================================================="
  echo "# Setup override block generated by scripts/setup-end-to-end.sh"
  echo "# ============================================================================="
  echo
  echo "# --- PROVIDER & CREDENTIALS ---"
  echo "CMBAGENT_LLM_PROVIDER=\"$provider_choice\""
  
  case "$provider_choice" in
    azure)
      [[ -n "$az_key" ]] && echo "AZURE_OPENAI_API_KEY=\"$az_key\""
      [[ -n "$az_endpoint" ]] && echo "AZURE_OPENAI_ENDPOINT=\"$az_endpoint\""
      [[ -n "$az_deployment" ]] && echo "AZURE_OPENAI_DEPLOYMENT=\"$az_deployment\""
      [[ -n "$az_api_version" ]] && echo "AZURE_OPENAI_API_VERSION=\"$az_api_version\""
      ;;
    aws_bedrock)
      [[ -n "$aws_key" ]] && echo "AWS_ACCESS_KEY_ID=\"$aws_key\""
      [[ -n "$aws_secret" ]] && echo "AWS_SECRET_ACCESS_KEY=\"$aws_secret\""
      [[ -n "$aws_region" ]] && echo "AWS_DEFAULT_REGION=\"$aws_region\""
      [[ -n "$aws_session_token" ]] && echo "AWS_SESSION_TOKEN=\"$aws_session_token\""
      ;;
    openai)
      [[ -n "$openai_key" ]] && echo "OPENAI_API_KEY=\"$openai_key\""
      ;;
    anthropic)
      [[ -n "$anthropic_key" ]] && echo "ANTHROPIC_API_KEY=\"$anthropic_key\""
      ;;
    google)
      [[ -n "$gemini_key" ]] && echo "GEMINI_API_KEY=\"$gemini_key\""
      [[ -n "$gcp_project" ]] && echo "GOOGLE_CLOUD_PROJECT=\"$gcp_project\""
      ;;
    mistral)
      [[ -n "$mistral_key" ]] && echo "MISTRAL_API_KEY=\"$mistral_key\""
      ;;
    nvidia)
      [[ -n "$nvidia_key" ]] && echo "NVIDIA_API_KEY=\"$nvidia_key\""
      [[ -n "$nvidia_base_url" ]] && echo "NVIDIA_BASE_URL=\"$nvidia_base_url\""
      ;;
  esac
  
  echo
  echo "# --- AUTH ---"
  echo "JWT_SECRET_KEY=\"$jwt_secret\""
  echo "ACCESS_TOKEN_EXPIRE_MINUTES=\"15\""
  echo "REFRESH_TOKEN_EXPIRE_DAYS=\"7\""
  echo "DEFAULT_ADMIN_EMAIL=\"$admin_email\""
  echo "DEFAULT_ADMIN_PASSWORD=\"$admin_password\""
  
  echo
  echo "# --- BACKEND CONFIG ---"
  echo "PORT=$backend_port"
  echo "CMBAGENT_APP_TITLE=\"CMBAgent API\""
  echo "CMBAGENT_APP_VERSION=\"1.0.0\""
  echo "CMBAGENT_CORS_ORIGINS=\"http://localhost:3000,http://localhost:3001,http://localhost:3002,http://localhost:3003,http://localhost:3004,http://localhost:3005\""
  echo "CMBAGENT_DEBUG=\"false\""
  echo "CMBAGENT_MAX_FILE_SIZE_MB=\"10\""
  
  echo
  echo "# --- WORK DIRECTORY ---"
  echo "CMBAGENT_DEFAULT_WORK_DIR=\"$working_dir\""
  
  echo
  echo "# --- RUNTIME FLAGS ---"
  echo "CMBAGENT_DISABLE_RAG=\"true\""
  
  echo
  echo "# --- LOGGING ---"
  echo "LOG_LEVEL=\"INFO\""
  echo "LOG_JSON=\"false\""
  
  if [[ "$langfuse_mode" != "none" ]]; then
    echo
    echo "# --- LANGFUSE TRACING ---"
    [[ -n "$langfuse_host" ]] && echo "LANGFUSE_HOST=\"$langfuse_host\""
    [[ -n "$langfuse_public" ]] && echo "LANGFUSE_PUBLIC_KEY=\"$langfuse_public\""
    [[ -n "$langfuse_secret" ]] && echo "LANGFUSE_SECRET_KEY=\"$langfuse_secret\""
    echo "MARS_TRACING_REDACT=\"prompts\""
  fi
  
} >> "$BACKEND_ENV"

ws_url="$(to_ws_url "$api_url")"

cat > "$FRONTEND_ENV_LOCAL" <<EOF
# Generated by setup-end-to-end.sh
NEXT_PUBLIC_API_URL=$api_url
NEXT_PUBLIC_WS_URL=$ws_url
NEXT_PUBLIC_CMBAGENT_WORK_DIR=$working_dir
EOF

echo
echo "========================================="
echo "✓ Configuration Complete"
echo "========================================="
echo "Backend .env: $BACKEND_ENV"
echo "  Port: $backend_port"
echo "  API URL: $api_url"
echo "  Work Dir: $working_dir"
echo "  Provider: $provider_choice"
if [[ "$langfuse_mode" != "none" ]]; then
  echo "  Langfuse: $langfuse_mode ($langfuse_host)"
fi
echo
echo "Frontend .env.local: $FRONTEND_ENV_LOCAL"
echo "  API URL: $api_url"
echo "  WS URL: $ws_url"
echo

echo "========================================="
echo "Starting Services"
echo "========================================="
if yes_no "Start backend and frontend now?" "y"; then
  (cd "$BACKEND_DIR" && nohup "$VENV_PY" run.py > /tmp/paperpulse_backend.log 2>&1 &)
  (cd "$FRONTEND_DIR" && nohup npm run dev > /tmp/paperpulse_frontend.log 2>&1 &)
  echo "✓ Started backend and frontend (pid in background)"
  echo
  echo "View logs:"
  echo "  Backend:  tail -f /tmp/paperpulse_backend.log"
  echo "  Frontend: tail -f /tmp/paperpulse_frontend.log"
  echo
  echo "Access:"
  echo "  Frontend: http://localhost:3000"
  echo "  API: $api_url"
  echo "  Admin: $admin_email"
  echo
  if [[ "$langfuse_mode" == "local" ]]; then
    echo "⚠ Langfuse Local Mode:"
    echo "  Make sure Langfuse is running on $langfuse_host"
    echo "  Example: cd ../ace-monorepo && LANGFUSE_MODE=local docker compose up -d"
    echo "  Get project API keys from Langfuse UI and update .env if needed."
  fi
else
  echo
  echo "To start manually:"
  echo "  Backend:  cd $BACKEND_DIR && source ${VENV_DIR#"$BACKEND_DIR/"}/bin/activate && python run.py"
  echo "  Frontend: cd $FRONTEND_DIR && npm run dev"
fi

echo
echo "Setup complete!"
