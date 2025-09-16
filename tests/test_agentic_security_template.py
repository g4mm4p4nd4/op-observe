import json
import tempfile
import unittest
from pathlib import Path

from templates.agentic_security_minimal import radar_report


class AgenticSecurityTemplateTest(unittest.TestCase):
    def test_generate_security_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            html_path, json_path = radar_report.generate_security_report(
                question="How do we handle filesystem writes?", output_dir=output_dir
            )
            self.assertTrue(html_path.exists())
            self.assertTrue(json_path.exists())
            html = html_path.read_text(encoding="utf-8")
            self.assertIn("Agentic Security Radar Report", html)
            self.assertIn("Workflow Visualization", html)
            data = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(data["question"], "How do we handle filesystem writes?")
            self.assertTrue(data["answer"])
            self.assertTrue(data["vulnerabilities"], "Expected at least one vulnerability finding")
            llm_categories = [cat for vuln in data["vulnerabilities"] for cat in vuln["owasp_llm"]]
            self.assertTrue(any(cat.startswith("LLM") for cat in llm_categories))


if __name__ == "__main__":
    unittest.main()
