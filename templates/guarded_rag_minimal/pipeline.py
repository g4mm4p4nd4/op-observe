"""Guarded RAG demo powered by an in-memory Qdrant instance."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams

CONFIG_PATH = Path(__file__).with_name("guard_config.json")

DOCUMENTS: List[Dict[str, Any]] = [
    {
        "id": 1,
        "title": "Agentic Radar Overview",
        "text": "Agentic radar maps LangGraph workflows to OWASP risks and produces HTML reports.",
        "triggers": ["radar", "owasp", "langgraph"],
    },
    {
        "id": 2,
        "title": "Guardrails & LLM-Critic",
        "text": "Guardrails with an LLM-Critic ensure answers cite retrieved evidence before release.",
        "triggers": ["guardrails", "critic", "evidence"],
    },
    {
        "id": 3,
        "title": "TruLens & OpenLIT",
        "text": "Lightweight evals track retrieval recall and precision for every conversation.",
        "triggers": ["evals", "recall", "precision"],
    },
]


class SimpleEmbedder:
    """Deterministic embedding used to avoid network calls in tests."""

    dimension = 8

    def embed(self, text: str) -> List[float]:
        vector = [0.0] * self.dimension
        tokens = text.lower().split()
        if not tokens:
            return vector
        for index, token in enumerate(tokens):
            bucket = index % self.dimension
            score = sum(ord(ch) for ch in token) % 101
            vector[bucket] += score / 100.0
        norm = sum(value * value for value in vector) ** 0.5 or 1.0
        return [round(value / norm, 6) for value in vector]


@dataclass
class CriticReport:
    score: float
    passed: bool
    reasons: List[str]
    covered_contexts: int


class SimpleLLMCritic:
    """Rule-based critic that verifies whether answers cite retrieved contexts."""

    def __init__(self, min_score: float, require_overlap: bool) -> None:
        self.min_score = min_score
        self.require_overlap = require_overlap

    def review(self, question: str, answer: str, contexts: Sequence[Dict[str, Any]]) -> CriticReport:
        lowered_answer = answer.lower()
        overlap = sum(1 for ctx in contexts if ctx["text"].lower() in lowered_answer)
        coverage = overlap / max(len(contexts), 1)
        reasons: List[str] = []
        if self.require_overlap and overlap == 0 and contexts:
            reasons.append("Answer does not include retrieved evidence verbatim.")
        if len(answer.split()) < 8:
            reasons.append("Answer is too short to be actionable.")
        passed = coverage >= self.min_score and (not self.require_overlap or overlap > 0 or not contexts)
        return CriticReport(score=round(coverage, 3), passed=passed, reasons=reasons, covered_contexts=overlap)


@dataclass
class GuardOutcome:
    answer: str
    passed: bool
    report: CriticReport


class Guardrails:
    def __init__(self, critic: SimpleLLMCritic, fallback_response: str) -> None:
        self.critic = critic
        self.fallback_response = fallback_response

    def enforce(self, question: str, answer: str, contexts: Sequence[Dict[str, Any]]) -> GuardOutcome:
        report = self.critic.review(question, answer, contexts)
        final_answer = answer if report.passed else self.fallback_response
        return GuardOutcome(answer=final_answer, passed=report.passed, report=report)


@dataclass
class EvalMetrics:
    retrieval_recall: float
    context_precision: float


class EvaluationSuite:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.recall_floor = float(config.get("recall_floor", 0.0))
        self.precision_floor = float(config.get("precision_floor", 0.0))

    def _expected_documents(self, question: str) -> List[int]:
        lowered = question.lower()
        matches = [doc["id"] for doc in DOCUMENTS if any(trigger in lowered for trigger in doc["triggers"])]
        return matches or [doc["id"] for doc in DOCUMENTS]

    def evaluate(self, question: str, contexts: Sequence[Dict[str, Any]]) -> EvalMetrics:
        expected = set(self._expected_documents(question))
        retrieved = {ctx["id"] for ctx in contexts}
        recall = len(expected & retrieved) / len(expected)
        precision = 1.0 if not retrieved else len(expected & retrieved) / len(retrieved)
        return EvalMetrics(
            retrieval_recall=round(recall, 3),
            context_precision=round(precision, 3),
        )


class GuardedRAGPipeline:
    def __init__(self, config_path: Path | None = None) -> None:
        path = config_path or CONFIG_PATH
        self.config = json.loads(path.read_text())
        self.embedder = SimpleEmbedder()
        self.client = QdrantClient(location=":memory:")
        self.collection_name = "guarded_rag"
        self._ensure_collection()
        self.guardrails = Guardrails(
            critic=SimpleLLMCritic(
                min_score=float(self.config["llm_critic"]["min_score"]),
                require_overlap=bool(self.config["llm_critic"].get("require_context_overlap", True)),
            ),
            fallback_response=self.config["llm_critic"]["fallback_response"],
        )
        self.evaluator = EvaluationSuite(self.config.get("evals", {}))
        self.bootstrap_knowledge_base(DOCUMENTS)

    def _ensure_collection(self) -> None:
        self.client.recreate_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=self.embedder.dimension, distance=Distance.COSINE),
        )

    def bootstrap_knowledge_base(self, documents: Iterable[Dict[str, Any]]) -> None:
        points = [
            PointStruct(
                id=doc["id"],
                vector=self.embedder.embed(doc["text"]),
                payload={"text": doc["text"], "triggers": doc["triggers"], "title": doc["title"]},
            )
            for doc in documents
        ]
        self.client.upsert(collection_name=self.collection_name, points=points)

    def retrieve(self, question: str, limit: int = 3) -> List[Dict[str, Any]]:
        query = self.embedder.embed(question)
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query,
            limit=limit,
        )
        return [
            {
                "id": int(hit.id),
                "score": float(hit.score),
                "text": hit.payload["text"],
                "triggers": hit.payload["triggers"],
                "title": hit.payload["title"],
            }
            for hit in results
        ]

    def generate_answer(self, question: str, contexts: Sequence[Dict[str, Any]]) -> str:
        if not contexts:
            return "No supporting evidence was retrieved."
        snippets = [ctx["text"] for ctx in contexts[:2]]
        joined = " ".join(snippets)
        return (
            "The guardrailed knowledge base reports: "
            f"{joined}"
        )

    def answer_question(self, question: str) -> Dict[str, Any]:
        contexts = self.retrieve(question)
        draft_answer = self.generate_answer(question, contexts)
        guard_outcome = self.guardrails.enforce(question, draft_answer, contexts)
        eval_metrics = self.evaluator.evaluate(question, contexts)
        return {
            "answer": guard_outcome.answer,
            "guard_passed": guard_outcome.passed,
            "critic": {
                "score": guard_outcome.report.score,
                "reasons": guard_outcome.report.reasons,
                "covered_contexts": guard_outcome.report.covered_contexts,
            },
            "retrieved_context": contexts,
            "evals": asdict(eval_metrics),
        }


def main() -> None:
    pipeline = GuardedRAGPipeline()
    question = "How does the radar integrate with guardrails?"
    result = pipeline.answer_question(question)
    print(f"Question: {question}")
    print(f"Answer: {result['answer']}")
    print("Guard verdict:", result["guard_passed"], "score=", result["critic"]["score"])
    print("Eval metrics:", result["evals"])


if __name__ == "__main__":
    main()
