from pathlib import Path


class CorpusSandboxError(ValueError):
    pass


def resolve_corpus_path(corpus_root: str, relative_or_absolute: str) -> Path:
    root = Path(corpus_root).expanduser().resolve()
    if not root.is_dir():
        raise CorpusSandboxError(f"Corpus root does not exist: {root}")

    candidate = Path(relative_or_absolute).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate

    resolved = candidate.resolve()

    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise CorpusSandboxError(f"Path escapes corpus root: {relative_or_absolute}") from exc

    return resolved


def validate_corpus_root(corpus_root: str) -> Path:
    root = Path(corpus_root).expanduser().resolve()
    if not root.is_dir():
        raise CorpusSandboxError(f"Corpus root does not exist: {root}")
    return root
