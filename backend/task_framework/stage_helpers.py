"""
Stage-specific helpers for Deepresearch stages 1-3.

Pure functions that handle prompt formatting, result extraction,
post-processing, file I/O, and output structuring for each stage.
Called directly from the router -- no Phase subclasses needed.
"""

import os
import re
import json
import shutil
import logging
import mimetypes
from typing import List, Tuple, Optional

from task_framework.config import (
    INPUT_FILES, IDEA_FILE, METHOD_FILE, RESULTS_FILE, PLOTS_FOLDER,
)
from task_framework.utils import (
    get_task_result, create_work_dir, extract_clean_markdown,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Stage 3 — Artifact manifest
# ═══════════════════════════════════════════════════════════════════════════

# Subdir cmbagent's experiment phase writes into. Mirrors create_work_dir(..., "experiment").
EXPERIMENT_SUBDIR = "experiment_generation_output"
ARTIFACT_MANIFEST_FILE = "artifact_manifest.json"

# Files we never expose: binary internals, caches, sentinel files.
_ARTIFACT_SKIP_NAMES = {ARTIFACT_MANIFEST_FILE}
_ARTIFACT_SKIP_EXTS = {".pyc", ".pkl"}
_ARTIFACT_SKIP_DIR_NAMES = {"__pycache__", ".ipynb_checkpoints"}

# Category → file extensions. The directory the file lives in *also* shapes the
# classification (chats/ → chats, planning/ → planning), so a .json under
# control/chats/ is correctly labelled instead of being lumped into "data".
_PLOT_EXTS    = {".png", ".jpg", ".jpeg", ".pdf", ".svg", ".gif"}
_CODE_EXTS    = {".py", ".ipynb", ".sh", ".r", ".jl"}
_DATA_EXTS    = {".csv", ".tsv", ".json", ".jsonl", ".parquet",
                 ".npy", ".npz", ".h5", ".hdf5", ".feather", ".arrow", ".xml", ".yaml", ".yml"}
_REPORT_EXTS  = {".html", ".htm", ".txt", ".log", ".tex"}
_RESULTS_EXTS = {".md"}


def _classify_artifact(rel_root: str, fname: str, ext: str) -> Optional[str]:
    """Decide which category a file belongs to (or None to skip).

    rel_root is path relative to ``experiment_generation_output``.
    """
    if fname in _ARTIFACT_SKIP_NAMES or ext in _ARTIFACT_SKIP_EXTS:
        return None

    rel_root_norm = rel_root.replace("\\", "/").strip("/").lower()
    parts = rel_root_norm.split("/") if rel_root_norm and rel_root_norm != "." else []

    # Directory-scoped categories (these win over extension-only matching)
    if "chats" in parts:
        return "chats"
    if "planning" in parts:
        return "planning"
    if "plots" in parts:
        return "plots"

    # Extension-driven categorisation
    if ext in _PLOT_EXTS:
        return "plots"
    if ext in _CODE_EXTS:
        return "code"
    if ext in _RESULTS_EXTS:
        return "results"
    if ext in _DATA_EXTS:
        return "data"
    if ext in _REPORT_EXTS:
        return "reports"

    return None  # unknown → skip; bumps to "other" only via include_other flag


_STEP_RE = re.compile(r"step[_-]?(\d+)", re.IGNORECASE)


def _parse_step(fname: str) -> Optional[int]:
    """Extract the step index from filenames like ``chat_history_step_3.json``."""
    m = _STEP_RE.search(fname)
    return int(m.group(1)) if m else None


def collect_experiment_artifacts(work_dir: str) -> dict:
    """Walk Stage-3 output locations and return a categorized manifest.

    Stage 3 writes to two places under ``work_dir``:
      * ``experiment_generation_output/`` — cmbagent's planning + control phase
        scratch, code, intermediate data, chat transcripts, plan JSON.
      * ``input_files/results.md`` and ``input_files/plots/`` — the extracted
        final markdown and the figures lifted out of ``displayed_images`` by
        ``save_experiment``. These are the user-facing deliverables and live
        as siblings of ``experiment_generation_output/``, not inside it.

    ``rel_path`` is computed relative to ``work_dir`` so entries from both
    locations share a single, unambiguous root.

    Skips: __pycache__, hidden files, .pkl context dumps, the manifest itself.
    Returns empty manifest if the work dir doesn't exist — keeps the API
    shape stable for failed runs.
    """
    work_dir = str(work_dir)
    manifest: dict[str, list] = {
        "results":  [],
        "plots":    [],
        "code":     [],
        "data":     [],
        "reports":  [],
        "chats":    [],
        "planning": [],
    }

    def _emit(full: str, category: Optional[str]) -> None:
        if category is None:
            return
        try:
            stat = os.stat(full)
        except OSError:
            return
        fname = os.path.basename(full)
        manifest[category].append({
            "name":     fname,
            "path":     os.path.realpath(full),
            "rel_path": os.path.relpath(full, work_dir),
            "size":     stat.st_size,
            "mime":     mimetypes.guess_type(fname)[0] or "application/octet-stream",
            "step":     _parse_step(fname),
            "modified": stat.st_mtime,
        })

    # 1) cmbagent's experiment subdir — code, data, chats, planning, intermediate plots
    base = os.path.join(work_dir, EXPERIMENT_SUBDIR)
    if os.path.isdir(base):
        for root, dirs, files in os.walk(base):
            dirs[:] = [
                d for d in dirs
                if not d.startswith(".") and d not in _ARTIFACT_SKIP_DIR_NAMES
            ]
            rel_root = os.path.relpath(root, base)
            for fname in sorted(files):
                if fname.startswith("."):
                    continue
                ext = os.path.splitext(fname)[1].lower()
                _emit(os.path.join(root, fname), _classify_artifact(rel_root, fname, ext))

    # 2) The two final Stage-3 deliverables that save_experiment writes outside
    #    experiment_generation_output/. Without these the manifest is missing
    #    the actual results.md and plot PNG/PDFs the user came here to see.
    input_files_dir = os.path.join(work_dir, "input_files")
    results_md = os.path.join(input_files_dir, "results.md")
    if os.path.isfile(results_md):
        _emit(results_md, "results")
    plots_dir = os.path.join(input_files_dir, "plots")
    if os.path.isdir(plots_dir):
        for fname in sorted(os.listdir(plots_dir)):
            if fname.startswith("."):
                continue
            full = os.path.join(plots_dir, fname)
            if os.path.isfile(full):
                _emit(full, "plots")

    # Sort chats and planning by step where present, else by name
    manifest["chats"].sort(key=lambda a: (a.get("step") if a.get("step") is not None else 1_000_000, a["name"]))
    manifest["planning"].sort(key=lambda a: a["name"])
    return manifest


def write_artifact_manifest(work_dir: str, manifest: dict) -> str:
    """Persist the artifact manifest to disk for audit/replay. Returns the path.

    Best-effort: failure to write is logged but not raised — the in-memory
    manifest still flows through to the DB and API response.
    """
    base = os.path.join(str(work_dir), EXPERIMENT_SUBDIR)
    try:
        os.makedirs(base, exist_ok=True)
    except OSError as exc:
        logger.warning("artifact_manifest_mkdir_failed dir=%s error=%s", base, exc)
        return ""

    manifest_path = os.path.join(base, ARTIFACT_MANIFEST_FILE)
    try:
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2, default=str)
    except OSError as exc:
        logger.warning("artifact_manifest_write_failed path=%s error=%s", manifest_path, exc)
        return ""
    return manifest_path


