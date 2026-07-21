"""LangGraph node implementations for the Stage 5 report pipeline."""

from __future__ import annotations

import logging
import os
import random
import re
import shutil
from typing import Any, Dict, List, Optional

from .state import AboutCard, PageSection, ReportState, TocEntry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_THIS_DIR = os.path.dirname(__file__)          # report_agents/
_BACKEND = os.path.dirname(os.path.dirname(_THIS_DIR))  # backend/
_APP_ROOT = os.path.dirname(os.path.dirname(_BACKEND))  # MARS_APP/
DEFAULT_IMAGES_DIR = os.path.join(_APP_ROOT, "images_to_use")

# context.md lives at the app root
CONTEXT_MD_PATH = os.path.join(_APP_ROOT, "context.md")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}


def _read_file(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read().strip()
    except Exception:
        return ""


def _strip_latex(text: str) -> str:
    """Remove LaTeX markup, preserve content as readable text with markdown structure."""

    def _list_env_to_bullets(m: re.Match) -> str:
        items = re.findall(r'\\item\s+(.*?)(?=\\item|\\end\{)', m.group(0), re.DOTALL)
        result = '\n'
        for item in items:
            item = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', item.strip())
            item = re.sub(r'\\[a-zA-Z]+', '', item)
            item = re.sub(r'[{}]', '', item)
            item = re.sub(r'\s+', ' ', item).strip()
            if item and len(item) > 3:
                result += f'- {item}\n'
        return result + '\n'

    def _table_env_to_heading(m: re.Match) -> str:
        content = m.group(0)
        cap = re.search(r'\\caption\{([^}]+)\}', content)
        if cap:
            caption = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', cap.group(1))
            caption = re.sub(r'\\[a-zA-Z]+', '', caption).strip()
            if caption:
                return f'\n\n## {caption}\n\n'
        return '\n'

    # Strip document wrapper tags FIRST so the catch-all below can't consume the entire content
    text = re.sub(r'\\begin\{document\}', '', text)
    text = re.sub(r'\\end\{document\}', '', text)

    # Convert itemize/enumerate to markdown bullets
    text = re.sub(
        r'\\begin\{(?:itemize|enumerate)\}.*?\\end\{(?:itemize|enumerate)\}',
        _list_env_to_bullets, text, flags=re.DOTALL,
    )
    # Convert tables: keep caption as a subheading
    text = re.sub(
        r'\\begin\{table\*?\}.*?\\end\{table\*?\}',
        _table_env_to_heading, text, flags=re.DOTALL,
    )
    # Remove math environments entirely
    text = re.sub(r'\\begin\{equation\*?\}.*?\\end\{equation\*?\}', '', text, flags=re.DOTALL)
    text = re.sub(r'\\begin\{align\*?\}.*?\\end\{align\*?\}', '', text, flags=re.DOTALL)
    text = re.sub(r'\$\$.*?\$\$', '', text, flags=re.DOTALL)
    text = re.sub(r'\$[^$\n]+\$', '', text)
    # Remove figure environments
    text = re.sub(r'\\begin\{figure\*?\}.*?\\end\{figure\*?\}', '', text, flags=re.DOTALL)
    # Remove any remaining environments (document already stripped above)
    text = re.sub(r'\\begin\{[^}]+\}.*?\\end\{[^}]+\}', '', text, flags=re.DOTALL)

    # Preserve subsection headings as ## markers
    text = re.sub(r'\\section\*?\{([^}]*)\}', r'\n\n## \1\n\n', text)
    text = re.sub(r'\\subsection\*?\{([^}]*)\}', r'\n\n## \1\n\n', text)
    text = re.sub(r'\\subsubsection\*?\{([^}]*)\}', r'\n\n### \1\n\n', text)

    # Unwrap text formatting commands
    text = re.sub(r'\\textbf\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\emph\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\textit\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\text\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\texttt\{([^}]*)\}', r'\1', text)

    # Remove citations, refs, labels
    text = re.sub(r'\\cite[tp]?\*?\{[^}]*\}', '', text)
    text = re.sub(r'\\ref\{[^}]*\}', '', text)
    text = re.sub(r'\\label\{[^}]*\}', '', text)

    # Unescape LaTeX special characters before removing commands
    for esc, char in [('\\%', '%'), ('\\_', '_'), ('\\&', '&'), ('\\#', '#'),
                      ('\\$', '$'), ('\\~', ' '), ('\\ ', ' ')]:
        text = text.replace(esc, char)

    # Replace LaTeX non-breaking space ~ with regular space
    text = text.replace('~', ' ')

    # Remove remaining LaTeX commands
    text = re.sub(r'\\[a-zA-Z]+\*?(?:\[[^\]]*\])?\{[^}]*\}', '', text)
    text = re.sub(r'\\[a-zA-Z]+\*?(?:\[[^\]]*\])?', '', text)
    text = re.sub(r'[{}]', '', text)

    # Clean up orphaned fragments left by math removal
    text = re.sub(r'\bwhere\s+(?:is|are)\s+the\b', 'where the', text)
    # Remove empty parentheses (left after removing math content)
    text = re.sub(r'\(\s*\)', '', text)
    # Remove duplicate consecutive common words left by math variable stripping
    text = re.sub(r'\b(and|or|the|to|a|an|in|of|is|are)\s+\1\b', r'\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+,', ',', text)
    text = re.sub(r'\s+\.', '.', text)
    # Clean up "( ," and ", )" artifacts
    text = re.sub(r'\(\s*,', '(', text)
    text = re.sub(r',\s*\)', ')', text)

    # Normalise whitespace (preserve ## and - lines)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


def _strip_markdown(text: str) -> str:
    """Remove ALL markdown formatting including headings and bullets."""
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'#{1,6}\s+', '', text)
    text = re.sub(r'^\s*[-*+•]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'`[^`]+`', '', text)
    text = re.sub(r'_{1,2}([^_]+)_{1,2}', r'\1', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _clean_content(text: str) -> str:
    """Strip both LaTeX and markdown — use for fallback plain text."""
    return _strip_markdown(_strip_latex(text))


def _clean_enhanced(text: str) -> str:
    """Strip LaTeX and inline markdown from LLM output; keep ## headings and - bullets."""
    text = _strip_latex(text)
    # Remove inline bold/italic but preserve heading/bullet lines
    text = re.sub(r'\*\*([^*\n]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*\n]+)\*', r'\1', text)
    text = re.sub(r'_{1,2}([^_\n]+)_{1,2}', r'\1', text)
    text = re.sub(r'`[^`\n]+`', '', text)
    # Collapse H1 and H3+ down to ## level
    text = re.sub(r'^#(?!#)\s+(.*?)$', r'## \1', text, flags=re.MULTILINE)
    text = re.sub(r'^#{3,}\s+(.*?)$', r'## \1', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _parse_context_md(path: str) -> List[AboutCard]:
    """Parse context.md into 4 AboutCard dicts."""
    raw = _read_file(path)
    if not raw:
        return _default_about_cards()

    cards: List[AboutCard] = []
    # Split on bold headings: **Title**
    parts = re.split(r'\*\*([^*]+)\*\*', raw)
    # parts = [intro, title1, body1, title2, body2, ...]
    i = 1
    while i + 1 < len(parts):
        title = parts[i].strip().lstrip('—').strip()
        body = parts[i + 1].strip()
        body = re.sub(r'^\s*-{2,}\s*', '', body)       # leading ---
        body = re.sub(r'\s*-{2,}\s*$', '', body).strip()  # trailing ---
        if title and body:
            cards.append({"title": title, "content": body})
        i += 2

    if not cards:
        return _default_about_cards()

    return cards[:4]  # keep at most 4


def _default_about_cards() -> List[AboutCard]:
    return [
        {"title": "iCETS", "content": "iCETS is Infosys's dedicated engine for exploring and shaping the technologies of tomorrow."},
        {"title": "Living Labs", "content": "Living Labs is where ideas become tangible experiences and emerging technologies come to life."},
        {"title": "Advance AI", "content": "Advance AI is iCETS's research sub-team pushing the frontier of artificial intelligence."},
        {"title": "Topaz", "content": "Topaz is a flagship intelligent technology fabric enabling seamless enterprise integration."},
    ]


def _list_images(images_dir: str) -> List[str]:
    if not os.path.isdir(images_dir):
        return []
    return sorted(
        os.path.join(images_dir, f)
        for f in os.listdir(images_dir)
        if os.path.splitext(f)[1].lower() in _IMAGE_EXTS
    )


def _list_plots(work_dir: str) -> List[str]:
    plots_dir = os.path.join(work_dir, "input_files", "plots")
    if not os.path.isdir(plots_dir):
        return []
    return sorted(
        os.path.join(plots_dir, f)
        for f in os.listdir(plots_dir)
        if os.path.splitext(f)[1].lower() in _IMAGE_EXTS | {".pdf"}
    )


def _make_llm(state: ReportState):
    """Build a LangChain LLM from available credentials."""
    keys = state.get("keys")
    if not keys:
        return None

    model = state.get("llm_model", "gemini-2.5-flash")
    temp = float(state.get("llm_temperature", 0.7))
    max_tokens = int(state.get("llm_max_tokens", 8192))

    try:
        if model.startswith("bedrock/"):
            from botocore.config import Config as BotoConfig
            from langchain_aws import ChatBedrock
            bid = model.removeprefix("bedrock/")
            return ChatBedrock(
                model_id=bid,
                region_name=getattr(keys, "AWS_REGION", None) or "us-east-1",
                aws_access_key_id=getattr(keys, "AWS_ACCESS_KEY_ID", None),
                aws_secret_access_key=getattr(keys, "AWS_SECRET_ACCESS_KEY", None),
                config=BotoConfig(read_timeout=600, connect_timeout=30),
                model_kwargs={"temperature": temp, "max_tokens": min(max_tokens, 8192)},
            )
        if model.startswith("nvidia/") or "nemotron" in model.lower():
            # NVIDIA NIM is OpenAI-compatible — use ChatOpenAI with the NVIDIA base_url.
            from langchain_openai import ChatOpenAI
            base_url = getattr(keys, "NVIDIA_BASE_URL", None) or "https://integrate.api.nvidia.com/v1"
            return ChatOpenAI(
                model=model, temperature=temp,
                openai_api_key=getattr(keys, "NVIDIA", None),
                base_url=base_url,
                max_tokens=max_tokens,
            )
        if "gemini" in model:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=model, temperature=temp,
                google_api_key=getattr(keys, "GEMINI", None),
                max_output_tokens=max_tokens,
            )
        if any(k in model for k in ("gpt", "o3", "o4")):
            if getattr(keys, "OPENAI", None):
                from langchain_openai import ChatOpenAI
                return ChatOpenAI(model=model, temperature=temp, openai_api_key=keys.OPENAI)
            if getattr(keys, "AZURE_OPENAI_API_KEY", None):
                from langchain_openai import AzureChatOpenAI
                return AzureChatOpenAI(
                    azure_deployment=keys.AZURE_OPENAI_DEPLOYMENT,
                    azure_endpoint=keys.AZURE_OPENAI_ENDPOINT,
                    api_key=keys.AZURE_OPENAI_API_KEY,
                    api_version=getattr(keys, "AZURE_OPENAI_API_VERSION", None) or "2024-12-01-preview",
                    temperature=temp,
                )
        if "claude" in model or "anthropic" in model:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=model, temperature=temp,
                anthropic_api_key=getattr(keys, "ANTHROPIC", None),
                max_tokens=max_tokens,
            )
    except Exception as exc:
        logger.warning("report_llm_init_failed model=%s error=%s", model, exc)
    return None


