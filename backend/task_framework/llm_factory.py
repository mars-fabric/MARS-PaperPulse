"""
Provider-agnostic LangChain chat-model factory for PaperPulse agents.

Picks the right LangChain integration based on the model name prefix:
- `bedrock/…`  -> langchain_aws.ChatBedrockConverse
- `gpt-*`, `o3*` -> ChatOpenAI or AzureChatOpenAI (Azure when OPENAI key missing)
- `claude-*`, `anthropic*` -> ChatAnthropic
- `gemini-*`   -> ChatGoogleGenerativeAI

When the active deployment is AWS-only (no OpenAI/Azure/Gemini/Anthropic keys
and a hardcoded OpenAI model like `gpt-4o` arrives from cmbagent defaults),
the model is remapped to the configured Bedrock default so agents still run.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


_BEDROCK_DEFAULT_MODEL = os.getenv(
    "CMBAGENT_BEDROCK_DEFAULT_MODEL",
    "openai.gpt-oss-120b-1:0",
)

# Bedrock read_timeout / connect_timeout in seconds. Default 600s because
# Sonnet-tier models writing long paper sections routinely exceed boto3's
# 60s default and surface as `Read timeout on endpoint URL: …/converse`.
_BEDROCK_TIMEOUT = int(os.getenv("CMBAGENT_BEDROCK_TIMEOUT", "600"))
_BEDROCK_MAX_RETRIES = int(os.getenv("CMBAGENT_BEDROCK_MAX_RETRIES", "3"))


def _strip_bedrock_prefix(model: str) -> str:
    """langchain_aws wants the bare Bedrock model id (no `bedrock/` prefix)."""
    return model[len("bedrock/"):] if model.startswith("bedrock/") else model


def _has_aws_creds(keys: Any) -> bool:
    ak = getattr(keys, "AWS_ACCESS_KEY_ID", None)
    sk = getattr(keys, "AWS_SECRET_ACCESS_KEY", None)
    return bool(ak and sk) or bool(os.getenv("AWS_PROFILE"))


def _build_bedrock(model: str, temperature: float, keys: Any):
    from langchain_aws import ChatBedrockConverse

    region = (
        getattr(keys, "AWS_REGION", None)
        or os.getenv("AWS_DEFAULT_REGION")
        or os.getenv("AWS_REGION")
        or "us-east-1"
    )
    aws_access_key_id = getattr(keys, "AWS_ACCESS_KEY_ID", None) or os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = getattr(keys, "AWS_SECRET_ACCESS_KEY", None) or os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_session_token = getattr(keys, "AWS_SESSION_TOKEN", None) or os.getenv("AWS_SESSION_TOKEN")

    model_id = _strip_bedrock_prefix(model)

    kwargs = {
        "model": model_id,
        "region_name": region,
        "temperature": temperature,
        "timeout": _BEDROCK_TIMEOUT,
        "max_retries": _BEDROCK_MAX_RETRIES,
    }
    # langchain-aws reads creds from boto3's chain if not passed explicitly;
    # passing them lets us inject per-request keys from CredentialVault.
    if aws_access_key_id:
        kwargs["aws_access_key_id"] = aws_access_key_id
    if aws_secret_access_key:
        kwargs["aws_secret_access_key"] = aws_secret_access_key
    if aws_session_token:
        kwargs["aws_session_token"] = aws_session_token

    return ChatBedrockConverse(**kwargs)


def build_chat_model(model: str, temperature: float, keys: Any):
    """
    Return a LangChain chat model routed to the right provider for *model*.

    Falls through to a Bedrock default when no matching provider is configured
    but AWS credentials are present.
    """
    model_lc = (model or "").lower()

    if model_lc.startswith("bedrock/"):
        return _build_bedrock(model, temperature, keys)

    if "gemini" in model_lc:
        if getattr(keys, "GEMINI", None):
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=model,
                temperature=temperature,
                google_api_key=keys.GEMINI,
            )
        if _has_aws_creds(keys):
            logger.info(
                "Gemini model %s requested without GEMINI key; routing through Bedrock default %s.",
                model, _BEDROCK_DEFAULT_MODEL,
            )
            return _build_bedrock(f"bedrock/{_BEDROCK_DEFAULT_MODEL}", temperature, keys)
        raise ValueError(
            f"Gemini model {model} requested but no GEMINI/GOOGLE_API_KEY and no AWS credentials found."
        )

    if "claude" in model_lc or "anthropic" in model_lc:
        if getattr(keys, "ANTHROPIC", None):
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=model,
                temperature=temperature,
                anthropic_api_key=keys.ANTHROPIC,
            )
        # Claude without an Anthropic key: use Bedrock if AWS is available.
        if _has_aws_creds(keys):
            logger.info(
                "Claude model %s requested without ANTHROPIC key; routing through Bedrock.",
                model,
            )
            return _build_bedrock(f"bedrock/{_BEDROCK_DEFAULT_MODEL}", temperature, keys)
        raise ValueError(
            f"Claude model {model} requested but no ANTHROPIC_API_KEY and no AWS credentials found."
        )

    if any(k in model_lc for k in ("gpt", "o3", "o1")):
        openai_key = getattr(keys, "OPENAI", None)
        azure_key = getattr(keys, "AZURE_OPENAI_API_KEY", None)
        azure_ep = getattr(keys, "AZURE_OPENAI_ENDPOINT", None)
        azure_dep = getattr(keys, "AZURE_OPENAI_DEPLOYMENT", None)
        azure_ver = getattr(keys, "AZURE_OPENAI_API_VERSION", None)

        if openai_key:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model,
                temperature=temperature,
                openai_api_key=openai_key,
            )
        if azure_key and azure_ep and azure_dep:
            from langchain_openai import AzureChatOpenAI
            return AzureChatOpenAI(
                azure_deployment=azure_dep,
                azure_endpoint=azure_ep,
                api_key=azure_key,
                api_version=azure_ver or "2024-12-01-preview",
                temperature=temperature,
            )
        # OpenAI-style model name but no OpenAI/Azure creds — fall back to Bedrock.
        if _has_aws_creds(keys):
            logger.info(
                "OpenAI-style model %s requested without OPENAI/Azure keys; routing through Bedrock (default=%s).",
                model, _BEDROCK_DEFAULT_MODEL,
            )
            return _build_bedrock(f"bedrock/{_BEDROCK_DEFAULT_MODEL}", temperature, keys)
        raise ValueError(
            "No OpenAI credentials found. Set OPENAI_API_KEY or "
            "AZURE_OPENAI_API_KEY + AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_DEPLOYMENT, "
            "or provide AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY to run on Bedrock."
        )

    # Unknown model family. If AWS creds exist, assume Bedrock; otherwise fail loud.
    if _has_aws_creds(keys):
        logger.info(
            "Unknown model family %s; routing to Bedrock default %s.",
            model, _BEDROCK_DEFAULT_MODEL,
        )
        return _build_bedrock(f"bedrock/{_BEDROCK_DEFAULT_MODEL}", temperature, keys)
    raise ValueError(f"Cannot route model '{model}' — no matching provider credentials configured.")
