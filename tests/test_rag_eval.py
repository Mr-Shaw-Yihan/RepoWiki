"""The retrieval eval fixture suite, pinned at its recorded baseline.

This is the blocking form of evals/run_eval.py: every direct fixture question
must keep hitting its expected file through the plain TF-IDF channel, and the
module-card boosted channel must pass the whole suite, paraphrase questions
included. A drop means chunking, tokenization or the card layer moved under
the answers. The CI rag-eval job reruns the same suite as a soft gate.
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
    missed = [
        f"[{c.repo}] {c.question}"
        for c in report.cases
        if not c.passed and c.tier != "paraphrase"
    ]
    assert not missed, "direct eval cases lost their expected file:\n" + "\n".join(missed)
    assert report.overall >= baseline["overall"]
    boosted_missed = [f"[{c.repo}] {c.question}" for c in report.boosted_cases if not c.passed]
    assert not boosted_missed, (
        "the module-card channel lost an expected file:\n" + "\n".join(boosted_missed)
    )
    assert report.boosted_overall >= baseline["boosted"]["overall"]


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