_ENHANCE_SYSTEM = (
    "You are a professional technical writer creating an engaging magazine-style research report "
    "for Infosys iCETS. Your prose is sophisticated, clear, and accessible to senior technology executives. "
    "You write with depth, incorporating specific data and findings to make the report genuinely informative."
)

_ENHANCE_TEMPLATE = """\
Transform the following research content into polished magazine-style prose for a professional technology report.

FORMATTING RULES:
- Use "## Subheading" lines for major topic subsections — keep any existing section structure
- Use "- item" bullet lines ONLY for lists of 3 or more distinct items (results, metrics, contributions)
- Write flowing paragraphs of 4-6 sentences for narrative and analytical content
- NO LaTeX commands, NO backslash commands, NO math formulas
- NO bold (**) or italic (*) — plain text only within paragraphs
- Preserve ALL specific numbers, percentages, model names, and technical findings exactly
- Write at least {min_paragraphs} substantive paragraphs of meaningful depth

Section: {section_name}

Content:
{content}

Enhanced content:"""


def _enhance_via_llm(llm, section_name: str, content: str, min_paragraphs: int = 4) -> str:
    """Call LLM to enhance a section. Falls back to cleaned original on failure."""
    if not llm or not content.strip():
        # No LLM: strip LaTeX but keep ## headings and - bullets for rich layout
        return _clean_enhanced(content)

    from langchain_core.messages import HumanMessage, SystemMessage

    # Pre-clean content before sending to LLM so it gets readable text
    content_for_llm = _strip_latex(content)
    if not content_for_llm.strip():
        content_for_llm = content

    prompt = _ENHANCE_TEMPLATE.format(
        section_name=section_name,
        content=content_for_llm,
        min_paragraphs=min_paragraphs,
    )
    try:
        try:
            from cmbagent.tracing import get_tracer
            _tracer = get_tracer("paperpulse.langgraph.report")
        except Exception:
            _tracer = None
        if _tracer is not None:
            with _tracer.start_as_current_span("report.enhance_section") as _span:
                try:
                    _span.set_attribute("report.section", section_name)
                except Exception:
                    pass
                response = llm.invoke([SystemMessage(content=_ENHANCE_SYSTEM), HumanMessage(content=prompt)])
        else:
            response = llm.invoke([SystemMessage(content=_ENHANCE_SYSTEM), HumanMessage(content=prompt)])
        text = response.content if hasattr(response, "content") else str(response)
        # Keep markdown structure (## headings, - bullets), only strip LaTeX artifacts
        cleaned = _clean_enhanced(text)
        if len(cleaned) > 300:
            return cleaned
        logger.warning("report_enhance_short_response section=%s len=%d", section_name, len(cleaned))
        return _clean_content(content)
    except Exception as exc:
        logger.error("report_enhance_failed section=%s error=%s", section_name, exc)
        return _clean_content(content)


