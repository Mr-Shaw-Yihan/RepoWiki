"""RAG retrieval eval: fixture questions whose source file is known.

Each fixture repo goes through the real ingest + index path, every question is
retrieved with top_k=5, and a case passes when any expected file shows up in
the retrieved chunks. Deterministic and key-free: this guards chunking and
retrieval regressions in CI as a soft gate. Answer-quality eval against an
LLM stays a manual, keyed follow-up.

Usage:
    python evals/run_eval.py                  # report, exit 2 below baseline
    python evals/run_eval.py --update-baseline
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent
REPOS_DIR = EVALS_DIR / "fixtures" / "repos"
QUESTIONS_PATH = EVALS_DIR / "fixtures" / "questions.json"
BASELINE_PATH = EVALS_DIR / "baseline.json"
TOP_K = 5


@dataclass
class CaseResult:
    repo: str
    question: str
    hits: list[str]
    expect_files: list[str]

    @property
    def passed(self) -> bool:
        return bool(self.hits)


@dataclass
class EvalReport:
    cases: list[CaseResult] = field(default_factory=list)

    @property
    def overall(self) -> float:
        if not self.cases:
            return 0.0
        return sum(1 for c in self.cases if c.passed) / len(self.cases)

    def per_repo(self) -> dict[str, float]:
        repos: dict[str, list[bool]] = {}
        for case in self.cases:
            repos.setdefault(case.repo, []).append(case.passed)
        return {name: sum(marks) / len(marks) for name, marks in repos.items()}


def run_eval() -> EvalReport:
    # imported here so `python evals/run_eval.py` works from the repo root
    # with an editable install, without paying the import on --help
    from repowiki.core.rag import SimpleRAG
    from repowiki.ingest.local import ingest_local

    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    report = EvalReport()
    projects: dict[str, SimpleRAG] = {}
    for case in questions:
        repo = case["repo"]
        if repo not in projects:
            repo_dir = REPOS_DIR / repo
            if not repo_dir.is_dir():
                raise FileNotFoundError(f"fixture repo missing: {repo_dir}")
            rag = SimpleRAG()
            rag.index(ingest_local(repo_dir))
            projects[repo] = rag
        chunks = projects[repo].retrieve(case["question"], top_k=TOP_K)
        found = sorted({c.file_path for c in chunks if c.file_path in case["expect_files"]})
        report.cases.append(
            CaseResult(
                repo=repo,
                question=case["question"],
                hits=found,
                expect_files=case["expect_files"],
            )
        )
    return report


def print_report(report: EvalReport, baseline: dict | None) -> None:
    per_repo = report.per_repo()
    print(f"{'repo':<14} {'hit-rate':>8} {'baseline':>8}")
    for name in sorted(per_repo):
        base_line = ""
        if baseline and name in baseline.get("repos", {}):
            base_line = f"{baseline['repos'][name]:.0%}"
        print(f"{name:<14} {per_repo[name]:>8.0%} {base_line:>8}")
    print(f"{'overall':<14} {report.overall:>8.0%}", end="")
    if baseline and "overall" in baseline:
        print(f" {baseline['overall']:>8.0%}")
    else:
        print()
    failures = [c for c in report.cases if not c.passed]
    if failures:
        print("\nmissed cases:")
        for case in failures:
            print(f"  [{case.repo}] {case.question}")
            print(f"    expected one of: {', '.join(case.expect_files)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="record the current hit-rates as the new baseline",
    )
    args = parser.parse_args(argv)

    report = run_eval()
    if args.update_baseline:
        payload = {
            "overall": report.overall,
            "repos": report.per_repo(),
        }
        BASELINE_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"baseline updated: overall {report.overall:.0%}")
        return 0

    baseline = None
    if BASELINE_PATH.exists():
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    print_report(report, baseline)
    if baseline and report.overall < baseline.get("overall", 0.0):
        print(f"\nREGRESSION: hit-rate {report.overall:.0%} below baseline {baseline['overall']:.0%}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
