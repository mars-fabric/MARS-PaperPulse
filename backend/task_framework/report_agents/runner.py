"""Async entry-point for the Stage 5 report pipeline."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from services.tracing_bridge import filter_langchain_callbacks as _filter_langchain_callbacks

logger = logging.getLogger(__name__)

# Path to images_to_use/ resolved relative to this file at import time
_THIS_DIR = os.path.dirname(__file__)            # report_agents/
_BACKEND  = os.path.dirname(os.path.dirname(_THIS_DIR))  # backend/
_APP_ROOT = os.path.dirname(os.path.dirname(_BACKEND))   # MARS_APP/
DEFAULT_IMAGES_DIR = os.path.join(_APP_ROOT, "images_to_use")


async def run_report_pipeline(
    work_dir: str,
    llm_model: str = "gemini-2.5-flash",
    llm_temperature: float = 0.7,
    llm_max_tokens: int = 8192,
    keys: Any = None,
    images_dir: str = "",
    callbacks: Any = None,  # ← ACCEPT CALLBACKS FOR TRACING
) -> Dict[str, Any]:
    """Run the full Stage 5 report pipeline and return a result dict.

    Returns:
        {
            "status": "completed" | "failed",
            "output_pdf_path": str,
            "error": str | None,
        }
    """
    from .graph import build_report_graph

    images_dir = images_dir or DEFAULT_IMAGES_DIR

    initial_state = {
        "work_dir":       work_dir,
        "images_dir":     images_dir,
        "report_dir":     os.path.join(work_dir, "report"),
        "llm_model":      llm_model,
        "llm_temperature": llm_temperature,
        "llm_max_tokens": llm_max_tokens,
        "keys":           keys,
        # Raw content — filled by load_content_node
        "raw_title":      "",
        "raw_idea":       "",
        "raw_methods":    "",
        "raw_results":    "",
        "raw_conclusions": "",
        "raw_abstract":   "",
        # Filled by later nodes
        "report_title":   "",
        "about_cards":    [],
        "sections":       [],
        "toc_entries":    [],
        "output_pdf_path": "",
        "error":          None,
    }

    langgraph_config = {
        "configurable": {"thread_id": "report-stage5"},
        "recursion_limit": 50,
    }

    # NOTE: cmbagent's ``WorkflowCallbacks`` is NOT a LangChain callback handler
    # and must never be placed in ``config["callbacks"]`` — LangGraph/LangChain
    # expect BaseCallbackHandler instances there and will raise
    # ``AttributeError: 'WorkflowCallbacks' object has no attribute 'parent_run_id'``.
    # Stage 4-5 LLM calls are traced to Langfuse via the global OpenInference
    # LangChain instrumentor (see services/tracing_bridge.instrument_langchain),
    # so no per-invocation callback injection is required here. Only forward
    # genuine LangChain BaseCallbackHandler instances if any are provided.
    lc_callbacks = _filter_langchain_callbacks(callbacks)
    if lc_callbacks:
        langgraph_config["callbacks"] = lc_callbacks

    try:
        graph = build_report_graph()
        final_state = await graph.ainvoke(initial_state, langgraph_config)

        pdf_path = final_state.get("output_pdf_path", "")
        error    = final_state.get("error")

        if pdf_path and os.path.exists(pdf_path) and not error:
            return {"status": "completed", "output_pdf_path": pdf_path, "error": None}
        else:
            return {
                "status": "failed",
                "output_pdf_path": pdf_path,
                "error": error or "PDF not found after pipeline execution",
            }
    except Exception as exc:
        logger.error("report_pipeline_exception error=%s", exc, exc_info=True)
        return {"status": "failed", "output_pdf_path": "", "error": str(exc)}
