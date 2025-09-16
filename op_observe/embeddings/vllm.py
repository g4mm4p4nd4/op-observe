"""vLLM embedding backend using an OpenAI-compatible HTTP endpoint."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable, List, Mapping, MutableMapping, Optional

from .base import BaseEmbedder
from ..models import Vector, ensure_vector

try:  # pragma: no cover - optional dependency
    import requests
except Exception:  # pragma: no cover - optional dependency
    requests = None  # type: ignore


@dataclass
class VLLMConfig:
    endpoint: str
    model: str
    api_key: Optional[str] = None
    timeout: float = 10.0
    headers: Optional[Mapping[str, str]] = None


class VLLMEmbedder(BaseEmbedder):
    """Call a vLLM server that exposes the OpenAI embeddings API."""

    def __init__(self, config: VLLMConfig):
        if requests is None:  # pragma: no cover - environment dependent
            raise RuntimeError("requests is required for the vLLM embedder")
        self._config = config
        self._dimension = None

    @property
    def dimension(self) -> int:
        if self._dimension is None:  # pragma: no cover - network dependent
            vector = self.embed("")
            self._dimension = len(vector)
        return self._dimension

    def _headers(self) -> MutableMapping[str, str]:
        headers: MutableMapping[str, str] = {"Content-Type": "application/json"}
        if self._config.headers:
            headers.update(dict(self._config.headers))
        if self._config.api_key:
            headers.setdefault("Authorization", f"Bearer {self._config.api_key}")
        return headers

    def embed(self, text: str) -> Vector:
        payload = {"input": [text], "model": self._config.model}
        response = requests.post(  # type: ignore[operator]
            self._config.endpoint,
            data=json.dumps(payload),
            headers=self._headers(),
            timeout=self._config.timeout,
        )
        response.raise_for_status()
        data = response.json()
        vector = data["data"][0]["embedding"]
        return ensure_vector(vector)

    def embed_batch(self, texts: Iterable[str]) -> List[Vector]:
        payload = {"input": list(texts), "model": self._config.model}
        response = requests.post(  # type: ignore[operator]
            self._config.endpoint,
            data=json.dumps(payload),
            headers=self._headers(),
            timeout=self._config.timeout,
        )
        response.raise_for_status()
        data = response.json()
        return [ensure_vector(item["embedding"]) for item in data["data"]]
