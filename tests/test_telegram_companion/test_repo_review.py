from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_ai.git.repository import GitRepositoryFacade
from agent_ai.runtime.telegram.companion import TelegramCompanion
from agent_ai.runtime.telegram.handler import TelegramUpdateHandler
from agent_ai.runtime.telegram.security import TelegramSecurityManager
from agent_ai.runtime.telegram.views import (
    render_project_selector_view,
    render_repo_view,
)


# =============================================================================
# 1. GATEWAY SERVICE: STRICT ACTIVE PROJECT REPOSITORY INFO
# =============================================================================


def test_get_active_repository_info_strict():
    """Memastikan get_active_repository_info strictly merujuk ke project aktif tanpa fallback."""
    from apps.django_app.api.services import GatewayService

    mock_store = MagicMock()
    svc = GatewayService(project_store=mock_store)

    # 1. Ketika tidak ada project aktif
    mock_store.get_active_project_id.return_value = None
    info_none = svc.get_active_repository_info()
    assert info_none["has_active_project"] is False
    assert info_none["is_repo"] is False
    assert info_none["root"] == "-"
    assert info_none["name"] == "-"

    # 2. Ketika project aktif bukan git repository
    with tempfile.TemporaryDirectory() as tmpdir:
        non_git_path = Path(tmpdir) / "my_non_git_proj"
        non_git_path.mkdir()
        mock_store.get_active_project_id.return_value = "proj-123"
        mock_store.get_project.return_value = {
            "id": "proj-123",
            "name": "My Non Git Proj",
            "path": str(non_git_path),
        }

        info_non_git = svc.get_active_repository_info()
        assert info_non_git["has_active_project"] is True
        assert info_non_git["is_repo"] is False
        assert info_non_git["name"] == "My Non Git Proj"
        assert info_non_git["root"] == str(non_git_path)

    # 3. Ketika project aktif adalah valid git repository
    with tempfile.TemporaryDirectory() as tmpdir:
        git_path = Path(tmpdir) / "my_git_proj"
        git_path.mkdir()
        facade = GitRepositoryFacade(root=git_path)
        facade.init()
        (git_path / "hello.txt").write_text("Hello Git", encoding="utf-8")
        facade.commit(message="Initial commit", stage_all=True)

        mock_store.get_active_project_id.return_value = "proj-456"
        mock_store.get_project.return_value = {
            "id": "proj-456",
            "name": "My Git Proj",
            "path": str(git_path),
        }

        info_git = svc.get_active_repository_info()
        assert info_git["has_active_project"] is True
        assert info_git["is_repo"] is True
        assert info_git["name"] == "My Git Proj"
        assert info_git["root"] == str(git_path)
        assert info_git["branch"] in ("main", "master")
        assert "Initial commit" in info_git["last_commit"]
        assert info_git["uncommitted_changes"] == 0
        assert info_git["is_dirty"] is False


# =============================================================================
# 2. GIT FACADE: GET_CHANGED_FILES_SUMMARY (M, A, D)
# =============================================================================


def test_get_changed_files_summary():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir) / "repo"
        root.mkdir()
        facade = GitRepositoryFacade(root=root)

        # Bukan repository git -> []
        assert facade.get_changed_files_summary() == []

        facade.init()
        # Clean repo -> []
        assert facade.get_changed_files_summary() == []

        # Commit berkas awal
        f1 = root / "file1.txt"
        f1.write_text("line 1\nline 2\nline 3\n", encoding="utf-8")
        f2 = root / "file2.txt"
        f2.write_text("hello world\n", encoding="utf-8")
        facade.commit(message="initial commit", stage_all=True)
        assert facade.get_changed_files_summary() == []

        # 1. Modify f1
        f1.write_text("line 1\nline 2 edited\nline 3\nline 4\n", encoding="utf-8")

        # 2. Add new file (untracked)
        f3 = root / "file3.txt"
        f3.write_text("new untracked line 1\nnew untracked line 2\n", encoding="utf-8")

        # 3. Delete f2
        f2.unlink()

        summary = facade.get_changed_files_summary()
        summary_by_path = {item["path"]: item for item in summary}

        assert "file1.txt" in summary_by_path
        assert summary_by_path["file1.txt"]["status"] == "M"
        assert summary_by_path["file1.txt"]["lines"] > 0

        assert "file3.txt" in summary_by_path
        assert summary_by_path["file3.txt"]["status"] == "A"
        assert summary_by_path["file3.txt"]["lines"] == 2

        assert "file2.txt" in summary_by_path
        assert summary_by_path["file2.txt"]["status"] == "D"
        assert summary_by_path["file2.txt"]["lines"] >= 1


# =============================================================================
# 3. VIEWS: PROJECT SELECTOR & REPO VIEWS
# =============================================================================


