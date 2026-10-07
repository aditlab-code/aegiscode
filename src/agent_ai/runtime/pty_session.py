"""Pseudo-Terminal (PTY) Supervisor Module for AegisCode.

Provides full interactive terminal sessions with non-blocking I/O, raw ANSI
escape sequence streaming, signal propagation (including Ctrl+C / SIGINT),
window resize synchronization, and multi-platform compatibility.
"""

from __future__ import annotations

import abc
import os
import signal
import subprocess
import threading
from typing import Callable, Optional

# Conditional imports for POSIX PTY APIs
_IS_POSIX = os.name != "nt"
if _IS_POSIX:
    import fcntl
    import pty
    import select
    import struct
    import termios
else:
    fcntl = None  # type: ignore[assignment]
    pty = None  # type: ignore[assignment]
    select = None  # type: ignore[assignment]
    struct = None  # type: ignore[assignment]
    termios = None  # type: ignore[assignment]


def _find_posix_descendants(parent_pid: int) -> list[int]:
    """Recursively discover all child and descendant PIDs for a given process."""
    descendants: list[int] = []
    try:
        out = subprocess.check_output(
            ["pgrep", "-P", str(parent_pid)],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=0.5,
        )
        direct = [int(p.strip()) for p in out.strip().split() if p.strip().isdigit()]
    except Exception:
        try:
            out = subprocess.check_output(
                ["ps", "-o", "pid=", "--ppid", str(parent_pid)],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=0.5,
            )
            direct = [int(p.strip()) for p in out.strip().split() if p.strip().isdigit()]
        except Exception:
            direct = []

    for child in direct:
        descendants.append(child)
        descendants.extend(_find_posix_descendants(child))
    return descendants

class BasePTYSession(abc.ABC):
    """Abstract base class defining the PTY session interface."""

    def __init__(self, workspace_root: str, on_output: Callable[[bytes], None]) -> None:
        self.workspace_root = workspace_root
        self.on_output = on_output
        self.is_alive = False
        self._lock = threading.Lock()
        self._terminated = False

    @property
    @abc.abstractmethod
    def pid(self) -> Optional[int]:
        """Return the process ID of the running shell or None."""

    @abc.abstractmethod
    def start(self, shell_cmd: Optional[list[str]] = None) -> None:
        """Start the interactive shell process."""

    @abc.abstractmethod
    def write(self, data: str) -> None:
        """Write raw character/keystroke input to the terminal."""

    @abc.abstractmethod
    def resize(self, rows: int, cols: int) -> None:
        """Update terminal dimensions (rows and columns)."""

    @abc.abstractmethod
    def terminate(self) -> None:
        """Cleanly terminate the shell process and release file descriptors."""


class PosixPTYSession(BasePTYSession):
    """Production-grade POSIX PTY session using openpty and subprocess.Popen.

    Avoids os.fork() issues in multi-threaded Python servers by delegating child
    process spawning to subprocess.Popen with slave fd attached to stdin/stdout/stderr.
    """

    def __init__(self, workspace_root: str, on_output: Callable[[bytes], None]) -> None:
        super().__init__(workspace_root, on_output)
        self.master_fd: Optional[int] = None
        self.proc: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None

    @property
    def pid(self) -> Optional[int]:
        with self._lock:
            return self.proc.pid if self.proc is not None else None

    def start(self, shell_cmd: Optional[list[str]] = None) -> None:
        with self._lock:
            if self.is_alive:
                return

            if shell_cmd is None:
                # Use user's default shell or fallback to bash/sh
                default_shell = os.environ.get("SHELL", "/bin/bash")
                if not os.path.exists(default_shell):
                    default_shell = "/bin/sh"
                shell_cmd = [default_shell]

            # Allocate pseudo-terminal master/slave pair
            master_fd, slave_fd = pty.openpty()
            self.master_fd = master_fd

            child_env = os.environ.copy()
            child_env["TERM"] = "xterm-256color"
            child_env["COLORTERM"] = "truecolor"

            # Resolve working directory safely
            cwd = self.workspace_root if os.path.isdir(self.workspace_root) else os.getcwd()

            try:
                # Spawn shell with slave_fd as stdin/stdout/stderr
                # start_new_session=True creates a new process group (setsid)
                self.proc = subprocess.Popen(
                    shell_cmd,
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    cwd=cwd,
                    env=child_env,
                    start_new_session=True,
                    close_fds=True,
                )
            finally:
                # Slave fd must be closed in parent process so master_fd receives EOF when child exits
                try:
                    os.close(slave_fd)
                except OSError:
                    pass

            self.is_alive = True
            self._terminated = False
            self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._reader_thread.start()

    def _read_loop(self) -> None:
        """Continuously read output from master_fd in non-blocking select mode."""
        while True:
            with self._lock:
                if not self.is_alive or self.master_fd is None:
                    break
                fd = self.master_fd

            try:
                r, _, _ = select.select([fd], [], [], 0.05)
                if fd in r:
                    data = os.read(fd, 4096)
                    if not data:
                        # EOF indicates shell has exited
                        break
                    self.on_output(data)
            except (OSError, ValueError):
                break
        self.terminate()
    def write(self, data: str) -> None:
        """Send input string or control character (e.g. \\x03 for Ctrl+C) to shell."""
        with self._lock:
            fd = self.master_fd
            alive = self.is_alive
        if alive and fd is not None:
            try:
                os.write(fd, data.encode("utf-8"))
            except OSError:
                pass

    def resize(self, rows: int, cols: int) -> None:
        """Synchronize window dimensions with PTY device via TIOCSWINSZ ioctl."""
        with self._lock:
            fd = self.master_fd
            alive = self.is_alive
        if alive and fd is not None and fcntl and struct and termios:
            try:
                winsize = struct.pack("HHHH", max(1, int(rows)), max(1, int(cols)), 0, 0)
                fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
            except (OSError, ValueError):
                pass

    def terminate(self) -> None:
        """Cleanly terminate shell process group and release master file descriptor."""
        with self._lock:
            if self._terminated:
                return
            self._terminated = True
            self.is_alive = False

            fd_to_close = self.master_fd
            self.master_fd = None

            proc_to_kill = self.proc
            self.proc = None

            reader_thread = self._reader_thread
            self._reader_thread = None

        if fd_to_close is not None:
            try:
                os.close(fd_to_close)
            except OSError:
                pass

        if proc_to_kill is not None:
            pid = proc_to_kill.pid
            # Discover all child/descendant PIDs and their process groups
            child_pids = _find_posix_descendants(pid)
            all_pids = {pid} | set(child_pids)
            pgids = set()
            for p in all_pids:
                try:
                    pgids.add(os.getpgid(p))
                except (ProcessLookupError, OSError):
                    pass

            # Attempt gentle SIGTERM on all process groups and individual PIDs
            for pgid in pgids:
                try:
                    os.killpg(pgid, signal.SIGTERM)
                except (ProcessLookupError, OSError):
                    pass
            for p in all_pids:
                try:
                    os.kill(p, signal.SIGTERM)
                except (ProcessLookupError, OSError):
                    pass

            # Wait briefly for process to exit cleanly
            try:
                proc_to_kill.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                # Force kill process groups and lingering child PIDs
                for pgid in pgids:
                    try:
                        os.killpg(pgid, signal.SIGKILL)
                    except (ProcessLookupError, OSError):
                        pass
                for p in all_pids:
                    try:
                        os.kill(p, signal.SIGKILL)
                    except (ProcessLookupError, OSError):
                        pass
                try:
                    proc_to_kill.wait(timeout=0.1)
                except Exception:
                    pass
        # Prevent self-join deadlock
        if reader_thread is not None and threading.current_thread() != reader_thread:
            reader_thread.join(timeout=0.2)


