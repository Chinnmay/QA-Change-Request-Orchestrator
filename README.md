# QA Change Request Orchestrator

An AI-powered tool that automatically updates and generates test cases based on change requests.

## What It Does

This tool helps QA engineers by:
- **Updating existing test cases** when features change or bugs are fixed
- **Creating new test cases** for new features (positive, negative, edge cases)
- **Generating detailed reports** explaining what changed and why

## Quick Start

### 1. Setup

#### Option A: Quick Setup (Recommended)
```bash
# Run the setup script - handles everything automatically (First time setup)
./setup_venv.sh
```

#### Option B: Manual Setup
```bash
# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Run
```bash
# Quick run (recommended for daily usage)
./run.sh

# Or run manually
python src/cli.py
```

The tool will:
1. Show you sample change requests to choose from
2. Process your selection with AI
3. Update/create test cases
4. Generate a detailed report

## API Keys (Required)

**Important:** API keys are required for the tool to work properly with real AI providers.

### Option A: Environment Variables
```bash
# Gemini (recommended)
export GEMINI_API_KEY="your_api_key_here"

# Or OpenAI
export OPENAI_API_KEY="your_api_key_here"
```

### Option B: .env File (Recommended)
Create a `.env` file in the project root:
```bash
# Copy the example file
cp env.example .env

# Edit .env with your actual API keys
GEMINI_API_KEY=your_actual_gemini_key_here
# OPENAI_API_KEY=your_openai_key_here
# LLM_PROVIDER=gemini
```

**Note:** Without API keys, the tool falls back to a mock AI provider for testing only.

## How It Works

### 1. **Change Request Types**
- **New Feature**: Creates 3 new test cases (positive, negative, edge)
- **Feature Update**: Updates existing test cases affected by changes
- **Bug Fix**: Updates test cases to address the bug

### 2. **Smart Hybrid Retrieval System**
- Combines keyword search with semantic embeddings for optimal results
- Uses keyword extraction and SQL-based matching with sentence transformers for semantic similarity
- **Intelligent Priority Scoring**: P1-Critical (1.0), P2-High (0.8), P3-Medium (0.6), P4-Low (0.4)
- Ranks results by weighted scoring (keyword + semantic + priority)
- Filters out low-relevance matches with configurable thresholds
- Extensible architecture for future retrieval methods

### 3. **Intelligent AI-Powered Analysis**
- **Smart Decision Making**: Evaluates if test cases actually need updates before making changes
- **Minimal Updates**: Only modifies test cases when absolutely necessary
- **Numerical Consistency**: Preserves original values unless bug fix specifically requires changes
- **Targeted Changes**: Adds minimal steps or makes surgical edits rather than wholesale rewrites
- **Detailed Reasoning**: Provides comprehensive justification for all decisions and changes

### 4. **Quality Assurance**
- Validates all outputs against JSON schema
- Ensures test cases remain valid and readable
- Generates comprehensive audit trails

## Sample Change Requests

The tool comes with 3 sample change requests:

1. **Bug Fix**: Push notification token refresh issue
2. **Feature Update**: Reduce cancellation window from 24h to 12h  
3. **New Feature**: Waitlist for full shifts

## Output

### Test Cases
- **Updated files**: Modified existing test cases
- **Created files**: New test cases for new features
- All files are valid JSON following the schema

### Report
Each run generates a detailed report (`reports/`) with:
- Change request metadata
- Test cases analyzed (with scores)
- Test cases updated/created
- Detailed reasoning for each change
- Assumptions made during analysis

## File Structure

```
src/
├── cli.py              # Main entry point
├── pipelines/          # Core logic for each change type
├── llm/               # AI provider integration
├── retrieval/         # Test case search system
│   └── hybrid/        # Hybrid retrieval implementation
├── database/          # Database and storage layer
├── validation/        # Schema validation
├── reporting/         # Report generation
├── parsers/           # Change request parsing
└── prompts/           # AI prompt templates

test_cases/            # Your test cases (JSON files)
sample_change_requests/ # Example change requests
reports/              # Generated reports
schema/               # Test case JSON schema
config/               # Configuration files
```

## Configuration

The tool uses `config/llm_config.yaml` for settings:
- AI provider configuration (Gemini, OpenAI, Mock)
- Hybrid retrieval settings (keyword extraction, semantic similarity)
- Database and caching configuration
- Report formatting and similarity thresholds
- Pipeline-specific parameters (top-k, similarity thresholds)

## Troubleshooting

### Common Issues

#### ModuleNotFoundError: No module named 'src'
**Problem**: Python can't find the `src` module.

**Solutions**:
```bash
# Option 1: Set PYTHONPATH manually
export PYTHONPATH="$PWD"
python src/cli.py

# Option 2: Use the run script (recommended)
./run.sh
```

#### Virtual Environment Issues
**Problem**: Packages not found or wrong Python version.

**Solutions**:
```bash
# Recreate virtual environment
rm -rf venv
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### API Errors
**Problem**: LLM provider not working.

**Solutions**:
```bash
# Check API key is set
echo $GEMINI_API_KEY
echo $OPENAI_API_KEY

# If no API key, get one:
# Gemini: https://makersuite.google.com/app/apikey
# OpenAI: https://platform.openai.com/api-keys

# Test with mock provider (development only)
# Edit config/llm_config.yaml: default_provider: "mock"
```

