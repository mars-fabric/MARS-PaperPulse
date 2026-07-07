"""LangGraph state definition for the Stage 5 report pipeline."""

from typing import TypedDict, List, Dict, Any, Optional


class PageSection(TypedDict):
    chapter_num: int
    title: str
    content: str          # enhanced plain-text body (no LaTeX, no markdown)
    image_path: Optional[str]  # absolute path from images_to_use/
    plots: List[str]      # absolute paths to research plots/figures


class TocEntry(TypedDict):
    title: str
    page_num: int
    level: int            # 1=chapter section, 2=sub-section


class AboutCard(TypedDict):
    title: str
    content: str


class ReportState(TypedDict):
    # Runtime config
    work_dir: str
    images_dir: str
    report_dir: str

    # LLM config
    llm_model: str
    llm_temperature: float
    llm_max_tokens: int
    keys: Any             # KeyManager instance

    # Raw content loaded from Stage 1-4 outputs
    raw_title: str
    raw_idea: str
    raw_methods: str
    raw_results: str
    raw_conclusions: str
    raw_abstract: str

    # Structured report content
    report_title: str
    about_cards: List[AboutCard]   # page 3 cards from context.md
    sections: List[PageSection]    # all content sections

    # TOC (computed after sections)
    toc_entries: List[TocEntry]

    # Output
    output_pdf_path: str
    error: Optional[str]
