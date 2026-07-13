"""Deepresearch Stage 5: Enhanced PDF Report Phase.

Wraps the LangGraph report pipeline in the same Phase/PhaseResult pattern
used by Stage 4 (phases/paper.py).
"""

import logging
import os
import traceback
from dataclasses import dataclass, field
from typing import Any, List, Optional

from cmbagent.phases.base import Phase, PhaseConfig, PhaseContext, PhaseResult, PhaseStatus
from cmbagent.phases.registry import PhaseRegistry

logger = logging.getLogger(__name__)


@dataclass
class DeepresearchReportPhaseConfig(PhaseConfig):
    phase_type: str = "deepresearch_report"

    llm_model: str = "gemini-2.5-flash"
    llm_temperature: float = 0.7
    llm_max_output_tokens: int = 8192

    # Stage routing: "report" = new magazine PDF, "paper" = run Stage-4 pipeline
    pipeline_choice: str = "report"

    parent_run_id: str = ""
    stage_name: str = "report_generation"

    api_keys: Any = None


@PhaseRegistry.register("deepresearch_report")
class DeepresearchReportPhase(Phase):
    """Generate an enhanced magazine-style PDF report using LangGraph."""

    config_class = DeepresearchReportPhaseConfig

    def __init__(self, config: DeepresearchReportPhaseConfig = None):
        if config is None:
            config = DeepresearchReportPhaseConfig()
        super().__init__(config)
        self.config: DeepresearchReportPhaseConfig = config

    @property
    def phase_type(self) -> str:
        return "deepresearch_report"

    @property
    def display_name(self) -> str:
        return "Deepresearch Enhanced Report"

    def get_required_agents(self) -> List[str]:
        return []

    async def execute(self, context: PhaseContext) -> PhaseResult:
        from cmbagent.phases.execution_manager import PhaseExecutionManager
        from task_framework.key_manager import KeyManager
        from task_framework.report_agents.runner import run_report_pipeline

        manager = PhaseExecutionManager(context, self)
        manager.start()

        try:
            work_dir = os.path.abspath(str(context.work_dir))
            context.work_dir = work_dir

            # Resolve keys
            keys = self.config.api_keys
            if keys is None:
                keys = KeyManager()
                keys.get_keys_from_env()
            elif isinstance(keys, dict):
                keys = KeyManager(**keys)

            # Auto-select LLM model based on available credentials
            llm_model = self.config.llm_model
            # If NVIDIA is the active provider (or the only credential present),
            # use Nemotron for Stage 5 too so the whole pipeline is consistent.
            active_provider = os.getenv("CMBAGENT_LLM_PROVIDER", "").strip().lower()
            nvidia_key = getattr(keys, "NVIDIA", None)
            if active_provider == "nvidia" and nvidia_key:
                llm_model = os.getenv(
                    "CMBAGENT_NVIDIA_DEFAULT_MODEL", "nvidia/nemotron-3-super-120b-a12b"
                )
            if "gemini" in llm_model and not getattr(keys, "GEMINI", None):
                if nvidia_key:
                    llm_model = os.getenv(
                        "CMBAGENT_NVIDIA_DEFAULT_MODEL", "nvidia/nemotron-3-super-120b-a12b"
                    )
                elif getattr(keys, "OPENAI", None):
                    llm_model = "gpt-4o"
                elif getattr(keys, "AZURE_OPENAI_API_KEY", None):
                    llm_model = "gpt-4o"
                elif getattr(keys, "ANTHROPIC", None):
                    llm_model = "claude-3-5-sonnet-20241022"
                elif getattr(keys, "AWS_ACCESS_KEY_ID", None):
                    llm_model = "bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0"
                else:
                    raise ValueError(
                        "No LLM credentials found. Set GOOGLE_API_KEY, OPENAI_API_KEY, "
                        "ANTHROPIC_API_KEY, NVIDIA_API_KEY, or AWS credentials."
                    )

            manager.start_step(1, "Generating enhanced report PDF")

            result = await run_report_pipeline(
                work_dir=work_dir,
                llm_model=llm_model,
                llm_temperature=self.config.llm_temperature,
                llm_max_tokens=self.config.llm_max_output_tokens,
                keys=keys,
            )

            if result["status"] != "completed":
                raise RuntimeError(result.get("error") or "Report pipeline failed")

            pdf_path = result["output_pdf_path"]
            manager.complete_step(1, f"Enhanced report generated: {pdf_path}")

            artifacts = {}
            if pdf_path and os.path.exists(pdf_path):
                artifacts[os.path.basename(pdf_path)] = pdf_path

            # Also include any extra files in the report dir
            report_dir = os.path.join(work_dir, "report")
            if os.path.isdir(report_dir):
                for fname in os.listdir(report_dir):
                    if fname.endswith(".pdf") and fname not in artifacts:
                        artifacts[fname] = os.path.join(report_dir, fname)

            return manager.complete(output_data={
                "shared": {
                    "report_dir": report_dir,
                    "report_pdf": pdf_path,
                },
                "artifacts": artifacts,
            })

        except Exception as exc:
            logger.error("report_phase_failed: %s", exc, exc_info=True)
            return manager.fail(str(exc), traceback.format_exc())

    def validate_input(self, context: PhaseContext) -> List[str]:
        errors = []
        input_files_dir = os.path.join(str(context.work_dir), "input_files")
        if not os.path.exists(input_files_dir):
            errors.append(
                "input_files/ directory not found — run idea, method, experiment phases first"
            )
        return errors