# ---------------------------------------------------------------------------
# Node 1: load_content
# ---------------------------------------------------------------------------

def load_content_node(state: ReportState) -> Dict[str, Any]:
    """Load content from Stage 1-4 outputs."""
    work_dir = state["work_dir"]
    images_dir = state.get("images_dir") or DEFAULT_IMAGES_DIR
    report_dir = os.path.join(work_dir, "report")
    os.makedirs(report_dir, exist_ok=True)

    # Prefer individual section temp files from Stage 4
    paper_temp = os.path.join(work_dir, "paper", "temp")

    def _read_section(temp_name: str, fallback_path: str) -> str:
        temp_path = os.path.join(paper_temp, temp_name)
        if os.path.exists(temp_path):
            return _read_file(temp_path)
        return _read_file(fallback_path)

    raw_title = _read_section("Title.tex", "")
    raw_abstract = _read_section("Abstract.tex", "")
    raw_intro = _read_section("Introduction.tex", os.path.join(work_dir, "input_files", "idea.md"))
    raw_methods = _read_section("Methods.tex", os.path.join(work_dir, "input_files", "methods.md"))

    # For results, prefer the refined version
    raw_results = ""
    for fname in ("Results_refined.tex", "Results.tex"):
        p = os.path.join(paper_temp, fname)
        if os.path.exists(p):
            raw_results = _read_file(p)
            break
    if not raw_results:
        raw_results = _read_file(os.path.join(work_dir, "input_files", "results.md"))

    raw_conclusions = _read_section("Conclusions.tex", "")

    # Extract plain title
    title_clean = _strip_latex(raw_title)
    if not title_clean:
        # Try from the full tex file
        for vname in ("paper_v2_no_citations.tex", "paper_v1_preliminary.tex"):
            tex = _read_file(os.path.join(work_dir, "paper", vname))
            m = re.search(r'\\title\{([^}]+)\}', tex)
            if m:
                title_clean = m.group(1).strip()
                break
    if not title_clean:
        title_clean = "Research Report"

    # About cards from context.md
    about_cards = _parse_context_md(CONTEXT_MD_PATH)

    logger.info(
        "report_load_content title=%r idea_len=%d methods_len=%d results_len=%d",
        title_clean[:60], len(raw_intro), len(raw_methods), len(raw_results),
    )

    return {
        "work_dir": work_dir,
        "images_dir": images_dir,
        "report_dir": report_dir,
        "report_title": title_clean,
        "raw_title": raw_title,
        "raw_idea": raw_intro,
        "raw_methods": raw_methods,
        "raw_results": raw_results,
        "raw_conclusions": raw_conclusions,
        "raw_abstract": raw_abstract,
        "about_cards": about_cards,
        "error": None,
    }


