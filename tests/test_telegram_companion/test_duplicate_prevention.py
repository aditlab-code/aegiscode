from __future__ import annotations

import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_ai.runtime.telegram.bot_client import TelegramBotClient
from agent_ai.runtime.telegram.handler import TelegramUpdateHandler
from agent_ai.runtime.telegram.lock import TelegramPollerLock
from agent_ai.runtime.telegram.stream_relay import TelegramStreamRelay


def test_telegram_poller_lock_mutual_exclusion():
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = Path(tmpdir) / "test_poller.lock"
        lock1 = TelegramPollerLock(lock_path=lock_file)
        lock2 = TelegramPollerLock(lock_path=lock_file)

        # Process 1 acquires lock
        assert lock1.acquire() is True
        assert lock_file.exists()

        # Process 2 attempts to acquire lock on the same file -> fails
        assert lock2.acquire() is False

        # Process 1 releases lock
        lock1.release()

        # Process 2 can now acquire lock
        assert lock2.acquire() is True
        lock2.release()


def test_bot_client_offset_persistence_and_deduplication():
    with tempfile.TemporaryDirectory() as tmpdir:
        offset_file = Path(tmpdir) / "telegram_offset.json"
        bot = TelegramBotClient(bot_token="test_token", offset_path=offset_file)

        # Initial offset is 0
        assert bot._offset == 0

        # Simulate Telegram API returning updates
        raw_updates = [
            {"update_id": 100, "message": {"text": "msg 100"}},
            {"update_id": 101, "message": {"text": "msg 101"}},
        ]

        with patch.object(bot, "_post", return_value={"ok": True, "result": raw_updates}):
            received = bot.get_updates()
            assert len(received) == 2
            assert bot._offset == 102
            # Offset was persisted to disk
            assert offset_file.exists()

        # Simulate Telegram returning the same update again (e.g. network retry)
        duplicate_updates = [
            {"update_id": 101, "message": {"text": "msg 101"}},
            {"update_id": 102, "message": {"text": "msg 102"}},
        ]

        with patch.object(bot, "_post", return_value={"ok": True, "result": duplicate_updates}):
            received2 = bot.get_updates()
            # update_id 101 must be deduplicated; only 102 accepted
            assert len(received2) == 1
            assert received2[0]["update_id"] == 102
            assert bot._offset == 103

        # Simulate bot client re-initialization (e.g. server restart)
        bot_restarted = TelegramBotClient(bot_token="test_token", offset_path=offset_file)
        # Offset must be restored from disk, NOT 0!
        assert bot_restarted._offset == 103


def test_bot_client_generation_terminates_zombie_threads():
    with tempfile.TemporaryDirectory() as tmpdir:
        offset_file = Path(tmpdir) / "telegram_offset.json"
        bot = TelegramBotClient(bot_token="test_token", offset_path=offset_file)

        dispatched_updates = []
        barrier = threading.Event()
        unblock_get_updates = threading.Event()

        def slow_get_updates():
            barrier.set()
            # Block until test signals
            unblock_get_updates.wait(timeout=2.0)
            return [{"update_id": 500, "message": {"text": "late update"}}]

        with patch.object(bot, "get_updates", side_effect=slow_get_updates):
            with patch.object(bot, "set_my_commands", return_value=True):
                # Start Poller Thread 1
                assert bot.start_polling(on_update=lambda u: dispatched_updates.append(u)) is True
                assert barrier.wait(timeout=1.0) is True

                # Thread 1 is currently blocked in slow_get_updates()
                # Stop Poller - this advances generation
                old_gen = bot._polling_generation
                bot.stop_polling()
                assert bot._polling_generation > old_gen

                # Now unblock the old get_updates call
                unblock_get_updates.set()
                time.sleep(0.1)

                # The old thread woke up with an old generation, so dispatched_updates must be EMPTY!
                assert len(dispatched_updates) == 0


