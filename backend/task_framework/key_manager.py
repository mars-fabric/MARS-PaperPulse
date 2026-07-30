import os
from pydantic import BaseModel
from dotenv import load_dotenv


class KeyManager(BaseModel):
    ANTHROPIC: str | None = ""
    GEMINI: str | None = ""
    OPENAI: str | None = ""
    PERPLEXITY: str | None = ""
    SEMANTIC_SCHOLAR: str | None = ""
    AZURE_OPENAI_API_KEY: str | None = ""
    AZURE_OPENAI_ENDPOINT: str | None = ""
    AZURE_OPENAI_DEPLOYMENT: str | None = ""
    AZURE_OPENAI_API_VERSION: str | None = ""
    AWS_ACCESS_KEY_ID: str | None = ""
    AWS_SECRET_ACCESS_KEY: str | None = ""
    AWS_REGION: str | None = ""
    NVIDIA: str | None = ""
    NVIDIA_BASE_URL: str | None = ""

    # Prevent Pydantic / Python from serializing actual key values into
    # repr/str output.  OpenInference LangGraph instrumentation serializes
    # the full GraphState (which includes this object) as a span attribute
    # (input.value).  Redacting __repr__ / __str__ provides defence-in-depth
    # even before the span-processor redaction runs.
    def __repr__(self) -> str:
        present = [k for k, v in self.__dict__.items() if v]
        return f"KeyManager(providers=[{', '.join(present)}])"

    def __str__(self) -> str:
        return self.__repr__()

    def model_dump(self, **kwargs) -> dict:
        base = super().model_dump(**kwargs)
        return {k: ("***" if v else None) for k, v in base.items()}

    def get_keys_from_env(self) -> None:
        load_dotenv()

        self.OPENAI                  = os.getenv("OPENAI_API_KEY")
        self.GEMINI                  = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.ANTHROPIC               = os.getenv("ANTHROPIC_API_KEY")
        self.PERPLEXITY              = os.getenv("PERPLEXITY_API_KEY")
        self.SEMANTIC_SCHOLAR        = os.getenv("SEMANTIC_SCHOLAR_KEY")
        self.AZURE_OPENAI_API_KEY    = os.getenv("AZURE_OPENAI_API_KEY")
        self.AZURE_OPENAI_ENDPOINT   = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.AZURE_OPENAI_DEPLOYMENT  = os.getenv("AZURE_OPENAI_DEPLOYMENT")
        self.AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
        self.AWS_ACCESS_KEY_ID       = os.getenv("AWS_ACCESS_KEY_ID")
        self.AWS_SECRET_ACCESS_KEY   = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.AWS_REGION              = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
        self.NVIDIA                  = os.getenv("NVIDIA_API_KEY")
        self.NVIDIA_BASE_URL         = os.getenv("NVIDIA_BASE_URL") or "https://integrate.api.nvidia.com/v1"

    def get_keys_from_vault(self) -> None:
        """Load credentials from CredentialVault (UI-stored keys).

        Vault entries take priority over environment variables.  Falls back
        to env vars for any field not present in the vault.  This is the
        correct path when a user provides a different Azure (or other)
        credential via the Settings UI — the vault reflects the per-user
        choice; os.environ may still hold the server-wide default.
        """
        self.get_keys_from_env()  # baseline from env / .env file

        try:
            from services.credential_vault import CredentialVault
            vault = CredentialVault()

            # Azure OpenAI
            azure = vault.get("azure_openai") or {}
            if azure.get("api_key"):
                self.AZURE_OPENAI_API_KEY    = azure["api_key"]
            if azure.get("endpoint"):
                self.AZURE_OPENAI_ENDPOINT   = azure["endpoint"]
            if azure.get("deployment"):
                self.AZURE_OPENAI_DEPLOYMENT  = azure["deployment"]
            if azure.get("api_version"):
                self.AZURE_OPENAI_API_VERSION = azure["api_version"]

            # OpenAI
            openai_creds = vault.get("openai") or {}
            if openai_creds.get("api_key"):
                self.OPENAI = openai_creds["api_key"]

            # Anthropic
            anthropic = vault.get("anthropic") or {}
            if anthropic.get("api_key"):
                self.ANTHROPIC = anthropic["api_key"]

            # Google / Gemini
            google = vault.get("google_gemini") or {}
            if google.get("api_key"):
                self.GEMINI = google["api_key"]

            # AWS Bedrock
            aws = vault.get("aws_bedrock") or {}
            if aws.get("access_key_id"):
                self.AWS_ACCESS_KEY_ID     = aws["access_key_id"]
            if aws.get("secret_access_key"):
                self.AWS_SECRET_ACCESS_KEY = aws["secret_access_key"]
            if aws.get("region"):
                self.AWS_REGION = aws["region"]

            # NVIDIA
            nvidia = vault.get("nvidia") or {}
            if nvidia.get("api_key"):
                self.NVIDIA = nvidia["api_key"]
            if nvidia.get("base_url"):
                self.NVIDIA_BASE_URL = nvidia["base_url"]

        except Exception:
            pass  # vault unavailable (tests, standalone use) — env vars suffice

    def __getitem__(self, key: str) -> str:
        return getattr(self, key)

    def __setitem__(self, key: str, value: str) -> None:
        setattr(self, key, value)
