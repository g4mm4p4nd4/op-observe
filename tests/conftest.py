from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from op_observe.embeddings.base import BaseEmbedder
from op_observe.retrieval import RetrievalConfig, RetrievalPipeline
from op_observe.rerankers import DotProductReranker
from op_observe.vector_store.qdrant import LocalQdrantClient, QdrantVectorStore


class DeterministicEmbedder(BaseEmbedder):
    def __init__(self, dimension: int = 8):
        self._dimension = dimension
        self.calls = 0

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, text: str):
        self.calls += 1
        vector = [0.0 for _ in range(self._dimension)]
        text_lower = text.lower()
        tokens = text_lower.split()
        if not tokens:
            return vector
        for token in tokens:
            bucket = sum(ord(char) for char in token) % self._dimension
            vector[bucket] += 1.0
        return vector

    def embed_batch(self, texts: Iterable[str]):
        return [self.embed(text) for text in texts]


@dataclass
class PipelineFixture:
    embedder: DeterministicEmbedder
    pipeline: RetrievalPipeline


def build_pipeline(use_reranker: bool = False, cache_size: int = 16) -> PipelineFixture:
    embedder = DeterministicEmbedder()
    client = LocalQdrantClient()
    store = QdrantVectorStore(client, "test", embedder.dimension)
    config = RetrievalConfig(use_reranker=use_reranker, cache_size=cache_size)
    reranker = DotProductReranker() if use_reranker else None
    pipeline = RetrievalPipeline(embedder, store, reranker=reranker, config=config)
    return PipelineFixture(embedder=embedder, pipeline=pipeline)
