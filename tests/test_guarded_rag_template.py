import unittest

from templates.guarded_rag_minimal.pipeline import GuardedRAGPipeline


class GuardedRAGTemplateTest(unittest.TestCase):
    def test_guarded_rag_pipeline_runs(self) -> None:
        pipeline = GuardedRAGPipeline()
        question = "Explain how radar and guardrails work together."
        result = pipeline.answer_question(question)
        self.assertIn("answer", result)
        self.assertTrue(result["retrieved_context"], "Expected retrieval hits")
        self.assertTrue(result["guard_passed"])
        self.assertGreaterEqual(result["critic"]["score"], pipeline.config["llm_critic"]["min_score"])
        self.assertGreaterEqual(result["evals"]["retrieval_recall"], 0.0)
        self.assertLessEqual(result["evals"]["retrieval_recall"], 1.0)
        self.assertGreaterEqual(result["evals"]["context_precision"], 0.0)
        self.assertLessEqual(result["evals"]["context_precision"], 1.0)


if __name__ == "__main__":
    unittest.main()
