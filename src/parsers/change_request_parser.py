from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass
class ChangeRequest:
    change_type: str
    title: str
    description: str
    acceptance_criteria: list[str]


CHANGE_TYPES = {"new_feature", "feature_update", "bug_fix"}


def parse_change_request(path: Path) -> ChangeRequest:
    """Parse a change request file and extract structured information.
    
    Args:
        path: Path to the change request file
        
    Returns:
        ChangeRequest object with parsed information
    """
    text = path.read_text(encoding="utf-8")
    change_type = _extract_change_type(text)
    title = _extract_title(text)
    description = _extract_section(text, pattern=r"(?im)^description\s*:|^##\s*description\b") or text.strip()[:2000]
    acceptance = _extract_bullets(text, pattern=r"(?im)^acceptance criteria\s*:|^##\s*acceptance criteria\b|^###\s*acceptance criteria\b")
    return ChangeRequest(
        change_type=change_type,
        title=title,
        description=description.strip(),
        acceptance_criteria=acceptance,
    )


def _extract_title(text: str) -> str:
    m = re.search(r"(?im)^#\s+(.+)$", text)
    return m.group(1).strip() if m else "Untitled Change Request"


def _extract_change_type(text: str) -> str:
    m = re.search(r"(?im)change[_ -]?type\s*[:|-]\s*(new_feature|feature_update|bug[_ -]?fix)", text)
    if m:
        value = m.group(1).replace(" ", "_").replace("-", "_")
        return value
    # Fallback: infer from keywords
    if re.search(r"(?i)bug|fix|patch", text):
        return "bug_fix"
    if re.search(r"(?i)update|modify|tweak", text):
        return "feature_update"
    return "new_feature"


def _extract_section(text: str, pattern: str) -> str | None:
    m = re.search(pattern, text)
    if not m:
        return None
    start = m.end()
    following = text[start:]
    # Stop at next heading
    end_match = re.search(r"\n#{1,3}\s+\w+|\n[A-Za-z][A-Za-z _-]*:\s*\n", following)
    end = end_match.start() if end_match else len(following)
    return following[:end].strip()


def _extract_bullets(text: str, pattern: str) -> list[str]:
    section = _extract_section(text, pattern)
    if not section:
        return []
    bullets = re.findall(r"(?m)^[-*]\s+(.+)$", section)
    return [b.strip() for b in bullets if b.strip()]