# ---------------------------------------------------------------------------
# Node 2: enhance_content
# ---------------------------------------------------------------------------

def enhance_content_node(state: ReportState) -> Dict[str, Any]:
    """Use LLM to transform academic text into engaging magazine prose."""
    llm = _make_llm(state)

    raw_sections = [
        ("Executive Summary", state.get("raw_abstract") or state.get("raw_idea", ""), 3),
        ("Introduction", state.get("raw_idea", ""), 4),
        ("Methodology", state.get("raw_methods", ""), 4),
        ("Results & Findings", state.get("raw_results", ""), 5),
        ("Conclusions & Future Directions", state.get("raw_conclusions") or state.get("raw_results", ""), 3),
    ]

    sections: List[PageSection] = []
    for chapter_num, (name, raw, min_p) in enumerate(raw_sections, start=1):
        if not raw.strip():
            raw = f"This section covers {name.lower()} of the research."
        enhanced = _enhance_via_llm(llm, name, raw, min_paragraphs=min_p)
        sections.append({
            "chapter_num": chapter_num,
            "title": name,
            "content": enhanced,
            "image_path": None,   # filled by select_images_node
            "plots": [],          # filled by process_figures_node
        })
        logger.info("report_enhanced_section section=%s len=%d", name, len(enhanced))

    return {"sections": sections}


