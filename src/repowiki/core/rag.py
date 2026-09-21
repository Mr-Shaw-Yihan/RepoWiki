"""lightweight TF-IDF retrieval for Q&A chat."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from repowiki.core.models import ProjectContext

_INDEX_DIR = Path.home() / ".repowiki" / "rag"
_INDEX_VERSION = 2


def _file_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:24]


def _repo_key(project: ProjectContext) -> str:
    return hashlib.sha256(str(Path(project.root).resolve()).encode()).hexdigest()[:24]


@dataclass
class Chunk:
    file_path: str
    line_start: int
    line_end: int
    content: str
    score: float = 0.0


def index_fingerprint(project: ProjectContext) -> str:
    """Hash of the repo root plus every indexed file's path, size, and content.

    Any edit, add, or delete under the repo changes the fingerprint, so a stale
    index on disk simply never matches.
    """
    h = hashlib.sha256()
    h.update(str(Path(project.root).resolve()).encode())
    for f in sorted(project.files, key=lambda x: x.path):
        text = f.content or f.preview
        h.update(f.path.encode())
        h.update(str(f.size).encode())
        h.update(hashlib.sha256(text.encode()).digest())
    return h.hexdigest()[:24]


class SimpleRAG:
    """TF-IDF based code retrieval, no external dependencies."""

    def __init__(self):
        self.chunks: list[Chunk] = []
        self._idf: dict[str, float] = {}
        self._tf_vectors: list[Counter] = []
        self.file_hashes: dict[str, str] = {}
        self.last_build_stats: dict[str, int] = {"reused": 0, "rebuilt": 0}

    def index(self, project: ProjectContext) -> None:
        """chunk project files and build the TF-IDF index."""
        self.chunks = []
        self._tf_vectors = []
        self.file_hashes = {}
        for f in project.files:
            text = f.content or f.preview
            if not text:
                continue
            self.file_hashes[f.path] = _file_hash(text)
            for chunk in _split_into_chunks(text, f.path):
                self.chunks.append(chunk)
                self._tf_vectors.append(Counter(_tokenize(chunk.content)))
        self.last_build_stats = {"reused": 0, "rebuilt": len(self.file_hashes)}
        self._build_idf()

    def index_incremental(
        self,
        project: ProjectContext,
        previous: SimpleRAG | None,
        file_hashes: dict[str, str] | None = None,
    ) -> None:
        """Rebuild only the chunks whose file changed since ``previous``.

        Chunks and tf vectors of untouched files are reused verbatim; idf is
        recomputed from the merged corpus, which is cheap next to re-tokenizing
        the whole repo on every edit. ``file_hashes`` may be passed in when the
        caller already computed them, to avoid hashing the repo twice.
        """
        old_hashes = previous.file_hashes if previous is not None else {}
        old_by_file: dict[str, list[tuple[Chunk, Counter]]] = {}
        if previous is not None:
            for chunk, tf in zip(previous.chunks, previous._tf_vectors):
                old_by_file.setdefault(chunk.file_path, []).append((chunk, tf))

        self.chunks = []
        self._tf_vectors = []
        self.file_hashes = file_hashes if file_hashes is not None else {}
        stats = {"reused": 0, "rebuilt": 0}
        for f in project.files:
            text = f.content or f.preview
            if not text:
                continue
            digest = (
                self.file_hashes[f.path]
                if f.path in self.file_hashes
                else self.file_hashes.setdefault(f.path, _file_hash(text))
            )
            if old_hashes.get(f.path) == digest:
                for chunk, tf in old_by_file[f.path]:
                    self.chunks.append(chunk)
                    self._tf_vectors.append(tf)
                stats["reused"] += 1
            else:
                for chunk in _split_into_chunks(text, f.path):
                    self.chunks.append(chunk)
                    self._tf_vectors.append(Counter(_tokenize(chunk.content)))
                stats["rebuilt"] += 1
        self.last_build_stats = stats
        self._build_idf()

    def _build_idf(self) -> None:
        self._idf = _compute_idf(self._tf_vectors)

    def save_index(self, path: Path) -> None:
        """Persist chunks and vectors as JSON; written atomically so a
        half-written file never reads back as a valid index."""
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": _INDEX_VERSION,
            "file_hashes": self.file_hashes,
            "chunks": [
                {
                    "file_path": c.file_path,
                    "line_start": c.line_start,
                    "line_end": c.line_end,
                    "content": c.content,
                }
                for c in self.chunks
            ],
            "idf": self._idf,
            "tf_vectors": [dict(tf) for tf in self._tf_vectors],
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    @classmethod
    def load_index(cls, path: Path) -> SimpleRAG | None:
        """Read back a saved index; any corruption is treated as a cache miss."""
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            rag = cls()
            rag.chunks = [Chunk(**c) for c in payload["chunks"]]
            rag._idf = {t: float(v) for t, v in payload["idf"].items()}
            rag._tf_vectors = [Counter(tf) for tf in payload["tf_vectors"]]
            if len(rag.chunks) != len(rag._tf_vectors):
                return None
            file_hashes = payload.get("file_hashes")
            rag.file_hashes = (
                {str(k): str(v) for k, v in file_hashes.items()}
                if isinstance(file_hashes, dict)
                else {}
            )
            return rag
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        boost: dict[str, float] | None = None,
        alpha: float = 0.4,
    ) -> list[Chunk]:
        """find top-k chunks most relevant to the query.

        ``boost`` maps a file path to an extra score (a ModuleIndex match is
        the producer), so a module card can pull its files' chunks up even
        when the question shares no vocabulary with the code itself. Lexical
        hits always group above boost-only chunks: the card channel fills
        gaps the lexical channel cannot serve, it never displaces a direct
        hit out of the list.
        """
        if not self.chunks:
            return []

        query_tokens = _tokenize(query)
        query_tf = Counter(query_tokens)

        scores = []
        for i, chunk in enumerate(self.chunks):
            direct = _cosine_similarity(query_tf, self._tf_vectors[i], self._idf)
            total = direct
            if boost:
                total += alpha * boost.get(chunk.file_path, 0.0)
            scores.append((1 if direct > 0 else 0, total, i))

        scores.sort(reverse=True)
        results = []
        for _, score, idx in scores[:top_k]:
            if score <= 0:
                break
            chunk = self.chunks[idx]
            chunk.score = score
            results.append(chunk)

        return results


class ModuleIndex:
    """TF-IDF over module cards, bridging natural-language questions to files.

    Module cards carry the vocabulary the LLM wrote about a module (purpose,
    key concepts, file purposes), which raw code chunks lack. A paraphrased
    question with zero lexical overlap against the code can still reach the
    right files through the card.
    """

    def __init__(self):
        self._vectors: list[Counter] = []
        self._files: list[list[str]] = []  # file paths per module doc
        self._idf: dict[str, float] = {}

    @classmethod
    def from_modules(cls, modules) -> ModuleIndex:
        idx = cls()
        for m in modules:
            files = [f.path for f in getattr(m, "files", []) if getattr(f, "path", "")]
            if not files:
                continue
            idx._vectors.append(Counter(_tokenize(_module_card_text(m))))
            idx._files.append(files)
        idx._idf = _compute_idf(idx._vectors)
        return idx

    def file_scores(self, query: str, top_k: int = 3) -> dict[str, float]:
        """Map file path to the score of the best-matching module holding it."""
        if not self._vectors:
            return {}
        query_tf = Counter(_tokenize(query))
        scored = sorted(
            (
                (_cosine_similarity(query_tf, vec, self._idf), i)
                for i, vec in enumerate(self._vectors)
            ),
            reverse=True,
        )
        out: dict[str, float] = {}
        for score, i in scored[:top_k]:
            if score <= 0:
                break
            for path in self._files[i]:
                out[path] = max(out.get(path, 0.0), score)
        return out


def _module_card_text(m) -> str:
    """Flatten a module card into indexable text."""
    parts = [getattr(m, "name", ""), getattr(m, "purpose", ""), getattr(m, "description", "")]
    for c in getattr(m, "key_concepts", []):
        parts.append(f"{getattr(c, 'name', '')} {getattr(c, 'explanation', '')}")
    for f in getattr(m, "files", []):
        parts.append(getattr(f, "path", ""))
        parts.append(getattr(f, "purpose", ""))
        parts.extend(getattr(s, "name", "") for s in getattr(f, "key_symbols", []))
    return " ".join(p for p in parts if p)


def load_or_build_index(
    project: ProjectContext, index_dir: str | Path | None = None
) -> tuple[SimpleRAG, bool]:
    """Load a persisted index, rebuilding only what changed.

    The cache file is keyed by repo root, not content, so it survives edits;
    per-file hashes inside the payload decide which chunks are reused.
    Returns (rag, cache_hit) where cache_hit is True only when every file
    matched, i.e. no work happened at all.
    """
    index_dir = Path(index_dir) if index_dir is not None else _INDEX_DIR
    path = index_dir / f"{_repo_key(project)}.json"
    current_hashes = {
        f.path: _file_hash(f.content or f.preview) for f in project.files
    }
    previous = SimpleRAG.load_index(path)
    if previous is not None and previous.chunks and previous.file_hashes == current_hashes:
        return previous, True
    rag = SimpleRAG()
    rag.index_incremental(project, previous, current_hashes)
    if rag.chunks:
        try:
            rag.save_index(path)
        except OSError:
            pass  # a cache that cannot be written should not break chat
    return rag, False


def format_context(chunks: list[Chunk]) -> str:
    """Render retrieved chunks into a prompt-ready context block.

    Each chunk becomes a fenced section labelled with its file path and line
    range, so the model can cite specific locations. Empty input yields a
    short placeholder rather than a blank prompt.
    """
    if not chunks:
        return "(no relevant code found in this repository)"
    blocks = []
    for c in chunks:
        blocks.append(
            f"### {c.file_path} (lines {c.line_start}-{c.line_end})\n```\n{c.content}\n```"
        )
    return "\n\n".join(blocks)


def _tokenize(text: str) -> list[str]:
    """split text into lowercase tokens, keeping identifiers intact.

    CJK runs become character bigrams: without word boundaries they would
    tokenize to nothing at all, leaving Chinese questions unanswerable.
    """
    tokens = re.findall(r"[a-zA-Z_]\w*", text.lower())
    for run in re.findall(r"[一-鿿]+", text):
        if len(run) == 1:
            tokens.append(run)
        else:
            tokens.extend(run[i : i + 2] for i in range(len(run) - 1))
    return tokens


def _compute_idf(tf_vectors: list[Counter]) -> dict[str, float]:
    """Shared idf for the chunk and module-card indexes."""
    doc_count = len(tf_vectors)
    if doc_count == 0:
        return {}
    df: Counter = Counter()
    for tf in tf_vectors:
        for token in tf:
            df[token] += 1
    return {token: math.log(doc_count / (count + 1)) for token, count in df.items()}


def _cosine_similarity(vec_a: Counter, vec_b: Counter, idf: dict[str, float]) -> float:
    """TF-IDF weighted cosine similarity."""
    common = set(vec_a) & set(vec_b)
    if not common:
        return 0.0

    dot = sum(vec_a[t] * idf.get(t, 0) * vec_b[t] * idf.get(t, 0) for t in common)
    norm_a = math.sqrt(sum((vec_a[t] * idf.get(t, 0)) ** 2 for t in vec_a))
    norm_b = math.sqrt(sum((vec_b[t] * idf.get(t, 0)) ** 2 for t in vec_b))

    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _split_into_chunks(text: str, file_path: str, max_chunk_lines: int = 30) -> list[Chunk]:
    """split file content into chunks at blank line boundaries."""
    lines = text.splitlines()
    chunks = []
    current_start = 0
    current_lines: list[str] = []

    for i, line in enumerate(lines):
        current_lines.append(line)

        # split at blank lines or when chunk gets too large
        is_boundary = line.strip() == "" and len(current_lines) >= 5
        is_too_long = len(current_lines) >= max_chunk_lines

        if is_boundary or is_too_long or i == len(lines) - 1:
            if current_lines:
                content = "\n".join(current_lines)
                if content.strip():
                    chunks.append(
                        Chunk(
                            file_path=file_path,
                            line_start=current_start + 1,
                            line_end=current_start + len(current_lines),
                            content=content,
                        )
                    )
                current_start = i + 1
                current_lines = []

    return chunks
