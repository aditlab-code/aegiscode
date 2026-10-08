import os
import sys
import threading
import time
from pathlib import Path
import pytest
from agent_ai.runtime.pty_session import (
    BasePTYSession,
    PosixPTYSession,
    PTYSession,
    WindowsPTYFallback,
    create_pty_session,
)


def test_factory_creates_session(tmp_path: Path) -> None:
    received = []
    session = create_pty_session(
        workspace_root=str(tmp_path),
        on_output=lambda chunk: received.append(chunk),
    )
    assert isinstance(session, BasePTYSession)
    if os.name != "nt":
        assert isinstance(session, PosixPTYSession)
    else:
        assert isinstance(session, WindowsPTYFallback)


@pytest.mark.skipif(os.name == "nt", reason="POSIX PTY test")
def test_posix_pty_session_execution(tmp_path: Path) -> None:
    output_chunks: list[bytes] = []

    def on_output(data: bytes) -> None:
        output_chunks.append(data)

    session = PosixPTYSession(workspace_root=str(tmp_path), on_output=on_output)
    assert not session.is_alive
    assert session.pid is None

    # Use /bin/sh for maximum portability
    session.start(["/bin/sh"])
    assert session.is_alive
    assert session.pid is not None
    assert session.master_fd is not None

    # Test writing to terminal
    session.write("echo AEGIS_PTY_OK\n")

    # Wait for output with timeout
    start_time = time.time()
    accumulated = b""
    while time.time() - start_time < 3.0:
        accumulated = b"".join(output_chunks)
        if b"AEGIS_PTY_OK" in accumulated:
            break
        time.sleep(0.05)

    assert b"AEGIS_PTY_OK" in accumulated

    # Test resize
    session.resize(rows=30, cols=100)

    # Test Ctrl+C interrupt
    session.write("\x03")
    time.sleep(0.05)

    # Test clean termination
    session.terminate()
    assert not session.is_alive
    assert session.master_fd is None
    assert session.proc is None


def test_windows_fallback_structure(tmp_path: Path) -> None:
    session = WindowsPTYFallback(
        workspace_root=str(tmp_path),
        on_output=lambda data: None,
    )
    assert not session.is_alive
    assert session.pid is None
    # resize should be safe no-op
    session.resize(24, 80)
    # terminate when not running should be safe no-op
    session.terminate()

@pytest.mark.skipif(os.name == "nt", reason="POSIX PTY test")
def test_posix_pty_session_concurrent_terminate(tmp_path: Path) -> None:
    session = PosixPTYSession(
        workspace_root=str(tmp_path),
        on_output=lambda data: None,
    )
    session.start(["/bin/sh"])
    assert session.is_alive
    assert session.master_fd is not None

    exceptions: list[Exception] = []

    def _worker() -> None:
        try:
            session.terminate()
        except Exception as exc:
            exceptions.append(exc)

    threads = [threading.Thread(target=_worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=2.0)

    assert not exceptions, f"Unexpected exceptions during concurrent terminate: {exceptions}"
    assert not session.is_alive
    assert session.master_fd is None
    assert session.proc is None

    # Idempotent re-call should never raise
    session.terminate()


@pytest.mark.skipif(os.name == "nt", reason="POSIX PTY test")
def test_posix_pty_session_kills_child_process_group(tmp_path: Path) -> None:
    session = PosixPTYSession(
        workspace_root=str(tmp_path),
        on_output=lambda data: None,
    )
    session.start(["/bin/sh"])
    shell_pid = session.pid
    assert shell_pid is not None

    pid_file = tmp_path / "child.pid"
    # Launch background sleep process inside the shell and capture its PID
    session.write(f"(sleep 30) & echo $! > '{pid_file}'\n")

    # Wait for child.pid file to be written
    start_time = time.time()
    child_pid = None
    while time.time() - start_time < 3.0:
        if pid_file.exists():
            content = pid_file.read_text().strip()
            if content.isdigit():
                child_pid = int(content)
                break
        time.sleep(0.05)

    assert child_pid is not None, "Child background process PID was not recorded"

    # Ensure child process is currently alive
    try:
        os.kill(child_pid, 0)
    except ProcessLookupError:
        pytest.fail("Child process is not running prior to terminate")

    # Terminate PTY session (should kill process group including child_pid)
    session.terminate()
    assert not session.is_alive

    # Verify child_pid is killed (ProcessLookupError)
    child_dead = False
    deadline = time.time() + 2.0
    while time.time() < deadline:
        try:
            os.kill(child_pid, 0)
            time.sleep(0.05)
        except ProcessLookupError:
            child_dead = True
            break

    assert child_dead, f"Child process {child_pid} was not terminated by PTY session teardown"