# ─── Default model assignments — loaded from model_config.yaml via registry ──

# Non-model execution defaults for the experiment stage (not model names)
_EXPERIMENT_EXEC_DEFAULTS = {
    "involved_agents": ["engineer", "researcher"],
    "max_n_attempts": 10,
    "max_n_steps": 6,
    "restart_at_step": -1,
    "hardware_constraints": "",
}


def _get_idea_defaults() -> dict:
    from cmbagent.config.model_registry import get_model_registry
    return get_model_registry().get_stage_defaults("deepresearch", 1)


def _get_method_defaults() -> dict:
    from cmbagent.config.model_registry import get_model_registry
    return get_model_registry().get_stage_defaults("deepresearch", 2)


def _get_experiment_defaults() -> dict:
    from cmbagent.config.model_registry import get_model_registry
    return {
        **_EXPERIMENT_EXEC_DEFAULTS,
        **get_model_registry().get_stage_defaults("deepresearch", 3),
    }


# ═══════════════════════════════════════════════════════════════════════════
# Stage 1 — Idea Generation
# ═══════════════════════════════════════════════════════════════════════════

def build_idea_kwargs(
    data_description: str,
    work_dir: str,
    api_keys: dict | None = None,
    parent_run_id: str | None = None,
    config_overrides: dict | None = None,
    callbacks=None,
) -> dict:
    """Build kwargs dict for planning_and_control_context_carryover (idea stage).

    The returned dict includes 'task' as a key; the caller should pop it
    and pass it as the first positional argument.
    """
    from task_framework.prompts.deepresearch.idea import idea_planner_prompt

    cfg = {**_get_idea_defaults(), **(config_overrides or {})}
    idea_dir = create_work_dir(work_dir, "idea")

    return dict(
        task=data_description,
        n_plan_reviews=1,
        max_plan_steps=6,
        idea_maker_model=cfg["idea_maker_model"],
        idea_hater_model=cfg["idea_hater_model"],
        plan_instructions=idea_planner_prompt,
        planner_model=cfg["planner_model"],
        plan_reviewer_model=cfg["plan_reviewer_model"],
        work_dir=str(idea_dir),
        api_keys=api_keys,
        default_llm_model=cfg["orchestration_model"],
        default_formatter_model=cfg["formatter_model"],
        parent_run_id=parent_run_id,
        stage_name="idea_generation",
        callbacks=callbacks,
    )


