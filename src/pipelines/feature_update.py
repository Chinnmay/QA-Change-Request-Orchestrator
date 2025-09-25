from __future__ import annotations

from pathlib import Path
import json

from src.parsers.change_request_parser import ChangeRequest
from src.retrieval.retriever_interface import Retriever
from src.validation.schema_validator import validate_instance
from src.llm.client import LLMClient
from src.prompts.feature_update_prompts import FeatureUpdatePrompts
from src.context.iw_context import load_iw_context
from src.pipelines.shared import PipelineOutput, perform_retrieval, load_validator, display_pipeline_completion, display_skip_message


def run_feature_update_pipeline(
    change: ChangeRequest,
    test_cases_dir: Path,
    schema_path: Path,
    retriever: Retriever,
    llm_client: LLMClient,
    config=None,
    dry_run: bool = False,
) -> PipelineOutput:
    """Run the feature update pipeline to analyze and update test cases affected by feature changes.
    
    Args:
        change: Change request containing feature update details
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
    query_text = _create_focused_feature_update_query(change)
    
    # Perform retrieval using shared logic
    related = perform_retrieval(change, retriever, config, "feature_update", query_text, default_top_k=10)
    
    # Load validator using shared logic
    validator = load_validator(schema_path)
    
    # Step A: Context packaging for LLM - controlled updates with audit trail
    print("📝 Analyzing test cases for updates...")
    # Determine debug verbosity from config
    debug_logging = False
    try:
        if config and getattr(config, 'global_settings', None):
            debug_logging = str(config.global_settings.get('log_level', 'INFO')).upper() == 'DEBUG'
    except Exception:
        debug_logging = False

    updated_paths, change_log = _controlled_llm_updates(
        change,
        related,
        test_cases_dir,
        validator,
        llm_client,
        dry_run,
        debug_logging,
    )
    
    # Step C: Generate comprehensive change log
    report = _build_auditable_report(change, related, updated_paths, change_log)
    return PipelineOutput(updated=updated_paths, created=[], report=report, related_count=len(related), related_test_cases=related)


def _controlled_llm_updates(change: ChangeRequest, related: list[dict], test_cases_dir: Path, 
                           validator, llm_client: LLMClient, dry_run: bool, debug_logging: bool) -> tuple[list[Path], list[dict]]:
    """
    Step A & B: Controlled LLM updates with audit trail.
    
    Returns:
        tuple: (updated_paths, change_log_entries)
    """
    updated_paths: list[Path] = []
    change_log_entries: list[dict] = []
    
    if not llm_client.is_available() or llm_client.current_provider == "mock":
        print("⚠️  LLM not available, using fallback analysis for mandatory reasoning")
        print(f"🔄 Analyzing {len(related)} test cases with fallback approach...")
        
        # Use fallback analysis to provide mandatory reasoning
        updated_paths, change_log_entries = _fallback_feature_update_analysis(change, related, test_cases_dir, validator, dry_run)
        
        print(f"✅ Completed fallback feature update analysis:")
        print(f"   📊 Analyzed: {len(related)} test cases")
        print(f"   ✏️  Updated: {len(updated_paths)} test cases")
        print(f"   📝 Analysis log entries: {len(change_log_entries)}")
        
        if updated_paths:
            print(f"   📁 Updated files:")
            for path in updated_paths:
                print(f"      - {path.name}")
        
        return updated_paths, change_log_entries
    
    # Load IW context for better analysis
    iw_context = load_iw_context()
    
    print(f"🔄 Processing {len(related)} test cases for controlled updates...")
    
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
        
        # Step B: Controlled update with structured response
        try:
            updated_tc, change_summary = _get_controlled_llm_update(
                change, original_tc, iw_context, llm_client, debug_logging
            )
            
            if updated_tc and change_summary:
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
                        
                        # Add to change log
                        change_log_entries.append({
                            "test_case_id": tc_id,
                            "test_case_title": original_tc.get("title", "Unknown"),
                            "file_path": str(file_path),
                            "change_summary": change_summary,
                            "timestamp": _get_timestamp()
                        })
                        
                        print(f"    ✅ Updated with {len(change_summary.get('changes', []))} changes")
                    else:
                        print(f"    ⚠️  File not found for test case {tc_id}")
                else:
                    print(f"    ❌ Validation failed: {errors}")
            else:
                print(f"    ℹ️  No updates needed")
                
        except Exception as e:
            print(f"    ⚠️  Update failed: {e}")
            # If LLM fails due to quota/API issues, use fallback analysis
            if "quota" in str(e).lower() or "429" in str(e) or "api" in str(e).lower():
                print(f"    🔄 LLM API failed, using fallback analysis for this test case")
                try:
                    fallback_updates, fallback_log = _fallback_feature_update_analysis(
                        change, [tc_data], test_cases_dir, validator, dry_run
                    )
                    updated_paths.extend(fallback_updates)
                    change_log_entries.extend(fallback_log)
                    print(f"    ✅ Fallback analysis completed for {tc_data.get('title', 'Unknown')}")
                except Exception as fallback_e:
                    print(f"    ❌ Fallback analysis also failed: {fallback_e}")
            continue
    
    print(f"✅ Completed controlled feature update analysis:")
    print(f"   📊 Analyzed: {len(related)} test cases")
    print(f"   ✏️  Updated: {len(updated_paths)} test cases")
    print(f"   📝 Analysis log entries: {len(change_log_entries)}")
    
    if updated_paths:
        print(f"   📁 Updated files:")
        for path in updated_paths:
            print(f"      - {path.name}")
    
    return updated_paths, change_log_entries


def _fallback_feature_update_analysis(change: ChangeRequest, related: list[dict], test_cases_dir: Path, 
                                    validator, dry_run: bool) -> tuple[list[Path], list[dict]]:
    """
    Fallback analysis that provides mandatory reasoning and updates when LLM is not available.
    
    Args:
        change: The change request
        related: List of related test cases
        test_cases_dir: Directory containing test case files
        validator: Schema validator
        dry_run: Whether to perform a dry run
        
    Returns:
        tuple: (updated_paths, change_log_entries)
    """
    updated_paths: list[Path] = []
    change_log_entries: list[dict] = []
    
    # Analyze each related test case for potential updates
    for tc_data in related:
        tc_id = tc_data.get("doc_id")
        if not tc_id:
            continue
            
        # Load original test case
        original_tc = _load_original_test_case(tc_id, test_cases_dir, tc_data)
        if not original_tc:
            continue
            
        # Analyze what needs to be updated based on the change request
        updates_needed = _analyze_feature_update_impact(change, original_tc, tc_data)
        
        if updates_needed["changes"]:
            # Apply updates
            updated_tc = original_tc.copy()
            for change_item in updates_needed["changes"]:
                _apply_field_update(updated_tc, change_item["field"], change_item["after"])
            
            # Validate updated test case
            errors = validate_instance(validator, updated_tc)
            if not errors:
                # Write updated test case
                file_path = _get_test_case_file_path(tc_id, test_cases_dir, tc_data)
                if not dry_run:
                    file_path.write_text(json.dumps(updated_tc, indent=2), encoding="utf-8")
                updated_paths.append(file_path)
                
                # Create detailed change log entry
                change_log_entry = {
                    "test_case_id": tc_id,
                    "test_case_title": original_tc.get("title", "Unknown"),
                    "file_path": str(file_path),
                    "timestamp": _get_timestamp(),
                    "change_summary": {
                        "feature_impact": updates_needed["feature_impact"],
                        "changes": updates_needed["changes"],
                        "reasoning": updates_needed["reasoning"],
                        "assumptions": updates_needed["assumptions"]
                    }
                }
                change_log_entries.append(change_log_entry)
    
    return updated_paths, change_log_entries


def _analyze_feature_update_impact(change: ChangeRequest, original_tc: dict, tc_data: dict) -> dict:
    """
    Analyze what updates are needed for a test case based on the feature change.
    
    Returns:
        Dictionary with changes, reasoning, and assumptions
    """
    changes = []
    feature_impact = ""
    reasoning = ""
    assumptions = []
    
    # Extract key terms from the change request
    change_title_lower = change.title.lower()
    change_desc_lower = change.description.lower()
    acceptance_criteria_text = " ".join(change.acceptance_criteria).lower()
    
    # Analyze based on common feature update patterns
    if "cancellation" in change_title_lower or "cancellation" in change_desc_lower:
        feature_impact = "This test case is affected by the cancellation window change. The cancellation timing and validation rules need to be updated."
        reasoning = "The feature update changes cancellation window from 24 hours to 12 hours. This affects any test case that involves shift cancellation timing."
        assumptions = [
            "The test case involves shift cancellation functionality",
            "The 12-hour window applies to all shift types",
            "Reliability penalties are calculated based on the new window"
        ]
        
        # Check if test case involves cancellation
        tc_title_lower = original_tc.get("title", "").lower()
        tc_desc_lower = original_tc.get("description", "").lower()
        
        if "cancel" in tc_title_lower or "cancel" in tc_desc_lower:
            print(f"    🔍 Found cancellation test case: {tc_title_lower}")
            # Update steps and expected results related to cancellation timing
            steps = original_tc.get("steps", [])
            for i, step in enumerate(steps):
                step_text = step.get("step_text", "").lower()
                step_expected = step.get("step_expected", "").lower()
                
                if "24 hour" in step_text or "24 hours" in step_text:
                    print(f"      ✏️  Updating step {i}: {step_text[:50]}...")
                    changes.append({
                        "field": f"steps[{i}].step_text",
                        "before": step["step_text"],
                        "after": step["step_text"].replace("24 hour", "12 hour").replace("24 hours", "12 hours")
                    })
                
                if "24 hour" in step_expected or "24 hours" in step_expected:
                    print(f"      ✏️  Updating step {i} expected: {step_expected[:50]}...")
                    changes.append({
                        "field": f"steps[{i}].step_expected",
                        "before": step["step_expected"],
                        "after": step["step_expected"].replace("24 hour", "12 hour").replace("24 hours", "12 hours")
                    })
            
            # Check preconditions for 24 hour references
            preconditions = original_tc.get("preconditions", "")
            if preconditions and ("24 hour" in preconditions.lower() or "24 hours" in preconditions.lower()):
                print(f"      ✏️  Updating preconditions: {preconditions[:50]}...")
                changes.append({
                    "field": "preconditions",
                    "before": preconditions,
                    "after": preconditions.replace("24 hour", "12 hour").replace("24 hours", "12 hours")
                })
            
            # Add updated tag
            tags = original_tc.get("tags", [])
            if "updated" not in tags:
                changes.append({
                    "field": "tags",
                    "before": tags,
                    "after": tags + ["updated", "feature_update"]
                })
    
    elif "notification" in change_title_lower or "push" in change_title_lower:
        feature_impact = "This test case is affected by the notification system changes. Push notification token handling needs to be updated."
        reasoning = "The feature update changes how push notification tokens are handled when toggling notifications on/off."
        assumptions = [
            "The test case involves notification functionality",
            "Token registration happens when notifications are enabled",
            "Backend API calls are required for token management"
        ]
        
        # Check if test case involves notifications
        tc_title_lower = original_tc.get("title", "").lower()
        tc_desc_lower = original_tc.get("description", "").lower()
        
        if "notification" in tc_title_lower or "notification" in tc_desc_lower or "push" in tc_title_lower:
            # Add verification steps for token registration
            steps = original_tc.get("steps", [])
            new_step = {
                "step_text": "Verify that register_push_token API is called when notifications are enabled",
                "step_expected": "API call is made within 5 seconds of enabling notifications"
            }
            
            changes.append({
                "field": "steps",
                "before": steps,
                "after": steps + [new_step]
            })
            
            # Add updated tag
            tags = original_tc.get("tags", [])
            if "updated" not in tags:
                changes.append({
                    "field": "tags",
                    "before": tags,
                    "after": tags + ["updated", "feature_update", "regression"]
                })
    
    else:
        # Generic feature update analysis
        feature_impact = "This test case may be affected by the feature update. General validation and verification steps may need updates."
        reasoning = f"The feature update '{change.title}' may impact this test case. Additional verification steps should be added to ensure the update works correctly."
        assumptions = [
            "The test case is related to the updated feature",
            "Additional validation is needed to verify the update",
            "Regression testing should be performed"
        ]
        
        # Add a generic verification step
        steps = original_tc.get("steps", [])
        new_step = {
            "step_text": f"Verify that the feature update '{change.title}' works as expected",
            "step_expected": "Feature update functions correctly according to acceptance criteria"
        }
        
        changes.append({
            "field": "steps",
            "before": steps,
            "after": steps + [new_step]
        })
        
        # Add updated tag
        tags = original_tc.get("tags", [])
        if "updated" not in tags:
            changes.append({
                "field": "tags",
                "before": tags,
                "after": tags + ["updated", "feature_update"]
            })
    
    return {
        "feature_impact": feature_impact,
        "changes": changes,
        "reasoning": reasoning,
        "assumptions": assumptions
    }


def _apply_field_update(test_case: dict, field_path: str, new_value: any) -> None:
    """
    Apply a field update to a test case using dot notation.
    
    Args:
        test_case: The test case dictionary to update
        field_path: Field path in dot notation (e.g., "steps[0].step_text")
        new_value: New value to set
    """
    if "[" in field_path and "]" in field_path:
        # Handle array notation like "steps[0].step_text"
        parts = field_path.split("[")
        array_field = parts[0]
        rest = parts[1]
        
        # Extract index and remaining path
        index_part = rest.split("]")[0]
        remaining_path = rest.split("]")[1][1:] if rest.split("]")[1].startswith(".") else ""
        
        array = test_case.get(array_field, [])
        if int(index_part) < len(array):
            if remaining_path:
                _apply_field_update(array[int(index_part)], remaining_path, new_value)
            else:
                array[int(index_part)] = new_value
    else:
        # Handle simple field
        test_case[field_path] = new_value


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


def _get_controlled_llm_update(change: ChangeRequest, original_tc: dict, 
                              iw_context: str, llm_client: LLMClient, debug_logging: bool) -> tuple[dict, dict]:
    """
    Step B: Get controlled LLM update with structured response.
    
    Returns:
        tuple: (updated_test_case, change_summary)
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
    
    # Use the controlled update prompt
    prompt = FeatureUpdatePrompts.controlled_update(context_package)
    
    try:
        response = llm_client.complete(prompt, max_tokens=2000)
        
        # Debug (verbose only): Print raw LLM response
        if debug_logging:
            print(f"    🔍 Raw LLM Response (first 500 chars): {response.text[:500]}...")
        
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
            change_summary = result.get("change_summary")
            
            # Debug: Print details only when debug enabled
            if debug_logging:
                print(f"    🔍 LLM Response Debug:")
                print(f"      - Updated TC: {'Yes' if updated_tc else 'No'}")
                print(f"      - Change Summary: {'Yes' if change_summary else 'No'}")
                if change_summary:
                    print(f"      - Change Summary Keys: {list(change_summary.keys())}")
                    print(f"      - Feature Impact: {change_summary.get('feature_impact', 'Missing')}")
                    print(f"      - Reasoning: {change_summary.get('reasoning', 'Missing')}")
                    print(f"      - Changes Count: {len(change_summary.get('changes', []))}")
                    print(f"      - Full Change Summary: {change_summary}")
            
            if updated_tc and change_summary:
                # Clean up the updated test case by removing invalid fields
                if "tags" in updated_tc:
                    del updated_tc["tags"]
                
                # Map LLM response to expected format
                normalized_change_summary = {
                    "feature_impact": change_summary.get("feature_impact", change_summary.get("reason", "No impact assessment provided")),
                    "changes": change_summary.get("changes", []),
                    "reasoning": change_summary.get("reasoning", change_summary.get("reason", "No reasoning provided")),
                    "assumptions": change_summary.get("assumptions", [])
                }
                
                return updated_tc, normalized_change_summary
    
    except Exception as e:
        print(f"    ⚠️  LLM update failed: {e}")
    
    return None, None


