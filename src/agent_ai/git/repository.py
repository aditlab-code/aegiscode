"""GitRepository facade: akses Git read-only yang terikat workspace boundary.

Provider-agnostic, read-only. Facade ini:
    - menerima workspace root,
    - memastikan operasi tetap berada pada repository root (workspace boundary),
    - memakai GitClient,
    - TIDAK menjalankan agent logic,
    - TIDAK melakukan file mutation atau Git mutation.

Boundary: memakai `_resolve_within_root` dari tools/filesystem agar konsisten
dengan workspace security AETHER.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from agent_ai.git.client import GitClient, SubprocessGitClient
from agent_ai.git.models import (
    GitBranchInfo,
    GitCommit,
    GitDiffSummary,
    GitRepository,
    GitStatus,
)
from agent_ai.tools.filesystem import _DEFAULT_ROOT, _resolve_within_root


class GitRepositoryFacade:
    """Facade Git read-only untuk sebuah workspace root.

    Args:
        root: workspace root (boundary). Default: root project.
        client: GitClient. Default: SubprocessGitClient().
    """

    def __init__(
        self,
        root: Optional[Path] = None,
        client: Optional[GitClient] = None,
    ) -> None:
        self.root = (Path(root) if root else _DEFAULT_ROOT).resolve()
        self.client = client or SubprocessGitClient()

    # ------------------------------------------------------------------ #
    # Boundary
    # ------------------------------------------------------------------ #
    def _resolve(self, path: Optional[str] = None) -> Path:
        """Resolve path relatif terhadap root, tetap di dalam boundary.

        Raises:
            ValueError: bila path keluar dari workspace boundary.
        """
        rel = path if path else "."
        return _resolve_within_root(rel, self.root)

    # ------------------------------------------------------------------ #
    # Read-only operations
    # ------------------------------------------------------------------ #
    def repository(self, path: Optional[str] = None) -> GitRepository:
        """Info repository untuk path (dalam boundary)."""
        target = self._resolve(path)
        is_repo = self.client.is_repository(target)
        branch = self.client.current_branch(target) if is_repo else None
        return GitRepository(root=str(target), is_repository=is_repo, branch=branch)

    def is_repository(self, path: Optional[str] = None) -> bool:
        """True bila path berada di dalam repository Git."""
        return self.client.is_repository(self._resolve(path))

    def current_branch(self, path: Optional[str] = None) -> Optional[str]:
        """Nama branch saat ini (None bila bukan repo/detached)."""
        target = self._resolve(path)
        if not self.client.is_repository(target):
            return None
        return self.client.current_branch(target)

    def branch_info(self, path: Optional[str] = None) -> GitBranchInfo:
        """Detail branch aktif, upstream remote, dan status sinkronisasi."""
        target = self._resolve(path)
        if not self.client.is_repository(target):
            return GitBranchInfo()
        return self.client.branch_info(target)

    def status(self, path: Optional[str] = None) -> GitStatus:
        """Status repository (branch, clean, files)."""
        target = self._resolve(path)
        if not self.client.is_repository(target):
            return GitStatus(branch=None, clean=True, files=[])
        return self.client.status(target)

    def diff(self, path: Optional[str] = None) -> List[GitDiffSummary]:
        """Ringkasan diff per file (working tree vs HEAD)."""
        target = self._resolve(path)
        if not self.client.is_repository(target):
            return []
        return self.client.diff(target)

    def log(self, limit: int = 10, path: Optional[str] = None) -> List[GitCommit]:
        """Daftar commit terakhir (terbaru dulu)."""
        target = self._resolve(path)
        if not self.client.is_repository(target):
            return []
        return self.client.log(target, limit=limit)

    def file_content_at_ref(self, file_path: str, ref: str = "HEAD") -> Optional[str]:
        """Ambil isi file pada ref tertentu (mis. HEAD) dalam boundary workspace."""
        target = self._resolve(file_path)
        if not self.client.is_repository(self.root):
            return None
        rel_path = target.relative_to(self.root).as_posix()
        return self.client.show_file(self.root, rel_path, ref=ref)

    def file_diff_unified(self, file_path: Optional[str] = None) -> str:
        """Unified diff untuk satu file atau seluruh repo dalam boundary workspace."""
        if not self.client.is_repository(self.root):
            return ""
        rel_path = None
        if file_path:
            target = self._resolve(file_path)
            rel_path = target.relative_to(self.root).as_posix()
        return self.client.diff_unified(self.root, rel_path)

    def diff_detail(self, file_path: str) -> Dict[str, Any]:
        """Detail diff side-by-side untuk Monaco Diff Editor."""
        target = self._resolve(file_path)
        rel_path = target.relative_to(self.root).as_posix()

        # Baca konten working tree (modified)
        modified_content = ""
        exists_on_disk = target.exists() and target.is_file()
        if exists_on_disk:
            try:
                modified_content = target.read_text(encoding="utf-8", errors="replace")
            except Exception:
                modified_content = ""

        # Baca konten HEAD (original)
        original_content = self.file_content_at_ref(rel_path, ref="HEAD")

        status = "modified"
        if original_content is None:
            original_content = ""
            status = "untracked" if exists_on_disk else "deleted"
        elif not exists_on_disk:
            status = "deleted"

        diff_text = self.file_diff_unified(rel_path)

        return {
            "path": rel_path,
            "status": status,
            "original": original_content,
            "modified": modified_content,
            "diff": diff_text,
        }

    def discard(self, file_path: Optional[str] = None) -> Dict[str, Any]:
        """Tolak / buang perubahan pada file tertentu atau seluruh repository."""
        if file_path:
            target = self._resolve(file_path)
            rel_path = target.relative_to(self.root).as_posix()
            ok = self.client.discard(self.root, file_path=rel_path)
            return {"ok": ok, "file_path": rel_path}

        ok = self.client.discard(self.root, file_path=None)
        return {"ok": ok, "file_path": None}
