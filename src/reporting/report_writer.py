from __future__ import annotations

from pathlib import Path


def write_report(report_text: str, output_dir: Path, filename: str = "report.md") -> Path:
    """Write report text to a file in the specified output directory.
    
    Args:
        report_text: The report content to write
        output_dir: Directory where the report will be saved
        filename: Name of the report file (default: "report.md")
        
    Returns:
        Path to the created report file
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    path.write_text(report_text, encoding="utf-8")
    return path


