import os
import sys
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
