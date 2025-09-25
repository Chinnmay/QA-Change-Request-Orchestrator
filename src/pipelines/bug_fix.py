from __future__ import annotations

from pathlib import Path
import json

from src.parsers.change_request_parser import ChangeRequest
from src.retrieval.retriever_interface import Retriever
from src.validation.schema_validator import validate_instance
from src.llm.client import LLMClient
from src.prompts.bug_fix_prompts import BugFixPrompts
from src.context.iw_context import load_iw_context
from src.pipelines.shared import PipelineOutput, perform_retrieval, load_validator, display_pipeline_completion, display_skip_message


def run_bug_fix_pipeline(
    change: ChangeRequest,
    test_cases_dir: Path,
    schema_path: Path,
    retriever: Retriever,
    llm_client: LLMClient,
    config=None,
    dry_run: bool = False,
) -> PipelineOutput:
    """Run the bug fix pipeline to analyze and update test cases affected by bug fixes.
    
    Args:
        change: Change request containing bug fix details
        test_cases_dir: Directory containing test case files
        schema_path: Path to JSON schema for validation
        retriever: Test case retriever for finding relevant cases
        llm_client: LLM client for AI analysis
        config: Configuration object (optional)
        dry_run: If True, don't actually update files
        
    Returns:
        PipelineOutput with updated test cases and analysis report
    """
    # Create focused query text for better retrieval
    query_text = _create_focused_bug_fix_query(change)
    
    # Perform retrieval using shared logic
    related = perform_retrieval(change, retriever, config, "bug_fix", query_text, default_top_k=8)
    
    # Load validator using shared logic
    validator = load_validator(schema_path)
    
    # Step A: Controlled bug fix analysis with audit trail
    print("📝 Analyzing bug fix impact with controlled approach...")
    updated_paths, analysis_log = _controlled_bug_fix_analysis(change, related, test_cases_dir, validator, llm_client, dry_run)
    
    # Step C: Generate comprehensive change log
    report = _build_auditable_report(change, related, updated_paths, analysis_log)
    return PipelineOutput(updated=updated_paths, created=[], report=report, related_count=len(related), related_test_cases=related)


def _controlled_bug_fix_analysis(change: ChangeRequest, related: list[dict], test_cases_dir: Path, 
                                validator, llm_client: LLMClient, dry_run: bool) -> tuple[list[Path], list[dict]]:
    """
    Step A & B: Controlled bug fix analysis with audit trail.
    
    Returns:
        tuple: (updated_paths, analysis_log_entries)
    """
    updated_paths: list[Path] = []
    analysis_log_entries: list[dict] = []
    
    if not llm_client.is_available() or llm_client.current_provider == "mock":
        display_skip_message("bug fix", "LLM not available", len(related), len(updated_paths), 0, len(analysis_log_entries))
        return updated_paths, analysis_log_entries
    
    # Load IW context for better analysis
    iw_context = load_iw_context()
    
    print(f"🔄 Analyzing {len(related)} test cases for bug fix impact...")
    
    for i, tc_data in enumerate(related, 1):
        tc_id = tc_data.get("doc_id")
        if not tc_id:
            continue
            
        print(f"  📋 Analyzing test case {i}/{len(related)}: {tc_data.get('title', 'Unknown')}")
        
        # Step A: Context packaging for LLM
        original_tc = _load_original_test_case(tc_id, test_cases_dir, tc_data)
        if not original_tc:
            print(f"    ❌ Could not load original test case {tc_id}")
            print("    The local index may be stale or corrupted.")
            print("    Please run: python reset_database.py and re-run the tool.")
            import sys
            sys.exit(1)
        
        # Step B: Controlled analysis with structured response
        try:
            updated_tc, analysis_summary = _get_controlled_bug_fix_analysis(
                change, original_tc, iw_context, llm_client
            )
            
            if updated_tc and analysis_summary:
                # Validate the updated test case
                errors = validate_instance(validator, updated_tc)
                if not errors:
                    # Apply the update
                    file_path = _get_test_case_file_path(tc_id, test_cases_dir, tc_data)
                    if file_path and file_path.exists():
                        if not dry_run:
                            import json
                            file_path.write_text(json.dumps(updated_tc, indent=2), encoding="utf-8")
                        updated_paths.append(file_path)
                        
                        # Add to analysis log
                        analysis_log_entries.append({
                            "test_case_id": tc_id,
                            "test_case_title": original_tc.get("title", "Unknown"),
                            "file_path": str(file_path),
                            "analysis_summary": analysis_summary,
                            "timestamp": _get_timestamp()
                        })
                        
                        print(f"    ✅ Updated with {len(analysis_summary.get('changes', []))} changes")
                    else:
                        print(f"    ⚠️  File not found for test case {tc_id}")
                else:
                    print(f"    ❌ Validation failed: {errors}")
            else:
                print(f"    ℹ️  No updates needed")
                
        except Exception as e:
            print(f"    ⚠️  Analysis failed: {e}")
            continue
    
    display_pipeline_completion("controlled bug fix", len(related), len(updated_paths), 0, len(analysis_log_entries), updated_paths)
    
    return updated_paths, analysis_log_entries


