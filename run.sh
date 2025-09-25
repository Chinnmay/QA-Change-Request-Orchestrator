#!/bin/bash

# Quick run script for QA Change Request Orchestrator
# This script activates the virtual environment and runs the CLI

set -e  # Exit on any error

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run setup_venv.sh first."
    exit 1
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Set PYTHONPATH
export PYTHONPATH="$PWD"

# Run the CLI (no arguments needed)
echo "🚀 Running QA Change Request Orchestrator..."
python src/cli.py
