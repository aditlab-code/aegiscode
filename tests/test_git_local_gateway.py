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
    hello_file.write_text("print('hello world')\nprint('welcome to aegis')\n", encoding="utf-8")

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
    assert "welcome to aegis" not in diff_hello["original"]
    assert "welcome to aegis" in diff_hello["modified"]
    assert "+print('welcome to aegis')" in diff_hello["diff"]

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



def test_git_repository_facade_stage_and_unstage(temp_git_repo):
    facade = GitRepositoryFacade(root=temp_git_repo)
    assert facade.is_repository() is True

    # Create 2 modified files
    file_a = temp_git_repo / "hello.py"
    file_a.write_text("print('hello world')\n# change 1\n", encoding="utf-8")

    file_b = temp_git_repo / "extra.py"
    file_b.write_text("print('extra file')\n", encoding="utf-8")

    st = facade.status()
    assert st.clean is False
    st_map = {f.path: f for f in st.files}
    assert st_map["hello.py"].staged is False
    assert st_map["extra.py"].staged is False

    # Stage only hello.py
    res_stage = facade.stage("hello.py")
    assert res_stage["ok"] is True
    assert res_stage["file_path"] == "hello.py"

    # Check status and diff_detail
    st = facade.status()
    st_map = {f.path: f for f in st.files}
    assert st_map["hello.py"].staged is True
    assert st_map["extra.py"].staged is False

    diff_a = facade.diff_detail("hello.py")
    assert diff_a["staged"] is True
    diff_b = facade.diff_detail("extra.py")
    assert diff_b["staged"] is False

    # Unstage hello.py
    res_unstage = facade.unstage("hello.py")
    assert res_unstage["ok"] is True
    assert res_unstage["file_path"] == "hello.py"

    st = facade.status()
    st_map = {f.path: f for f in st.files}
    assert st_map["hello.py"].staged is False
    diff_a_after = facade.diff_detail("hello.py")
    assert diff_a_after["staged"] is False

    # Stage all
    res_stage_all = facade.stage()
    assert res_stage_all["ok"] is True
    st = facade.status()
    for f in st.files:
        assert f.staged is True

    # Unstage all
    res_unstage_all = facade.unstage()
    assert res_unstage_all["ok"] is True
    st = facade.status()
    for f in st.files:
        assert f.staged is False


def test_git_gateway_stage_and_unstage_endpoints(temp_git_repo):
    mock_store = MagicMock()
    mock_store.get_project.return_value = {"id": "proj-stage-1", "path": str(temp_git_repo)}

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

        # Modify hello.py
        (temp_git_repo / "hello.py").write_text("changed content\n", encoding="utf-8")

        # POST stage
        res_stage = client.post(
            "/api/projects/proj-stage-1/git/stage",
            data='{"file_path": "hello.py"}',
            content_type="application/json",
        )
        assert res_stage.status_code == 200
        data_stage = res_stage.json()
        assert data_stage["ok"] is True
        assert data_stage["file_path"] == "hello.py"

        # Verify via diff endpoint
        res_diff = client.get("/api/projects/proj-stage-1/git/diff?path=hello.py")
        assert res_diff.status_code == 200
        assert res_diff.json()["staged"] is True

        # POST unstage
        res_unstage = client.post(
            "/api/projects/proj-stage-1/git/unstage",
            data='{"file_path": "hello.py"}',
            content_type="application/json",
        )
        assert res_unstage.status_code == 200
        data_unstage = res_unstage.json()
        assert data_unstage["ok"] is True
        assert data_unstage["file_path"] == "hello.py"

        # Verify diff endpoint now shows unstaged
        res_diff2 = client.get("/api/projects/proj-stage-1/git/diff?path=hello.py")
        assert res_diff2.status_code == 200
        assert res_diff2.json()["staged"] is False
    finally:
        views.get_service = orig_get_service


