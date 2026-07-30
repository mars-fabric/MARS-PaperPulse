"""
End-to-end tests for the deepresearch stage pipeline.

Covers:
  1. Stage 4 null-output guard — a failed paper generation is marked "failed",
     not silently "completed" with empty artifacts.
  2. No API keys in Langfuse traces — DynamicSessionProcessor / SessionAttributeProcessor
     redact input.value, output.value, and KeyManager repr never exposes key values.
  3. Session grouping — all stages (1-5) emit spans with the same session.id
     (task_id), but only root spans get langfuse.trace.name.
  4. Azure credential routing — KeyManager.get_keys_from_vault() prefers vault
     credentials over os.environ, allowing per-user Azure key overrides.
  5. Trace context propagation — ContextVar values set by set_task_trace_context
     are visible inside asyncio tasks and threading.Thread workers.
"""

import asyncio
import os
import sys
import threading
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

# Ensure backend is importable
BACKEND_DIR = os.path.dirname(os.path.dirname(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


# ──────────────────────────────────────────────────────────────────────────────
# 1. Stage 4 null-output guard
# ──────────────────────────────────────────────────────────────────────────────

class TestStage4NullGuard:
    """paper.py must raise when graph.ainvoke() produces no output files."""

    def _make_context(self, tmp_path):
        from cmbagent.phases.base import PhaseContext
        work_dir = str(tmp_path)
        # Create minimal input_files structure so validate_input passes
        input_dir = tmp_path / "input_files"
        input_dir.mkdir()
        (input_dir / "idea.md").write_text("test idea")
        (input_dir / "methods.md").write_text("test methods")
        (input_dir / "results.md").write_text("test results")
        (input_dir / "plots").mkdir()
        return PhaseContext(
            workflow_id="wf-test",
            run_id="task-test",
            phase_id="stage-4",
            task="test task",
            work_dir=work_dir,
        )

    @pytest.mark.asyncio
    async def test_fails_when_no_paper_files_produced(self, tmp_path):
        """If ainvoke() runs without creating paper/*.tex, phase must FAIL."""
        from task_framework.phases.paper import DeepresearchPaperPhase, DeepresearchPaperPhaseConfig
        from cmbagent.phases.base import PhaseStatus

        context = self._make_context(tmp_path)

        # Mock graph so ainvoke() completes without writing any .tex files
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(return_value={})

        with patch("task_framework.paper_agents.agents_graph.build_graph", return_value=mock_graph):
            phase = DeepresearchPaperPhase(DeepresearchPaperPhaseConfig(parent_run_id="task-test"))
            result = await phase.execute(context)

        assert result.status == PhaseStatus.FAILED
        assert result.error is not None
        assert "no output files" in result.error.lower() or "paper" in result.error.lower()

    @pytest.mark.asyncio
    async def test_succeeds_when_tex_file_exists(self, tmp_path):
        """If ainvoke() writes a .tex file, phase must return COMPLETED."""
        from task_framework.phases.paper import DeepresearchPaperPhase, DeepresearchPaperPhaseConfig
        from task_framework.config import PAPER_FOLDER
        from cmbagent.phases.base import PhaseStatus

        context = self._make_context(tmp_path)

        # Create paper dir and a .tex file so the existence check passes
        paper_dir = tmp_path / PAPER_FOLDER
        paper_dir.mkdir()
        (paper_dir / "paper_v1_preliminary.tex").write_text("\\documentclass{article}")

        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(return_value={})

        with patch("task_framework.paper_agents.agents_graph.build_graph", return_value=mock_graph):
            phase = DeepresearchPaperPhase(DeepresearchPaperPhaseConfig(parent_run_id="task-test"))
            result = await phase.execute(context)

        assert result.status == PhaseStatus.COMPLETED
        assert "paper_v1_preliminary.tex" in result.output_data.get("artifacts", {})


# ──────────────────────────────────────────────────────────────────────────────
# 2. No API keys in Langfuse traces
# ──────────────────────────────────────────────────────────────────────────────

class TestApiKeyRedaction:
    """Span processors must never emit API key values in span attributes."""

    def test_dynamic_session_processor_redacts_input_value(self):
        """DynamicSessionProcessor.on_end() strips input.value."""
        from services.tracing_bridge import DynamicSessionProcessor

        span = MagicMock()
        span._attributes = {
            "input.value": '{"keys": {"AZURE_OPENAI_API_KEY": "secret-azure-key-12345"}}',
            "output.value": "paper text",
            "span.name": "preprocess_node",
        }
        proc = DynamicSessionProcessor()
        with patch.dict(os.environ, {"MARS_TRACING_REDACT": "prompts"}):
            proc.on_end(span)

        assert span._attributes["input.value"] == "<redacted>"
        assert span._attributes["output.value"] == "<redacted>"
        assert span._attributes["span.name"] == "preprocess_node"  # untouched

    def test_dynamic_session_processor_no_redaction_when_none(self):
        """With MARS_TRACING_REDACT=none, attributes are preserved."""
        from services.tracing_bridge import DynamicSessionProcessor

        original = '{"keys": "val"}'
        span = MagicMock()
        span._attributes = {"input.value": original}
        proc = DynamicSessionProcessor()
        with patch.dict(os.environ, {"MARS_TRACING_REDACT": "none"}):
            proc.on_end(span)

        assert span._attributes["input.value"] == original

    def test_dynamic_session_processor_redacts_gen_ai_prompts(self):
        """gen_ai.prompt.* attributes are redacted (existing behaviour preserved)."""
        from services.tracing_bridge import DynamicSessionProcessor

        span = MagicMock()
        span._attributes = {
            "gen_ai.prompt.0.content": "my secret prompt",
            "gen_ai.completion.0.content": "model answer",
            "task_id": "abc",
        }
        proc = DynamicSessionProcessor()
        with patch.dict(os.environ, {"MARS_TRACING_REDACT": "prompts"}):
            proc.on_end(span)

        assert span._attributes["gen_ai.prompt.0.content"] == "<redacted>"
        assert span._attributes["gen_ai.completion.0.content"] == "<redacted>"
        assert span._attributes["task_id"] == "abc"  # non-secret preserved

    def test_key_manager_repr_does_not_expose_keys(self):
        """KeyManager.__repr__ / __str__ must not include actual key values."""
        from task_framework.key_manager import KeyManager

        km = KeyManager(
            OPENAI="sk-secret-openai",
            AZURE_OPENAI_API_KEY="azure-secret-key",
            ANTHROPIC="sk-ant-secret",
            GEMINI="AIza-secret",
        )
        r = repr(km)
        s = str(km)

        for secret in ("sk-secret-openai", "azure-secret-key", "sk-ant-secret", "AIza-secret"):
            assert secret not in r, f"repr exposed {secret!r}"
            assert secret not in s, f"str exposed {secret!r}"

        # Provider names (without values) may appear
        assert "OPENAI" in r or "providers" in r.lower()

    def test_session_attribute_processor_redacts_input_output_value(self):
        """SessionAttributeProcessor in cmbagent/tracing.py covers input.value."""
        import cmbagent.tracing as _t

        # Build a real SessionAttributeProcessor via the private factory
        with patch.dict(os.environ, {"MARS_TRACING_REDACT": "prompts"}):
            proc = _t._build_session_processor("sess-1", "trace-1")

        span = MagicMock()
        span._attributes = {
            "input.value": '{"keys": {"OPENAI": "sk-secret"}}',
            "output.value": "paper result",
            "safe_attr": "keep me",
        }
        proc.on_end(span)

        assert span._attributes["input.value"] == "<redacted>"
        assert span._attributes["output.value"] == "<redacted>"
        assert span._attributes["safe_attr"] == "keep me"


# ──────────────────────────────────────────────────────────────────────────────
# 3. Session grouping — only root spans get langfuse.trace.name
# ──────────────────────────────────────────────────────────────────────────────

class TestSessionGrouping:
    """All stages share session.id = task_id; trace name only on root spans."""

    def _make_span(self, has_valid_parent: bool):
        span = MagicMock()
        if has_valid_parent:
            span.parent = MagicMock(is_valid=True)
        else:
            span.parent = None
        return span

    def test_root_span_gets_session_id_and_trace_name(self):
        from services.tracing_bridge import (
            DynamicSessionProcessor, _session_id_var, _trace_name_var, _user_id_var,
        )

        t1 = _session_id_var.set("task-session-001")
        t2 = _trace_name_var.set("stage1_idea_generation_task-session-001")
        t3 = _user_id_var.set("user-abc")
        try:
            span = self._make_span(has_valid_parent=False)
            DynamicSessionProcessor().on_start(span)
        finally:
            _session_id_var.reset(t1)
            _trace_name_var.reset(t2)
            _user_id_var.reset(t3)

        calls = {c.args[0]: c.args[1] for c in span.set_attribute.call_args_list}
        assert calls["session.id"] == "task-session-001"
        assert calls["langfuse.trace.name"] == "stage1_idea_generation_task-session-001"
        assert calls["user.id"] == "user-abc"

    def test_child_span_gets_session_id_but_not_trace_name(self):
        """LangChain child spans must NOT get langfuse.trace.name."""
        from services.tracing_bridge import (
            DynamicSessionProcessor, _session_id_var, _trace_name_var, _user_id_var,
        )

        t1 = _session_id_var.set("task-session-002")
        t2 = _trace_name_var.set("stage4_paper_generation_task-session-002")
        t3 = _user_id_var.set("user-xyz")
        try:
            span = self._make_span(has_valid_parent=True)
            DynamicSessionProcessor().on_start(span)
        finally:
            _session_id_var.reset(t1)
            _trace_name_var.reset(t2)
            _user_id_var.reset(t3)

        set_calls = {c.args[0]: c.args[1] for c in span.set_attribute.call_args_list}
        assert set_calls["session.id"] == "task-session-002"
        assert "langfuse.trace.name" not in set_calls, (
            "Child span must not receive langfuse.trace.name — it would split into a separate trace"
        )

    def test_all_stages_use_same_session_id_from_task_id(self):
        """build_trace_name keeps task_id consistent; session.id == task_id."""
        from services.tracing_bridge import build_trace_name

        task_id = "task-abc-123"
        for stage_num, name in enumerate(
            ["idea_generation", "method_development", "experiment_execution",
             "paper_generation", "report_generation"], start=1
        ):
            trace_name = build_trace_name(task_id, stage_num, name)
            assert trace_name.startswith(f"stage{stage_num}_")
            assert trace_name.endswith(task_id)


# ──────────────────────────────────────────────────────────────────────────────
# 4. Azure credential routing via vault
# ──────────────────────────────────────────────────────────────────────────────

class TestAzureVaultRouting:
    """Vault credentials override env vars so per-user Azure keys work."""

    def test_vault_azure_key_overrides_env(self):
        from task_framework.key_manager import KeyManager

        vault_creds = {
            "azure_openai": {
                "api_key": "vault-azure-key-9999",
                "endpoint": "https://vault-endpoint.openai.azure.com",
                "deployment": "vault-deployment",
                "api_version": "2024-12-01-preview",
            }
        }

        mock_vault = MagicMock()
        mock_vault.get = lambda provider_id, *a, **kw: vault_creds.get(provider_id, {})

        with patch.dict(os.environ, {
            "AZURE_OPENAI_API_KEY": "env-azure-key-old",
            "AZURE_OPENAI_ENDPOINT": "https://env-endpoint.openai.azure.com",
            "AZURE_OPENAI_DEPLOYMENT": "env-deployment",
        }, clear=False):
            with patch("services.credential_vault.CredentialVault", return_value=mock_vault):
                km = KeyManager()
                km.get_keys_from_vault()

        assert km.AZURE_OPENAI_API_KEY == "vault-azure-key-9999"
        assert km.AZURE_OPENAI_ENDPOINT == "https://vault-endpoint.openai.azure.com"
        assert km.AZURE_OPENAI_DEPLOYMENT == "vault-deployment"

    def test_env_used_as_fallback_when_vault_empty(self):
        """When vault has no Azure entry, env var is used."""
        from task_framework.key_manager import KeyManager

        mock_vault = MagicMock()
        mock_vault.get = lambda *a, **kw: {}

        with patch.dict(os.environ, {"AZURE_OPENAI_API_KEY": "env-fallback-key"}, clear=False):
            with patch("services.credential_vault.CredentialVault", return_value=mock_vault):
                km = KeyManager()
                km.get_keys_from_vault()

        assert km.AZURE_OPENAI_API_KEY == "env-fallback-key"

    def test_vault_unavailable_falls_back_to_env(self):
        """If CredentialVault raises, env vars are still used as fallback."""
        from task_framework.key_manager import KeyManager

        mock_vault = MagicMock()
        mock_vault.get = MagicMock(side_effect=Exception("vault unavailable"))

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env-openai"}, clear=False):
            with patch("services.credential_vault.CredentialVault", return_value=mock_vault):
                km = KeyManager()
                km.get_keys_from_vault()

        assert km.OPENAI == "sk-env-openai"


# ──────────────────────────────────────────────────────────────────────────────
# 5. Trace context propagation across asyncio tasks and threads
# ──────────────────────────────────────────────────────────────────────────────

class TestTraceContextPropagation:
    """set_task_trace_context values must reach asyncio tasks and worker threads."""

    @pytest.mark.asyncio
    async def test_context_visible_in_asyncio_task(self):
        from services.tracing_bridge import (
            set_task_trace_context, clear_task_trace_context,
            _session_id_var, _trace_name_var,
        )

        captured = {}

        async def _inner():
            captured["session_id"] = _session_id_var.get()
            captured["trace_name"] = _trace_name_var.get()

        tokens = set_task_trace_context("task-async-1", "user-1",
                                         stage_num=2, stage_name="method_development")
        # asyncio.create_task inherits the current context snapshot
        await asyncio.create_task(_inner())
        clear_task_trace_context(tokens)

        assert captured["session_id"] == "task-async-1"
        assert "stage2_method_development" in captured["trace_name"]

    def test_context_visible_in_worker_thread(self):
        import contextvars
        from services.tracing_bridge import (
            set_task_trace_context, clear_task_trace_context,
            _session_id_var,
        )

        captured = {}

        def worker():
            captured["session_id"] = _session_id_var.get()

        tokens = set_task_trace_context("task-thread-1", "user-thread")
        ctx = contextvars.copy_context()
        t = threading.Thread(target=ctx.run, args=(worker,))
        t.start()
        t.join()
        clear_task_trace_context(tokens)

        assert captured["session_id"] == "task-thread-1"

    def test_stage_trace_names_are_unique_per_stage(self):
        """Each stage produces a distinct trace_name but the same session_id."""
        from services.tracing_bridge import build_trace_name, set_task_trace_context, clear_task_trace_context, get_task_trace_context

        task_id = "task-multi-stage"
        seen_trace_names = set()

        for stage_num in range(1, 6):
            stage_name = ["idea_generation", "method_development", "experiment_execution",
                           "paper_generation", "report_generation"][stage_num - 1]
            tokens = set_task_trace_context(task_id, "user-x",
                                             stage_num=stage_num, stage_name=stage_name)
            ctx = get_task_trace_context()
            assert ctx["session_id"] == task_id, "session.id must always equal task_id"
            seen_trace_names.add(ctx["trace_name"])
            clear_task_trace_context(tokens)

        assert len(seen_trace_names) == 5, "Each stage must generate a unique trace name"


# ──────────────────────────────────────────────────────────────────────────────
# 6. Stage 4 DB persist path — output_data stored correctly
# ──────────────────────────────────────────────────────────────────────────────

class TestStage4DbPersist:
    """When paper phase completes, _run_paper_stage writes output_data to DB."""

    @pytest.mark.asyncio
    async def test_completed_stage_has_nonempty_output_data(self, tmp_path):
        """PhaseExecutionManager.complete() must set context.output_data."""
        from cmbagent.phases.base import PhaseContext, PhaseStatus
        from cmbagent.phases.execution_manager import PhaseExecutionManager
        from task_framework.phases.paper import DeepresearchPaperPhase, DeepresearchPaperPhaseConfig
        from task_framework.config import PAPER_FOLDER

        input_dir = tmp_path / "input_files"
        input_dir.mkdir()
        for f in ("idea.md", "methods.md", "results.md"):
            (input_dir / f).write_text("content")
        (input_dir / "plots").mkdir()

        paper_dir = tmp_path / PAPER_FOLDER
        paper_dir.mkdir()
        tex_file = paper_dir / "paper_v1_preliminary.tex"
        tex_file.write_text("\\documentclass{article}")

        context = PhaseContext(
            workflow_id="wf-1",
            run_id="task-persist-1",
            phase_id="stage-4",
            task="Test paper task",
            work_dir=str(tmp_path),
        )

        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(return_value={})

        with patch("task_framework.paper_agents.agents_graph.build_graph", return_value=mock_graph):
            phase = DeepresearchPaperPhase(DeepresearchPaperPhaseConfig(parent_run_id="task-persist-1"))
            result = await phase.execute(context)

        assert result.status == PhaseStatus.COMPLETED
        assert result.output_data  # not empty
        assert result.context.output_data  # also accessible via context
        assert "paper_v1_preliminary.tex" in result.output_data.get("artifacts", {})
        assert result.output_data["shared"]["paper_tex"] == str(tex_file)
