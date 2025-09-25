from pathlib import Path
from src.parsers.change_request_parser import parse_change_request


def test_parse_change_request(tmp_path: Path):
    content = """
# Add Search by Date

Change-Type: new_feature

## Acceptance Criteria
- User can filter by date range
- Show empty state when no results
""".strip()
    p = tmp_path / "cr.md"
    p.write_text(content, encoding="utf-8")
    cr = parse_change_request(p)
    assert cr.change_type == "new_feature"
    assert "Add Search by Date" in cr.title
    assert len(cr.acceptance_criteria) == 2


