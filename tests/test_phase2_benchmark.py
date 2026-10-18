"""Phase 2 — ENG-09 benchmark harness smoke tests."""
import json
import os
import subprocess
import sys


class TestBenchmarkHarness:
    def test_gold_data_exists(self):
        gold_dir = os.path.join(os.path.dirname(__file__), "..",
                                "benchmarks", "resume_gold")
        files = [f for f in os.listdir(gold_dir) if f.endswith(".json")]
        assert len(files) >= 10, "need at least 10 gold resumes"

    def test_gold_labels_complete(self):
        gold_dir = os.path.join(os.path.dirname(__file__), "..",
                                "benchmarks", "resume_gold")
        for fn in os.listdir(gold_dir):
            if not fn.endswith(".json"):
                continue
            with open(os.path.join(gold_dir, fn)) as f:
                item = json.load(f)
            assert "text" in item and len(item["text"]) > 50
            labels = item["labels"]
            for field in ["name", "email", "phone", "skills"]:
                assert field in labels, f"{fn} missing {field}"

    def test_benchmark_runs(self):
        result = subprocess.run(
            [sys.executable, "benchmarks/run.py", "--quick"],
            capture_output=True, text=True, cwd=os.path.join(
                os.path.dirname(__file__), ".."),
            timeout=60)
        assert result.returncode == 0, result.stderr
        out = json.loads(result.stdout.split("\nWrote")[0])
        assert out["n_items"] == 10
        assert out["parse_success_rate"] >= 0.9
