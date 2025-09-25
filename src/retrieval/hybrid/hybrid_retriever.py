"""Hybrid retriever with keyword filtering and semantic ranking."""

import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional

from src.database.test_case_store import TestCaseStore
from ..retriever_interface import Retriever


class HybridRetriever(Retriever):
    """Hybrid retriever with keyword filtering and semantic ranking."""
    
    def __init__(self, store: TestCaseStore, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the hybrid retriever.
        
        Args:
            store: Test case store instance
            config: Configuration dictionary with retrieval parameters
        """
        self.store = store
        self.config = config or {
            'keyword_weight': 0.4,
            'semantic_weight': 0.4,
            'priority_weight': 0.2,
            'max_candidates': 200,
            'max_results': 10,
            'min_similarity_threshold': 0.1
        }
        self._embedding_model = None
    
    @classmethod
    def from_test_case_dir(cls, test_cases_dir: Path, db_path: Optional[Path] = None, config: Optional[Dict[str, Any]] = None) -> 'HybridRetriever':
        """
        Create a hybrid retriever from a test cases directory.
        
        Args:
            test_cases_dir: Directory containing test case JSON files
            db_path: Optional path to database file
            config: Optional retrieval configuration
            
        Returns:
            HybridRetriever instance
        """
        if db_path is None:
            db_path = Path("test_cases.db")
        
        store = TestCaseStore(db_path)
        
        # Store all test cases from directory
        print(f"📚 Loading test cases from {test_cases_dir}...")
        count = store.store_test_cases_from_directory(test_cases_dir)
        print(f"✅ Stored {count} test cases in database")
        
        return cls(store, config)
    
    
    def query(self, query_text: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Query test cases using the new filtering + ranking approach.
        
        Args:
            query_text: Query text from change request
            top_k: Number of results to return
            
        Returns:
            List of relevant test cases with scores
        """
        # Step B: Extract keywords and run deterministic filters
        keywords = self._extract_keywords(query_text)
        candidates = self.store.search_by_keywords(keywords, self.config["max_candidates"])
        
        if not candidates:
            return []
        
        # Step C: Lightweight semantic re-rank
        if self._embedding_model is not None:
            candidates = self._semantic_rerank(query_text, candidates)
        
        # Apply final ranking with weights
        ranked_results = self._apply_ranking(query_text, candidates)
        
        # Return top_k results
        return ranked_results[:top_k]
    
    def _extract_keywords(self, query_text: str) -> List[str]:
        """
        Extract keywords from query text using proper stopwords library.
        
        Args:
            query_text: Input query text
            
        Returns:
            List of extracted keywords
        """
        import re
        from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
        
        # Domain-specific terms (higher priority)
        domain_terms = [
            'onboarding', 'positions', 'graphql', 'api', 'ui', 'auth', 'authentication',
            'booking', 'shift', 'approval', 'cancellation', 'notification', 'push',
            'token', 'refresh', 'login', 'logout', 'user', 'profile', 'settings',
            'payment', 'billing', 'subscription', 'waitlist', 'queue', 'priority'
        ]
        
        query_lower = query_text.lower()
        
        # Extract domain-specific keywords first (higher priority)
        domain_keywords = [term for term in domain_terms if term in query_lower]
        
        # Extract general keywords using proper stopwords
        words = re.findall(r'\b[a-zA-Z0-9_-]+\b', query_lower)
        general_keywords = [word for word in words if len(word) > 2 and word not in ENGLISH_STOP_WORDS]
        
        # Combine and remove duplicates, prioritizing domain terms
        all_keywords = domain_keywords + general_keywords
        return list(dict.fromkeys(all_keywords))  # Preserve order, remove duplicates
    
    def _semantic_rerank(self, query_text: str, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply semantic re-ranking using embeddings.
        
        Args:
            query_text: Original query text
            candidates: List of candidate test cases
            
        Returns:
            Re-ranked candidates with semantic scores
        """
        try:
            # Generate query embedding - this will raise an exception if embeddings are not available
            query_embedding = self._get_embedding(query_text)
            
            # Calculate semantic similarity for each candidate
            for candidate in candidates:
                candidate_vector = candidate.get("vector")
                if candidate_vector:
                    similarity = self._cosine_similarity(query_embedding, candidate_vector)
                    candidate["semantic_score"] = similarity
                else:
                    test_case_id = candidate.get('doc_id', candidate.get('id', 'unknown'))
                    raise ValueError(f"Test case {test_case_id} has no vector embedding. Please run generate_embeddings() first.")
            
            return candidates
            
        except Exception as e:
            raise RuntimeError(f"Semantic re-ranking failed: {e}") from e
    
    def _apply_ranking(self, query_text: str, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply final ranking with weighted scores.
        
        Args:
            query_text: Original query text
            candidates: List of candidate test cases
            
        Returns:
            Ranked results with final scores
        """
        query_lower = query_text.lower()
        
        for candidate in candidates:
            # Calculate keyword match score
            keyword_score = self._calculate_keyword_score(query_lower, candidate)
            
            # Get semantic score (default to 0 if not available)
            semantic_score = candidate.get("semantic_score", 0.0)
            
            # Calculate priority score
            priority_score = self._calculate_priority_score(candidate.get("priority", "P2"))
            
            # Calculate weighted final score
            final_score = (
                self.config["keyword_weight"] * keyword_score +
                self.config["semantic_weight"] * semantic_score +
                self.config["priority_weight"] * priority_score
            )
            
            candidate["score"] = final_score
            candidate["keyword_score"] = keyword_score
            candidate["priority_score"] = priority_score
        
        # Sort by final score (descending)
        ranked = sorted(candidates, key=lambda x: x["score"], reverse=True)
        
        # Filter by minimum similarity threshold
        filtered = [candidate for candidate in ranked if candidate["score"] >= self.config["min_similarity_threshold"]]
        
        # Log filtering results
        filtered_count = len(ranked) - len(filtered)
        if filtered_count > 0:
            threshold = self.config["min_similarity_threshold"]
            print(f"🔍 Similarity threshold filtering: {filtered_count} test cases excluded (score < {threshold})")
        
        return filtered
    
    def _calculate_keyword_score(self, query_lower: str, candidate: Dict[str, Any]) -> float:
        """Calculate keyword matching score."""
        score = 0.0
        
        # Title matches (highest weight)
        title = candidate.get("title", "").lower()
        if any(word in title for word in query_lower.split()):
            score += 0.5
        
        # Text blob matches
        text_blob = candidate.get("text_blob", "").lower()
        matches = sum(1 for word in query_lower.split() if word in text_blob)
        score += min(matches * 0.1, 0.3)  # Cap at 0.3
        
        # Tags and components matches
        tags = candidate.get("tags", [])
        components = candidate.get("components", [])
        all_tags = " ".join(tags + components).lower()
        if any(word in all_tags for word in query_lower.split()):
            score += 0.2
        
        return min(score, 1.0)  # Cap at 1.0
    
    def _calculate_priority_score(self, priority: str) -> float:
        """Calculate priority-based score."""
        priority_scores = {
            "P1": 1.0,  # Critical - highest priority
            "P2": 0.8,  # High
            "P3": 0.6,  # Medium
            "P4": 0.4   # Low - lowest priority
        }
        
        # Extract just the priority prefix (e.g., "P2" from "P2 - High")
        priority_prefix = priority.split()[0].upper() if priority else "P3"
        return priority_scores.get(priority_prefix, 0.6)
    
    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding for text using sentence transformers."""
        self._load_embedding_model()  # This will raise an exception if embeddings are not available
        
        try:
            embedding = self._embedding_model.encode([text])[0]
            return embedding.tolist()
        except Exception as e:
            raise RuntimeError(f"Failed to generate embedding: {e}") from e
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        try:
            v1 = np.array(vec1)
            v2 = np.array(vec2)
            
            dot_product = np.dot(v1, v2)
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            return dot_product / (norm1 * norm2)
        except Exception:
            return 0.0
    
    def _load_embedding_model(self):
        """Load the embedding model if not already loaded."""
        if self._embedding_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            except ImportError as e:
                raise ImportError("sentence-transformers is required for semantic ranking. Please install it with: pip install sentence-transformers") from e
    
    def generate_embeddings(self, batch_size: int = 100):
        """Generate embeddings for all test cases without vectors."""
        self._load_embedding_model()  # This will raise an exception if embeddings are not available
        
        test_cases = self.store.get_all_test_cases()
        cases_without_vectors = [tc for tc in test_cases if tc.get("vector") is None]
        
        if not cases_without_vectors:
            print("✅ All test cases already have embeddings")
            return
        
        print(f"🔄 Generating embeddings for {len(cases_without_vectors)} test cases...")
        
        for i in range(0, len(cases_without_vectors), batch_size):
            batch = cases_without_vectors[i:i + batch_size]
            texts = [tc["text_blob"] for tc in batch]
            
            try:
                embeddings = self._embedding_model.encode(texts)
                
                for tc, embedding in zip(batch, embeddings):
                    self.store.update_vector(tc["id"], embedding.tolist())
                
                print(f"✅ Generated embeddings for batch {i//batch_size + 1}")
                
            except Exception as e:
                print(f"⚠️  Failed to generate embeddings for batch {i//batch_size + 1}: {e}")
    
    
    def dump(self, cache_dir: Path):
        """Dump retriever state (database is already persistent)."""
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Save configuration
        config_path = cache_dir / "retriever_config.json"
        with open(config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
        
        print(f"✅ Hybrid retriever state saved to {cache_dir}")
    
    @classmethod
    def load_from_cache(cls, cache_dir: Path, db_path: Optional[Path] = None, config: Optional[Dict[str, Any]] = None) -> Optional['HybridRetriever']:
        """Load retriever from cache."""
        if db_path is None:
            db_path = Path("test_cases.db")
        
        if not db_path.exists():
            return None
        
        try:
            store = TestCaseStore(db_path)
            retriever = cls(store, config)
            
            # Load configuration if available
            config_path = cache_dir / "retriever_config.json"
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config_data = json.load(f)
                    retriever.config = config_data
            
            retriever._load_embedding_model()
            return retriever
            
        except Exception as e:
            print(f"⚠️  Failed to load hybrid retriever: {e}")
            return None
