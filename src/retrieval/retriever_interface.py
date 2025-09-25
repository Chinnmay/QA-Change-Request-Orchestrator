from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Dict


class Retriever(ABC):
    @abstractmethod
    def query(self, query_text: str, top_k: int = 10) -> List[Dict]:  # pragma: no cover - interface only
        raise NotImplementedError