def _load_original_test_case(tc_id: str, test_cases_dir: Path, tc_data: dict) -> dict:
    """Load the original test case from file."""
    try:
        file_path = _get_test_case_file_path(tc_id, test_cases_dir, tc_data)
        if file_path and file_path.exists():
            import json
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"    ⚠️  Failed to load test case {tc_id}: {e}")
    return None


def _get_test_case_file_path(tc_id: str, test_cases_dir: Path, tc_data: dict) -> Path:
    """Get the file path for a test case."""
    # First try to get the original file path from metadata
    metadata = tc_data.get("metadata", {})
    original_file = metadata.get("original_file", "")
    if original_file and Path(original_file).exists():
        return Path(original_file)
    
    # Fallback to legacy file field
    if "file" in tc_data:
        return Path(tc_data["file"])
    
    # Last resort: try to construct path from ID (unlikely to work)
    return test_cases_dir / f"{tc_id}.json"


def _get_controlled_bug_fix_analysis(change: ChangeRequest, original_tc: dict, 
                                    iw_context: str, llm_client: LLMClient) -> tuple[dict, dict]:
    """
    Step B: Get controlled bug fix analysis with structured response.
    
    Returns:
        tuple: (updated_test_case, analysis_summary)
    """
    # Create context package for LLM
    context_package = {
        "change_request": {
            "title": change.title,
            "description": change.description,
            "acceptance_criteria": change.acceptance_criteria,
            "change_type": change.change_type
        },
        "original_test_case": original_tc,
        "iw_context": iw_context
    }
    
    # Use the controlled bug fix analysis prompt
    prompt = BugFixPrompts.controlled_analysis(context_package)
    
    try:
        response = llm_client.complete(prompt, max_tokens=2000)
        
        # Extract structured JSON response
        import re
        
        # Extract JSON using improved method
        json_str = None
        
        # First try to find JSON in code blocks
        code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response.text, re.DOTALL)
        if code_block_match:
            json_str = code_block_match.group(1)
        else:
            # Try to find the largest JSON object by counting braces
            brace_count = 0
            start_pos = -1
            for i, char in enumerate(response.text):
                if char == '{':
                    if brace_count == 0:
                        start_pos = i
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0 and start_pos != -1:
                        json_str = response.text[start_pos:i+1]
                        break
        
        # Validate JSON
        if json_str:
            try:
                import json
                json.loads(json_str)  # Validate JSON
            except (json.JSONDecodeError, TypeError):
                json_str = None
        
        if json_str:
            import json
            result = json.loads(json_str)
            
            updated_tc = result.get("updated_test_case")
            analysis_summary = result.get("analysis_summary")
            
            if updated_tc and analysis_summary:
                return updated_tc, analysis_summary
    
    except Exception as e:
        print(f"    ⚠️  LLM analysis failed: {e}")
    
    return None, None


def _get_timestamp() -> str:
    """Get current timestamp for audit trail."""
    from datetime import datetime
    return datetime.now().isoformat()


def _create_focused_bug_fix_query(change: ChangeRequest) -> str:
    """Create a focused query text for bug fix retrieval."""
    # Extract key terms from the bug fix description
    title_words = change.title.lower().split()
    description_words = change.description.lower().split()
    
    # Filter out common words and focus on technical terms
    common_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "must", "can", "this", "that", "these", "those", "change", "request", "author", "engineer", "overview", "discovered", "when", "pro", "turns", "back", "resulting", "missed", "steps", "reproduce", "launch", "allowed", "go", "settings", "notifications", "toggle", "allow", "push", "notifications", "off", "kill", "relaunch", "removed", "return", "observe", "via", "charles", "proxyman", "no", "api", "call", "sent", "acceptance", "criteria", "sends", "fresh", "within", "seconds", "success", "toast", "re-enabled", "displayed", "present", "django", "admin", "under", "user", "profile"}
    
    # Extract meaningful terms, avoiding duplicates
    key_terms = []
    seen_terms = set()
    for word in title_words + description_words:
        word = word.strip(".,!?;:()[]{}*`")
        if len(word) > 2 and word not in common_words and word.isalpha() and word not in seen_terms:
            key_terms.append(word)
            seen_terms.add(word)
    
    # Prioritize important technical terms
    priority_terms = []
    other_terms = []
    important_words = {"notification", "push", "token", "refresh", "register", "settings", "toggle", "permission", "enable", "disable", "backend", "api", "app"}
    
    for term in key_terms:
        if term in important_words:
            priority_terms.append(term)
        else:
            other_terms.append(term)
    
    # Create focused query with priority terms first
    focused_terms = priority_terms + other_terms[:10]  # Limit to 15 total terms
    focused_query = " ".join(focused_terms)
    return focused_query




