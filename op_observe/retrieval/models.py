"""Data models used across the retrieval pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, MutableMapping, Optional


@dataclass(frozen=True)
class Document:
    """Container representing a retrievable document."""

    doc_id: str
    content: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass
class SearchHit:
    """Represents a scored document returned by the retrieval pipeline."""

    document: Document
    score: float
    rank: int
    metadata: MutableMapping[str, Any] = field(default_factory=dict)

    def with_score(
        self,
        *,
        score: float,
        rank: int,
        score_source: str,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> "SearchHit":
        """Return a copy of the hit updated with a new score and rank.

        The original metadata is preserved and augmented with baseline score
        bookkeeping to make provenance explicit when a reranker adjusts the
        ordering.
        """

        merged: Dict[str, Any] = dict(self.metadata)
        merged.setdefault("baseline_score", self.score)
        merged["score_source"] = score_source
        if extra_metadata:
            merged.update(extra_metadata)
        return SearchHit(document=self.document, score=score, rank=rank, metadata=merged)


__all__ = ["Document", "SearchHit"]
