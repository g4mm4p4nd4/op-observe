"""
Retrieval module for OP-Observe.

This package defines retrieval infrastructure for semantic search and RAG.

Components:
- Vector database management using Qdrant with HNSW index and NVMe storage.
- Embedding utilities using efficient on-device models (ONNX INT8 or vLLM).
- Search functions implementing low-latency approximate nearest neighbor (ANN) search.
- Optional reranking integration for improved recall without impacting p95 latency.
- Caching strategies, ef_search tuning, NUMA pinning, and asynchronous refinement.

Future work:
Implement retrieval API, dataset ingestion pipelines, and integration with agent frameworks.

"""
