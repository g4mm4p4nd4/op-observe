"""In-memory Qdrant-compatible vector store used for tests."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, MutableMapping

from ..models import Vector, VectorMatch, VectorRecord
from .hnsw import HnswIndex


@dataclass
class CollectionConfig:
    name: str
    vector_size: int
    m: int = 16
    ef_search: int = 32


class LocalQdrantClient:
    """Simple in-memory substitute for the Qdrant client."""

    def __init__(self) -> None:
        self._collections: MutableMapping[str, HnswIndex] = {}
        self._payloads: MutableMapping[str, MutableMapping[str, MutableMapping[str, object]]] = {}

    def recreate_collection(self, collection_name: str, config: CollectionConfig) -> None:
        self._collections[collection_name] = HnswIndex(
            dim=config.vector_size,
            m=config.m,
            ef_search=config.ef_search,
        )
        self._payloads[collection_name] = {}

    def upsert(self, collection_name: str, records: Iterable[VectorRecord]) -> None:
        index = self._collections[collection_name]
        payload_store = self._payloads[collection_name]
        for record in records:
            payload_store[record.point_id] = dict(record.payload)
            if record.point_id in index._vectors:
                index.update_point(record.point_id, record.vector)
            else:
                index.add_point(record.point_id, record.vector)

    def search(self, collection_name: str, vector: Vector, top_k: int) -> List[VectorMatch]:
        index = self._collections[collection_name]
        payload_store = self._payloads[collection_name]
        matches = index.search(vector, top_k)
        results = [
            VectorMatch(
                point_id=point_id,
                score=score,
                payload=dict(payload_store[point_id]),
                vector=list(index._vectors[point_id]),
            )
            for point_id, score in matches
        ]
        return results


class QdrantVectorStore:
    """Facade over :class:`LocalQdrantClient` for ingestion and search."""

    def __init__(
        self,
        client: LocalQdrantClient,
        collection_name: str,
        vector_size: int,
        m: int = 16,
        ef_search: int = 32,
    ) -> None:
        self.client = client
        self.collection_name = collection_name
        self.config = CollectionConfig(collection_name, vector_size, m=m, ef_search=ef_search)
        self.client.recreate_collection(collection_name, self.config)

    def upsert_documents(self, records: Iterable[VectorRecord]) -> None:
        self.client.upsert(self.collection_name, records)

    def search(self, vector: Vector, top_k: int) -> List[VectorMatch]:
        return self.client.search(self.collection_name, vector, top_k)

    def __len__(self) -> int:
        index = self.client._collections[self.collection_name]
        return len(index)
