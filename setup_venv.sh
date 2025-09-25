#!/bin/bash

# Virtual Environment Setup Script for QA Change Request Orchestrator
# This script creates and configures a virtual environment for the project

set -e  # Exit on any error

echo "🚀 Setting up virtual environment for QA Change Request Orchestrator..."

# Check if Python 3.11 is available
if ! command -v python3.11 &> /dev/null; then
    echo "❌ Python 3.11 not found. Please install Python 3.11 first."
    echo "   You can install it using: brew install python@3.11"
    exit 1
fi

# Create virtual environment
echo "📦 Creating virtual environment..."
python3.11 -m venv venv

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📚 Installing project dependencies..."
pip install -r requirements.txt

echo ""
echo "✅ Virtual environment setup complete!"
echo ""
echo "To activate the virtual environment, run:"
echo "  source venv/bin/activate"
echo ""
echo "To run the QA Change Request Orchestrator:"
echo "  source venv/bin/activate"
echo "  export PYTHONPATH=\"\$PWD\""
echo "  python -m src.cli --interactive"
echo ""
echo "To deactivate the virtual environment:"
echo "  deactivate"
echo ""
