"""Mention resolver for @file references in user prompts and tasks.

Detects '@path/to/file' patterns in user input, checks them against the
project workspace root, and extracts safe file contents to attach directly
as prompt context for LLMs and agents.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

#: Max size of any single mentioned file to read (64 KB).
MAX_MENTION_FILE_BYTES = 64 * 1024

#: Max number of files that can be attached from mentions in a single prompt.
MAX_MENTION_FILES = 8

#: Regex to capture @file mentions. Matches '@path/to/file.ext' when preceded
#: by start-of-string, whitespace, or boundary punctuation.
#: Strictly ignores email-like patterns (e.g. 'user@domain.com').
_MENTION_RE = re.compile(
    r"(?:^|[\s\(\[\{,<:;])@([A-Za-z0-9_\-][A-Za-z0-9_\-\.\/\\]*)"
)


def extract_mention_paths(text: str) -> List[str]:
    """Extract candidate file paths from @mentions in text."""
    if not text or not isinstance(text, str):
        return []
    matches = _MENTION_RE.findall(text)
    seen: set = set()
    result: List[str] = []
    for m in matches:
        cleaned = m.strip().strip("'\"").replace("\\", "/")
        cleaned = cleaned.strip("/")
        # Filter out trivial non-file tokens (e.g. single dots or empty)
        if cleaned and cleaned not in (".", "..") and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


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
            target_path = (resolved_root / rel_path).resolve()
            # Boundary guard: Must reside strictly inside resolved_root
            if not target_path.is_relative_to(resolved_root):
                continue
            if not target_path.is_file():
                continue

            file_size = target_path.stat().st_size
            is_truncated = file_size > max_bytes_per_file

            with open(target_path, "rb") as f:
                raw_bytes = f.read(max_bytes_per_file)

            # Decode safely
            content = raw_bytes.decode("utf-8", errors="replace")

            attachments.append(
                {
                    "path": rel_path,
                    "content": content,
                    "truncated": is_truncated,
                    "size": file_size,
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
        trunc_note = " (sebagian / terpotong)" if att["truncated"] else ""
        attachment_blocks.append(f"## File: {att['path']}{trunc_note}")
        attachment_blocks.append(f"```{lang}")
        attachment_blocks.append(att["content"])
        attachment_blocks.append("```")

    attachment_blocks.append("---")
    enriched_text = text.rstrip() + "\n" + "\n".join(attachment_blocks)

    return enriched_text, attachments