def test_render_views():
    # 1. Project selector - kosong
    text_empty, markup_empty = render_project_selector_view([])
    assert "Belum ada project yang tersimpan" in text_empty
    assert markup_empty["inline_keyboard"] == []

    # 2. Project selector - ada projects
    projects = [
        {"id": "proj-1", "name": "Aegis Project Alpha"},
        {"id": "proj-2", "name": "Beta Tools"},
    ]
    text_sel, markup_sel = render_project_selector_view(projects)
    assert "Pilih Project Aktif di Aegis IDE:" in text_sel
    buttons = markup_sel["inline_keyboard"]
    assert len(buttons) == 2
    assert buttons[0][0]["text"] == "📁 Aegis Project Alpha"
    assert buttons[0][0]["callback_data"] == "project:select:proj-1"
    assert buttons[1][0]["text"] == "📁 Beta Tools"
    assert buttons[1][0]["callback_data"] == "project:select:proj-2"

    # 3. Repo view - tanpa active project
    info_no_act = {"has_active_project": False}
    text_no_act, markup_no_act = render_repo_view(info_no_act)
    assert "Belum ada project yang aktif di Aegis IDE" in text_no_act
    assert markup_no_act["inline_keyboard"][0][0]["callback_data"] == "repo:switch_project"

    # 4. Repo view - non-git repo
    info_non_git = {
        "has_active_project": True,
        "is_repo": False,
        "name": "Presentasi",
        "root": "/docs/presentasi",
    }
    text_non_git, markup_non_git = render_repo_view(info_non_git)
    assert "Belum diinisialisasi sebagai repositori Git" in text_non_git
    non_git_cbs = [b[0]["callback_data"] for b in markup_non_git["inline_keyboard"]]
    assert "repo:init" in non_git_cbs
    assert "repo:switch_project" in non_git_cbs

    # 5. Repo view - git repo dengan perubahan
    info_git = {
        "has_active_project": True,
        "is_repo": True,
        "name": "Presentasi",
        "root": "/docs/presentasi",
        "branch": "main",
        "last_commit": "abc1234 init",
        "uncommitted_changes": 2,
    }
    changed_files = [
        {"path": "index.html", "lines": 14, "status": "M"},
        {"path": "styles.css", "lines": 5, "status": "A"},
    ]
    text_git, markup_git = render_repo_view(info_git, changed_files=changed_files)
    assert "<code>index.html 14 line M</code>" in text_git
    assert "<code>styles.css 5 line A</code>" in text_git
    git_cbs = [b["callback_data"] for row in markup_git["inline_keyboard"] for b in row]
    assert "repo:accept" in git_cbs
    assert "repo:discard" in git_cbs
    assert "repo:switch_project" in git_cbs


# =============================================================================
# 4. COMPANION: ACTIVE PROJECT BINDING & REPO ACTIONS
# =============================================================================


def test_companion_project_binding():
    with tempfile.TemporaryDirectory() as tmpdir:
        proj_dir = Path(tmpdir) / "proj"
        proj_dir.mkdir()
        facade = GitRepositoryFacade(root=proj_dir)
        facade.init()
        (proj_dir / "file.txt").write_text("v1\n", encoding="utf-8")
        facade.commit(message="initial", stage_all=True)

        mock_svc = MagicMock()
        mock_svc.get_active_project.return_value = {
            "id": "p-1",
            "name": "Test Proj",
            "path": str(proj_dir),
        }
        mock_svc.project_store.list_projects.return_value = [
            {"id": "p-1", "name": "Test Proj", "path": str(proj_dir)}
        ]

        with patch("agent_ai.runtime.telegram.companion._get_gateway_service", return_value=mock_svc):
            comp = TelegramCompanion()

            # list_projects & set_active_project
            assert len(comp.list_projects()) == 1
            assert comp.set_active_project("p-1") is True
            mock_svc.set_active_project.assert_called_with("p-1")

            # get_changed_files when clean
            assert comp.get_changed_files() == []

            # Buat perubahan
            (proj_dir / "file.txt").write_text("v2\nmodified\n", encoding="utf-8")
            changes = comp.get_changed_files()
            assert len(changes) == 1
            assert changes[0]["path"] == "file.txt"
            assert changes[0]["status"] == "M"

            # Accept changes (commit)
            mock_svc.dispatch_remote_turn.return_value = {
                "response": "feat: update file to v2"
            }
            res_accept = comp.accept_repo_changes()
            assert res_accept["ok"] is True
            assert res_accept["message"] == "feat: update file to v2"
            assert comp.get_changed_files() == []

            # Buat perubahan lagi lalu discard
            (proj_dir / "file.txt").write_text("v3 garbage\n", encoding="utf-8")
            (proj_dir / "untracked.tmp").write_text("junk", encoding="utf-8")
            assert len(comp.get_changed_files()) == 2

            res_discard = comp.discard_repo_changes()
            assert res_discard["ok"] is True
            assert comp.get_changed_files() == []
            assert not (proj_dir / "untracked.tmp").exists()


# =============================================================================
# 5. HANDLER: ROUTING, SWITCHER & CALLBACKS
# =============================================================================


