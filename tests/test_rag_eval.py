"""The retrieval eval fixture suite, pinned at its recorded baseline.

This is the blocking form of evals/run_eval.py: every fixture question must
keep hitting its expected file. A drop means chunking or tokenization moved
under the answers. The CI rag-eval job reruns the same suite as a soft gate.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evals"))

from run_eval import BASELINE_PATH, run_eval  # noqa: E402


def test_fixture_suite_holds_baseline():
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    report = run_eval()
    missed = [f"[{c.repo}] {c.question}" for c in report.cases if not c.passed]
    assert not missed, "eval cases lost their expected file:\n" + "\n".join(missed)
    assert report.overall >= baseline["overall"]


def test_runner_reports_missed_cases(tmp_path, monkeypatch):
    # a case whose expected file cannot exist must fail loudly, not silently pass
    import run_eval as runner

    fake_questions = [
        {"repo": "taskvane", "question": "How are tasks persisted to disk?", "expect_files": ["nope/missing.py"]}
    ]
    monkeypatch.setattr(runner, "QUESTIONS_PATH", _write(tmp_path, fake_questions))
    report = runner.run_eval()
    assert report.overall == 0.0
    assert all(not case.passed for case in report.cases)


def _write(tmp_path: Path, payload) -> Path:
    path = tmp_path / "questions.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path