# ---------------------------------------------------------------------------
# Node 3: select_images
# ---------------------------------------------------------------------------

def select_images_node(state: ReportState) -> Dict[str, Any]:
    """Randomly assign background images from images_to_use/ to each section."""
    images = _list_images(state["images_dir"])
    if not images:
        logger.warning("report_no_images dir=%s", state["images_dir"])
        sections = [{**s} for s in state["sections"]]
        return {"sections": sections}

    # Seed deterministically from title so the same paper always gets the same images
    rng = random.Random(hash(state.get("report_title", "")) % (2**31))
    shuffled = images[:]
    rng.shuffle(shuffled)

    sections = []
    for i, sec in enumerate(state["sections"]):
        img = shuffled[i % len(shuffled)]
        sections.append({**sec, "image_path": img})

    return {"sections": sections}


# ---------------------------------------------------------------------------
# Node 4: process_figures
# ---------------------------------------------------------------------------

def process_figures_node(state: ReportState) -> Dict[str, Any]:
    """Copy research plots to report_dir and assign them to sections."""
    plots = _list_plots(state["work_dir"])
    report_dir = state["report_dir"]

    # Copy plots to report dir (ReportLab needs accessible paths)
    copied: List[str] = []
    for src in plots[:20]:  # cap at 20
        dst = os.path.join(report_dir, "plot_" + os.path.basename(src))
        if not os.path.exists(dst):
            try:
                shutil.copy2(src, dst)
            except Exception:
                pass
        if os.path.exists(dst):
            copied.append(dst)

    # Assign plots primarily to Results section (chapter_num == 4)
    sections = []
    plot_idx = 0
    for sec in state["sections"]:
        s = {**sec}
        if sec["chapter_num"] == 4 and copied:
            # Give the Results section up to 4 plots
            s["plots"] = copied[plot_idx: plot_idx + 4]
            plot_idx += len(s["plots"])
        elif sec["chapter_num"] == 2 and copied and plot_idx < len(copied):
            # Give Introduction 1 plot if available
            s["plots"] = [copied[plot_idx]]
            plot_idx += 1
        else:
            s["plots"] = []
        sections.append(s)

    logger.info("report_figures total=%d assigned=%d", len(copied), plot_idx)
    return {"sections": sections}


