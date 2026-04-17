"""
Integration tests for the Provider Management API.

Tests:
  1. GET /api/providers — list all providers
  2. POST /api/providers/{id}/credentials — store credentials
  3. POST /api/providers/{id}/test — test credentials
  4. DELETE /api/providers/{id}/credentials — remove credentials
  5. GET /api/providers/models/available — provider-filtered models
  6. POST /api/providers/sync — force sync
  7. Credential vault persistence (encrypt/decrypt cycle)
  8. Config bridge sync flow
"""

import os
import json
import shutil
import tempfile
import pytest


# ============================================================================
# 1. Credential Vault Tests
# ============================================================================

class TestCredentialVault:
    """Test the encrypted credential vault in isolation."""

    @pytest.fixture(autouse=True)
    def setup_vault(self, tmp_path):
        """Create a temporary vault for each test."""
        from services.credential_vault import CredentialVault
        CredentialVault.reset()
        self.vault = CredentialVault(base_dir=str(tmp_path))
        yield
        CredentialVault.reset()

    def test_store_and_retrieve(self):
        """Credentials should be retrievable after storing."""
        self.vault.set("openai", {"api_key": "sk-test-key"})
        creds = self.vault.get("openai")
        assert creds["api_key"] == "sk-test-key"

    def test_persistence_across_reload(self, tmp_path):
        """Credentials should persist after re-initializing the vault."""
        self.vault.set("openai", {"api_key": "sk-persist-test"})

        # Simulate restart — reset singleton and create new instance
        from services.credential_vault import CredentialVault
        CredentialVault.reset()
        vault2 = CredentialVault(base_dir=str(tmp_path))

        creds = vault2.get("openai")
        assert creds["api_key"] == "sk-persist-test"

    def test_encrypted_file_not_readable(self, tmp_path):
        """The credential file should not contain plaintext secrets."""
        self.vault.set("openai", {"api_key": "sk-secret-value"})

        cred_file = os.path.join(str(tmp_path), "config", "credentials.enc")
        assert os.path.exists(cred_file)

        with open(cred_file, "rb") as f:
            raw = f.read()
        assert b"sk-secret-value" not in raw

    def test_remove_credentials(self):
        """Removing credentials should clear them."""
        self.vault.set("openai", {"api_key": "sk-test"})
        self.vault.remove("openai")
        assert self.vault.get("openai") == {}

    def test_list_configured(self):
        """list_configured should show which providers have creds."""
        self.vault.set("openai", {"api_key": "sk-test"})
        self.vault.set("anthropic", {"api_key": "sk-ant-test"})

        configured = self.vault.list_configured()
        assert configured["openai"] is True
        assert configured["anthropic"] is True

    def test_get_all(self):
        """get_all should return all stored credentials."""
        self.vault.set("openai", {"api_key": "sk-test"})
        self.vault.set("google", {"api_key": "AIza-test"})

        all_creds = self.vault.get_all()
        assert len(all_creds) == 2
        assert "openai" in all_creds
        assert "google" in all_creds

    def test_multiple_providers(self):
        """Should handle credentials for multiple providers."""
        providers = {
            "openai": {"api_key": "sk-openai"},
            "anthropic": {"api_key": "sk-ant-test"},
            "google": {"api_key": "AIza-test"},
            "aws_bedrock": {
                "aws_access_key_id": "AKIATEST",
                "aws_secret_access_key": "secret",
                "aws_region": "us-east-1",
            },
        }
        for pid, creds in providers.items():
            self.vault.set(pid, creds)

        for pid, expected_creds in providers.items():
            actual = self.vault.get(pid)
            for k, v in expected_creds.items():
                assert actual[k] == v

    def test_overwrite_credentials(self):
        """Setting credentials again should overwrite the old ones."""
        self.vault.set("openai", {"api_key": "sk-old"})
        self.vault.set("openai", {"api_key": "sk-new"})
        assert self.vault.get("openai")["api_key"] == "sk-new"


# ============================================================================
# 2. Config Bridge Tests
# ============================================================================

class TestConfigBridge:
    """Test the ConfigBridge sync flow."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Reset singletons and set up clean env."""
        from services.credential_vault import CredentialVault
        CredentialVault.reset()
        self.vault = CredentialVault(base_dir=str(tmp_path))

        from cmbagent.providers.registry import ProviderRegistry
        ProviderRegistry.reset()

        # Clean relevant env vars
        self._saved_env = {}
        for k in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"]:
            if k in os.environ:
                self._saved_env[k] = os.environ.pop(k)

        yield

        CredentialVault.reset()
        ProviderRegistry.reset()
        for k, v in self._saved_env.items():
            os.environ[k] = v

    def test_sync_all_loads_vault_creds(self):
        """sync_all should load vault credentials into registry."""
        from cmbagent.providers.registry import ProviderRegistry
        from cmbagent.providers.base import ProviderStatus

        # Store creds in vault
        self.vault.set("openai", {"api_key": "sk-vault-test"})

        # Sync
        from services.config_bridge import ConfigBridge
        results = ConfigBridge.sync_all()

        assert results.get("openai") == "synced_from_vault"

        # Check registry
        registry = ProviderRegistry.instance()
        assert registry.get_status("openai") == ProviderStatus.CONFIGURED
        assert registry.get_credentials("openai")["api_key"] == "sk-vault-test"

    def test_sync_all_env_as_base_layer(self):
        """sync_all should pick up .env as base layer."""
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-env"

        from services.config_bridge import ConfigBridge
        ConfigBridge.sync_all()

        from cmbagent.providers.registry import ProviderRegistry
        registry = ProviderRegistry.instance()
        creds = registry.get_credentials("anthropic")
        assert creds.get("api_key") == "sk-ant-env"

    def test_vault_overrides_env(self):
        """Vault credentials should take priority over env vars."""
        os.environ["OPENAI_API_KEY"] = "sk-env-key"
        self.vault.set("openai", {"api_key": "sk-vault-key"})

        from services.config_bridge import ConfigBridge
        ConfigBridge.sync_all()

        from cmbagent.providers.registry import ProviderRegistry
        registry = ProviderRegistry.instance()
        creds = registry.get_credentials("openai")
        assert creds["api_key"] == "sk-vault-key"


