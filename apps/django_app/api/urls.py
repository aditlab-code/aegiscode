"""URL routing untuk Aegis Gateway API (#50).

Endpoint minimum:
    GET  /api/health
    GET  /api/projects
    GET  /api/tasks             (list/history, #53)
    POST /api/tasks
    GET  /api/tasks/<task_id>
    GET  /api/events            (SSE, #51)
"""

from __future__ import annotations

from django.urls import path

from api import views
from api import telegram_views

urlpatterns = [
    path("health", views.health, name="health"),
    # Sovereign Local Password & Identity Gateway
    path("auth/status", views.auth_status, name="auth_status"),
    path("auth/login", views.auth_login, name="auth_login"),
    path("auth/setup", views.auth_setup, name="auth_setup"),
    path("auth/pin", views.auth_pin_login, name="auth_pin_login"),
    path("auth/pin/setup", views.auth_pin_setup, name="auth_pin_setup"),
    path("auth/me", views.auth_me, name="auth_me"),
    path("auth/logout", views.auth_logout, name="auth_logout"),
    path("config", views.config, name="config"),
    # Global Settings (sumber tunggal `data/settings.json`; UI Sidebar Settings).
    path("settings", views.global_settings, name="global_settings"),
    path(
        "settings/update",
        views.global_settings_update,
        name="global_settings_update",
    ),
    # LLM Config / Settings (LLMConfigService Aegis existing).
    path("llm/config", views.llm_config, name="llm_config"),
    path("llm/credentials", views.llm_credentials, name="llm_credentials"),
    path(
        "llm/credentials/delete",
        views.delete_llm_credential,
        name="delete_llm_credential",
    ),
    path("llm/providers", views.llm_providers, name="llm_providers"),
    path("llm/providers/test", views.llm_provider_test, name="llm_provider_test"),
    path(
        "llm/providers/<str:provider_id>",
        views.llm_provider_detail,
        name="llm_provider_detail",
    ),
    path("llm/models", views.llm_models, name="llm_models"),
    path("llm/models/<str:model_id>", views.llm_model_detail, name="llm_model_detail"),
    path("projects", views.projects, name="projects"),
    # Folder picker (native OS dialog). HARUS didahulukan sebelum
    # "projects/<str:project_id>" agar literal "pick-folder" tidak tertangkap
    # sebagai project_id oleh delete_project.
    path(
        "projects/pick-folder",
        views.project_pick_folder,
        name="project_pick_folder",
    ),
    # GitHub Backup routes HARUS mendahului "projects/<str:project_id>" agar
    # sub-path literal tidak tertukar (project_id tidak memuat '/', namun
    # urutan eksplisit lebih aman & konsisten).
    path(
        "projects/<str:project_id>/github",
        views.project_github,
        name="project_github",
    ),
    path(
        "projects/<str:project_id>/github/test",
        views.project_github_test,
        name="project_github_test",
    ),
    path(
        "projects/<str:project_id>/github/checkpoints",
        views.project_github_checkpoints,
        name="project_github_checkpoints",
    ),
    path(
        "projects/<str:project_id>/github/restore",
        views.project_github_restore,
        name="project_github_restore",
    ),
    # Local Git routes (#Fase 1.2). Mendahului "projects/<str:project_id>".
    path(
        "projects/<str:project_id>/git/status",
        views.project_git_status,
        name="project_git_status",
    ),
    path(
        "projects/<str:project_id>/git/diff",
        views.project_git_diff,
        name="project_git_diff",
    ),
    path(
        "projects/<str:project_id>/git/commits",
        views.project_git_commits,
        name="project_git_commits",
    ),
    path(
        "projects/<str:project_id>/git/branches",
        views.project_git_branches,
        name="project_git_branches",
    ),
    path(
        "projects/<str:project_id>/git/checkout",
        views.project_git_checkout,
        name="project_git_checkout",
    ),
    path(
        "projects/<str:project_id>/git/branches/create",
        views.project_git_create_branch,
        name="project_git_create_branch",
    ),
    path(
        "projects/<str:project_id>/git/branches/delete",
        views.project_git_delete_branch,
        name="project_git_delete_branch",
    ),
    path(
        "projects/<str:project_id>/git/merge",
        views.project_git_merge,
        name="project_git_merge",
    ),
    path(
        "projects/<str:project_id>/git/stash",
        views.project_git_stash,
        name="project_git_stash",
    ),
    path(
        "projects/<str:project_id>/git/stash/list",
        views.project_git_stash_list,
        name="project_git_stash_list",
    ),
    path(
        "projects/<str:project_id>/git/stash/pop",
        views.project_git_stash_pop,
        name="project_git_stash_pop",
    ),
    path(
        "projects/<str:project_id>/git/stash/apply",
        views.project_git_stash_apply,
        name="project_git_stash_apply",
    ),
    path(
        "projects/<str:project_id>/git/stash/drop",
        views.project_git_stash_drop,
        name="project_git_stash_drop",
    ),
    path(
        "projects/<str:project_id>/git/push",
        views.project_git_push,
        name="project_git_push",
    ),
    path(
        "projects/<str:project_id>/git/pull",
        views.project_git_pull,
        name="project_git_pull",
    ),
    path(
        "projects/<str:project_id>/git/fetch",
        views.project_git_fetch,
        name="project_git_fetch",
    ),
    path(
        "projects/<str:project_id>/git/remotes",
        views.project_git_remotes,
        name="project_git_remotes",
    ),
    path(
        "projects/<str:project_id>/git/clone",
        views.project_git_clone,
        name="project_git_clone",
    ),
    path(
        "projects/<str:project_id>/git/commit",
        views.project_git_commit,
        name="project_git_commit",
    ),
    path(
        "projects/<str:project_id>/git/discard",
        views.project_git_discard,
        name="project_git_discard",
    ),
    path(
        "projects/<str:project_id>/git/stage",
        views.project_git_stage,
        name="project_git_stage",
    ),
    path(
        "projects/<str:project_id>/git/unstage",
        views.project_git_unstage,
        name="project_git_unstage",
    ),
    path(
        "projects/<str:project_id>/git/init",
        views.project_git_init,
        name="project_git_init",
    ),
    path(
        "projects/<str:project_id>/git/deinit",
        views.project_git_deinit,
        name="project_git_deinit",
    ),
    # Project Policy / Permission (PROJECT-LOCAL). Mendahului
    # "projects/<str:project_id>" agar sub-path literal tidak di-shadow.
    path(
        "projects/<str:project_id>/policy",
        views.project_policy,
        name="project_policy",
    ),
    path(
        "projects/<str:project_id>/lint",
        views.project_lint,
        name="project_lint",
    ),
    path("projects/<str:project_id>", views.delete_project, name="delete_project"),
    path("active-project", views.active_project, name="active_project"),
    path("mode", views.mode_view, name="operational_mode"),
    path("open-in-explorer", views.open_in_explorer, name="open_in_explorer"),
    path("reveal-in-explorer", views.reveal_in_explorer, name="reveal_in_explorer"),
    path("delete-entry", views.delete_entry, name="delete_entry"),
    path("files", views.files, name="files"),
    path("files/content", views.file_content, name="file_content"),
    path("files/rename", views.rename_entry, name="rename_entry"),
    path("tasks", views.tasks, name="tasks"),
    # Approval (ASK) — keputusan user untuk action yang ditahan policy.
    # Literal route \"tasks/approvals\" HARUS mendahului \"tasks/<str:task_id>\"
    # agar tidak di-shadow.
    path("tasks/approvals", views.task_approvals, name="task_approvals"),
    path(
        "tasks/approvals/resolve",
        views.task_approval_resolve,
        name="task_approval_resolve",
    ),
    # Task Queue API (TAMPILAN/kontrol UI antrian). Literal route "tasks/queue"
    # dan sub-route-nya HARUS mendahului "tasks/<str:task_id>" agar tidak
    # di-shadow (task_id="queue").
    path("tasks/queue", views.task_queue, name="task_queue"),
    path("tasks/queue/clear", views.task_queue_clear, name="task_queue_clear"),
    path(
        "tasks/queue/<str:task_id>/disable",
        views.task_queue_disable,
        name="task_queue_disable",
    ),
    path(
        "tasks/queue/<str:task_id>/enable",
        views.task_queue_enable,
        name="task_queue_enable",
    ),
    path(
        "tasks/queue/<str:task_id>/move",
        views.task_queue_move,
        name="task_queue_move",
    ),
    path(
        "tasks/queue/<str:task_id>/remove",
        views.task_queue_remove,
        name="task_queue_remove",
    ),
    # Task History (reads .aegis/log/ persistent store).
    # PENTING: route literal "tasks/history" HARUS mendahului
    # "tasks/<str:task_id>" agar tidak di-shadow (task_id="history").
    path("tasks/history", views.task_history, name="task_history"),
    path("tasks/history/clear", views.task_history_clear, name="task_history_clear"),
    path("tasks/history/<str:task_id>", views.task_history_detail, name="task_history_detail"),
    path("tasks/<str:task_id>", views.get_task, name="get_task"),
    path("tasks/<str:task_id>/cancel", views.cancel_task, name="cancel_task"),
    # Activity API (chronological events per task)
    path("tasks/<str:task_id>/activity", views.task_activity, name="task_activity"),
    # Report API (final Agent Report per task)
    path("tasks/<str:task_id>/report", views.task_report, name="task_report"),
    # Consultant API (Aegis reasoning layer, read-only terhadap CODE PROJECT)
    path("consultant/sessions", views.consultant_sessions, name="consultant_sessions"),
    path(
        "consultant/sessions/<str:session_id>",
        views.consultant_session_detail,
        name="consultant_session_detail",
    ),
    path("consultant/consult", views.consultant_consult, name="consultant_consult"),
    # Unified Session API (Unified Threaded Session Architecture)
    path("sessions", views.sessions_view, name="sessions_view"),
    path("sessions/<str:session_id>", views.session_detail_view, name="session_detail_view"),
    path("sessions/<str:session_id>/turns", views.session_turns_view, name="session_turns_view"),
    path("sessions/<str:session_id>/cancel", views.session_cancel_view, name="session_cancel_view"),
    # Extension Management (Task 07) - generic management API (thin facade over ExtensionManager)
    path("extensions", views.extensions_list, name="extensions_list"),
    path("extensions/install", views.extensions_install, name="extensions_install"),
    # Extension UI System (Task 05) - generic viewer/config contract
    path("extensions/ui", views.extensions_ui, name="extensions_ui"),
    path("extensions/config/<str:extension_id>", views.extension_config, name="extension_config"),
    path("extensions/config/<str:extension_id>/<str:key>", views.extension_config_key, name="extension_config_key"),
    path("extensions/result", views.extensions_result, name="extensions_result"),
    path("extensions/<str:extension_id>", views.extensions_detail, name="extensions_detail"),
    path("extensions/<str:extension_id>/enable", views.extensions_enable, name="extensions_enable"),
    path("extensions/<str:extension_id>/disable", views.extensions_disable, name="extensions_disable"),
    path("extensions/<str:extension_id>/update", views.extensions_update, name="extensions_update"),
    path("events", views.events, name="events"),
    # Terminal: user-initiated command execution (streaming SSE)
    path("terminal/run", views.terminal_run, name="terminal_run"),
    # Server lifecycle termination (Zero-Zombie process tree kill)
    path("server/terminate", views.server_terminate, name="server_terminate"),
    # Skills Catalog API (Dynamic Addy Osmani skills discovery)
    path("skills/catalog", views.skills_catalog, name="skills_catalog"),
    # Telegram Remote Companion API
    path("telegram/status", telegram_views.telegram_status, name="telegram_status"),
    path("telegram/pairing-qr", telegram_views.telegram_pairing_qr, name="telegram_pairing_qr"),
    path("telegram/unlink", telegram_views.telegram_unlink, name="telegram_unlink"),
    path("telegram/start-poller", telegram_views.telegram_start_poller, name="telegram_start_poller"),
    path("telegram/stop-poller", telegram_views.telegram_stop_poller, name="telegram_stop_poller"),
]