def extract_idea_result(results: dict) -> str:
    """Extract and post-process idea from chat_history.

    Tries ``idea_maker`` first (actual content agent), then
    ``idea_maker_nest`` (wrapper — usually has empty content).
    Falls back to scanning all idea-related agents for the longest
    non-empty message if the primary agents return nothing.
    """
    chat_history = results["chat_history"]

    # Try idea_maker first (actual content), then nest wrapper
    task_result = ""
    for agent_name in ("idea_maker", "idea_maker_nest"):
        try:
            candidate = get_task_result(chat_history, agent_name)
            if candidate and candidate.strip():
                task_result = candidate
                break
        except ValueError:
            continue

    # Broader fallback: scan ALL messages from idea-related agents,
    # pick the longest non-empty content (likely the final refined idea)
    if not task_result:
        logger.warning("Primary idea extraction failed, scanning all idea-related messages")
        best = ""
        for msg in chat_history:
            name = msg.get("name", "")
            content = msg.get("content", "")
            if name and "idea_maker" in name and content and content.strip():
                if len(content) > len(best):
                    best = content
        if best:
            task_result = best
            logger.info("Recovered idea from broad scan, length=%d", len(best))

    if not task_result:
        # Log available agent names for debugging
        agent_names = [msg.get("name", "<no name>") for msg in chat_history if msg.get("name")]
        logger.error(
            "Idea extraction failed. Agents in chat_history: %s",
            list(set(agent_names)),
        )
        raise ValueError(
            "Neither 'idea_maker' nor 'idea_maker_nest' found with content in chat history. "
            f"Available agents: {list(set(agent_names))}"
        )

    logger.info("Extracted idea, length=%d", len(task_result))

    # Post-processing regex from original idea.py:82-84
    pattern = r'\*\*Ideas\*\*\s*\n- Idea 1:'
    replacement = "Project Idea:"
    return re.sub(pattern, replacement, task_result)


def save_idea(research_idea: str, work_dir: str) -> str:
    """Write idea.md to input_files/ and return the file path."""
    input_files_dir = os.path.join(str(work_dir), INPUT_FILES)
    os.makedirs(input_files_dir, exist_ok=True)
    idea_path = os.path.join(input_files_dir, IDEA_FILE)
    with open(idea_path, "w") as f:
        f.write(research_idea)
    logger.info("Saved idea to %s, length=%d", idea_path, len(research_idea))
    return idea_path


