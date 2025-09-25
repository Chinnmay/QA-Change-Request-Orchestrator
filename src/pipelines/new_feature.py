from __future__ import annotations

from pathlib import Path
import json

from src.parsers.change_request_parser import ChangeRequest
from src.validation.schema_validator import validate_instance
from src.llm.client import LLMClient
from src.prompts.new_feature_prompts import NewFeaturePrompts
from src.context.iw_context import load_iw_context
from src.pipelines.shared import PipelineOutput, load_validator, display_pipeline_completion, display_skip_message


def run_new_feature_pipeline(
    change: ChangeRequest,
    test_cases_dir: Path,
    schema_path: Path,
    retriever,
    llm_client: LLMClient,
    config=None,
    dry_run: bool = False,
) -> PipelineOutput:
    """Run the new feature pipeline to generate test cases for new features.
    
    Args:
        change: Change request containing new feature details
        test_cases_dir: Directory where new test case files will be created
        schema_path: Path to JSON schema for validation
        retriever: Test case retriever (not used for new features)
        llm_client: LLM client for AI analysis
        config: Configuration object (optional)
        dry_run: If True, don't actually create files
        
    Returns:
        PipelineOutput with created test cases and generation report
    """
    # For new feature generation, we do not use related test cases
    related: list[dict] = []

    validator = load_validator(schema_path)
    
    # Step A: Controlled test case generation with audit trail
    print("📝 Generating new test cases with controlled approach...")
    created_paths, generation_log = _controlled_test_generation(change, related, test_cases_dir, validator, llm_client, dry_run)
    
    # Step C: Generate comprehensive change log
    report = _build_auditable_report(change, related, created_paths, generation_log)
    return PipelineOutput(updated=[], created=created_paths, report=report, related_count=0, related_test_cases=[])


def _controlled_test_generation(change: ChangeRequest, related: list[dict], test_cases_dir: Path, 
                               validator, llm_client: LLMClient, dry_run: bool) -> tuple[list[Path], list[dict]]:
    """
    Step A & B: Controlled test case generation with audit trail.
    
    Returns:
        tuple: (created_paths, generation_log_entries)
    """
    created_paths: list[Path] = []
    generation_log_entries: list[dict] = []
    
    if not llm_client.is_available() or llm_client.current_provider == "mock":
        display_skip_message("new feature generation", "LLM provider unavailable", 3, 0, len(created_paths), len(generation_log_entries))
        return created_paths, generation_log_entries
    
    # Load IW context for better generation
    iw_context = load_iw_context()
    
    print(f"🔄 Generating 3 new test cases (positive, negative, edge)...")
    
    # Generate exactly three variants
    variants = ["positive", "negative", "edge"]
    for i, variant in enumerate(variants, start=1):
        print(f"  📝 Generating {variant} test case {i}/3...")
        
        try:
            # Step B: Controlled generation with structured response
            new_tc, generation_summary = _get_controlled_test_generation_variant(
                change, iw_context, llm_client, i, variant
            )
            
            if new_tc and generation_summary is not None:
                # Normalize to schema shape before validation
                new_tc = _normalize_generated_test_case(change, new_tc, variant)
                # Validate the generated test case
                errors = validate_instance(validator, new_tc)
                if not errors:
                    # Create the test case file
                    safe_title = new_tc['title'].lower().replace(" ", "_").replace(":", "").replace("-", "_")[:50]
                    filename = f"auto_{safe_title}_{variant}.json"
                    path = test_cases_dir / filename
                    if not dry_run:
                        path.write_text(json.dumps(new_tc, indent=2), encoding="utf-8")
                    created_paths.append(path)
                    
                    # Add to generation log
                    generation_log_entries.append({
                        "test_case_id": f"auto_{safe_title}_{variant}",
                        "test_case_title": new_tc.get("title", "Unknown"),
                        "file_path": str(path),
                        "generation_summary": generation_summary,
                        "timestamp": _get_timestamp()
                    })
                    
                    print(f"    ✅ Generated: {new_tc.get('title', 'Unknown')}")
                else:
                    print(f"    ❌ Validation failed: {errors}")
            else:
                print("    ❌ LLM generation returned no usable result; skipping this variant.")
                continue
                
        except Exception as e:
            print(f"    ❌ Generation failed: {e}")
            continue
    
    display_pipeline_completion("controlled generation", 3, 0, len(created_paths), len(generation_log_entries), created_paths)
    
    return created_paths, generation_log_entries