def test_handler_repo_and_project_switcher():
    bot = MagicMock()
    sec = MagicMock(is_authorized=MagicMock(return_value=True))
    pairing = MagicMock()

    mock_svc = MagicMock()
    mock_svc.get_active_project.return_value = None
    mock_svc.project_store.list_projects.return_value = [
        {"id": "proj-a", "name": "Project Alpha", "path": "/path/a"},
        {"id": "proj-b", "name": "Project Beta", "path": "/path/b"},
    ]

    handler = TelegramUpdateHandler(
        bot_client=bot,
        security_manager=sec,
        pairing_manager=pairing,
        get_repo_info=lambda: {"has_active_project": False},
        list_projects=mock_svc.project_store.list_projects,
        set_active_project=mock_svc.set_active_project,
    )

    # 1. /repo when no active project -> automatically shows project selector
    handler.handle_update({"message": {"chat": {"id": 123}, "from": {"id": 123}, "text": "/repo"}})
    assert bot.send_message.called
    text = bot.send_message.call_args[1]["text"]
    assert "Pilih Project Aktif di Aegis IDE:" in text
    kb = bot.send_message.call_args[1]["reply_markup"]["inline_keyboard"]
    assert kb[0][0]["callback_data"] == "project:select:proj-a"

    # 2. Callback project:select:proj-a
    bot.reset_mock()
    cb_update = {
        "callback_query": {
            "id": "cb-1",
            "from": {"id": 123},
            "message": {"message_id": 99, "chat": {"id": 123}},
            "data": "project:select:proj-a",
        }
    }
    handler.handle_update(cb_update)
    mock_svc.set_active_project.assert_called_with("proj-a")
    bot.answer_callback_query.assert_called_with(
        callback_query_id="cb-1", text="Mengaktifkan project..."
    )
    assert bot.edit_message_text.called

    # 3. Callback repo:switch_project
    bot.reset_mock()
    cb_switch = {
        "callback_query": {
            "id": "cb-2",
            "from": {"id": 123},
            "message": {"message_id": 99, "chat": {"id": 123}},
            "data": "repo:switch_project",
        }
    }
    handler.handle_update(cb_switch)
    bot.answer_callback_query.assert_called_with(
        callback_query_id="cb-2", text="Memuat daftar project..."
    )
    assert bot.edit_message_text.called
    edit_call_args = bot.edit_message_text.call_args[1]
    assert edit_call_args["chat_id"] == 123
    assert edit_call_args["message_id"] == 99
    assert "Pilih Project Aktif di Aegis IDE:" in edit_call_args["text"]


def test_handler_repo_accept_and_discard_callbacks():
    bot = MagicMock()
    sec = MagicMock(is_authorized=MagicMock(return_value=True))
    pairing = MagicMock()

    accept_spy = MagicMock(return_value={"ok": True, "message": "feat: test commit", "commit": "c123"})
    discard_spy = MagicMock(return_value={"ok": True, "message": "Semua perubahan berhasil dibatalkan."})
    init_spy = MagicMock(return_value={"ok": True, "message": "Repositori Git berhasil diinisialisasi."})

    handler = TelegramUpdateHandler(
        bot_client=bot,
        security_manager=sec,
        pairing_manager=pairing,
        on_repo_accept=accept_spy,
        on_repo_discard=discard_spy,
        on_repo_init=init_spy,
    )

    # 1. repo:accept
    handler.handle_update({
        "callback_query": {
            "id": "cb-acc",
            "from": {"id": 123},
            "message": {"message_id": 101, "chat": {"id": 123}},
            "data": "repo:accept",
        }
    })
    accept_spy.assert_called_once()
    bot.answer_callback_query.assert_called_with(callback_query_id="cb-acc", text="Memproses commit...")
    bot.edit_message_text.assert_called_with(
        chat_id=123,
        message_id=101,
        text=(
            "✅ <b>Perubahan Berhasil Di-commit!</b>\n\n"
            "• <b>Commit Hash:</b> <code>c123</code>\n"
            "• <b>Pesan Commit:</b> <i>feat: test commit</i>"
        ),
        reply_markup=None,
    )

    # 2. repo:discard
    handler.handle_update({
        "callback_query": {
            "id": "cb-disc",
            "from": {"id": 123},
            "message": {"message_id": 102, "chat": {"id": 123}},
            "data": "repo:discard",
        }
    })
    discard_spy.assert_called_once()
    bot.answer_callback_query.assert_called_with(callback_query_id="cb-disc", text="Membatalkan perubahan...")
    bot.edit_message_text.assert_called_with(
        chat_id=123,
        message_id=102,
        text="🗑️ <b>Seluruh Perubahan Dibatalkan</b>\n\nWorking directory telah di-reset dan bersih kembali.",
        reply_markup=None,
    )

    # 3. repo:init
    handler.handle_update({
        "callback_query": {
            "id": "cb-init",
            "from": {"id": 123},
            "message": {"message_id": 103, "chat": {"id": 123}},
            "data": "repo:init",
        }
    })
    init_spy.assert_called_once()
    bot.answer_callback_query.assert_called_with(callback_query_id="cb-init", text="Menginisialisasi Git...")
    assert bot.edit_message_text.called
    init_call_args = bot.edit_message_text.call_args[1]
    assert init_call_args["chat_id"] == 123
    assert init_call_args["message_id"] == 103
    assert "Git Berhasil Diinisialisasi!" in init_call_args["text"]
