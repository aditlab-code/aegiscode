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
                "staged": False,
            }

        from agent_ai.git.client import _is_internal_ignored_path
        if _is_internal_ignored_path(file_path):
            return {
                "path": file_path,
                "status": "clean",
                "original": "",
                "modified": "",
                "diff": "",
                "staged": False,
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
                "staged": False,
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
        st = self.status()
        is_staged = any(f.path == rel_path and f.staged for f in st.files)

        return {
            "path": rel_path,
            "status": status,
            "original": original_content,
            "modified": modified_content,
            "diff": diff_text,
            "staged": is_staged,
        }

    def get_changed_files_summary(self) -> List[Dict[str, Any]]:
        """Dapatkan ringkasan berkas yang berubah dengan format path, total lines, dan status (M, A, D)."""
        if not self.is_repository():
            return []

        st = self.status()
        if not st or st.clean:
            return []

        diff_list = self.diff()
        diff_by_path = {d.path: d for d in diff_list}

        results: List[Dict[str, Any]] = []
        for f in st.files:
            raw_stat = (f.status or "").strip().upper()
            path = f.path

            # Tentukan status ringkas: M, A, D
            if f.untracked or "A" in raw_stat or "??" in raw_stat:
                code = "A"
            elif "D" in raw_stat:
                code = "D"
            else:
                code = "M"

            # Hitung jumlah baris
            diff_item = diff_by_path.get(path)
            lines = 0
            if diff_item:
                if code == "D":
                    lines = diff_item.deletions
                elif code == "A":
                    lines = diff_item.additions
                else:
                    lines = diff_item.additions + diff_item.deletions
            else:
                # File untracked atau belum ada di numstat
                if code == "A":
                    try:
                        resolved = self._resolve(path)
                        if resolved.exists() and resolved.is_file():
                            text = resolved.read_text(encoding="utf-8", errors="replace")
                            lines = len(text.splitlines())
                    except Exception:
                        lines = 0

            results.append({
                "path": path,
                "lines": lines,
                "status": code,
            })

        return results

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

    def stage(self, file_path: Optional[str] = None) -> Dict[str, Any]:
        """Tambahkan perubahan pada file tertentu atau seluruh repository ke staging index."""
        if not self.is_repository():
            return {"ok": False, "file_path": file_path, "error": "not_a_repository"}

        if file_path:
            target = self._resolve(file_path)
            rel_path = target.relative_to(self.root).as_posix()
            ok = self.client.stage(self.root, file_path=rel_path)
            return {"ok": ok, "file_path": rel_path}

        ok = self.client.stage(self.root, file_path=None)
        return {"ok": ok, "file_path": None}

    def unstage(self, file_path: Optional[str] = None) -> Dict[str, Any]:
        """Hapus perubahan pada file tertentu atau seluruh repository dari staging index."""
        if not self.is_repository():
            return {"ok": False, "file_path": file_path, "error": "not_a_repository"}

        if file_path:
            target = self._resolve(file_path)
            rel_path = target.relative_to(self.root).as_posix()
            ok = self.client.unstage(self.root, file_path=rel_path)
            return {"ok": ok, "file_path": rel_path}

        ok = self.client.unstage(self.root, file_path=None)
        return {"ok": ok, "file_path": None}

    def checkout(
        self, branch: str, create: bool = False, start_point: Optional[str] = None
    ) -> Dict[str, Any]:
        """Beralih branch atau buat branch baru bila create=True."""
        if not self.is_repository():
            return {"ok": False, "error": "not_a_repository"}
        clean_branch = (branch or "").strip()
        if not clean_branch:
            return {"ok": False, "error": "Branch name is required"}
        ok = self.client.checkout(
            self.root, clean_branch, create=create, start_point=start_point
        )
        return {
            "ok": ok,
            "branch": clean_branch,
            "current_branch": self.current_branch(),
        }

    def create_branch(
        self, branch: str, start_point: Optional[str] = None, checkout: bool = False
    ) -> Dict[str, Any]:
        """Buat branch baru."""
        if not self.is_repository():
            return {"ok": False, "error": "not_a_repository"}
        clean_branch = (branch or "").strip()
        if not clean_branch:
            return {"ok": False, "error": "Branch name is required"}
        ok = self.client.create_branch(
            self.root, clean_branch, start_point=start_point, checkout=checkout
        )
        return {
            "ok": ok,
            "branch": clean_branch,
            "current_branch": self.current_branch(),
        }

    def delete_branch(
        self,
        branch: str,
        force: bool = False,
        is_remote: bool = False,
        remote: str = "origin",
    ) -> Dict[str, Any]:
        """Hapus branch (lokal atau remote)."""
        if not self.is_repository():
            return {"ok": False, "error": "not_a_repository"}
        clean_branch = (branch or "").strip()
        if not clean_branch:
            return {"ok": False, "error": "Branch name is required"}
        ok = self.client.delete_branch(
            self.root, clean_branch, force=force, is_remote=is_remote, remote=remote
        )
        return {"ok": ok, "branch": clean_branch}

    def merge(
        self, branch: str, message: Optional[str] = None, no_ff: bool = False
    ) -> Dict[str, Any]:
        """Gabungkan branch lain ke branch aktif saat ini."""
        if not self.is_repository():
            return {"ok": False, "error": "not_a_repository"}
        clean_branch = (branch or "").strip()
        if not clean_branch:
            return {"ok": False, "error": "Branch name is required"}
        return self.client.merge(
            self.root, clean_branch, message=message, no_ff=no_ff
        )

    def stash(
        self, message: Optional[str] = None, include_untracked: bool = True
    ) -> Dict[str, Any]:
        """Simpan perubahan ke git stash."""
        if not self.is_repository():
            return {"ok": False, "error": "not_a_repository"}
        ok = self.client.stash(
            self.root, message=message, include_untracked=include_untracked
        )
        return {"ok": ok}

    def stash_list(self) -> List[Dict[str, Any]]:
        """Daftar stashes dalam repositori."""
        if not self.is_repository():
            return []
        return self.client.stash_list(self.root)

    def stash_pop(self, index: int = 0) -> Dict[str, Any]:
        """Terapkan stash dan hapus dari stash list."""
        if not self.is_repository():
            return {"ok": False, "error": "not_a_repository"}
        ok = self.client.stash_pop(self.root, index=index)
        return {"ok": ok, "index": index}

    def stash_apply(self, index: int = 0) -> Dict[str, Any]:
        """Terapkan stash tanpa menghapus dari stash list."""
        if not self.is_repository():
            return {"ok": False, "error": "not_a_repository"}
        ok = self.client.stash_apply(self.root, index=index)
        return {"ok": ok, "index": index}

    def stash_drop(self, index: int = 0) -> Dict[str, Any]:
        """Hapus stash dari stash list."""
        if not self.is_repository():
            return {"ok": False, "error": "not_a_repository"}
        ok = self.client.stash_drop(self.root, index=index)
        return {"ok": ok, "index": index}

    def push(
        self,
        remote: Optional[str] = None,
        branch: Optional[str] = None,
        set_upstream: bool = False,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Push commit ke remote repositori."""
        if not self.is_repository():
            return {"ok": False, "error": "not_a_repository"}
        return self.client.push(
            self.root,
            remote=remote,
            branch=branch,
            set_upstream=set_upstream,
            force=force,
        )

    def pull(
        self,
        remote: Optional[str] = None,
        branch: Optional[str] = None,
        rebase: bool = False,
    ) -> Dict[str, Any]:
        """Pull perubahan terbaru dari remote repositori."""
        if not self.is_repository():
            return {"ok": False, "error": "not_a_repository"}
        return self.client.pull(
            self.root, remote=remote, branch=branch, rebase=rebase
        )

    def fetch(
        self, remote: Optional[str] = None, prune: bool = True
    ) -> Dict[str, Any]:
        """Fetch referensi terbaru dari remote repositori."""
        if not self.is_repository():
            return {"ok": False, "error": "not_a_repository"}
        return self.client.fetch(self.root, remote=remote, prune=prune)

    def remotes(self) -> List[Dict[str, str]]:
        """Daftar remote repositori."""
        if not self.is_repository():
            return []
        return self.client.remotes(self.root)

    def add_remote(self, name: str, url: str) -> Dict[str, Any]:
        """Tambahkan remote repositori baru."""
        if not self.is_repository():
            return {"ok": False, "error": "not_a_repository"}
        clean_name = (name or "").strip()
        clean_url = (url or "").strip()
        if not clean_name or not clean_url:
            return {"ok": False, "error": "Name and URL are required"}
        ok = self.client.add_remote(self.root, clean_name, clean_url)
        return {"ok": ok, "name": clean_name, "url": clean_url}

    def set_remote_url(self, name: str, url: str) -> Dict[str, Any]:
        """Perbarui URL remote repositori."""
        if not self.is_repository():
            return {"ok": False, "error": "not_a_repository"}
        clean_name = (name or "").strip()
        clean_url = (url or "").strip()
        if not clean_name or not clean_url:
            return {"ok": False, "error": "Name and URL are required"}
        ok = self.client.set_remote_url(self.root, clean_name, clean_url)
        return {"ok": ok, "name": clean_name, "url": clean_url}

    def clone(self, url: str, target_dir: Optional[str] = None) -> Dict[str, Any]:
        """Clone repositori ke dalam boundary workspace."""
        clean_url = (url or "").strip()
        if not clean_url:
            return {"ok": False, "error": "Repository URL is required"}
        target = self._resolve(target_dir) if target_dir else self.root
        ok = self.client.clone(clean_url, target)
        return {"ok": ok, "target": str(target)}

    def commit(
        self, message: str, stage_all: bool = False
    ) -> Dict[str, Any]:
        """Buat git commit pada branch aktif saat ini."""
        if not self.is_repository():
            return {"ok": False, "error": "not_a_repository"}
        clean_msg = (message or "").strip()
        if not clean_msg:
            return {"ok": False, "error": "Commit message is required."}
        return self.client.commit(self.root, clean_msg, stage_all=stage_all)