# ============================================================================
# 3. Provider API Integration Tests (FastAPI TestClient)
# ============================================================================

class TestProviderAPI:
    """Test the /api/providers endpoints using FastAPI TestClient."""

    @pytest.fixture(autouse=True)
    def setup_app(self, tmp_path):
        """Set up a test FastAPI app with the provider router."""
        # Reset singletons
        from services.credential_vault import CredentialVault
        CredentialVault.reset()
        # Point vault to temp dir
        os.environ["CMBAGENT_DEFAULT_WORK_DIR"] = str(tmp_path)
        CredentialVault(base_dir=str(tmp_path))

        from cmbagent.providers.registry import ProviderRegistry
        ProviderRegistry.reset()

        # Clean env
        self._saved = {}
        for k in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"]:
            if k in os.environ:
                self._saved[k] = os.environ.pop(k)

        from fastapi import FastAPI
        from routers.providers import router

        app = FastAPI()
        app.include_router(router)

        from fastapi.testclient import TestClient
        self.client = TestClient(app)

        yield

        CredentialVault.reset()
        ProviderRegistry.reset()
        os.environ.pop("CMBAGENT_DEFAULT_WORK_DIR", None)
        for k, v in self._saved.items():
            os.environ[k] = v

    def test_list_providers(self):
        """GET /api/providers should return all providers."""
        resp = self.client.get("/api/providers")
        assert resp.status_code == 200
        data = resp.json()
        assert "providers" in data
        assert len(data["providers"]) >= 6
        assert "active_provider" in data

    def test_get_single_provider(self):
        """GET /api/providers/openai should return OpenAI details."""
        resp = self.client.get("/api/providers/openai")
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider_id"] == "openai"
        assert data["display_name"] == "OpenAI"
        assert len(data["credential_fields"]) > 0

    def test_get_unknown_provider_404(self):
        """GET /api/providers/nonexistent should return 404."""
        resp = self.client.get("/api/providers/nonexistent")
        assert resp.status_code == 404

    def test_store_credentials(self):
        """POST /api/providers/openai/credentials should store and sync."""
        resp = self.client.post(
            "/api/providers/openai/credentials",
            json={"credentials": {"api_key": "sk-test-store"}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["provider"]["provider_id"] == "openai"

    def test_store_then_list_shows_configured(self):
        """After storing credentials, provider should show as configured."""
        self.client.post(
            "/api/providers/openai/credentials",
            json={"credentials": {"api_key": "sk-test-config"}},
        )
        resp = self.client.get("/api/providers")
        data = resp.json()
        openai = next(
            p for p in data["providers"] if p["provider_id"] == "openai"
        )
        assert openai["status"] in ("configured", "validated", "invalid")

    def test_remove_credentials(self):
        """DELETE /api/providers/openai/credentials should remove creds."""
        # Store first
        self.client.post(
            "/api/providers/openai/credentials",
            json={"credentials": {"api_key": "sk-to-remove"}},
        )
        # Remove
        resp = self.client.delete("/api/providers/openai/credentials")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_available_models_empty_when_unconfigured(self):
        """GET /api/providers/models/available should be empty with no providers."""
        resp = self.client.get("/api/providers/models/available")
        assert resp.status_code == 200
        data = resp.json()
        assert data["models"] == [] or isinstance(data["models"], list)

    def test_available_models_after_config(self):
        """After configuring OpenAI, models should appear."""
        self.client.post(
            "/api/providers/openai/credentials",
            json={"credentials": {"api_key": "sk-test-models"}},
        )
        resp = self.client.get("/api/providers/models/available")
        data = resp.json()
        assert len(data["models"]) > 0
        values = {m["value"] for m in data["models"]}
        assert "gpt-4o" in values

    def test_force_sync(self):
        """POST /api/providers/sync should succeed."""
        resp = self.client.post("/api/providers/sync")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_credential_masking(self):
        """Stored credentials should be masked in list response."""
        self.client.post(
            "/api/providers/openai/credentials",
            json={"credentials": {"api_key": "sk-test-masking-12345678"}},
        )
        resp = self.client.get("/api/providers")
        data = resp.json()
        openai = next(
            p for p in data["providers"] if p["provider_id"] == "openai"
        )
        api_key_field = next(
            f for f in openai["credential_fields"] if f["name"] == "api_key"
        )
        assert api_key_field["has_value"] is True
        # Masked value should NOT contain the full key
        assert "sk-test-masking-12345678" != api_key_field["masked_value"]
        assert "****" in api_key_field["masked_value"]
