"""Mention resolver for @file references in user prompts and tasks.

Detects '@path/to/file' and '@[path/to/file]' patterns in user input, checks
them against the project workspace root with 3-layer resolution:
1. Exact relative path.
2. Fuzzy workspace subpath / filename match (with directory ignore policy).
3. Semantic fallback (Local Vector DB) if filename is conceptual or not found.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

#: Max size of any single mentioned file to read (64 KB).
MAX_MENTION_FILE_BYTES = 64 * 1024

#: Max number of files that can be attached from mentions in a single prompt.
MAX_MENTION_FILES = 8

#: Regex to capture @[path/to/file] mentions.
_MENTION_BRACKET_RE = re.compile(
    r"@\[([A-Za-z0-9_\-][A-Za-z0-9_\-\.\/\\]*)\]"
)

#: Regex to capture standard @file mentions.
_MENTION_STANDARD_RE = re.compile(
    r"(?:^|[\s\(\[\{,<:;])@([A-Za-z0-9_\-][A-Za-z0-9_\-\.\/\\]*)"
)

#: Directories strictly excluded from workspace fuzzy file search.
_EXCLUDED_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        "venv",
        ".venv",
        "env",
        ".env",
        "__pycache__",
        ".pytest_cache",
        "build",
        "dist",
        "out",
        ".aegis",
        ".aether",
        ".idea",
        ".vscode",
        "dummy_test",
    }
)


def extract_mention_paths(text: str) -> List[str]:
    """Extract candidate file paths from @mentions in text (standard and bracketed)."""
    if not text or not isinstance(text, str):
        return []
    bracket_matches = _MENTION_BRACKET_RE.findall(text)
    standard_matches = _MENTION_STANDARD_RE.findall(text)
    seen: set = set()
    result: List[str] = []
    for m in bracket_matches + standard_matches:
        cleaned = m.strip().strip("'\"").replace("\\", "/")
        cleaned = cleaned.strip("/")
        # Filter out trivial non-file tokens (e.g. single dots or empty)
        if cleaned and cleaned not in (".", "..") and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


def _find_fuzzy_file(rel_path: str, root: Path) -> Optional[Path]:
    """Search workspace for matching file when exact path does not exist."""
    clean_target = rel_path.strip("/").lower()
    target_name = Path(rel_path).name.lower()

    # If target is a directory in workspace, check for index/readme or primary md
    candidate_dir = root / rel_path
    if candidate_dir.is_dir() and candidate_dir.is_relative_to(root):
        for candidate_name in ("README.md", "readme.md", "index.md", f"{candidate_dir.name}.md"):
            direct_file = candidate_dir / candidate_name
            if direct_file.is_file():
                return direct_file
        try:
            for child in candidate_dir.iterdir():
                if child.is_file() and child.suffix.lower() == ".md":
                    return child
        except OSError:
            pass

    # Walk workspace with exclusion filter to find matching filename or subpath
    matched_files: List[Path] = []
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            # Prune excluded directories in-place
            dirnames[:] = [
                d
                for d in dirnames
                if d.lower() not in _EXCLUDED_DIRS and not d.startswith(".")
            ]
            for fname in filenames:
                if fname.lower() == target_name:
                    full_p = Path(dirpath) / fname
                    matched_files.append(full_p)
                elif clean_target in fname.lower():
                    full_p = Path(dirpath) / fname
                    matched_files.append(full_p)
    except OSError:
        pass

    if not matched_files:
        return None

    # Prioritize files matching exact subpath suffix, then shorter path
    matched_files.sort(
        key=lambda p: (
            0 if str(p.relative_to(root)).replace("\\", "/").lower().endswith(clean_target) else 1,
            len(str(p.relative_to(root))),
        )
    )
    return matched_files[0]


def _semantic_fallback_search(
    query: str,
    root: Path,
) -> Optional[Dict[str, Any]]:
    """Legacy vector search fallback decommissioned in favor of deterministic CodeGraph AST."""
    return None


def _detect_fence_language(path: str) -> str:
    """Determine markdown code fence language from file extension."""
    ext = Path(path).suffix.lower().lstrip(".")
    mapping = {
        "py": "python",
        "js": "javascript",
        "mjs": "javascript",
        "ts": "typescript",
        "vue": "vue",
        "json": "json",
        "md": "markdown",
        "html": "html",
        "css": "css",
        "yaml": "yaml",
        "yml": "yaml",
        "sh": "bash",
        "toml": "toml",
        "sql": "sql",
        "rs": "rust",
        "go": "go",
        "c": "c",
        "cpp": "cpp",
        "h": "c",
    }
    return mapping.get(ext, "")


def resolve_file_mentions(
    text: str,
    root: Optional[str | Path],
    *,
    max_files: int = MAX_MENTION_FILES,
    max_bytes_per_file: int = MAX_MENTION_FILE_BYTES,
) -> Tuple[str, List[Dict[str, Any]]]:
    """Resolve @file mentions against root, read contents, and return enriched text.

    Uses 3-layer resolution:
    1. Exact relative path.
    2. Fuzzy workspace subpath or filename match.
    3. Local semantic embedding fallback.

    Args:
        text: User message or task prompt.
        root: Workspace root directory.
        max_files: Limit on how many files can be attached.
        max_bytes_per_file: Maximum bytes to read per file.

    Returns:
        (enriched_text, attachments) where attachments is a list of
        dict metadata for each resolved file.
    """
    if not text or not root:
        return text, []

    try:
        resolved_root = Path(root).resolve()
        if not resolved_root.is_dir():
            return text, []
    except Exception:
        return text, []

    candidates = extract_mention_paths(text)
    if not candidates:
        return text, []

    attachments: List[Dict[str, Any]] = []

    for rel_path in candidates:
        if len(attachments) >= max_files:
            break
        try:
            target_path: Optional[Path] = (resolved_root / rel_path).resolve()

            # Lapis 1: Exact path check
            if (
                target_path
                and target_path.is_relative_to(resolved_root)
                and target_path.is_file()
            ):
                actual_rel_path = str(target_path.relative_to(resolved_root)).replace("\\", "/")
            else:
                # Lapis 2: Fuzzy workspace lookup
                fuzzy_target = _find_fuzzy_file(rel_path, resolved_root)
                if fuzzy_target and fuzzy_target.is_file():
                    target_path = fuzzy_target
                    actual_rel_path = str(target_path.relative_to(resolved_root)).replace("\\", "/")
                else:
                    target_path = None
                    actual_rel_path = ""

            if target_path and target_path.is_file():
                file_size = target_path.stat().st_size
                is_truncated = file_size > max_bytes_per_file

                with open(target_path, "rb") as f:
                    raw_bytes = f.read(max_bytes_per_file)

                content = raw_bytes.decode("utf-8", errors="replace")
                attachments.append(
                    {
                        "path": actual_rel_path,
                        "content": content,
                        "truncated": is_truncated,
                        "size": file_size,
                    }
                )
            else:
                # Lapis 3: Semantic fallback search
                sem_hit = _semantic_fallback_search(rel_path, resolved_root)
                if sem_hit and sem_hit.get("snippet"):
                    attachments.append(
                        {
                            "path": f"{sem_hit['path']}#L{sem_hit.get('start_line', 1)}-L{sem_hit.get('end_line', 1)}",
                            "content": sem_hit["snippet"],
                            "truncated": False,
                            "size": len(sem_hit["snippet"].encode("utf-8")),
                            "semantic": True,
                            "query": rel_path,
                        }
                    )
        except Exception:
            continue

    if not attachments:
        return text, []

    # Build structured attachment markdown block
    attachment_blocks: List[str] = [
        "",
        "---",
        "# File Lampiran dari Mention (@file):",
    ]

    for att in attachments:
        lang = _detect_fence_language(att["path"])
        trunc_note = " (sebagian / terpotong)" if att.get("truncated") else ""
        if att.get("semantic"):
            attachment_blocks.append(
                f"## Rekomendasi Semantik untuk Mention (@{att['query']}): {att['path']}"
            )
        else:
            attachment_blocks.append(f"## File: {att['path']}{trunc_note}")
        attachment_blocks.append(f"```{lang}")
        attachment_blocks.append(att["content"])
        attachment_blocks.append("```")

    attachment_blocks.append("---")
    enriched_text = text.rstrip() + "\n" + "\n".join(attachment_blocks)

    return enriched_text, attachments