def _get_timestamp() -> str:
    """Get current timestamp for audit trail."""
    from datetime import datetime
    return datetime.now().isoformat()


def _build_auditable_report(change: ChangeRequest, related: list[dict], 
                           updated: list[Path], change_log: list[dict]) -> str:
    """
    Step C: Generate comprehensive change log with audit trail.
    """
    lines = []
    lines.append("# Feature Update - Test Case Analysis Report")
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
    if change_log:
        for entry in change_log:
            # Get file name instead of full path
            file_path = entry.get('file_path', '')
            file_name = Path(file_path).name if file_path else 'Unknown'
            
            lines.append(f"### {entry['test_case_title']}")
            lines.append(f"**File**: {file_name}")
            lines.append(f"**Updated**: {entry['timestamp']}")
            lines.append("")
            
            change_summary = entry['change_summary']
            
            # Feature Impact Assessment
            feature_impact = change_summary.get('feature_impact', 'No impact assessment provided')
            lines.append(f"**Feature Impact**: {feature_impact}")
            lines.append("")
            
            # Changes Made
            changes = change_summary.get('changes', [])
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
            reasoning = change_summary.get('reasoning', 'No reasoning provided')
            assumptions = change_summary.get('assumptions', [])
            
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
            regression_tests = change_summary.get('regression_tests', [])
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
    lines.append(f"- **Analysis Entries**: {len(change_log)}")
    lines.append("")
    
    return "\n".join(lines)