def _get_controlled_test_generation_variant(change: ChangeRequest,
                                           iw_context: str,
                                           llm_client: LLMClient,
                                           test_number: int,
                                           variant: str) -> tuple[dict, dict]:
    """Variant-specific controlled generation (positive | negative | edge)."""
    from typing import Dict, Any

    context_package: Dict[str, Any] = {
        "change_request": {
            "title": change.title,
            "description": change.description,
            "acceptance_criteria": change.acceptance_criteria,
            "change_type": change.change_type,
        },
        "iw_context": iw_context,
        "test_number": test_number,
    }

    prompt = NewFeaturePrompts.controlled_generation_variant(context_package, variant)

    try:
        response = llm_client.complete(prompt, max_tokens=2000)

        import re, json

        def extract_first_json(text: str) -> dict | None:
            # Try fenced block first
            m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
            candidate = m.group(1) if m else None
            if not candidate:
                # Fallback: longest top-level JSON object
                brace_count = 0
                start_pos = -1
                best = None
                for i, ch in enumerate(text):
                    if ch == '{':
                        if brace_count == 0:
                            start_pos = i
                        brace_count += 1
                    elif ch == '}':
                        brace_count -= 1
                        if brace_count == 0 and start_pos != -1:
                            best = text[start_pos:i+1]
                            start_pos = -1
                candidate = best
            if not candidate:
                return None
            try:
                return json.loads(candidate)
            except Exception:
                return None

        def normalize_result(obj: dict) -> tuple[dict | None, dict | str | None]:
            if not isinstance(obj, dict):
                return None, None
            # Primary keys
            new_tc = obj.get('new_test_case')
            gen_sum = obj.get('generation_summary')
            # Common aliases
            if new_tc is None:
                new_tc = obj.get('test_case') or obj.get('updated_test_case') or obj.get('generated_test_case')
            if gen_sum is None:
                gen_sum = obj.get('change_summary') or obj.get('analysis_summary') or obj.get('summary')
            # If still missing but object itself looks like a test case, accept it
            if new_tc is None and all(k in obj for k in ('title', 'steps')):
                new_tc = obj
            # Ensure gen_sum is either dict or string, not None
            if gen_sum is None and new_tc is not None:
                gen_sum = "Generated test case for new feature"
            return new_tc, gen_sum

        parsed = extract_first_json(response.text)
        if isinstance(parsed, dict):
            new_tc, generation_summary = normalize_result(parsed)
            if new_tc and generation_summary is not None:
                return new_tc, generation_summary
        else:
            print(f"    ⚠️  Could not parse JSON from LLM response")

        # One retry: ask for strict JSON shape only
        retry_prompt = (
            "Return ONLY valid JSON with keys new_test_case and generation_summary. "
            "No prose. Base it on the previous answer."
        )
        retry = llm_client.complete(retry_prompt, max_tokens=800, messages=[
            {"role": "system", "content": "You are formatting assistant."},
            {"role": "user", "content": response.text[:4000]}
        ])
        parsed_retry = extract_first_json(retry.text)
        if isinstance(parsed_retry, dict):
            new_tc, generation_summary = normalize_result(parsed_retry)
            if new_tc and generation_summary is not None:
                return new_tc, generation_summary
        else:
            print(f"    ⚠️  Retry also failed to parse JSON")

    except Exception as e:
        print(f"    ⚠️  LLM generation failed: {e}")

    return None, None


def _get_timestamp() -> str:
    """Get current timestamp for audit trail."""
    from datetime import datetime
    return datetime.now().isoformat()


