"""Tests untuk local Git gateway API dan GitRepositoryFacade (#Fase 1.2).

Memverifikasi:
- GitRepositoryFacade: diff_detail, file_content_at_ref, file_diff_unified
- GatewayService: git_status, git_diff, git_commits
- Django HTTP Endpoints:
    GET /api/projects/<id>/git/status
    GET /api/projects/<id>/git/diff
    GET /api/projects/<id>/git/commits
"""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Ensure PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "django_app"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ["DJANGO_ALLOWED_HOSTS"] = "testserver,127.0.0.1,localhost"

from django.conf import settings
if "testserver" not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS = ["testserver", "127.0.0.1", "localhost"] + list(settings.ALLOWED_HOSTS)

import django
try:
    django.setup()
except RuntimeError:
    pass

from django.test import Client
import api.views as views
from agent_ai.git.repository import GitRepositoryFacade
from api.services import GatewayService


@pytest.fixture
def temp_git_repo(tmp_path):
    """Buat temporary git repository dengan 1 initial commit."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    # Git init
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=str(repo_dir), check=True)

    # Initial file
    init_file = repo_dir / "hello.py"
    init_file.write_text("print('hello world')\n", encoding="utf-8")

    subprocess.run(["git", "add", "hello.py"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(repo_dir), check=True)

    return repo_dir


def test_git_repository_facade_diff_detail(temp_git_repo):
    facade = GitRepositoryFacade(root=temp_git_repo)
    assert facade.is_repository() is True

    # 1. Modify hello.py
    hello_file = temp_git_repo / "hello.py"
    hello_file.write_text("print('hello world')\nprint('welcome to aether')\n", encoding="utf-8")

    # 2. Add an untracked file
    new_file = temp_git_repo / "new_module.py"
    new_file.write_text("def test(): pass\n", encoding="utf-8")

    # Status check
    st = facade.status()
    assert st.clean is False
    status_map = {f.path: f.status for f in st.files}
    assert "hello.py" in status_map
    assert "new_module.py" in status_map

    # diff_detail for modified file
    diff_hello = facade.diff_detail("hello.py")
    assert diff_hello["path"] == "hello.py"
    assert diff_hello["status"] == "modified"
    assert "print('hello world')" in diff_hello["original"]
    assert "welcome to aether" not in diff_hello["original"]
    assert "welcome to aether" in diff_hello["modified"]
    assert "+print('welcome to aether')" in diff_hello["diff"]

    # diff_detail for untracked file
    diff_new = facade.diff_detail("new_module.py")
    assert diff_new["path"] == "new_module.py"
    assert diff_new["status"] == "untracked"
    assert diff_new["original"] == ""
    assert "def test(): pass" in diff_new["modified"]

    # log
    commits = facade.log(limit=5)
    assert len(commits) >= 1
    assert commits[0].subject == "Initial commit"


def test_gateway_service_git_endpoints(temp_git_repo):
    # Setup mock project store
    mock_store = MagicMock()
    mock_store.get_project.return_value = {"id": "proj-1", "path": str(temp_git_repo)}

    service = GatewayService(
        project_store=mock_store,
        project_registry=MagicMock(),
        task_preparation=MagicMock(),
        session_store=MagicMock(),
    )

    # 1. git_status
    st = service.git_status("proj-1")
    assert st["is_repository"] is True
    assert st["clean"] is True
    assert st["files"] == []

    # Modify file
    (temp_git_repo / "hello.py").write_text("modified\n", encoding="utf-8")

    st2 = service.git_status("proj-1")
    assert st2["clean"] is False
    assert len(st2["files"]) == 1
    assert st2["files"][0]["path"] == "hello.py"

    # 2. git_diff (detail & summary)
    diff_all = service.git_diff("proj-1")
    assert diff_all["is_repository"] is True
    assert len(diff_all["files"]) >= 1

    diff_file = service.git_diff("proj-1", file_path="hello.py")
    assert diff_file["is_repository"] is True
    assert diff_file["path"] == "hello.py"
    assert diff_file["status"] == "modified"
    assert "modified" in diff_file["modified"]

    # 3. git_commits
    commits = service.git_commits("proj-1", limit=5)
    assert commits["is_repository"] is True
    assert len(commits["commits"]) >= 1


def test_django_http_git_routes(temp_git_repo):
    mock_store = MagicMock()
    mock_store.get_project.return_value = {"id": "test-p1", "path": str(temp_git_repo)}

    service = GatewayService(
        project_store=mock_store,
        project_registry=MagicMock(),
        task_preparation=MagicMock(),
        session_store=MagicMock(),
    )

    orig_get_service = views.get_service
    views.get_service = lambda: service

    try:
        client = Client()

        # Modify file
        (temp_git_repo / "hello.py").write_text("changes here\n", encoding="utf-8")

        # GET /api/projects/test-p1/git/status
        res_status = client.get("/api/projects/test-p1/git/status")
        assert res_status.status_code == 200
        data_status = res_status.json()
        assert data_status["is_repository"] is True
        assert data_status["clean"] is False

        # GET /api/projects/test-p1/git/diff?path=hello.py
        res_diff = client.get("/api/projects/test-p1/git/diff?path=hello.py")
        assert res_diff.status_code == 200
        data_diff = res_diff.json()
        assert data_diff["path"] == "hello.py"
        assert data_diff["status"] == "modified"
        assert "changes here" in data_diff["modified"]

        # GET /api/projects/test-p1/git/commits
        res_commits = client.get("/api/projects/test-p1/git/commits")
        assert res_commits.status_code == 200
        data_commits = res_commits.json()
        assert len(data_commits["commits"]) >= 1
        assert "parents" in data_commits["commits"][0]
        assert "refs" in data_commits["commits"][0]

        # GET /api/projects/test-p1/git/branches
        res_branches = client.get("/api/projects/test-p1/git/branches")
        assert res_branches.status_code == 200
        data_branches = res_branches.json()
        assert data_branches["is_repository"] is True
        assert data_branches["current"] is not None
        assert "local_branches" in data_branches
        assert "remote_branches" in data_branches

        # POST /api/projects/test-p1/git/discard (single file)
        res_discard = client.post(
            "/api/projects/test-p1/git/discard",
            data='{"file_path": "hello.py"}',
            content_type="application/json",
        )
        assert res_discard.status_code == 200
        data_discard = res_discard.json()
        assert data_discard["ok"] is True
        assert (temp_git_repo / "hello.py").read_text(encoding="utf-8") == "print('hello world')\n"

        # POST /api/projects/test-p1/git/discard (untracked file)
        untracked = temp_git_repo / "untracked.txt"
        untracked.write_text("untracked content", encoding="utf-8")
        assert untracked.exists()
        res_discard_untracked = client.post(
            "/api/projects/test-p1/git/discard",
            data='{"file_path": "untracked.txt"}',
            content_type="application/json",
        )
        assert res_discard_untracked.status_code == 200
        assert not untracked.exists()

        # POST /api/projects/test-p1/git/discard (discard all)
        (temp_git_repo / "hello.py").write_text("dirty again\n", encoding="utf-8")
        (temp_git_repo / "extra.txt").write_text("extra", encoding="utf-8")
        res_discard_all = client.post(
            "/api/projects/test-p1/git/discard",
            data='{}',
            content_type="application/json",
        )
        assert res_discard_all.status_code == 200
        assert (temp_git_repo / "hello.py").read_text(encoding="utf-8") == "print('hello world')\n"
        assert not (temp_git_repo / "extra.txt").exists()
    finally:
        views.get_service = orig_get_service


def test_git_status_scoped_to_subfolder(temp_git_repo):
    # Create subdirectory subapp with file subapp/feature.py
    subapp = temp_git_repo / "subapp"
    subapp.mkdir()
    feature_file = subapp / "feature.py"
    feature_file.write_text("def feature(): return 1\n", encoding="utf-8")

    # Commit initial state for feature.py
    subprocess.run(["git", "add", "."], cwd=str(temp_git_repo), check=True)
    subprocess.run(["git", "commit", "-m", "Add subapp feature"], cwd=str(temp_git_repo), check=True)

    # Modify feature.py in subapp
    feature_file.write_text("def feature(): return 2\n", encoding="utf-8")

    # Create root file root_change.py outside subapp
    root_change = temp_git_repo / "root_change.py"
    root_change.write_text("# root change\n", encoding="utf-8")

    # 1. By default with strict_root=True, subfolder without .git is not a repo
    facade_strict = GitRepositoryFacade(root=subapp)
    assert facade_strict.is_repository() is False

    # 2. When strict_root=False (monorepo scoped subfolder mode), scopes to subapp
    facade = GitRepositoryFacade(root=subapp, strict_root=False)
    assert facade.is_repository() is True

    st = facade.status()
    file_paths = [f.path for f in st.files]

    # Assert root_change.py is NOT in st.files
    assert "root_change.py" not in file_paths
    assert not any("root_change" in p for p in file_paths)

    # Assert feature.py IS in st.files, with path "feature.py" (not "subapp/feature.py")
    assert "feature.py" in file_paths
    assert "subapp/feature.py" not in file_paths

    # Test facade.diff_detail("feature.py") successfully retrieves original content via show_file
    diff_detail = facade.diff_detail("feature.py")
    assert diff_detail["path"] == "feature.py"
    assert diff_detail["status"] == "modified"
    assert "def feature(): return 1" in diff_detail["original"]
    assert "def feature(): return 2" in diff_detail["modified"]

    # Test diff summary is also scoped
    diff_summaries = facade.diff()
    diff_paths = [d.path for d in diff_summaries]
    assert "feature.py" in diff_paths
    assert "root_change.py" not in diff_paths


def test_git_status_and_diff_filters_internal_mechanisms(temp_git_repo):
    """Memastikan metadata internal Aegis (.aegis, .aether, .aegis_tmp_*, swp, db) tidak bocor."""
    # 1. Buat direktori dan berkas internal
    aegis_dir = temp_git_repo / ".aegis"
    aegis_dir.mkdir(exist_ok=True)
    (aegis_dir / "ENVIRONMENT.md").write_text("# Aegis Environment", encoding="utf-8")

    aether_dir = temp_git_repo / ".aether"
    aether_dir.mkdir(exist_ok=True)
    (aether_dir / "task.log").write_text("log data", encoding="utf-8")

    tmp_swp = temp_git_repo / ".aegis_tmp_xyz123.swp"
    tmp_swp.write_text("swap content", encoding="utf-8")

    data_dir = temp_git_repo / "data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / "aegis.db").write_text("sqlite db dummy", encoding="utf-8")

    # 2. Buat berkas user biasa yang valid
    user_file = temp_git_repo / "user_code.py"
    user_file.write_text("print('user')", encoding="utf-8")

    facade = GitRepositoryFacade(root=temp_git_repo)
    st = facade.status()
    file_paths = [f.path for f in st.files]

    # Berkas user harus terdeteksi
    assert "user_code.py" in file_paths

    # Seluruh mekanisme internal harus disaring (tidak boleh terdeteksi)
    assert not any(p.startswith(".aegis") for p in file_paths)
    assert not any(p.startswith(".aether") for p in file_paths)
    assert not any(p.endswith(".swp") for p in file_paths)
    assert not any("data/aegis.db" in p for p in file_paths)

    # diff_detail pada berkas internal harus mengembalikan status clean
    detail_aegis = facade.diff_detail(".aegis/ENVIRONMENT.md")
    assert detail_aegis["status"] == "clean"
    assert detail_aegis["diff"] == ""

    # diff summary tidak boleh memuat mekanisme internal
    summaries = facade.diff()
    summary_paths = [s.path for s in summaries]
    assert not any(".aegis" in p for p in summary_paths)
    assert not any(".aether" in p for p in summary_paths)


def test_git_init_for_non_git_workspace(tmp_path):
    plain_dir = tmp_path / "plain_project"
    plain_dir.mkdir()

    facade = GitRepositoryFacade(root=plain_dir)
    assert facade.is_repository() is False

    res = facade.init()
    assert res["ok"] is True
    assert (plain_dir / ".git").exists()
    assert facade.is_repository() is True


def test_django_http_git_init_endpoint(tmp_path):
    project_dir = tmp_path / "init_project"
    project_dir.mkdir()

    mock_store = MagicMock()
    mock_store.get_project.return_value = {"id": "test-init-1", "path": str(project_dir)}

    service = GatewayService(
        project_store=mock_store,
        project_registry=MagicMock(),
        task_preparation=MagicMock(),
        session_store=MagicMock(),
    )

    orig_get_service = views.get_service
    views.get_service = lambda: service

    try:
        client = Client()

        # Status before init -> is_repository is False
        res_before = client.get("/api/projects/test-init-1/git/status")
        assert res_before.status_code == 200
        assert res_before.json()["is_repository"] is False

        # POST /api/projects/test-init-1/git/init
        res_init = client.post("/api/projects/test-init-1/git/init")
        assert res_init.status_code == 200
        data_init = res_init.json()
        assert data_init["ok"] is True
        assert data_init["is_repository"] is True

        # Status after init -> is_repository is True
        res_after = client.get("/api/projects/test-init-1/git/status")
        assert res_after.status_code == 200
        assert res_after.json()["is_repository"] is True

        # POST /api/projects/test-init-1/git/deinit
        res_deinit = client.post("/api/projects/test-init-1/git/deinit")
        assert res_deinit.status_code == 200
        data_deinit = res_deinit.json()
        assert data_deinit["ok"] is True
        assert data_deinit["is_repository"] is False

        # Status after deinit -> is_repository is False
        res_after_deinit = client.get("/api/projects/test-init-1/git/status")
        assert res_after_deinit.status_code == 200
        assert res_after_deinit.json()["is_repository"] is False
    finally:
        views.get_service = orig_get_service


def test_gitignore_patterns_and_sync(tmp_path):
    project_dir = tmp_path / "gi_project"
    project_dir.mkdir()

    gi_file = project_dir / ".gitignore"
    gi_file.write_text("# Comments\n*.log\nnode_modules/\nsecrets.env\n", encoding="utf-8")

    facade = GitRepositoryFacade(root=project_dir)
    patterns = facade.gitignore_patterns()
    assert patterns == ["*.log", "node_modules/", "secrets.env"]

    mock_store = MagicMock()
    mock_store.get_project.return_value = {"id": "proj-gi", "path": str(project_dir)}

    service = GatewayService(
        project_store=mock_store,
        project_registry=MagicMock(),
        task_preparation=MagicMock(),
        session_store=MagicMock(),
    )

    st = service.git_status("proj-gi")
    assert st["gitignore_rules"] == ["*.log", "node_modules/", "secrets.env"]


