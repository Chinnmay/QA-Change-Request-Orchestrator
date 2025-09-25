import logging
import os
import sys
from pathlib import Path

# Add project root to Python path for IDE debugging
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.parsers.change_request_parser import parse_change_request
from src.pipelines.new_feature import run_new_feature_pipeline
from src.pipelines.feature_update import run_feature_update_pipeline
from src.pipelines.bug_fix import run_bug_fix_pipeline
from src.reporting.report_writer import write_report
from src.llm.client import LLMClient
from config.config_loader import load_config, get_report_config
from src.database import setup_database_retriever


def get_change_request_file() -> Path:
    """Get change request file from user input."""
    print("🤖 AI-based QA Change Request Orchestrator")
    print("=" * 50)
    print()
    
    # Load configuration to get sample directory
    config = load_config(None)
    # Resolve sample directory relative to project root so it works from any CWD
    sample_dir = (project_root / config.system['sample_change_requests_dir']).resolve()
    sample_files = []
    if sample_dir.exists():
        patterns = ["*.md", "*.txt", "*change*", "*request*"]
        for pattern in patterns:
            sample_files.extend(sample_dir.glob(pattern))
        sample_files = sorted(list(set(sample_files)))
    
    if sample_files:
        print("📄 Available sample files:")
        for i, file_path in enumerate(sample_files, 1):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    first_line = f.readline().strip()
                    if first_line.startswith('#'):
                        title = first_line[1:].strip()
                    else:
                        title = first_line[:50] + "..." if len(first_line) > 50 else first_line
            except Exception:
                title = file_path.name
            print(f"  {i}. {file_path.name} - {title}")
        
        print()
        while True:
            try:
                choice = input("Select a sample file (1-{}) or enter custom path: ".format(len(sample_files))).strip()
                
                if choice.isdigit():
                    choice_num = int(choice)
                    if 1 <= choice_num <= len(sample_files):
                        return sample_files[choice_num - 1]
                    else:
                        print(f"Please enter a number between 1 and {len(sample_files)}")
                else:
                    # Custom path
                    file_path = Path(choice)
                    if file_path.exists():
                        return file_path
                    else:
                        print(f"File not found: {file_path}")
                        print("Please try again or use a sample file.")
            except (ValueError, KeyboardInterrupt):
                print("Please enter a valid number or file path.")
    else:
        # No sample files, ask for path
        while True:
            file_path = input("Enter path to change request file: ").strip()
            if not file_path:
                print("Please enter a file path.")
                continue
            
            file_path = Path(file_path)
            if file_path.exists():
                return file_path
            else:
                print(f"File not found: {file_path}")
                print("Please check the path and try again.")


def main() -> None:
    """Main entry point for the QA Change Request Orchestrator CLI application."""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Load configuration and setup first
    print("🔧 Initializing system...")
    config = load_config(None)
    provider_name = os.getenv("LLM_PROVIDER") or config.default_provider
    # Resolve all important paths relative to project root to avoid cwd issues
    test_cases_dir = (project_root / config.system['test_cases_dir']).resolve()
    schema_path = (project_root / config.system['schema_path']).resolve()
    report_out = (project_root / config.system['reports_dir']).resolve()
    cache_dir = (project_root / config.system['cache_dir']).resolve()
    
    # Initialize LLM client
    print("🧠 Initializing AI provider...")
    llm_client = LLMClient(config, provider_name)
    print(f"✅ Using: {llm_client.current_provider} ({llm_client.current_model})")
    
    if not llm_client.is_available():
        print(f"⚠️  Warning: {llm_client.current_provider} ({llm_client.current_model}) not available, using mock provider")
        llm_client.switch_provider("mock")
    print()
    
    # Build or load database retriever
    retriever = setup_database_retriever(config, test_cases_dir, cache_dir)
    
    # Get change request file
    change_request_path = get_change_request_file()
    print()
    
    # Parse change request
    print("📋 Parsing change request...")
    change = parse_change_request(change_request_path)
    print(f"✅ Change type: {change.change_type}")
    print(f"✅ Title: {change.title}")
    print()
    
    # Run the appropriate pipeline
    print("🚀 Processing change request...")
    print("-" * 40)
    
    if change.change_type == "new_feature":
        print("📝 Generating new test cases...")
        result = run_new_feature_pipeline(change, test_cases_dir, schema_path, retriever, llm_client, config)
    elif change.change_type == "feature_update":
        print("🔄 Updating existing test cases...")
        result = run_feature_update_pipeline(change, test_cases_dir, schema_path, retriever, llm_client, config)
    elif change.change_type == "bug_fix":
        print("🐛 Analyzing bug fix requirements...")
        result = run_bug_fix_pipeline(change, test_cases_dir, schema_path, retriever, llm_client, config)
    else:
        print(f"❌ Unknown change type: {change.change_type}")
        sys.exit(1)
    
    print("-" * 40)
    print("✅ Processing complete!")
    print()
    
    # Write report
    print("📊 Generating report...")
    report_out.mkdir(exist_ok=True)
    report_config = get_report_config(config)
    filename_template = report_config.get('filename_template', '{change_type}_{change_request_stem}_report.md')
    # Append simple timestamp (YYYYMMDD_HHMMSS) to report filename
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filename = filename_template.format(
        change_type=change.change_type,
        change_request_stem=change_request_path.stem,
        timestamp=ts
    )
    write_report(result.report, report_out, report_filename)
    report_path = report_out / report_filename
    print(f"✅ Report written to: {report_path}")
    print()
    
    # Show summary
    print("📋 Summary")
    print("=" * 20)
    print(f"Change Type: {change.change_type}")
    print(f"Title: {change.title}")
    print(f"AI Provider: {llm_client.current_provider} ({llm_client.current_model})")
    print(f"Search Method: database (filtering + semantic ranking)")
    print(f"Relevant TCs Retrieved: {getattr(result, 'related_count', 0)}")


    
    if result.created:
        print(f"Created in: {test_cases_dir}")
        print(f"Created Files: {len(result.created)}")
        for path in result.created:
            try:
                print(f"  - {path.name}")
            except Exception:
                print(f"  - {path}")
    
    if result.updated:
        print(f"Updated Files: {len(result.updated)}")
        for path in result.updated:
            try:
                print(f"  - {path.name}")
            except Exception:
                print(f"  - {path}")
    
    print(f"Report: {report_path}")
    print()
    print("🎉 All done! Check the report for details.")


if __name__ == "__main__":
    main()