def test_handler_update_id_deduplication():
    bot = MagicMock()
    sec = MagicMock(is_authorized=MagicMock(return_value=True))
    pairing = MagicMock()

    processed_messages = []

    handler = TelegramUpdateHandler(
        bot_client=bot,
        security_manager=sec,
        pairing_manager=pairing,
        get_repo_info=lambda: {"has_active_project": True, "name": "test"},
        get_changed_files=lambda: [],
    )

    # Patch _handle_message to observe execution
    with patch.object(handler, "_handle_message", side_effect=lambda m: processed_messages.append(m)):
        up1 = {"update_id": 777, "message": {"chat": {"id": 1}, "from": {"id": 2}, "text": "test 1"}}
        up2_duplicate = {"update_id": 777, "message": {"chat": {"id": 1}, "from": {"id": 2}, "text": "test 1 duplicate"}}
        up3_new = {"update_id": 778, "message": {"chat": {"id": 1}, "from": {"id": 2}, "text": "test 2"}}

        handler.handle_update(up1)
        handler.handle_update(up2_duplicate)
        handler.handle_update(up3_new)

        # Only up1 and up3 should have been executed; duplicate 777 dropped
        assert len(processed_messages) == 2
        assert processed_messages[0]["text"] == "test 1"
        assert processed_messages[1]["text"] == "test 2"


def test_stream_relay_handles_both_message_id_formats():
    bot = MagicMock()

    # Format 1: Direct dict returned by real TelegramBotClient.send_message
    bot.send_message.return_value = {"message_id": 444}
    relay1 = TelegramStreamRelay(bot_client=bot, chat_id=100, throttle_interval=0.0)
    assert relay1.message_id == 444

    # Format 2: Nested Telegram API response format
    bot.send_message.return_value = {"ok": True, "result": {"message_id": 555}}
    relay2 = TelegramStreamRelay(bot_client=bot, chat_id=100, throttle_interval=0.0)
    assert relay2.message_id == 555


def test_handler_gate_rejects_inbound_when_task_running():
    from agent_ai.runtime.telegram.gate import TelegramContextGate

    bot = MagicMock()
    sec = MagicMock(is_authorized=MagicMock(return_value=True))
    pairing = MagicMock()
    gate = TelegramContextGate(security_manager=sec)

    dispatched_turns = []

    def mock_on_steer(instruction, chat_id=None):
        dispatched_turns.append((chat_id, instruction))

    handler = TelegramUpdateHandler(
        bot_client=bot,
        security_manager=sec,
        pairing_manager=pairing,
        gate=gate,
        on_steer_command=mock_on_steer,
    )

    # 1. Register an active task in the Gate
    gate.register_task(chat_id=123, task_id="task-live-42")

    # 2. Inbound message sent while task is running
    up_during_task = {
        "update_id": 901,
        "message": {"chat": {"id": 123}, "from": {"id": 123, "username": "vizzyoc"}, "text": "buatkan endpoint baru"},
    }
    handler.handle_update(up_during_task)

    # Must NOT dispatch chat turn
    assert len(dispatched_turns) == 0
    # Must notify user that agent is busy
    assert bot.send_message.called
    sent_text = bot.send_message.call_args[1]["text"]
    assert "Agen Sedang Menjalankan Tugas" in sent_text
    assert "task-live-42" in sent_text

    # 3. Complete the task in the Gate
    bot.reset_mock()
    gate.complete_task(chat_id=123, task_id="task-live-42")

    # 4. Inbound message sent after task completes
    up_after_task = {
        "update_id": 902,
        "message": {"chat": {"id": 123}, "from": {"id": 123, "username": "vizzyoc"}, "text": "buatkan endpoint baru"},
    }
    handler.handle_update(up_after_task)

    # Now it must successfully dispatch chat turn!
    assert len(dispatched_turns) == 1
    assert dispatched_turns[0] == (123, "buatkan endpoint baru")

