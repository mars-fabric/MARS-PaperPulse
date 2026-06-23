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
from typing import Any, Dict, List, Tuple

from task_framework.config import (
    INPUT_FILES, IDEA_FILE, METHOD_FILE, RESULTS_FILE, PLOTS_FOLDER,
)
from task_framework.utils import (
    get_task_result, create_work_dir, extract_clean_markdown,
)

logger = logging.getLogger(__name__)


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


def _clean_overrides(overrides: dict | None) -> dict:
    """Drop keys whose UI value is empty/None.

    Frontend ModelSelect emits `undefined` (omitted in JSON) for "use default",
    but defensive coding: also strip explicit None or empty strings so a
    stray empty selection never silently overrides a provider profile default.
    """
    if not overrides:
        return {}
    return {k: v for k, v in overrides.items() if v not in (None, "", [])}


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

    cfg = {**_get_idea_defaults(), **_clean_overrides(config_overrides)}
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
        callbacks=callbacks,
    )


def _format_saved_ideas_as_markdown(ideas: list) -> str:
    """Render the JSON-saved ideas list back into the markdown form used downstream."""
    if not ideas:
        return ""
    lines = []
    for idx, idea in enumerate(ideas, start=1):
        title = (idea.get("idea_description") or "").strip() or f"Idea {idx}"
        lines.append(f"## Project Idea {idx}: {title}" if len(ideas) > 1 else f"Project Idea: {title}")
        for bp in idea.get("bullet_points", []) or []:
            text = str(bp).strip()
            if text:
                lines.append(f"- {text}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _load_latest_saved_ideas(work_dir: str) -> str:
    """Look under ``work_dir`` for the most recent ``ideas_*.json`` file.

    idea_saver writes these via a non-LLM ConversableAgent at run time; they
    are the authoritative output of Stage 1 regardless of which agent
    produced the very last chat message. Returns formatted markdown or "".
    """
    if not work_dir or not os.path.isdir(work_dir):
        return ""

    candidates: list[tuple[float, str]] = []
    for root, _dirs, files in os.walk(work_dir):
        for fname in files:
            if fname.startswith("ideas_") and fname.endswith(".json"):
                path = os.path.join(root, fname)
                try:
                    candidates.append((os.path.getmtime(path), path))
                except OSError:
                    continue

    if not candidates:
        return ""

    candidates.sort()
    latest_path = candidates[-1][1]
    try:
        with open(latest_path, "r", encoding="utf-8") as fh:
            ideas = json.load(fh)
    except (OSError, ValueError) as exc:
        logger.warning("Failed to load saved ideas from %s: %s", latest_path, exc)
        return ""

    if not isinstance(ideas, list) or not ideas:
        return ""

    logger.info("Loaded %d saved idea(s) from %s", len(ideas), latest_path)
    return _format_saved_ideas_as_markdown(ideas)


def extract_idea_result(results: dict, work_dir: str | None = None) -> str:
    """Extract and post-process idea from chat_history.

    Preference order:
      1. The latest ``ideas_*.json`` written by idea_saver under ``work_dir``
         (primary — idea_saver holds the authoritative selected best idea).
      2. ``idea_maker`` / ``idea_maker_nest`` content in chat_history.
      3. Longest content from any ``idea_maker*`` agent.

    JSON-first is critical: in AG2 2.0 the last ``idea_maker`` message is a
    short transition ("I will now ..."), and ``get_task_result`` picks the
    longest message which may be the raw 5-ideas brainstorm from step 1 —
    not the final selected idea. ``idea_saver`` writes the correct answer.
    """
    # Primary: idea_saver's JSON output is the authoritative selected idea
    if work_dir:
        saved = _load_latest_saved_ideas(work_dir)
        if saved:
            logger.info("Loaded idea from saved ideas_*.json (primary source)")
            return saved

    chat_history = results["chat_history"]

    # Fallback 1: explicit idea_maker / idea_maker_nest content
    task_result = ""
    for agent_name in ("idea_maker", "idea_maker_nest"):
        try:
            candidate = get_task_result(chat_history, agent_name)
            if candidate and candidate.strip():
                task_result = candidate
                break
        except ValueError:
            continue

    # Fallback 2: scan ALL messages from idea-related agents for longest content
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
        agent_names = [msg.get("name", "<no name>") for msg in chat_history if msg.get("name")]
        logger.error(
            "Idea extraction failed. Agents in chat_history: %s",
            list(set(agent_names)),
        )
        raise ValueError(
            "Neither 'idea_maker' nor 'idea_maker_nest' found with content in chat history, "
            f"and no ideas_*.json was found under work_dir. Available agents: {list(set(agent_names))}"
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

    cfg = {**_get_method_defaults(), **_clean_overrides(config_overrides)}
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
        callbacks=callbacks,
    )


def _compile_step_reports(control_dir: str) -> str:
    """Compile all researcher step reports saved to disk into one document.

    researcher_executor writes one file per step to ``{control_dir}/reports/``.
    Concatenating them in chronological (mtime) order gives the full output.
    Returns empty string if no reports found.
    """
    reports_dir = os.path.join(control_dir, "reports")
    if not os.path.isdir(reports_dir):
        return ""

    import re as _re
    _step_prefix = _re.compile(r"step_(\d+)_")
    files = []
    for fname in os.listdir(reports_dir):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(reports_dir, fname)
        m = _step_prefix.match(fname)
        step_n = int(m.group(1)) if m else 999
        mtime = os.path.getmtime(fpath)
        files.append((step_n, mtime, fname))
    # Sort by (step_n, mtime) so reports with different step numbers stay in
    # plan order; within the same step_n, use mtime (most recent last).
    files.sort(key=lambda t: (t[0], t[1]))

    if not files:
        return ""

    parts = []
    for seq, (step_n, _mtime, fname) in enumerate(files, start=1):
        fpath = os.path.join(reports_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as fh:
                content = fh.read().strip()
            # Strip the filename comment line if present
            lines = content.splitlines()
            if lines and lines[0].strip().startswith("<!-- filename:"):
                content = "\n".join(lines[1:]).strip()
            if content:
                parts.append(f"## Part {seq}\n\n{content}")
        except OSError:
            continue

    if not parts:
        return ""

    compiled = "\n\n".join(parts)
    logger.info("Compiled %d step report(s) from %s", len(parts), reports_dir)
    return compiled


def extract_method_result(results: dict) -> str:
    """Extract and post-process methodology from chat_history or disk reports.

    Preference order:
      1. Step reports on disk (``{control_dir}/reports/step_N_*.md``) — most
         complete; these are what researcher_executor saved verbatim.
      2. ``researcher_response_formatter`` / ``researcher`` from chat_history.
      3. Longest message scan across all agents.
    """
    # Primary: compile step reports saved to disk by researcher_executor
    final_context = results.get("final_context") or {}
    control_dir = final_context.get("work_dir") or ""
    if control_dir:
        compiled = _compile_step_reports(control_dir)
        if compiled:
            logger.info("Loaded methodology from disk step reports (primary source)")
            return compiled

    chat_history = results["chat_history"]

    task_result = ""
    for agent_name in ("researcher_response_formatter", "researcher"):
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

    cfg = {**_get_experiment_defaults(), **_clean_overrides(config_overrides)}
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
        callbacks=callbacks,
    )


def extract_experiment_result(results: dict) -> Tuple[str, List[str]]:
    """Extract experiment results text and plot paths.

    Preference order for results text:
      1. Step reports on disk (``{control_dir}/reports/step_N_*.md``) when the
         last step was researcher-type; compiled across all steps.
      2. ``researcher_response_formatter`` / ``researcher`` / ``engineer`` from
         chat_history — longest qualifying message.
      3. Broadest fallback: longest message from any agent.

    Returns:
        (experiment_results_markdown, plot_paths_list)
    """
    chat_history = results["chat_history"]
    final_context = results.get("final_context") or {}

    task_result = ""

    # Primary: compile researcher step reports from disk
    control_dir = final_context.get("work_dir") or ""
    if control_dir:
        compiled = _compile_step_reports(control_dir)
        if compiled:
            logger.info("Loaded experiment results from disk step reports (primary source)")
            task_result = compiled

    if not task_result:
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


def _collect_experiment_artifacts(work_dir: str) -> dict[str, str]:
    """Discover real files the engineer generated during Stage 3 execution.

    The engineer writes scripts to ``experiment_generation_output/control/codebase/``
    and data files to ``experiment_generation_output/control/data/`` (and
    sometimes ``plots/`` if it makes any). These exist on disk but were never
    surfaced through the API before — the frontend only saw ``results.md``.
    """
    artifacts: dict[str, str] = {}
    control_dir = os.path.join(str(work_dir), "experiment_generation_output", "control")
    if not os.path.isdir(control_dir):
        return artifacts
    for subdir in ("codebase", "data", "plots"):
        sub_path = os.path.join(control_dir, subdir)
        if not os.path.isdir(sub_path):
            continue
        for fname in sorted(os.listdir(sub_path)):
            fpath = os.path.join(sub_path, fname)
            if os.path.isfile(fpath):
                # Key is short label the frontend renders; value is absolute path
                artifacts[f"{subdir}/{fname}"] = fpath
    return artifacts


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
    """Build the output_data dict for DB storage (experiment stage)."""
    artifacts: dict[str, str] = {"results.md": results_path}
    # Add every plot the engineer actually generated as a first-class file
    # entry (so the frontend renders thumbnails individually, not a folder).
    for plot_path in final_plot_paths:
        artifacts[f"plots/{os.path.basename(plot_path)}"] = plot_path
    # Surface the engineer's generated code + data CSVs as artifacts too.
    if work_dir:
        artifacts.update(_collect_experiment_artifacts(work_dir))
    return {
        "shared": {
            "research_idea": research_idea,
            "data_description": data_description,
            "methodology": methodology,
            "results": experiment_results,
            "plot_paths": final_plot_paths,
        },
        "artifacts": artifacts,
        "chat_history": chat_history,
    }