def build_idea_output(
    research_idea: str,
    data_description: str,
    idea_path: str,
    chat_history: list,
) -> dict:
    """Build the output_data dict for DB storage (idea stage)."""
    return {
        "shared": {
            "research_idea": research_idea,
            "data_description": data_description,
        },
        "artifacts": {
            "idea.md": idea_path,
        },
        "chat_history": chat_history,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Stage 2 — Method Development
# ═══════════════════════════════════════════════════════════════════════════

def build_method_kwargs(
    data_description: str,
    research_idea: str,
    work_dir: str,
    api_keys: dict | None = None,
    parent_run_id: str | None = None,
    config_overrides: dict | None = None,
    callbacks=None,
) -> dict:
    """Build kwargs dict for planning_and_control_context_carryover (method stage)."""
    from task_framework.prompts.deepresearch.method import (
        method_planner_prompt,
        method_researcher_prompt,
    )

    cfg = {**_get_method_defaults(), **(config_overrides or {})}
    method_dir = create_work_dir(work_dir, "method")

    return dict(
        task=data_description,
        n_plan_reviews=1,
        max_n_attempts=4,
        max_plan_steps=4,
        researcher_model=cfg["researcher_model"],
        planner_model=cfg["planner_model"],
        plan_reviewer_model=cfg["plan_reviewer_model"],
        plan_instructions=method_planner_prompt.format(research_idea=research_idea),
        researcher_instructions=method_researcher_prompt.format(research_idea=research_idea),
        work_dir=str(method_dir),
        api_keys=api_keys,
        default_llm_model=cfg["orchestration_model"],
        default_formatter_model=cfg["formatter_model"],
        parent_run_id=parent_run_id,
        stage_name="method_development",
        callbacks=callbacks,
    )


def extract_method_result(results: dict) -> str:
    """Extract and post-process methodology from chat_history.

    Tries ``researcher_response_formatter`` first; falls back to
    ``researcher`` if the formatter returned empty content.
    As a last resort, scans all messages for the longest non-empty
    content from any agent.
    """
    chat_history = results["chat_history"]

    task_result = ""
    for agent_name in ("researcher", "researcher_response_formatter"):
        try:
            candidate = get_task_result(chat_history, agent_name)
            if candidate and candidate.strip():
                task_result = candidate
                break
        except ValueError:
            continue

    # Broader fallback: scan ALL messages for longest non-empty content
    if not task_result:
        logger.warning("Primary method extraction failed, scanning all messages")
        best = ""
        for msg in chat_history:
            name = msg.get("name", "")
            content = msg.get("content", "")
            if name and content and content.strip():
                if len(content) > len(best):
                    best = content
        if best:
            task_result = best
            logger.info("Recovered method result from broad scan, length=%d", len(best))

    if not task_result:
        agent_names = [msg.get("name", "<no name>") for msg in chat_history if msg.get("name")]
        logger.error(
            "Method extraction failed. Agents in chat_history: %s",
            list(set(agent_names)),
        )
        raise ValueError(
            "No agent found with content in chat history for methodology. "
            f"Available agents: {list(set(agent_names))}"
        )

    return extract_clean_markdown(task_result)


def save_method(methodology: str, work_dir: str) -> str:
    """Write methods.md to input_files/ and return the file path."""
    input_files_dir = os.path.join(str(work_dir), INPUT_FILES)
    os.makedirs(input_files_dir, exist_ok=True)
    methods_path = os.path.join(input_files_dir, METHOD_FILE)
    with open(methods_path, "w") as f:
        f.write(methodology)
    return methods_path


def build_method_output(
    research_idea: str,
    data_description: str,
    methodology: str,
    methods_path: str,
    chat_history: list,
) -> dict:
    """Build the output_data dict for DB storage (method stage)."""
    return {
        "shared": {
            "research_idea": research_idea,
            "data_description": data_description,
            "methodology": methodology,
        },
        "artifacts": {
            "methods.md": methods_path,
        },
        "chat_history": chat_history,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Stage 3 — Experiment Execution
# ═══════════════════════════════════════════════════════════════════════════

def build_experiment_kwargs(
    data_description: str,
    research_idea: str,
    methodology: str,
    work_dir: str,
    api_keys: dict | None = None,
    parent_run_id: str | None = None,
    config_overrides: dict | None = None,
    callbacks=None,
) -> dict:
    """Build kwargs dict for planning_and_control_context_carryover (experiment stage)."""
    from task_framework.prompts.deepresearch.experiment import (
        experiment_planner_prompt,
        experiment_engineer_prompt,
        experiment_researcher_prompt,
    )

    cfg = {**_get_experiment_defaults(), **(config_overrides or {})}
    involved_agents = cfg["involved_agents"]
    involved_agents_str = ", ".join(involved_agents)
    experiment_dir = create_work_dir(work_dir, "experiment")

    return dict(
        task=data_description,
        n_plan_reviews=1,
        max_n_attempts=cfg["max_n_attempts"],
        max_plan_steps=cfg["max_n_steps"],
        max_rounds_control=500,
        engineer_model=cfg["engineer_model"],
        researcher_model=cfg["researcher_model"],
        planner_model=cfg["planner_model"],
        plan_reviewer_model=cfg["plan_reviewer_model"],
        plan_instructions=experiment_planner_prompt.format(
            research_idea=research_idea,
            methodology=methodology,
            involved_agents_str=involved_agents_str,
        ),
        researcher_instructions=experiment_researcher_prompt.format(
            research_idea=research_idea,
            methodology=methodology,
        ),
        engineer_instructions=experiment_engineer_prompt.format(
            research_idea=research_idea,
            methodology=methodology,
        ),
        work_dir=str(experiment_dir),
        api_keys=api_keys,
        restart_at_step=cfg["restart_at_step"],
        hardware_constraints=cfg["hardware_constraints"],
        default_llm_model=cfg["orchestration_model"],
        default_formatter_model=cfg["formatter_model"],
        parent_run_id=parent_run_id,
        stage_name="experiment_execution",
        callbacks=callbacks,
    )


def extract_experiment_result(results: dict) -> Tuple[str, List[str]]:
    """Extract experiment results text and plot paths.

    Tries ``researcher_response_formatter`` first; falls back to
    ``researcher``, then ``engineer_response_formatter``, then
    ``engineer`` if earlier agents returned empty content.
    As a last resort, scans all messages for the longest non-empty
    content from any response-formatter or execution agent.

    Returns:
        (experiment_results_markdown, plot_paths_list)
    """
    chat_history = results["chat_history"]
    final_context = results["final_context"]

    task_result = ""
    for agent_name in (
        "researcher_response_formatter",
        "researcher",
        "engineer_response_formatter",
        "engineer",
        "executor_response_formatter",
    ):
        try:
            candidate = get_task_result(chat_history, agent_name)
            if candidate and candidate.strip():
                task_result = candidate
                break
        except ValueError:
            continue

    # Broader fallback: scan ALL messages for the longest non-empty content
    if not task_result:
        logger.warning("Primary experiment extraction failed, scanning all messages")
        best = ""
        for msg in chat_history:
            name = msg.get("name", "")
            content = msg.get("content", "")
            if name and content and content.strip():
                if len(content) > len(best):
                    best = content
        if best:
            task_result = best
            logger.info("Recovered experiment result from broad scan, length=%d", len(best))

    if not task_result:
        agent_names = [msg.get("name", "<no name>") for msg in chat_history if msg.get("name")]
        logger.error(
            "Experiment extraction failed. Agents in chat_history: %s",
            list(set(agent_names)),
        )
        raise ValueError(
            "No agent found with content in chat history for experiment results. "
            f"Available agents: {list(set(agent_names))}"
        )

    experiment_results = extract_clean_markdown(task_result)
    plot_paths = final_context.get("displayed_images", [])
    return experiment_results, plot_paths


def save_experiment(
    experiment_results: str,
    plot_paths: List[str],
    work_dir: str,
) -> Tuple[str, str, List[str]]:
    """Write results.md, move plots to input_files/plots/.

    Returns:
        (results_path, plots_dir, final_plot_paths)
    """
    input_files_dir = os.path.join(str(work_dir), INPUT_FILES)
    os.makedirs(input_files_dir, exist_ok=True)

    # Write results markdown
    results_path = os.path.join(input_files_dir, RESULTS_FILE)
    with open(results_path, "w") as f:
        f.write(experiment_results)

    # Prepare plots directory
    plots_dir = os.path.join(input_files_dir, PLOTS_FOLDER)
    os.makedirs(plots_dir, exist_ok=True)

    # Clear existing plots
    for file in os.listdir(plots_dir):
        file_path = os.path.join(plots_dir, file)
        if os.path.isfile(file_path):
            os.remove(file_path)

    # Move new plots
    for plot_path in plot_paths:
        if os.path.exists(plot_path):
            shutil.move(plot_path, plots_dir)

    # Build final plot paths list
    final_plot_paths = []
    if os.path.exists(plots_dir):
        final_plot_paths = [
            os.path.join(plots_dir, f)
            for f in os.listdir(plots_dir)
            if os.path.isfile(os.path.join(plots_dir, f))
        ]

    return results_path, plots_dir, final_plot_paths


def build_experiment_output(
    research_idea: str,
    data_description: str,
    methodology: str,
    experiment_results: str,
    final_plot_paths: List[str],
    results_path: str,
    plots_dir: str,
    chat_history: list,
    work_dir: str | None = None,
) -> dict:
    """Build the output_data dict for DB storage (experiment stage).

    When ``work_dir`` is provided, also walks the experiment subdirectory and
    embeds a categorized artifact manifest of every file Stage 3 produced —
    plots, code, data, reports, chat transcripts, planning artifacts. The
    same manifest is written to disk as ``artifact_manifest.json`` for
    audit / replay independent of the DB row.
    """
    output: dict = {
        "shared": {
            "research_idea": research_idea,
            "data_description": data_description,
            "methodology": methodology,
            "results": experiment_results,
            "plot_paths": final_plot_paths,
        },
        "artifacts": {
            "results.md": results_path,
            "plots/": plots_dir,
        },
        "chat_history": chat_history,
    }

    if work_dir:
        try:
            manifest = collect_experiment_artifacts(work_dir)
            manifest_path = write_artifact_manifest(work_dir, manifest)
            output["artifact_manifest"] = manifest
            if manifest_path:
                output["manifest_path"] = manifest_path
        except Exception as exc:
            logger.warning("artifact_manifest_collect_failed work_dir=%s error=%s", work_dir, exc)

    return output
