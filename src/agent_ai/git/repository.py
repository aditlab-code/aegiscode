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
        strict_root: bool = True,
    ) -> None:
        self.root = (Path(root) if root else _DEFAULT_ROOT).resolve()
        self.client = client or SubprocessGitClient()
        self.strict_root = strict_root

    # ------------------------------------------------------------------ #
    # Boundary
    # ------------------------------------------------------------------ #
    def _resolve(self, path: Optional[str] = None) -> Path:
        """Resolve path relatif terhadap root, tetap di dalam boundary.

        Raises:
            ValueError: bila path keluar dari workspace boundary.
        """
        rel = path if path else "."
        # Tangani path dengan leading slash jika bukan absolute path valid di dalam root
        if isinstance(rel, str) and rel.startswith("/"):
            candidate = Path(rel)
            if not (candidate.is_absolute() and (candidate == self.root or self.root in candidate.parents)):
                rel = rel.lstrip("/")
        return _resolve_within_root(rel, self.root)

    # ------------------------------------------------------------------ #
    # Operations
    # ------------------------------------------------------------------ #
    def init(self) -> Dict[str, Any]:
        """Inisialisasi repositori Git baru pada workspace root."""
        try:
            self.client.init(self.root)
            return {"ok": True, "message": "Initialized empty Git repository"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def deinit(self) -> Dict[str, Any]:
        """Hapus direktori .git pada workspace root (de-initialize repository)."""
        dot_git = self.root / ".git"
        if not dot_git.exists():
            return {"ok": True, "message": "No .git directory found"}

        import shutil
        import stat

        def on_rm_error(func, path, exc_info):
            try:
                Path(path).chmod(stat.S_IWRITE)
                func(path)
            except Exception:
                pass

        try:
            if dot_git.is_dir():
                shutil.rmtree(dot_git, onerror=on_rm_error)
            else:
                dot_git.unlink(missing_ok=True)
            return {"ok": True, "message": "Git repository de-initialized"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def gitignore_patterns(self) -> List[str]:
        """Baca pola aturan dari file .gitignore lokal di root project."""
        gi = self.root / ".gitignore"
        if not gi.is_file():
            return []
        try:
            content = gi.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return []
        patterns: List[str] = []
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            patterns.append(line)
        return patterns

    def repository(self, path: Optional[str] = None) -> GitRepository:
        """Info repository untuk path (dalam boundary)."""
        target = self._resolve(path)
        is_repo = self.is_repository(path)
        branch = self.client.current_branch(target) if is_repo else None
        return GitRepository(root=str(target), is_repository=is_repo, branch=branch)

    def is_repository(self, path: Optional[str] = None) -> bool:
        """True bila path berada di dalam repository Git dan terikat ke root workspace."""
        target = self._resolve(path)
        if target == self.root:
            return self.client.is_repository(target, strict_root=self.strict_root)
        if not self.client.is_repository(self.root, strict_root=self.strict_root):
            return False
        return self.client.is_repository(target, strict_root=False)

    def current_branch(self, path: Optional[str] = None) -> Optional[str]:
        """Nama branch saat ini (None bila bukan repo/detached)."""
        target = self._resolve(path)
        if not self.is_repository(path):
            return None
        return self.client.current_branch(target)

    def branch_info(self, path: Optional[str] = None) -> GitBranchInfo:
        """Detail branch aktif, upstream remote, dan status sinkronisasi."""
        target = self._resolve(path)
        if not self.is_repository(path):
            return GitBranchInfo()
        return self.client.branch_info(target)

    def status(self, path: Optional[str] = None) -> GitStatus:
        """Status repository (branch, clean, files)."""
        target = self._resolve(path)
        if not self.is_repository(path):
            return GitStatus(branch=None, clean=True, files=[])
        return self.client.status(target)

    def diff(self, path: Optional[str] = None) -> List[GitDiffSummary]:
        """Ringkasan diff per file (working tree vs HEAD)."""
        target = self._resolve(path)
        if not self.is_repository(path):
            return []
        return self.client.diff(target)

    def log(self, limit: int = 10, path: Optional[str] = None) -> List[GitCommit]:
        """Daftar commit terakhir (terbaru dulu)."""
        target = self._resolve(path)
        if not self.is_repository(path):
            return []
        return self.client.log(target, limit=limit)

    def file_content_at_ref(self, file_path: str, ref: str = "HEAD") -> Optional[str]:
        """Ambil isi file pada ref tertentu (mis. HEAD) dalam boundary workspace."""
        if not self.is_repository():
            return None
        target = self._resolve(file_path)
        rel_path = target.relative_to(self.root).as_posix()
        return self.client.show_file(self.root, rel_path, ref=ref)

    def file_diff_unified(self, file_path: Optional[str] = None) -> str:
        """Unified diff untuk satu file atau seluruh repo dalam boundary workspace."""
        if not self.is_repository():
            return ""
        rel_path = None
        if file_path:
            from agent_ai.git.client import _is_internal_ignored_path
            if _is_internal_ignored_path(file_path):
                return ""
            target = self._resolve(file_path)
            rel_path = target.relative_to(self.root).as_posix()
            if _is_internal_ignored_path(rel_path):
                return ""
        return self.client.diff_unified(self.root, rel_path)

    def diff_detail(self, file_path: str) -> Dict[str, Any]:
        """Detail diff side-by-side untuk Monaco Diff Editor."""
        if not self.is_repository():
            return {
                "path": file_path,
                "status": "clean",
                "original": "",
                "modified": "",
                "diff": "",
            }

        from agent_ai.git.client import _is_internal_ignored_path
        if _is_internal_ignored_path(file_path):
            return {
                "path": file_path,
                "status": "clean",
                "original": "",
                "modified": "",
                "diff": "",
            }

        target = self._resolve(file_path)
        rel_path = target.relative_to(self.root).as_posix()
        if _is_internal_ignored_path(rel_path):
            return {
                "path": rel_path,
                "status": "clean",
                "original": "",
                "modified": "",
                "diff": "",
            }

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
        if not self.is_repository():
            return {"ok": False, "file_path": file_path, "error": "not_a_repository"}

        if file_path:
            target = self._resolve(file_path)
            rel_path = target.relative_to(self.root).as_posix()
            ok = self.client.discard(self.root, file_path=rel_path)
            return {"ok": ok, "file_path": rel_path}

        ok = self.client.discard(self.root, file_path=None)
        return {"ok": ok, "file_path": None}
