"""Test case storage and management using SQLite with JSONB-like functionality."""

import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
import hashlib


class TestCaseStore:
    """SQLite-based test case store with JSONB-like functionality."""
    
    def __init__(self, db_path: Path = Path("test_cases.db")):
        """
        Initialize the test case store.
        
        Args:
            db_path: Path to the SQLite database file
        """
        # Ensure parent directory exists
        self.db_path = Path(db_path)
        parent_dir = self.db_path.parent
        if str(parent_dir) != '' and not parent_dir.exists():
            parent_dir.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Initialize the database schema."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS test_cases (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    priority TEXT DEFAULT 'P2',
                    tags TEXT,  -- JSON array of tags
                    components TEXT,  -- JSON array of components
                    text_blob TEXT NOT NULL,  -- Concatenated description, steps, expected_result
                    vector TEXT,  -- JSON array of embedding vector
                    metadata TEXT,  -- JSON object with additional metadata
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for better performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_title ON test_cases(title)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_priority ON test_cases(priority)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tags ON test_cases(tags)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_components ON test_cases(components)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_text_blob ON test_cases(text_blob)")
            
            conn.commit()
    
    def store_test_case(self, test_case: Dict[str, Any], vector: Optional[List[float]] = None) -> str:
        """
        Store a test case in the database.
        
        Args:
            test_case: Test case dictionary
            vector: Optional embedding vector
            
        Returns:
            Test case ID
        """
        tc_id = test_case.get("id", self._generate_id(test_case))
        
        # Extract components and tags
        tags = test_case.get("tags", [])
        components = self._extract_components(test_case)
        
        # Create text blob from description, steps, and expected result
        text_parts = []
        if test_case.get("description"):
            text_parts.append(test_case["description"])
        
        # Handle steps - can be strings or objects with step_text and step_expected
        if test_case.get("steps"):
            for step in test_case["steps"]:
                if isinstance(step, str):
                    text_parts.append(step)
                elif isinstance(step, dict):
                    if step.get("step_text"):
                        text_parts.append(step["step_text"])
                    if step.get("step_expected"):
                        text_parts.append(step["step_expected"])
        
        if test_case.get("expected_result"):
            text_parts.append(test_case["expected_result"])
        
        text_blob = " ".join(text_parts)
        
        # Determine priority from test case or tags
        priority = test_case.get("priority", "P2")
        if priority and not priority.startswith("P"):
            priority = self._extract_priority_from_string(priority)
        if not priority or not priority.startswith("P"):
            priority = self._extract_priority(tags)
        
        # Prepare metadata
        metadata = {
            "preconditions": test_case.get("preconditions", []),
            "original_file": test_case.get("_source_file", ""),
            "created_by": test_case.get("created_by", "system")
        }
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO test_cases 
                (id, title, priority, tags, components, text_blob, vector, metadata, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                tc_id,
                test_case["title"],
                priority,
                json.dumps(tags),
                json.dumps(components),
                text_blob,
                json.dumps(vector) if vector else None,
                json.dumps(metadata)
            ))
            conn.commit()
        
        return tc_id
    
    def store_test_cases_from_directory(self, test_cases_dir: Path) -> int:
        """
        Store all test cases from a directory.
        
        Args:
            test_cases_dir: Directory containing test case JSON files
            
        Returns:
            Number of test cases stored
        """
        count = 0
        for json_file in test_cases_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    test_case = json.load(f)
                    test_case["_source_file"] = str(json_file)
                    self.store_test_case(test_case)
                    count += 1
            except Exception as e:
                print(f"⚠️  Failed to store {json_file}: {e}")
        
        return count
    
    def search_by_keywords(self, keywords: List[str], limit: int = 200) -> List[Dict[str, Any]]:
        """
        Search test cases by keywords using SQL LIKE queries.
        
        Args:
            keywords: List of keywords to search for
            limit: Maximum number of results
            
        Returns:
            List of matching test cases
        """
        if not keywords:
            return []
        
        # Build SQL query with LIKE conditions
        conditions = []
        params = []
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            conditions.append("""
                (LOWER(title) LIKE ? OR 
                 LOWER(text_blob) LIKE ? OR 
                 LOWER(tags) LIKE ? OR 
                 LOWER(components) LIKE ?)
            """)
            params.extend([f"%{keyword_lower}%"] * 4)
        
        query = f"""
            SELECT id, title, priority, tags, components, text_blob, metadata, vector
            FROM test_cases 
            WHERE {' OR '.join(conditions)}
            ORDER BY priority ASC, title ASC
            LIMIT ?
        """
        params.append(limit)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            results = []
            
            for row in cursor.fetchall():
                result = {
                    "doc_id": row["id"],
                    "title": row["title"],
                    "priority": row["priority"],
                    "tags": json.loads(row["tags"]) if row["tags"] else [],
                    "components": json.loads(row["components"]) if row["components"] else [],
                    "text_blob": row["text_blob"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    "vector": json.loads(row["vector"]) if row["vector"] else None
                }
                results.append(result)
            
            return results
    
    def get_test_case(self, tc_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific test case by ID.
        
        Args:
            tc_id: Test case ID
            
        Returns:
            Test case dictionary or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM test_cases WHERE id = ?
            """, (tc_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "title": row["title"],
                    "priority": row["priority"],
                    "tags": json.loads(row["tags"]) if row["tags"] else [],
                    "components": json.loads(row["components"]) if row["components"] else [],
                    "text_blob": row["text_blob"],
                    "vector": json.loads(row["vector"]) if row["vector"] else None,
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {}
                }
        
        return None
    
    def get_all_test_cases(self) -> List[Dict[str, Any]]:
        """Get all test cases from the database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM test_cases ORDER BY priority ASC, title ASC")
            
            results = []
            for row in cursor.fetchall():
                result = {
                    "id": row["id"],
                    "title": row["title"],
                    "priority": row["priority"],
                    "tags": json.loads(row["tags"]) if row["tags"] else [],
                    "components": json.loads(row["components"]) if row["components"] else [],
                    "text_blob": row["text_blob"],
                    "vector": json.loads(row["vector"]) if row["vector"] else None,
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {}
                }
                results.append(result)
            
            return results
    
    def update_vector(self, tc_id: str, vector: List[float]):
        """Update the embedding vector for a test case."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE test_cases 
                SET vector = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            """, (json.dumps(vector), tc_id))
            conn.commit()
    
    def clear_database(self):
        """Clear all test cases from the database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM test_cases")
            conn.commit()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) as total FROM test_cases")
            total = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT COUNT(*) as with_vectors FROM test_cases WHERE vector IS NOT NULL")
            with_vectors = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT priority, COUNT(*) as count FROM test_cases GROUP BY priority")
            priority_counts = dict(cursor.fetchall())
            
            return {
                "total_test_cases": total,
                "with_vectors": with_vectors,
                "priority_distribution": priority_counts
            }
    
    def _generate_id(self, test_case: Dict[str, Any]) -> str:
        """Generate a unique ID for a test case."""
        content = f"{test_case.get('title', '')}{test_case.get('description', '')}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def _extract_components(self, test_case: Dict[str, Any]) -> List[str]:
        """Extract components from test case tags and content."""
        components = []
        
        # Extract from tags
        tags = test_case.get("tags", [])
        for tag in tags:
            if any(comp in tag.lower() for comp in ["onboarding", "positions", "graphql", "api", "ui", "auth"]):
                components.append(tag)
        
        # Extract from preconditions
        preconditions = test_case.get("preconditions", [])
        for precondition in preconditions:
            if any(comp in precondition.lower() for comp in ["onboarding", "positions", "graphql", "api", "ui", "auth"]):
                components.append(precondition)
        
        return list(set(components))
    
    def _extract_priority(self, tags: List[str]) -> str:
        """Extract priority from tags or default to P2."""
        for tag in tags:
            if tag.upper() in ["P0", "P1", "P2", "P3"]:
                return tag.upper()
        return "P2"
    
    def _extract_priority_from_string(self, priority_str: str) -> str:
        """Extract priority from string like 'P2 - High'."""
        if not priority_str:
            return "P2"
        
        # Look for P0, P1, P2, P3 pattern
        import re
        match = re.search(r'P([0-3])', priority_str.upper())
        if match:
            return f"P{match.group(1)}"
        
        # Fallback based on keywords
        priority_lower = priority_str.lower()
        if any(word in priority_lower for word in ["critical", "urgent", "p0"]):
            return "P0"
        elif any(word in priority_lower for word in ["high", "important", "p1"]):
            return "P1"
        elif any(word in priority_lower for word in ["medium", "normal", "p2"]):
            return "P2"
        elif any(word in priority_lower for word in ["low", "p3"]):
            return "P3"
        
        return "P2"
