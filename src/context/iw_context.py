from __future__ import annotations

from pathlib import Path
from typing import Optional


def load_iw_context(context_path: Path = Path("IW_OVERVIEW.md")) -> Optional[str]:
    """Load Instawork context for LLM prompts."""
    if not context_path.exists():
        return None
    return context_path.read_text(encoding="utf-8").strip()