#### No Test Cases Found
**Problem**: Tool can't find test cases.

**Solutions**:
- Ensure test cases are in `test_cases/` directory
- Check file permissions
- Verify JSON files are valid


### Reset Database
```bash
# Clear cached data and rebuild
python reset_database.py
```

## Docker (Optional)

### Build the Image
```bash
docker build -t test-case-copilot-improved .
```

### Run Options

#### Option 1: Interactive Mode (Recommended)
```bash
# Run with interactive shell - best for development
docker run --rm -it -v "$PWD":/app test-case-copilot-improved bash

# Inside the container, run the app
python src/cli.py
```

#### Option 2: Direct Run
```bash
# Run the app directly
docker run --rm -it -v "$PWD":/app test-case-copilot-improved python src/cli.py
```

#### Option 3: With API Keys
```bash
# If you have API keys set locally
docker run --rm -it \
  -v "$PWD":/app \
  -e GEMINI_API_KEY="$GEMINI_API_KEY" \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  test-case-copilot-improved python src/cli.py
```

**Docker Features:**
- ✅ Production-ready with security best practices
- ✅ Non-root user for security
- ✅ Optimized layer caching
- ✅ Proper environment setup
- ✅ Includes all required system dependencies
- ✅ Volume mounting for persistent data

## Testing

```bash
# Run unit tests
python -m pytest tests/
```

## Architecture

**Simple but Scalable Design:**
- **Hybrid Retrieval**: Keyword extraction + semantic embeddings with weighted scoring
- **AI Integration**: Pluggable providers (Mock, Gemini, OpenAI)
- **Validation**: JSON schema compliance with comprehensive error handling
- **Reporting**: Detailed audit trails with reasoning and assumptions
- **Caching**: Persistent search indices and embeddings cache
- **Modular Architecture**: Clean separation of concerns with shared utilities

## Key Features

✅ **Smart Test Case Updates**: Intelligent decision-making with minimal, targeted changes  
✅ **New Test Generation**: Positive, negative, edge cases automatically generated  
✅ **Enhanced Retrieval**: Keyword extraction + semantic search with intelligent priority scoring  
✅ **Numerical Consistency**: Preserves original values unless specifically required by bug fixes  
✅ **Schema Validation**: All outputs validated against JSON schema with error handling  
✅ **Multiple AI Providers**: Gemini 2.5 Flash Lite, OpenAI with mock fallback for development  
✅ **Comprehensive Reports**: Full audit trail with detailed reasoning and assumptions  
✅ **Production Docker**: Security-hardened container with optimized caching  
✅ **Modular Architecture**: Clean separation with shared utilities and extensible design  
✅ **Easy Setup**: Works out of the box with automated scripts and .env file support  
✅ **Smart Decision Framework**: Evaluates relevance before making any test case changes


## Example Usage

```bash
$ python src/cli.py

🤖 AI-based QA Change Request Orchestrator
==================================================

📄 Available sample files:
  1. sample_change_request_bug_fix.md
  2. sample_change_request_feature_update.md  
  3. sample_change_request_new_feature.md

Select a sample file (1-3): 2

📋 Parsing change request...
✅ Change type: feature_update
✅ Title: Reduce free cancellation window to 12 hours

🚀 Processing change request...
🔍 Retrieved 2 relevant test cases
📝 Analyzing test cases for updates...
✅ Completed: 2 test cases updated

📊 Summary
====================
Change Type: feature_update
Updated Files: 2
  - tc_004.json
  - tc_003.json
Report: reports/feature_update_..._report.md

🎉 All done! Check the report for details.
```

---

## Recent Improvements

### 🧠 **Enhanced AI Decision Making**
- **Smart Test Case Evaluation**: AI now evaluates whether test cases actually need updates before making changes
- **Minimal Change Philosophy**: Only modifies test cases when absolutely necessary
- **Numerical Consistency**: Preserves original values unless bug fix specifically requires changes
- **Decision Framework**: 4-question evaluation process to determine update necessity

### 🔍 **Improved Retrieval System**
- **Fixed Priority Scoring**: Now correctly differentiates P1-Critical (1.0), P2-High (0.8), P3-Medium (0.6), P4-Low (0.4)
- **Better Relevance Ranking**: Higher priority test cases get appropriate boost in search results
- **Enhanced Search Accuracy**: Improved keyword and semantic matching

### 🛠 **Better Developer Experience**
- **Automatic .env Support**: API keys automatically loaded from `.env` file
- **Streamlined Prompts**: Optimized prompt length for better AI performance
- **Enhanced Error Handling**: Better handling of LLM response parsing and validation
- **Improved Reporting**: More detailed decision-making documentation in reports

### 🚀 **Model & Configuration Updates**
- **Gemini 2.5 Flash Lite**: Updated to latest model for better performance
- **Balanced Safety Filters**: Configured for technical content while maintaining safety
- **Optimized Token Usage**: Reduced prompt verbosity without losing effectiveness

---

**Ready to use!** Just run `./run.sh` and follow the prompts.