#!/usr/bin/env python3
"""Simple script to reset the database cache."""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.database import clear_database_cache

def main():
    """Reset the database cache."""
    print("🔄 Resetting database cache...")
    
    cache_dir = Path('.cache')
    clear_database_cache(cache_dir)
    
    print("✅ Database cache cleared successfully!")
    print("🔄 The database will be rebuilt with fresh embeddings on next run.")
    print("\n💡 You can now run your pipelines and they will rebuild the database.")

if __name__ == "__main__":
    main()
