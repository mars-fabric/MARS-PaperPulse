import os
import tempfile
from pathlib import Path

from routers.deepresearch import _collect_stage_output_files


def test_collects_artifacts_from_report_dir_fallback(tmp_path):
    report_dir = tmp_path / "report"
    report_dir.mkdir()
    pdf_path = report_dir / "demo_enhanced_report.pdf"
    pdf_path.write_bytes(b"pdf")

    files = _collect_stage_output_files(
        work_dir=str(tmp_path),
        raw_files=[],
        output_data={
            "shared": {"report_dir": str(report_dir), "report_pdf": str(pdf_path)},
            "artifacts": {},
        },
    )

    assert str(pdf_path) in files


def test_expands_relative_output_files_against_work_dir(tmp_path):
    report_dir = tmp_path / "report"
    report_dir.mkdir()
    pdf_path = report_dir / "nested_report.pdf"
    pdf_path.write_bytes(b"pdf")

    files = _collect_stage_output_files(
        work_dir=str(tmp_path),
        raw_files=["report/nested_report.pdf"],
        output_data={},
    )

    assert str(pdf_path) in files


def test_resolves_relative_cmbdir_paths_against_cwd(tmp_path, monkeypatch):
    sessions_report = tmp_path / "cmbdir" / "sessions" / "sess" / "tasks" / "task" / "report"
    sessions_report.mkdir(parents=True)
    pdf_path = sessions_report / "stage5.pdf"
    pdf_path.write_bytes(b"pdf")

    monkeypatch.chdir(tmp_path)

    files = _collect_stage_output_files(
        work_dir=str(sessions_report.parent),
        raw_files=["./cmbdir/sessions/sess/tasks/task/report/stage5.pdf"],
        output_data={},
    )

    assert str(pdf_path) in files
