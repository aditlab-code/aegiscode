"""GitClient: abstraction untuk operasi Git read-only.

Provider-agnostic. Menggunakan executable `git` melalui subprocess (TANPA
library Git pihak ketiga). Read-only: tidak ada operasi mutasi Git.

    GitClient (ABC)
      └── SubprocessGitClient
"""

from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

from agent_ai.git.models import (
    GitBranchInfo,
    GitCommit,
    GitDiffSummary,
    GitFileStatus,
    GitRepository,
    GitStatus,
)


class GitError(Exception):
    """Base error untuk operasi Git."""


class GitNotAvailableError(GitError):
    """Executable `git` tidak tersedia."""


class GitCommandError(GitError):
    """Perintah git mengembalikan error."""


class GitClient(ABC):
    """Interface operasi Git read-only."""

    @abstractmethod
    def is_repository(self, path: Path, strict_root: bool = True) -> bool:
        """True bila `path` berada di dalam repository Git.
        Bila strict_root=True, wajib memiliki root repository tepat di path.
        """
        raise NotImplementedError

    @abstractmethod
    def init(self, path: Path) -> bool:
        """Inisialisasi repository Git baru di `path`."""
        raise NotImplementedError

    @abstractmethod
    def repo_root(self, path: Path) -> Optional[Path]:
        """Root directory dari repository Git terluar, atau None bila bukan repo."""
        raise NotImplementedError

    @abstractmethod
    def current_branch(self, path: Path) -> Optional[str]:
        """Nama branch saat ini (None bila detached/tidak ada)."""
        raise NotImplementedError

    @abstractmethod
    def branch_info(self, path: Path) -> GitBranchInfo:
        """Informasi lengkap branch aktif, upstream remote, dan daftar branches."""
        raise NotImplementedError

    @abstractmethod
    def status(self, path: Path) -> GitStatus:
        """Status repository (branch, clean, files)."""
        raise NotImplementedError

    @abstractmethod
    def diff(self, path: Path) -> List[GitDiffSummary]:
        """Ringkasan diff per file (working tree vs HEAD)."""
        raise NotImplementedError

    @abstractmethod
    def log(self, path: Path, limit: int = 10) -> List[GitCommit]:
        """Daftar commit terakhir (terbaru dulu)."""
        raise NotImplementedError

    @abstractmethod
    def show_file(self, path: Path, file_path: str, ref: str = "HEAD") -> Optional[str]:
        """Ambil isi file pada ref tertentu (mis. HEAD), atau None jika tidak ditemukan."""
        raise NotImplementedError

    @abstractmethod
    def diff_unified(self, path: Path, file_path: Optional[str] = None) -> str:
        """Keluaran unified diff (working tree vs HEAD) untuk satu file atau seluruh repo."""
        raise NotImplementedError

    @abstractmethod
    def discard(self, path: Path, file_path: Optional[str] = None) -> bool:
        """Tolak/buang perubahan working tree (revert ke HEAD atau hapus file untracked)."""
        raise NotImplementedError

    @abstractmethod
    def stage(self, path: Path, file_path: Optional[str] = None) -> bool:
        """Tambahkan perubahan ke staging index (git add)."""
        raise NotImplementedError

    @abstractmethod
    def unstage(self, path: Path, file_path: Optional[str] = None) -> bool:
        """Hapus perubahan dari staging index (git restore --staged atau git reset)."""
        raise NotImplementedError


def _is_internal_ignored_path(path: str) -> bool:
    """True bila path merupakan direktori atau file internal Aegis/Git yang tidak boleh bocor.

    Menangani backward compatibility (.aegis dan .aether), temporary swap files (.aegis_tmp_*),
    database lokal (data/aegis.db, data/aether.db), git internals, dan path traversal.
    """
    clean = str(path).strip().replace("\\", "/").rstrip("/")
    if not clean or clean.startswith("..") or "/../" in clean or clean == "..":
        return True
    parts = [seg for seg in clean.split("/") if seg]
    if not parts:
        return True
    first = parts[0]
    last = parts[-1]
    # Direktori internal pada root
    if first in (".aegis", ".aether", ".git", ".gemini", ".continue", ".ipynb_checkpoints", "__pycache__"):
        return True
    if first.startswith((".aegis", ".aether")):
        return True
    # Berkas temporer atomik atau swap
    if last.startswith((".aegis_tmp_", ".aether_tmp_")) or last.endswith(".swp"):
        return True
    # Database lokal Aegis/Aether
    if clean in ("data/aegis.db", "data/aether.db") or clean.startswith(("data/aegis.db-", "data/aether.db-")):
        return True
    return False