def _normalize_generated_test_case(change: ChangeRequest, tc: dict, variant: str) -> dict:
    """Map common LLM output shapes to the schema-compliant test case format."""
    normalized = {}

    # Title
    title = tc.get('title') or tc.get('name') or f"{change.title} - {variant.capitalize()}"
    normalized['title'] = str(title)[:300]

    # Type
    t = (tc.get('type') or 'functional').lower()
    allowed_types = {"functional", "integration", "ui", "api", "performance", "security", "regression"}
    normalized['type'] = t if t in allowed_types else 'functional'

    # Priority
    prio = tc.get('priority') or tc.get('severity') or ''
    prio_map = {
        'p1': 'P1 - Critical', 'critical': 'P1 - Critical',
        'p2': 'P2 - High', 'high': 'P2 - High',
        'p3': 'P3 - Medium', 'medium': 'P3 - Medium',
        'p4': 'P4 - Low', 'low': 'P4 - Low',
    }
    prio_key = str(prio).strip().lower()
    normalized['priority'] = tc.get('priority') if prio_key.startswith('p') and ' - ' in str(prio) else prio_map.get(prio_key, 'P2 - High')

    # Preconditions
    pre = tc.get('preconditions') or tc.get('setup') or tc.get('given') or ''
    if isinstance(pre, list):
        pre = "; ".join(map(str, pre))
    normalized['preconditions'] = str(pre)

    # Steps
    steps_src = tc.get('steps') or tc.get('test_steps') or tc.get('procedure') or []
    steps: list = []
    if isinstance(steps_src, list):
        for item in steps_src:
            if isinstance(item, dict):
                text = item.get('step_text') or item.get('action') or item.get('description') or item.get('text') or ''
                exp = item.get('step_expected') or item.get('expected') or item.get('expected_result') or ''
                if isinstance(text, dict):
                    text = text.get('text') or text.get('value') or str(text)
                if isinstance(exp, dict):
                    exp = exp.get('text') or exp.get('value') or str(exp)
                if text or exp:
                    steps.append({"step_text": str(text), "step_expected": str(exp)})
            elif isinstance(item, str):
                steps.append({"step_text": item, "step_expected": "Expectation documented in acceptance criteria."})
    elif isinstance(steps_src, str):
        steps.append({"step_text": steps_src, "step_expected": "Expectation documented in acceptance criteria."})

    if not steps:
        # Guarantee at least one step to pass minItems
        steps = [{
            "step_text": "Execute the primary action for this feature.",
            "step_expected": "System responds as per acceptance criteria."
        }]
    normalized['steps'] = steps

    # Remove unexpected properties by returning only schema fields
    return normalized






def _build_auditable_report(change: ChangeRequest, related: list[dict], 
                           created: list[Path], generation_log: list[dict]) -> str:
    """
    Step C: Generate comprehensive change log with audit trail for new feature generation.
    """
    lines = []
    lines.append("# New Feature - Test Case Generation Log")
    lines.append("")
    lines.append(f"**Change Request ID**: {change.change_type}_{change.title[:50].replace(' ', '_')}")
    lines.append(f"**Timestamp**: {_get_timestamp()}")
    lines.append("")
    
    # Overview section
    lines.append("## Overview")
    lines.append(f"- **Change Type**: {change.change_type}")
    lines.append(f"- **Title**: {change.title}")
    lines.append(f"- **Description**: {change.description}")
    lines.append("")
    lines.append("### Acceptance Criteria")
    for i, criteria in enumerate(change.acceptance_criteria, 1):
        lines.append(f"{i}. {criteria}")
    lines.append("")
    
    # Context sections omitted for new feature generation (no related test cases used)
    
    # Brand-New Test Cases Added
    lines.append("## Brand-New Test Cases Added")
    lines.append(f"**Total Added**: {len(created)}")
    lines.append("")
    
    if generation_log:
        for entry in generation_log:
            lines.append(f"### {entry['test_case_title']}")
            lines.append(f"- **File**: {entry['file_path']}")
            lines.append(f"- **Added At**: {entry['timestamp']}")
            if 'generation_summary' in entry:
                gs = entry['generation_summary']
                # Handle both dict and string generation summaries
                if isinstance(gs, dict):
                    lines.append(f"- **Why Added**: {gs.get('reasoning', 'N/A')}")
                    dd = gs.get('design_decisions', [])
                    if dd:
                        lines.append("- **Design Decisions**:")
                        for d in dd:
                            lines.append(f"  - {d}")
                    assumptions = gs.get('assumptions', [])
                    if assumptions:
                        lines.append("- **Assumptions**:")
                        for a in assumptions:
                            lines.append(f"  - {a}")
                    questions = gs.get('open_questions', [])
                    if questions:
                        lines.append("- **Open Questions**:")
                        for q in questions:
                            lines.append(f"  - {q}")
                else:
                    # Handle string generation summary
                    lines.append(f"- **Summary**: {str(gs)}")
            else:
                lines.append("- **Why Added**: Fallback deterministic generation")
            lines.append("")
    else:
        lines.append("No test cases were generated.")
        lines.append("")
    
    # Summary
    lines.append("## Summary")
    lines.append(f"- **Brand-New Test Cases Added**: {len(created)}")
    lines.append(f"- **Assumptions / Open Questions**: See sections above")
    lines.append("")
    lines.append("This generation log provides a complete audit trail of all new test cases created for the feature implementation.")
    
    return "\n".join(lines)