class WindowsPTYFallback(BasePTYSession):
    """Fallback implementation for Windows environments when native POSIX PTY is unavailable."""

    def __init__(self, workspace_root: str, on_output: Callable[[bytes], None]) -> None:
        super().__init__(workspace_root, on_output)
        self.proc: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None

    @property
    def pid(self) -> Optional[int]:
        with self._lock:
            return self.proc.pid if self.proc is not None else None

    def start(self, shell_cmd: Optional[list[str]] = None) -> None:
        with self._lock:
            if self.is_alive:
                return

            if shell_cmd is None:
                shell_cmd = ["cmd.exe"]

            cwd = self.workspace_root if os.path.isdir(self.workspace_root) else os.getcwd()

            self.proc = subprocess.Popen(
                shell_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=cwd,
                text=False,
                bufsize=0,
            )
            self.is_alive = True
            self._terminated = False
            self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._reader_thread.start()

    def _read_loop(self) -> None:
        while True:
            with self._lock:
                if not self.is_alive or not self.proc or not self.proc.stdout:
                    break
                stdout = self.proc.stdout
            try:
                chunk = stdout.read(1024)
                if not chunk:
                    break
                self.on_output(chunk)
            except Exception:
                break
        self.terminate()

    def write(self, data: str) -> None:
        with self._lock:
            proc = self.proc
            alive = self.is_alive
        if alive and proc and proc.stdin:
            try:
                proc.stdin.write(data.encode("utf-8"))
                proc.stdin.flush()
            except OSError:
                pass

    def resize(self, rows: int, cols: int) -> None:
        # Resize ioctl not supported in standard pipe fallback
        pass

    def terminate(self) -> None:
        with self._lock:
            if self._terminated:
                return
            self._terminated = True
            self.is_alive = False

            proc_to_kill = self.proc
            self.proc = None

            reader_thread = self._reader_thread
            self._reader_thread = None

        if proc_to_kill is not None:
            pid = proc_to_kill.pid
            if os.name == "nt":
                try:
                    creationflags = 0x08000000 if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                        capture_output=True,
                        creationflags=creationflags,
                        timeout=1.0,
                    )
                except Exception:
                    pass
            try:
                proc_to_kill.terminate()
            except OSError:
                pass
            try:
                proc_to_kill.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                try:
                    proc_to_kill.kill()
                except OSError:
                    pass
                try:
                    proc_to_kill.wait(timeout=0.1)
                except Exception:
                    pass

        if reader_thread is not None and threading.current_thread() != reader_thread:
            reader_thread.join(timeout=0.2)

def create_pty_session(
    workspace_root: str,
    on_output: Callable[[bytes], None],
) -> BasePTYSession:
    """Factory creating the appropriate PTY session based on operating system."""
    if _IS_POSIX:
        return PosixPTYSession(workspace_root=workspace_root, on_output=on_output)
    return WindowsPTYFallback(workspace_root=workspace_root, on_output=on_output)


# Direct alias for default session class
PTYSession = PosixPTYSession if _IS_POSIX else WindowsPTYFallback