class SubprocessGitClient(GitClient):
    """Implementasi GitClient via executable `git` (subprocess).

    Args:
        git_executable: nama/path executable git (default "git").
        timeout: batas waktu tiap perintah git (detik).
    """

    def __init__(self, git_executable: str = "git", timeout: float = 30.0) -> None:
        self.git_executable = git_executable
        self.timeout = timeout

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #
    def _run(self, args: List[str], cwd: Path) -> str:
        """Jalankan perintah git dan kembalikan stdout.

        Raises:
            GitNotAvailableError: bila executable git tidak ditemukan.
            GitCommandError: bila perintah gagal.
        """
        try:
            completed = subprocess.run(
                [self.git_executable, *args],
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=self.timeout,
                shell=False,
            )
        except FileNotFoundError as exc:
            raise GitNotAvailableError(
                f"Executable git tidak ditemukan: {self.git_executable}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise GitCommandError(f"Perintah git timeout: {' '.join(args)}") from exc
        except OSError as exc:
            raise GitCommandError(f"Gagal menjalankan git: {exc}") from exc

        if completed.returncode != 0:
            raise GitCommandError(
                f"git {' '.join(args)} gagal (exit {completed.returncode}): "
                f"{completed.stderr.strip()}"
            )
        return completed.stdout

    # ------------------------------------------------------------------ #
    # Interface
    # ------------------------------------------------------------------ #
    def is_repository(self, path: Path, strict_root: bool = True) -> bool:
        p = Path(path).resolve()
        if strict_root:
            dot_git = p / ".git"
            if not dot_git.exists():
                return False
            root = self.repo_root(p)
            return root is not None and root == p

        try:
            out = self._run(["rev-parse", "--is-inside-work-tree"], p)
        except GitError:
            return False
        return out.strip() == "true"

    def init(self, path: Path) -> bool:
        p = Path(path).resolve()
        self._run(["init"], p)
        return True

    def repo_root(self, path: Path) -> Optional[Path]:
        try:
            out = self._run(["rev-parse", "--show-toplevel"], path).strip()
            if out:
                return Path(out).resolve()
        except GitError:
            pass
        return None

    def current_branch(self, path: Path) -> Optional[str]:
        try:
            out = self._run(["rev-parse", "--abbrev-ref", "HEAD"], path)
        except GitError:
            return None
        branch = out.strip()
        if not branch or branch == "HEAD":  # detached HEAD
            return None
        return branch

    def branch_info(self, path: Path) -> GitBranchInfo:
        current = None
        detached = False
        try:
            out = self._run(["rev-parse", "--abbrev-ref", "HEAD"], path).strip()
            if out == "HEAD" or not out:
                detached = True
                try:
                    short = self._run(["rev-parse", "--short", "HEAD"], path).strip()
                    current = f"HEAD ({short})" if short else "HEAD"
                except Exception:
                    current = "HEAD"
            else:
                current = out
        except GitError:
            current = None

        upstream = None
        ahead = 0
        behind = 0
        try:
            up = self._run(
                ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
                path,
            ).strip()
            if up and not up.startswith("@"):
                upstream = up
        except GitError:
            upstream = None

        if upstream:
            try:
                counts = self._run(
                    ["rev-list", "--left-right", "--count", f"HEAD...{upstream}"],
                    path,
                ).strip()
                parts = counts.split()
                if len(parts) >= 2:
                    ahead = int(parts[0])
                    behind = int(parts[1])
            except (GitError, ValueError):
                pass

        local_branches: List[str] = []
        remote_branches: List[str] = []
        try:
            out = self._run(
                ["branch", "-a", "--format=%(refname)|%(refname:short)"],
                path,
            )
            for line in out.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split("|")
                if len(parts) < 2:
                    continue
                refname, shortname = parts[0], parts[1]
                if refname.startswith("refs/heads/"):
                    local_branches.append(shortname)
                elif refname.startswith("refs/remotes/"):
                    if not shortname.endswith("/HEAD"):
                        remote_branches.append(shortname)
        except GitError:
            pass

        return GitBranchInfo(
            current=current,
            upstream=upstream,
            ahead=ahead,
            behind=behind,
            detached=detached,
            local_branches=local_branches,
            remote_branches=remote_branches,
        )

    def status(self, path: Path) -> GitStatus:
        branch = self.current_branch(path)
        resolved_path = path.resolve()
        # --porcelain=v1 -z: format stabil & machine-readable, dibatasi ke direktori aktif.
        out = self._run(["status", "--porcelain=v1", "-z", "--", "."], resolved_path)
        repo_root = self.repo_root(resolved_path)
        prefix = ""
        if repo_root and resolved_path != repo_root:
            try:
                prefix = resolved_path.relative_to(repo_root).as_posix()
            except ValueError:
                prefix = ""
        files = self._parse_status(out, prefix=prefix)
        return GitStatus(branch=branch, clean=len(files) == 0, files=files)

    @staticmethod
    def _parse_status(raw: str, prefix: str = "") -> List[GitFileStatus]:
        """Parse output `git status --porcelain=v1 -z`."""
        files: List[GitFileStatus] = []
        # -z memisahkan entri dengan NUL; rename punya dua field.
        entries = [e for e in raw.split("\x00") if e]
        i = 0
        while i < len(entries):
            entry = entries[i]
            if len(entry) < 3:
                i += 1
                continue
            x = entry[0]  # status index (staged)
            y = entry[1]  # status working tree (unstaged)
            raw_path = entry[3:]
            # Rename/copy: entri berikutnya adalah path asal -> lewati.
            if x in ("R", "C"):
                i += 1

            if prefix:
                if not raw_path.startswith(f"{prefix}/"):
                    i += 1
                    continue
                file_path = raw_path[len(prefix) + 1:]
            else:
                if raw_path.startswith("..") or "/../" in raw_path:
                    i += 1
                    continue
                file_path = raw_path

            # Saring direktori/berkas internal Aegis/Git/Aether dan path traversal
            clean_fp = file_path.strip().rstrip("/")
            if _is_internal_ignored_path(clean_fp):
                i += 1
                continue
            untracked = x == "?" and y == "?"
            files.append(
                GitFileStatus(
                    path=file_path,
                    status=(x + y).strip() or "??",
                    staged=x not in (" ", "?"),
                    unstaged=y not in (" ", "?"),
                    untracked=untracked,
                )
            )
            i += 1
        return files

    def diff(self, path: Path) -> List[GitDiffSummary]:
        resolved_path = path.resolve()
        repo_root = self.repo_root(resolved_path)
        prefix = ""
        if repo_root and resolved_path != repo_root:
            try:
                prefix = resolved_path.relative_to(repo_root).as_posix()
            except ValueError:
                prefix = ""

        # --numstat: additions/deletions per file (working tree vs HEAD), dibatasi ke direktori aktif.
        try:
            out = self._run(["diff", "--numstat", "HEAD", "--", "."], resolved_path)
        except GitError:
            try:
                out = self._run(["diff", "--numstat", "--", "."], resolved_path)
            except GitError:
                return []
        summaries: List[GitDiffSummary] = []
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            add_raw, del_raw, raw_path = parts[0], parts[1], parts[2]
            if prefix:
                if not raw_path.startswith(f"{prefix}/"):
                    continue
                file_path = raw_path[len(prefix) + 1:]
            else:
                if raw_path.startswith("..") or "/../" in raw_path:
                    continue
                file_path = raw_path

            clean_fp = file_path.strip().rstrip("/")
            if _is_internal_ignored_path(clean_fp):
                continue
            additions = int(add_raw) if add_raw.isdigit() else 0
            deletions = int(del_raw) if del_raw.isdigit() else 0
            summaries.append(
                GitDiffSummary(
                    path=file_path,
                    additions=additions,
                    deletions=deletions,
                    status="modified",
                )
            )
        return summaries

    def show_file(self, path: Path, file_path: str, ref: str = "HEAD") -> Optional[str]:
        clean_path = file_path.strip().lstrip("./")
        if not clean_path or _is_internal_ignored_path(clean_path):
            return None
        try:
            return self._run(["show", f"{ref}:./{clean_path}"], path)
        except GitError:
            try:
                return self._run(["show", f"{ref}:{clean_path}"], path)
            except GitError:
                return None

    def diff_unified(self, path: Path, file_path: Optional[str] = None) -> str:
        if file_path:
            clean_path = file_path.strip().lstrip("./")
            if _is_internal_ignored_path(clean_path):
                return ""
            target_path = clean_path if clean_path else "."
            args = ["diff", "HEAD", "--", target_path]
            try:
                return self._run(args, path)
            except GitError:
                try:
                    return self._run(["diff", "--", target_path], path)
                except GitError:
                    return ""
        else:
            args = ["diff", "HEAD", "--", "."]
            try:
                return self._run(args, path)
            except GitError:
                try:
                    return self._run(["diff", "--", "."], path)
                except GitError:
                    return ""

    def log(self, path: Path, limit: int = 10) -> List[GitCommit]:
        # Format: hash<US>short<US>parents<US>refs<US>author<US>timestamp<US>subject
        fmt = "%H%x1f%h%x1f%P%x1f%D%x1f%an%x1f%at%x1f%s"
        out = self._run(["log", f"-n{int(limit)}", f"--pretty=format:{fmt}"], path)
        commits: List[GitCommit] = []
        for line in out.splitlines():
            if not line.strip():
                continue
            parts = line.split("\x1f")
            if len(parts) < 7:
                continue
            full, short, parents_raw, refs_raw, author, ts, subject = (
                parts[0],
                parts[1],
                parts[2],
                parts[3],
                parts[4],
                parts[5],
                parts[6],
            )
            parents = [p.strip() for p in parents_raw.split() if p.strip()]
            refs = [r.strip() for r in refs_raw.split(",") if r.strip()]
            try:
                timestamp = float(ts)
            except ValueError:
                timestamp = 0.0
            commits.append(
                GitCommit(
                    hash=full,
                    short_hash=short,
                    author=author,
                    timestamp=timestamp,
                    subject=subject,
                    parents=parents,
                    refs=refs,
                )
            )
        return commits

    def discard(self, path: Path, file_path: Optional[str] = None) -> bool:
        """Tolak / buang perubahan working tree (revert ke HEAD atau hapus file untracked).

        Bila `file_path` diberikan: hanya buang perubahan pada file tersebut.
        Bila `file_path` None: buang semua perubahan di repository.
        """
        if file_path:
            clean_fp = file_path.strip().rstrip("/")
            if (
                clean_fp == ".aegis"
                or clean_fp.startswith(".aegis/")
                or clean_fp == ".git"
                or clean_fp.startswith(".git/")
                or clean_fp.startswith("..")
                or "/../" in clean_fp
            ):
                return False

            target = (path / file_path).resolve()
            # Cek status file
            st = self.status(path)
            is_untracked = any(f.path == file_path and f.untracked for f in st.files)

            if is_untracked:
                if target.is_file():
                    target.unlink(missing_ok=True)
                elif target.is_dir():
                    import shutil
                    shutil.rmtree(target, ignore_errors=True)
                return True

            # Tracked file (modified / deleted / staged)
            try:
                self._run(["restore", "--staged", "--worktree", "--", file_path], path)
            except GitError:
                try:
                    self._run(["checkout", "HEAD", "--", file_path], path)
                except GitError:
                    return False
            return True

        # Discard all changes
        try:
            self._run(["restore", "--staged", "--worktree", "."], path)
        except GitError:
            try:
                self._run(["checkout", "HEAD", "--", "."], path)
            except GitError:
                pass

        try:
            # Clean untracked files & dirs, preserve .aegis
            self._run(["clean", "-fd", "-e", ".aegis"], path)
        except GitError:
            pass

        return True

    def stage(self, path: Path, file_path: Optional[str] = None) -> bool:
        """Tambahkan perubahan ke staging index (git add).

        Bila `file_path` diberikan: stage file tersebut.
        Bila `file_path` None: stage seluruh perubahan non-ignored di repository.
        """
        if file_path:
            if _is_internal_ignored_path(file_path):
                return False
            try:
                self._run(["add", "-A", "--", file_path], path)
                return True
            except GitError:
                return False

        try:
            self._run(["add", "-A", "."], path)
            return True
        except GitError:
            return False

    def unstage(self, path: Path, file_path: Optional[str] = None) -> bool:
        """Hapus perubahan dari staging index (git restore --staged atau git reset).

        Bila `file_path` diberikan: unstage file tersebut.
        Bila `file_path` None: unstage seluruh file di staging index.
        """
        if file_path:
            if _is_internal_ignored_path(file_path):
                return False
            try:
                self._run(["restore", "--staged", "--", file_path], path)
                return True
            except GitError:
                try:
                    self._run(["reset", "HEAD", "--", file_path], path)
                    return True
                except GitError:
                    return False

        try:
            self._run(["restore", "--staged", "."], path)
            return True
        except GitError:
            try:
                self._run(["reset", "HEAD"], path)
                return True
            except GitError:
                return False
