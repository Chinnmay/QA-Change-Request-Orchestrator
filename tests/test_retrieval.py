import json
from pathlib import Path
from src.retrieval.tfidf_retriever import TfidfRetriever


def test_tfidf_retriever(tmp_path: Path):
    a = {"title": "Login", "description": "User logs in", "steps": ["Go to login", "Enter creds"], "expected_result": "Dashboard"}
    b = {"title": "Logout", "description": "User logs out", "steps": ["Click logout"], "expected_result": "Login page"}
    (tmp_path / "tc_login.json").write_text(json.dumps(a), encoding="utf-8")
    (tmp_path / "tc_logout.json").write_text(json.dumps(b), encoding="utf-8")

    retriever = TfidfRetriever.from_test_case_dir(tmp_path)
    results = retriever.query("login", top_k=1)
    assert results
    assert results[0]["doc_id"].startswith("tc_login")


