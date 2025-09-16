## Retrieval Agent Tasks

### Overview
This agent is responsible for building and maintaining the retrieval layer of OP ‑Observe. It must provide sub‑200 ms semantic search by integrating Qdrant (HNSW index) for vector storage, efficient embeddings via ONNX or vLLM, optional reranking, and caching strategies. The agent will operate on‑prem and must integrate with guardrails and telemetry.

### Tasks
- **Vector store integration**: Write Python module to interface with Qdrant. Implement functions to create index, upsert documents (with metadata), delete, and query with filters. Ensure index uses HNSW with parameters that meet latency SLOs. Provide idempotent operations and snapshot exports to MinIO.
- **Embedding pipeline**: Provide embedding function that uses a lightweight embedding model (e.g., all-MiniLM) via ONNX runtime or vLLM (OpenAI compatible). Support both CPU INT8 and optional GPU acceleration. Add CLI or API to batch compute embeddings from documents.
- **Semantic search**: Implement search endpoint returning top‑k relevant documents in ≤200 ms p95. Use asynchronous calls to embeddings and Qdrant. Expose adjustable ef_search, ef_construction, and top‑k parameters. Include optional cross‑encoder or Mistral‑style reranker that is off by default; ensure reranking does not impact p95 path.
- **Caching & tuning**: Implement hot cache using LRU or TTL to store recent query embeddings and results. Provide config to tune ANN parameters for latency/accuracy trade‑offs. Expose metrics (latency histograms, cache hits) via OpenTelemetry.
- **Testing & benchmarks**: Write unit tests for index creation, ingestion, and query functions. Develop benchmark script to measure end‑to‑end latency under load and verify p95 ≤200 ms using representative dataset. Provide sample config for enabling/disabling reranker.

### Acceptance Criteria
- All functions for index management, embedding, and querying are implemented with docstrings and type hints.
- Benchmarks show search p95 latency ≤200 ms for 1K+ documents using CPU INT8 embeddings.
- Unit tests cover typical and edge cases (empty queries, missing docs, filter conditions).
- OpenTelemetry metrics for query latency and cache hits are exposed and verified with Prometheus.
- README examples demonstrate how to ingest documents and perform semantic search via API/CLI.