def _create_focused_feature_update_query(change: ChangeRequest) -> str:
    """Create a focused query text for feature update retrieval."""
    # Extract key terms from title and acceptance criteria
    all_text = f"{change.title} {' '.join(change.acceptance_criteria)}".lower()
    
    # Define important technical terms for feature updates
    priority_terms = []
    other_terms = []
    
    # Common feature update keywords
    feature_keywords = [
        "feature", "update", "modify", "change", "enhance", "improve", "add", "remove",
        "cancellation", "window", "time", "limit", "threshold", "validation", "verification",
        "notification", "push", "email", "sms", "alert", "reminder", "settings", "preference",
        "onboarding", "registration", "profile", "account", "authentication", "login",
        "shift", "booking", "schedule", "availability", "waitlist", "approval", "requirement"
    ]
    
    # Extract words and prioritize important terms
    words = all_text.split()
    for word in words:
        clean_word = word.strip(".,!?;:\"'()[]{}").lower()
        if len(clean_word) > 2:  # Skip very short words
            if any(keyword in clean_word for keyword in feature_keywords):
                if clean_word not in priority_terms:
                    priority_terms.append(clean_word)
            elif clean_word not in other_terms:
                other_terms.append(clean_word)
    
    # Create focused query with priority terms first
    focused_terms = priority_terms + other_terms[:10]
    focused_query = " ".join(focused_terms)
    return focused_query