# ---------------------------------------------------------------------------
# Node 5: build_toc
# ---------------------------------------------------------------------------

def build_toc_node(state: ReportState) -> Dict[str, Any]:
    """Compute page numbers for each section and build the TOC."""
    # Fixed pages: 1=cover, 2=TOC, 3=about
    page = 4

    toc_entries: List[TocEntry] = []
    sections = [{**s} for s in state["sections"]]

    for sec in sections:
        # Chapter divider page
        divider_page = page
        page += 1

        # Estimate content pages (rough: 1800 chars per page)
        content_len = len(sec.get("content", ""))
        n_plots = len(sec.get("plots", []))
        content_pages = max(1, -(-content_len // 1800))   # ceiling division
        content_pages += n_plots // 2  # plots take extra space

        toc_entries.append({
            "title": sec["title"],
            "page_num": page,    # first content page (after divider)
            "level": 1,
        })
        page += content_pages

    return {"toc_entries": toc_entries}


# ---------------------------------------------------------------------------
# Node 6: build_pdf
# ---------------------------------------------------------------------------

def build_pdf_node(state: ReportState) -> Dict[str, Any]:
    """Assemble the final PDF using ReportLab."""
    from .pdf_builder import PDFReportBuilder

    report_dir = state["report_dir"]
    os.makedirs(report_dir, exist_ok=True)

    # Derive a slug from the title for the filename
    slug = re.sub(r'[^A-Za-z0-9]+', '_', state["report_title"])[:50].strip('_')
    if not slug:
        slug = "report"
    output_path = os.path.join(report_dir, f"{slug}_enhanced_report.pdf")

    builder = PDFReportBuilder()
    try:
        builder.build(
            output_path=output_path,
            report_title=state["report_title"],
            about_cards=state.get("about_cards", []),
            sections=state["sections"],
            toc_entries=state.get("toc_entries", []),
            images_dir=state["images_dir"],
        )
        logger.info("report_pdf_built path=%s", output_path)
    except Exception as exc:
        logger.error("report_pdf_build_failed error=%s", exc, exc_info=True)
        return {"error": str(exc), "output_pdf_path": ""}

    return {"output_pdf_path": output_path}


# ---------------------------------------------------------------------------
# Node 7: finalize
# ---------------------------------------------------------------------------

def finalize_node(state: ReportState) -> Dict[str, Any]:
    """Verify output and log completion."""
    pdf = state.get("output_pdf_path", "")
    if pdf and os.path.exists(pdf):
        size_kb = os.path.getsize(pdf) // 1024
        logger.info("report_finalized path=%s size_kb=%d", pdf, size_kb)
        print(f"\n[Stage 5] Enhanced report PDF generated: {pdf}  ({size_kb} KB)\n")
    else:
        logger.error("report_pdf_missing path=%s", pdf)
        print(f"\n[Stage 5] ERROR: PDF not found at: {pdf}\n")
    return {}
