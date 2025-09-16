# OP-Observe Retrieval Pipeline

This package implements a retrieval pipeline for OP-Observe with an in-memory Qdrant-compatible
vector store, ONNX Runtime and vLLM embedding integrations, HNSW-inspired indexing, query caching,
and optional reranking.

The unit tests exercise ingestion, retrieval, caching, and latency guarantees, while the benchmark
test ensures sub-200ms search performance for typical workloads.
