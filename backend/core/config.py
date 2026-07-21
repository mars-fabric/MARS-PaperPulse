"""
Configuration settings for the CMBAgent backend.
"""

import os
from typing import List
from dataclasses import dataclass, field


@dataclass
class Settings:
    """Application settings with sensible defaults."""

    # App metadata
    app_title: str = "CMBAgent API"
    app_version: str = "1.0.0"

    # CORS settings — production-safe defaults (no wildcard).
    # Set CMBAGENT_CORS_ORIGINS env var to override (comma-separated).
    cors_origins: List[str] = field(default_factory=lambda: [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:3003",
        "http://localhost:3004",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:3002",
        "http://127.0.0.1:3003",
        "http://127.0.0.1:3004",
    ])

    # Default work directory
    default_work_dir: str = "~/Desktop/cmbdir"

    # File size limits
    max_file_size_mb: int = 10

    # Debug settings
    debug: bool = False

    # Azure OpenAI settings
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = ""
    azure_openai_api_version: str = "2024-12-01-preview"
    azure_openai_verify_ssl: bool = True

    # JWT / Auth settings
    jwt_secret_key: str = ""
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Default admin bootstrapped on first boot
    default_admin_email: str = ""
    default_admin_password: str = ""

    # Langfuse / OpenTelemetry tracing (all optional)
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
    tracing_redact: str = "prompts"

    def __post_init__(self):
        """Load settings from environment variables if available."""
        self.app_title = os.getenv("CMBAGENT_APP_TITLE", self.app_title)
        self.app_version = os.getenv("CMBAGENT_APP_VERSION", self.app_version)
        self.default_work_dir = os.getenv("CMBAGENT_DEFAULT_WORK_DIR", self.default_work_dir)
        
        # Load CORS origins from environment variable (comma-separated list)
        cors_env = os.getenv("CMBAGENT_CORS_ORIGINS")
        if cors_env:
            self.cors_origins = [origin.strip() for origin in cors_env.split(",")]
        try:
            self.max_file_size_mb = int(os.getenv("CMBAGENT_MAX_FILE_SIZE_MB", str(self.max_file_size_mb)))
        except (ValueError, TypeError):
            pass  # Keep default if env var is not a valid integer
        self.debug = os.getenv("CMBAGENT_DEBUG", "false").lower() == "true"

        # Azure OpenAI settings
        self.azure_openai_api_key = os.getenv("AZURE_OPENAI_API_KEY", self.azure_openai_api_key)
        self.azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", self.azure_openai_endpoint)
        self.azure_openai_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", self.azure_openai_deployment)
        self.azure_openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION", self.azure_openai_api_version)
        self.azure_openai_verify_ssl = os.getenv("AZURE_OPENAI_VERIFY_SSL", "true").lower() != "false"

        # Auth
        self.jwt_secret_key = os.getenv("JWT_SECRET_KEY", self.jwt_secret_key)
        try:
            self.access_token_expire_minutes = int(
                os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(self.access_token_expire_minutes))
            )
            self.refresh_token_expire_days = int(
                os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", str(self.refresh_token_expire_days))
            )
        except (ValueError, TypeError):
            pass
        self.default_admin_email = os.getenv("DEFAULT_ADMIN_EMAIL", self.default_admin_email)
        self.default_admin_password = os.getenv("DEFAULT_ADMIN_PASSWORD", self.default_admin_password)

        # Tracing
        self.langfuse_public_key = os.getenv("LANGFUSE_PUBLIC_KEY", self.langfuse_public_key)
        self.langfuse_secret_key = os.getenv("LANGFUSE_SECRET_KEY", self.langfuse_secret_key)
        self.langfuse_host = os.getenv("LANGFUSE_HOST", self.langfuse_host)
        self.tracing_redact = os.getenv("MARS_TRACING_REDACT", self.tracing_redact)


# Global settings instance
settings = Settings()
