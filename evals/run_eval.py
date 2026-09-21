"""RAG retrieval eval: fixture questions whose source file is known.

Each fixture repo goes through the real ingest + index path, every question is
retrieved with top_k=5, and a case passes when any expected file shows up in
the retrieved chunks. Deterministic and key-free: this guards chunking and
retrieval regressions in CI as a soft gate. Answer-quality eval against an
LLM stays a manual, keyed follow-up.

Two rates are reported. "plain" is raw TF-IDF and is gated on the direct
questions only, so paraphrase additions never mask a chunking regression.
"boosted" adds the module-card layer (fixtures under fixtures/modules/) and
is gated over every case; paraphrase questions exist to prove the boost.

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
from types import SimpleNamespace

EVALS_DIR = Path(__file__).resolve().parent
REPOS_DIR = EVALS_DIR / "fixtures" / "repos"
QUESTIONS_PATH = EVALS_DIR / "fixtures" / "questions.json"
MODULES_DIR = EVALS_DIR / "fixtures" / "modules"
BASELINE_PATH = EVALS_DIR / "baseline.json"
TOP_K = 5


def _as_namespace(value):
    """Recursively turn fixture JSON into attribute access, matching the
    ModuleDoc/Concept/FileDoc shape ModuleIndex reads."""
    if isinstance(value, dict):
        return SimpleNamespace(**{k: _as_namespace(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_as_namespace(v) for v in value]
    return value


@dataclass
class CaseResult:
    repo: str
    question: str
    tier: str
    hits: list[str]
    expect_files: list[str]

    @property
    def passed(self) -> bool:
        return bool(self.hits)


@dataclass
class EvalReport:
    cases: list[CaseResult] = field(default_factory=list)
    boosted_cases: list[CaseResult] = field(default_factory=list)

    @staticmethod
    def _rate(cases: list[CaseResult]) -> float:
        if not cases:
            return 0.0
        return sum(1 for c in cases if c.passed) / len(cases)

    @staticmethod
    def _per_repo(cases: list[CaseResult]) -> dict[str, float]:
        repos: dict[str, list[bool]] = {}
        for case in cases:
            repos.setdefault(case.repo, []).append(case.passed)
        return {name: sum(marks) / len(marks) for name, marks in repos.items()}

    @property
    def overall(self) -> float:
        """Plain TF-IDF over the direct questions (the historical gate)."""
        return self._rate([c for c in self.cases if c.tier != "paraphrase"])

    @property
    def boosted_overall(self) -> float:
        return self._rate(self.boosted_cases)

    def per_repo(self) -> dict[str, float]:
        return self._per_repo([c for c in self.cases if c.tier != "paraphrase"])

    def boosted_per_repo(self) -> dict[str, float]:
        return self._per_repo(self.boosted_cases)


def run_eval() -> EvalReport:
    # imported here so `python evals/run_eval.py` works from the repo root
    # with an editable install, without paying the import on --help
    from repowiki.core.rag import ModuleIndex, SimpleRAG
    from repowiki.ingest.local import ingest_local

    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    report = EvalReport()
    projects: dict[str, SimpleRAG] = {}
    module_indexes: dict[str, ModuleIndex] = {}
    for case in questions:
        repo = case["repo"]
        if repo not in projects:
            repo_dir = REPOS_DIR / repo
            if not repo_dir.is_dir():
                raise FileNotFoundError(f"fixture repo missing: {repo_dir}")
            rag = SimpleRAG()
            rag.index(ingest_local(repo_dir))
            projects[repo] = rag
            modules_path = MODULES_DIR / f"{repo}.json"
            if modules_path.is_file():
                module_indexes[repo] = ModuleIndex.from_modules(
                    _as_namespace(json.loads(modules_path.read_text(encoding="utf-8")))
                )
        rag = projects[repo]
        tier = case.get("tier", "direct")
        expect = case["expect_files"]

        chunks = rag.retrieve(case["question"], top_k=TOP_K)
        found = sorted({c.file_path for c in chunks if c.file_path in expect})
        report.cases.append(
            CaseResult(repo=repo, question=case["question"], tier=tier,
                       hits=found, expect_files=expect)
        )

        boost = None
        if repo in module_indexes:
            boost = module_indexes[repo].file_scores(case["question"])
        boosted_chunks = rag.retrieve(case["question"], top_k=TOP_K, boost=boost)
        boosted_found = sorted({c.file_path for c in boosted_chunks if c.file_path in expect})
        report.boosted_cases.append(
            CaseResult(repo=repo, question=case["question"], tier=tier,
                       hits=boosted_found, expect_files=expect)
        )
    return report


def print_report(report: EvalReport, baseline: dict | None) -> None:
    print(f"{'repo':<14} {'plain':>8} {'boosted':>8} {'baseline':>14}")
    plain_repos = report.per_repo()
    boosted_repos = report.boosted_per_repo()
    base_repos = (baseline or {}).get("repos", {})
    base_boosted = (baseline or {}).get("boosted", {}).get("repos", {})
    for name in sorted(plain_repos):
        marks = f"{base_repos.get(name, 0):.0%}/{base_boosted.get(name, 0):.0%}"
        print(f"{name:<14} {plain_repos[name]:>8.0%} {boosted_repos.get(name, 0):>8.0%} "
              f"{marks:>14}")
    base_pair = ""
    if baseline:
        base_pair = f"{baseline.get('overall', 0):.0%}/{baseline.get('boosted', {}).get('overall', 0):.0%}"
    print(f"{'overall':<14} {report.overall:>8.0%} {report.boosted_overall:>8.0%} "
          f"{base_pair:>14}")

    for label, cases in (("plain", report.cases), ("boosted", report.boosted_cases)):
        failures = [c for c in cases if not c.passed]
        if failures:
            print(f"\nmissed {label} cases:")
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
            "boosted": {
                "overall": report.boosted_overall,
                "repos": report.boosted_per_repo(),
            },
        }
        BASELINE_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"baseline updated: plain {report.overall:.0%}, boosted {report.boosted_overall:.0%}")
        return 0

    baseline = None
    if BASELINE_PATH.exists():
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    print_report(report, baseline)
    if baseline:
        if report.overall < baseline.get("overall", 0.0):
            print(f"\nREGRESSION: plain hit-rate {report.overall:.0%} below "
                  f"baseline {baseline['overall']:.0%}")
            return 2
        boosted_floor = baseline.get("boosted", {}).get("overall", 0.0)
        if report.boosted_overall < boosted_floor:
            print(f"\nREGRESSION: boosted hit-rate {report.boosted_overall:.0%} below "
                  f"baseline {boosted_floor:.0%}")
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
