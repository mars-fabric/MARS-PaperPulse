"""LangGraph pipeline for Stage 5 enhanced PDF report generation.

Linear topology (7 nodes):
  load_content → enhance_content → select_images → process_figures
               → build_toc → build_pdf → finalize
"""

from langgraph.graph import END, START, StateGraph

from .nodes import (
    build_pdf_node,
    build_toc_node,
    enhance_content_node,
    finalize_node,
    load_content_node,
    process_figures_node,
    select_images_node,
)
from .state import ReportState


def build_report_graph():
    """Build and compile the Stage 5 report LangGraph."""
    builder = StateGraph(ReportState)

    builder.add_node("load_content",     load_content_node)
    builder.add_node("enhance_content",  enhance_content_node)
    builder.add_node("select_images",    select_images_node)
    builder.add_node("process_figures",  process_figures_node)
    builder.add_node("build_toc",        build_toc_node)
    builder.add_node("build_pdf",        build_pdf_node)
    builder.add_node("finalize",         finalize_node)

    builder.add_edge(START,             "load_content")
    builder.add_edge("load_content",    "enhance_content")
    builder.add_edge("enhance_content", "select_images")
    builder.add_edge("select_images",   "process_figures")
    builder.add_edge("process_figures", "build_toc")
    builder.add_edge("build_toc",       "build_pdf")
    builder.add_edge("build_pdf",       "finalize")
    builder.add_edge("finalize",        END)

    return builder.compile()