def _build_auditable_report(change: ChangeRequest, related: list[dict], 
                           updated: list[Path], analysis_log: list[dict]) -> str:
    """
    Step C: Generate comprehensive change log with audit trail for bug fix analysis.
    """
    lines = []
    lines.append("# Bug Fix - Test Case Analysis Report")
    lines.append("")
    lines.append(f"**Generated**: {_get_timestamp()}")
    lines.append("")
    
    # Change Request Metadata
    lines.append("## Change Request Metadata")
    lines.append("")
    lines.append(f"**Type**: {change.change_type}")
    lines.append(f"**Title**: {change.title}")
    lines.append(f"**Description**: {change.description}")
    lines.append("")
    lines.append("**Acceptance Criteria**:")
    for i, criteria in enumerate(change.acceptance_criteria, 1):
        lines.append(f"{i}. {criteria}")
    lines.append("")
    
    # Test Cases Analyzed - Table Format
    lines.append("## Test Cases Analyzed")
    lines.append("")
    lines.append("| # | Test Case Title | Priority | Score | File Name |")
    lines.append("|---|----------------|----------|-------|-----------|")
    
    for i, tc in enumerate(related[:10], 1):
        title = tc.get('title', 'Unknown')
        priority = tc.get('priority', 'Unknown')
        score = tc.get('score', 0)
        
        # Get file name from metadata
        metadata = tc.get("metadata", {})
        original_file = metadata.get("original_file", "")
        if original_file:
            file_name = Path(original_file).name
        else:
            file_name = "Unknown"
        
        lines.append(f"| {i} | {title} | {priority} | {score:.3f} | {file_name} |")
    
    lines.append("")
    
    # Test Cases Updated
    lines.append("## Test Cases Updated")
    lines.append("")
    if analysis_log:
        for entry in analysis_log:
            # Get file name instead of full path
            file_path = entry.get('file_path', '')
            file_name = Path(file_path).name if file_path else 'Unknown'
            
            lines.append(f"### {entry['test_case_title']}")
            lines.append(f"**File**: {file_name}")
            lines.append(f"**Updated**: {entry['timestamp']}")
            lines.append("")
            
            analysis_summary = entry['analysis_summary']
            
            # Bug Impact Assessment
            bug_impact = analysis_summary.get('bug_impact', 'No impact assessment provided')
            lines.append(f"**Bug Impact**: {bug_impact}")
            lines.append("")
            
            # Changes Made
            changes = analysis_summary.get('changes', [])
            if changes:
                lines.append("**Changes Made**:")
                for change_item in changes:
                    field = change_item.get('field', 'Unknown')
                    before = change_item.get('before', 'N/A')
                    after = change_item.get('after', 'N/A')
                    lines.append(f"- **{field}**:")
                    lines.append(f"  - Before: {before}")
                    lines.append(f"  - After: {after}")
                lines.append("")
            
            # Why? Section - Reasoning and Assumptions
            lines.append("**Why?**")
            reasoning = analysis_summary.get('reasoning', 'No reasoning provided')
            assumptions = analysis_summary.get('assumptions', [])
            
            lines.append(f"**Reasoning**: {reasoning}")
            lines.append("")
            
            if assumptions:
                lines.append("**Assumptions Made**:")
                for assumption in assumptions:
                    lines.append(f"- {assumption}")
            else:
                lines.append("**Assumptions Made**: None documented")
            lines.append("")
            
            # Regression Tests
            regression_tests = analysis_summary.get('regression_tests', [])
            if regression_tests:
                lines.append("**Regression Tests Added**:")
                for test in regression_tests:
                    lines.append(f"- {test}")
                lines.append("")
    else:
        lines.append("No test cases were updated.")
        lines.append("")
    
    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total Test Cases Analyzed**: {len(related)}")
    lines.append(f"- **Total Test Cases Updated**: {len(updated)}")
    lines.append(f"- **Analysis Entries**: {len(analysis_log)}")
    lines.append("")
    
    return "\n".join(lines)