def test_create_checkpoint_selective_staging(temp_git_repo):
    from api.github_backup import GithubBackupService

    backup_service = GithubBackupService()
    backup_service.save_config(root=temp_git_repo, repository="", branch="main")

    # Commit .gitignore terlebih dahulu agar tidak terhitung sebagai untracked file baru
    gi = temp_git_repo / ".gitignore"
    gi.write_text(".aegis/\n", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore"], cwd=str(temp_git_repo), check=True)
    subprocess.run(["git", "commit", "-m", "Add gitignore"], cwd=str(temp_git_repo), check=True)

    facade = GitRepositoryFacade(root=temp_git_repo)

    # Create 2 modifications
    file_a = temp_git_repo / "hello.py"
    file_a.write_text("print('hello staged')\n", encoding="utf-8")

    file_b = temp_git_repo / "world.py"
    file_b.write_text("print('unstaged file')\n", encoding="utf-8")
    # Stage only file_a
    facade.stage("hello.py")

    st = facade.status()
    st_map = {f.path: f for f in st.files}
    assert st_map["hello.py"].staged is True
    assert st_map["world.py"].staged is False

    # Create checkpoint: should only commit hello.py
    res = backup_service.create_checkpoint(root=temp_git_repo, description="Checkpoint Staged Only")
    assert res["committed"] is True
    assert res["checkpoint"]["files_changed"] == 1

    # Verify world.py is still uncommitted in working tree
    st_after = facade.status()
    assert st_after.clean is False
    st_after_map = {f.path: f for f in st_after.files}
    assert "hello.py" not in st_after_map
    assert "world.py" in st_after_map
    assert st_after_map["world.py"].staged is False

    # Second checkpoint without manual staging: should auto-stage remaining changes
    res2 = backup_service.create_checkpoint(root=temp_git_repo, description="Checkpoint Fallback Auto Stage")
    assert res2["committed"] is True
    assert res2["checkpoint"]["files_changed"] == 1

    # Working tree should now be clean
    st_clean = facade.status()
    assert st_clean.clean is True
    assert st_clean.files == []


def test_git_branch_checkout_create_delete_merge(temp_git_repo):
    facade = GitRepositoryFacade(root=temp_git_repo)
    assert facade.is_repository() is True

    # Create new branch 'feature-auth' and checkout
    res_create = facade.create_branch("feature-auth", checkout=True)
    assert res_create["ok"] is True
    assert res_create["branch"] == "feature-auth"
    assert facade.current_branch() == "feature-auth"

    # Commit on feature-auth
    feat_file = temp_git_repo / "auth.py"
    feat_file.write_text("print('auth module')\n", encoding="utf-8")
    facade.stage("auth.py")
    subprocess.run(["git", "commit", "-m", "Add auth"], cwd=str(temp_git_repo), check=True)

    # Checkout back to initial branch (master or main)
    b_info = facade.branch_info()
    initial_branch = "main" if "main" in b_info.local_branches else "master"
    res_co = facade.checkout(initial_branch)
    assert res_co["ok"] is True
    assert facade.current_branch() == initial_branch

    # Merge feature-auth into initial_branch
    res_merge = facade.merge("feature-auth", message="Merge feature auth")
    assert res_merge["ok"] is True
    assert (temp_git_repo / "auth.py").exists()

    # Delete branch feature-auth
    res_del = facade.delete_branch("feature-auth")
    assert res_del["ok"] is True
    b_info_after = facade.branch_info()
    assert "feature-auth" not in b_info_after.local_branches


def test_git_stash_operations(temp_git_repo):
    facade = GitRepositoryFacade(root=temp_git_repo)

    # Make a change
    hello = temp_git_repo / "hello.py"
    hello.write_text("print('modified for stash')\n", encoding="utf-8")

    # Stash
    res_stash = facade.stash(message="WIP stash test")
    assert res_stash["ok"] is True
    assert facade.status().clean is True

    # Stash list
    stashes = facade.stash_list()
    assert len(stashes) >= 1
    assert "WIP stash test" in stashes[0]["message"]

    # Stash pop
    res_pop = facade.stash_pop(0)
    assert res_pop["ok"] is True
    assert facade.status().clean is False
    assert "modified for stash" in hello.read_text(encoding="utf-8")


def test_git_remotes_operations(temp_git_repo):
    facade = GitRepositoryFacade(root=temp_git_repo)

    # Add remote
    res_add = facade.add_remote("origin", "https://github.com/example/test.git")
    assert res_add["ok"] is True

    # List remotes
    remotes = facade.remotes()
    assert len(remotes) == 1
    assert remotes[0]["name"] == "origin"
    assert "https://github.com/example/test.git" in remotes[0]["fetch_url"]

    # Set remote url
    res_set = facade.set_remote_url("origin", "https://github.com/example/updated.git")
    assert res_set["ok"] is True
    remotes_updated = facade.remotes()
    assert "https://github.com/example/updated.git" in remotes_updated[0]["fetch_url"]


def test_git_endpoints_branch_stash_remotes(temp_git_repo):
    mock_store = MagicMock()
    mock_store.get_project.return_value = {
        "id": "proj-multi-1",
        "name": "Multi Branch Project",
        "path": str(temp_git_repo),
    }
    svc = GatewayService(project_store=mock_store)
    orig_get_service = views.get_service
    views.get_service = lambda: svc

    try:
        client = Client()

        # 1. Create branch endpoint
        res_create = client.post(
            "/api/projects/proj-multi-1/git/branches/create",
            data='{"branch": "endpoint-branch", "checkout": true}',
            content_type="application/json",
        )
        assert res_create.status_code == 200
        assert res_create.json()["ok"] is True
        assert res_create.json()["branch"] == "endpoint-branch"

        # 2. Checkout endpoint back
        b_info = svc.git_branches("proj-multi-1")
        main_b = "main" if "main" in b_info["local_branches"] else "master"
        res_co = client.post(
            "/api/projects/proj-multi-1/git/checkout",
            data=f'{{"branch": "{main_b}"}}',
            content_type="application/json",
        )
        assert res_co.status_code == 200
        assert res_co.json()["ok"] is True

        # 3. Merge endpoint
        res_merge = client.post(
            "/api/projects/proj-multi-1/git/merge",
            data='{"branch": "endpoint-branch"}',
            content_type="application/json",
        )
        assert res_merge.status_code == 200
        assert res_merge.json()["ok"] is True

        # 4. Stash endpoint
        hello = temp_git_repo / "hello.py"
        hello.write_text("print('endpoint stash')\n", encoding="utf-8")
        res_stash = client.post(
            "/api/projects/proj-multi-1/git/stash",
            data='{"message": "Endpoint stash"}',
            content_type="application/json",
        )
        assert res_stash.status_code == 200
        assert res_stash.json()["ok"] is True

        # 5. Stash list endpoint
        res_slist = client.get("/api/projects/proj-multi-1/git/stash/list")
        assert res_slist.status_code == 200
        assert len(res_slist.json()["stashes"]) >= 1

        # 6. Stash pop endpoint
        res_spop = client.post(
            "/api/projects/proj-multi-1/git/stash/pop",
            data='{"index": 0}',
            content_type="application/json",
        )
        assert res_spop.status_code == 200
        assert res_spop.json()["ok"] is True

        # 7. Remotes endpoint GET & POST
        res_rem_post = client.post(
            "/api/projects/proj-multi-1/git/remotes",
            data='{"name": "upstream", "url": "https://github.com/origin/repo.git"}',
            content_type="application/json",
        )
        assert res_rem_post.status_code == 200
        assert res_rem_post.json()["ok"] is True

        res_rem_get = client.get("/api/projects/proj-multi-1/git/remotes")
        assert res_rem_get.status_code == 200
        assert any(r["name"] == "upstream" for r in res_rem_get.json()["remotes"])

        # 8. Delete branch endpoint
        res_del = client.post(
            "/api/projects/proj-multi-1/git/branches/delete",
            data='{"branch": "endpoint-branch"}',
            content_type="application/json",
        )
        assert res_del.status_code == 200
        assert res_del.json()["ok"] is True
    finally:
        views.get_service = orig_get_service


def test_git_clone_operation(temp_git_repo):
    facade = GitRepositoryFacade(root=temp_git_repo)
    res_clone = facade.clone(url=str(temp_git_repo), target_dir="subclone")
    assert res_clone["ok"] is True
    assert (temp_git_repo / "subclone" / "hello.py").exists()


def test_git_native_commit_facade_and_endpoint(temp_git_repo):
    facade = GitRepositoryFacade(root=temp_git_repo)

    # 1. Modify file and test facade.commit
    hello = temp_git_repo / "hello.py"
    hello.write_text("print('native branch commit')\n", encoding="utf-8")
    facade.stage("hello.py")
    res_commit = facade.commit("Native commit on active branch")
    assert res_commit["ok"] is True
    assert res_commit["commit"] != ""
    assert facade.status().clean is True

    # 2. Test HTTP endpoint /git/commit
    hello.write_text("print('endpoint native commit')\n", encoding="utf-8")
    mock_store = MagicMock()
    mock_store.get_project.return_value = {
        "id": "proj-commit-1",
        "name": "Commit Project",
        "path": str(temp_git_repo),
    }
    svc = GatewayService(project_store=mock_store)
    orig_get_service = views.get_service
    views.get_service = lambda: svc
    try:
        client = Client()
        res = client.post(
            "/api/projects/proj-commit-1/git/commit",
            data='{"message": "Endpoint native commit", "stage_all": true}',
            content_type="application/json",
        )
        assert res.status_code == 200
        data = res.json()
        assert data["ok"] is True
        assert data["commit"] != ""
        assert facade.status().clean is True
    finally:
        views.get_service = orig_get_service
