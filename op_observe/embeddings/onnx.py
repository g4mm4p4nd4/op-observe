"""ONNX Runtime embedding backend."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from .base import BaseEmbedder
from ..models import Vector, ensure_vector

try:
    import onnxruntime as ort  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    ort = None  # type: ignore


class OnnxEmbedder(BaseEmbedder):
    """Embed texts using an ONNX model via ONNX Runtime."""

    def __init__(self, model_path: str | Path, input_name: str, output_name: str):
        if ort is None:  # pragma: no cover - environment dependent
            raise RuntimeError("onnxruntime is not installed")
        self._session = ort.InferenceSession(str(model_path))  # type: ignore[attr-defined]
        self._input_name = input_name
        self._output_name = output_name
        self._dimension = self._infer_dimension()

    def _infer_dimension(self) -> int:
        dummy_text = ""
        vector = self.embed(dummy_text)
        return len(vector)

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, text: str) -> Vector:
        inputs = {self._input_name: [text]}
        outputs = self._session.run([self._output_name], inputs)
        vector = outputs[0][0]
        return ensure_vector(vector)

    def embed_batch(self, texts: Iterable[str]) -> List[Vector]:
        inputs = {self._input_name: list(texts)}
        outputs = self._session.run([self._output_name], inputs)
        return [ensure_vector(vector) for vector in outputs[0]]
