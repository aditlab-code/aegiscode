"""Views HTTP untuk Aegis Gateway (#50).

Django views biasa (TANPA DRF). Views HANYA:
    - mem-parse & memvalidasi request HTTP,
    - memanggil GatewayService (facade tipis),
    - mengembalikan response JSON.

TIDAK ada logic Agent/Runtime/Planning/Tool di sini.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict

from django.conf import settings
from django.http import HttpRequest, JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from api.auth import require_auth
from api.services import GatewayError, GatewayService, get_service
from api.streaming import EventSubscription, sse_stream


def _json_response(data: Any, status: int = 200) -> JsonResponse:
    """Response JSON standar (tanpa indentasi)."""
    return JsonResponse(data, status=status, json_dumps_params={"ensure_ascii": False})


def _error_response(exc: GatewayError) -> JsonResponse:
    """Response error terstruktur dari GatewayError."""
    return _json_response(exc.to_dict(), status=exc.status_code)


def _parse_json_body(request: HttpRequest) -> Dict[str, Any]:
    """Parse body JSON dengan batas ukuran (bounded).

    Raises:
        GatewayError: bila body tidak valid / terlalu besar.
    """
    from api.services import ValidationError

    max_bytes = getattr(settings, "AEGIS_GATEWAY_MAX_BODY_BYTES", 1_000_000)
    if len(request.body) > max_bytes:
        raise ValidationError(f"Body request melebihi batas {max_bytes} bytes.")

    if not request.body:
        return {}
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValidationError(f"Body bukan JSON valid: {exc}") from exc
    if not isinstance(data, dict):
        raise ValidationError("Body JSON harus berupa object.")
    return data


def _handle(handler: Callable[..., JsonResponse]) -> Callable:
    """Decorator: tangani GatewayError -> response error terstruktur.

    Meneruskan URL kwargs (mis. task_id) ke handler.
    """

    def wrapper(request: HttpRequest, **kwargs: Any) -> JsonResponse:
        service = get_service()
        try:
            return handler(request, service, **kwargs)
        except GatewayError as exc:
            return _error_response(exc)
        except (FileNotFoundError, KeyError) as exc:
            return _json_response(
                {"error": {"code": "not_found", "message": str(exc)}},
                status=404,
            )
        except Exception as exc:  # noqa: BLE001 - generic fallback for extension UI
            msg = str(exc)
            exc_type = type(exc).__name__
            # Prioritaskan error 404 (not found / unknown entity / tidak ditemukan)
            if (
                "notfound" in exc_type.lower()
                or "not found" in msg.lower()
                or "tidak ditemukan" in msg.lower()
                or "unknown" in msg.lower()
            ):
                return _json_response(
                    {"error": {"code": "not_found", "message": msg}},
                    status=404,
                )
            # Map validation errors to 400
            if (
                "validation" in exc_type.lower()
                or "validation" in msg.lower()
                or "enum" in msg.lower()
                or isinstance(exc, ValueError)
            ):
                return _json_response(
                    {"error": {"code": "validation_error", "message": msg}},
                    status=400,
                )
            raise

    wrapper.__name__ = handler.__name__
    return wrapper


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@require_http_methods(["GET"])
@_handle
def health(request: HttpRequest, service: GatewayService) -> JsonResponse:
    """GET /api/health -> status gateway."""
    return _json_response(service.health())


@require_http_methods(["GET"])
@require_auth
@_handle
def config(request: HttpRequest, service: GatewayService) -> JsonResponse:
    """GET /api/config -> provider/model/mode dari konfigurasi Aegis.

    Frontend TIDAK meng-hardcode nama model/provider; semua dari Aegis.
    """
    return _json_response(service.get_config())


# ---------------------------------------------------------------------------
# Global Settings (`data/settings.json` — SATU sumber konfigurasi global).
#
# View HANYA meneruskan ke facade Aegis (loader `agent_ai.config.settings`).
# Perubahan MERGE ke file yang sama; key/setting lain tidak hilang.
# ---------------------------------------------------------------------------
@require_http_methods(["GET"])
@_handle
def global_settings(request: HttpRequest, service: GatewayService) -> JsonResponse:
    """GET /api/settings -> nilai AKTUAL konfigurasi global `data/settings.json`."""
    return _json_response(service.get_global_settings())


@csrf_exempt
@require_http_methods(["POST"])
@_handle
def global_settings_update(request: HttpRequest, service: GatewayService) -> JsonResponse:
    """POST /api/settings -> simpan perubahan konfigurasi global (deep-merge)."""
    body = _parse_json_body(request)
    return _json_response(service.update_global_settings(body))


# ---------------------------------------------------------------------------
# LLM Config (halaman Settings; LLMConfigService Aegis existing)
#
# Gateway HANYA memanggil facade konfigurasi LLM Aegis. Nilai secret (.env)
# TIDAK pernah dikembalikan ke klien: hanya versi masked.
# ---------------------------------------------------------------------------
@require_http_methods(["GET"])
@_handle
def llm_config(request: HttpRequest, service: GatewayService) -> JsonResponse:
    """GET /api/llm/config -> credential, provider type, provider + model."""
    return _json_response(service.get_llm_config())


@csrf_exempt
@require_http_methods(["POST", "DELETE"])
@_handle
def llm_credentials(request: HttpRequest, service: GatewayService) -> JsonResponse:
    """POST /api/llm/credentials -> set API key .env (body: {name, value}).
    DELETE /api/llm/credentials -> hapus API key .env (body: {name, force?}).
    """
    body = _parse_json_body(request)
    if request.method == "DELETE":
        return _json_response(
            service.delete_llm_credential(
                body.get("name"), force=bool(body.get("force", False))
            )
        )
    record = service.create_llm_credential(
        name=body.get("name"), value=body.get("value")
    )
    return _json_response(record, status=201)

@csrf_exempt
@require_http_methods(["POST"])
@_handle
def delete_llm_credential(request: HttpRequest, service: GatewayService) -> JsonResponse:
    """POST /api/llm/credentials/delete -> hapus API key .env (name, force?)."""
    body = _parse_json_body(request)
    return _json_response(
        service.delete_llm_credential(
            body.get("name"), force=bool(body.get("force", False))
        )
    )


@csrf_exempt
@require_http_methods(["GET", "POST"])
@_handle
def llm_providers(request: HttpRequest, service: GatewayService) -> JsonResponse:
    """GET /api/llm/providers -> daftar provider instance + nested model.

    POST /api/llm/providers -> buat provider instance baru.

    GET dipakai alur New Task: dropdown Provider Instance + Model diambil dari
    konfigurasi LLM tersimpan (SQLite), bukan dari settings/.env.
    """
    if request.method == "GET":
        return _json_response({"providers": service.list_llm_providers()})

    body = _parse_json_body(request)
    record = service.create_llm_provider(
        name=body.get("name"),
        provider_type=body.get("provider_type"),
        api_key_env=body.get("api_key_env") or "",
        api_url=body.get("api_url") or "",
        enabled=bool(body.get("enabled", True)),
    )
    return _json_response(record, status=201)


@csrf_exempt
@require_http_methods(["PUT", "DELETE"])
@_handle
def llm_provider_detail(
    request: HttpRequest, service: GatewayService, provider_id: str
) -> JsonResponse:
    """PUT/DELETE /api/llm/providers/<provider_id>."""
    if request.method == "DELETE":
        return _json_response(service.delete_llm_provider(provider_id))

    body = _parse_json_body(request)
    record = service.update_llm_provider(
        provider_id,
        name=body.get("name"),
        provider_type=body.get("provider_type"),
        api_key_env=body.get("api_key_env"),
        api_url=body.get("api_url"),
        enabled=body.get("enabled"),
    )
    return _json_response(record)


@csrf_exempt
@require_http_methods(["POST"])
@_handle
def llm_provider_test(request: HttpRequest, service: GatewayService) -> JsonResponse:
    """POST /api/llm/providers/test -> test connection ke provider instance.

    Body: {provider_id: str}
    """
    body = _parse_json_body(request)
    return _json_response(service.test_llm_provider(provider_id=body.get("provider_id")))


@csrf_exempt
@require_http_methods(["POST"])
@_handle
def llm_models(request: HttpRequest, service: GatewayService) -> JsonResponse:
    """POST /api/llm/models -> tambah model pada provider instance."""
    body = _parse_json_body(request)
    record = service.create_llm_model(
        provider_id=body.get("provider_id"),
        model_name=body.get("model_name"),
        enabled=bool(body.get("enabled", True)),
        context_window=body.get("context_window", 128000),
        supports_thinking=bool(body.get("supports_thinking", False)),
        reasoning_budget=body.get("reasoning_budget"),
        timeout=body.get("timeout", 60),
    )
    return _json_response(record, status=201)


@csrf_exempt
@require_http_methods(["PUT", "DELETE"])
@_handle
def llm_model_detail(
    request: HttpRequest, service: GatewayService, model_id: str
) -> JsonResponse:
    """PUT/DELETE /api/llm/models/<model_id>."""
    if request.method == "DELETE":
        return _json_response(service.delete_llm_model(model_id))

    body = _parse_json_body(request)
    update_kwargs: Dict[str, Any] = {
        "model_name": body.get("model_name"),
        "enabled": body.get("enabled"),
        "context_window": body.get("context_window"),
        "supports_thinking": body.get("supports_thinking"),
        "timeout": body.get("timeout"),
    }
    if "reasoning_budget" in body:
        update_kwargs["reasoning_budget"] = body.get("reasoning_budget")

    record = service.update_llm_model(model_id, **update_kwargs)
    return _json_response(record)


@csrf_exempt
@require_http_methods(["GET", "POST"])
@_handle
def projects(request: HttpRequest, service: GatewayService) -> JsonResponse:
    """GET /api/projects -> daftar project launcher (SQLite store).

    POST /api/projects -> buat project baru (name + path), daftarkan ke
    ProjectRegistry Aegis, simpan record, jadikan active project.
    """
    if request.method == "GET":
        return _json_response({"projects": service.list_launcher_projects()})

    body = _parse_json_body(request)
    record = service.create_project(name=body.get("name"), path=body.get("path"))
    return _json_response(record, status=201)


@csrf_exempt
@require_http_methods(["DELETE"])
@_handle
def delete_project(request: HttpRequest, service: GatewayService, project_id: str) -> JsonResponse:
    """DELETE /api/projects/<project_id> -> hapus RECORD project (bukan file)."""
    return _json_response(service.delete_project(project_id))


@csrf_exempt
@require_http_methods(["POST"])
@_handle
def project_pick_folder(request: HttpRequest, service: GatewayService) -> JsonResponse:
    """POST /api/projects/pick-folder -> buka dialog folder native OS.

    Browser tidak dapat memperoleh path absolut dari dialog sistem (HTML
    File API hanya memberi path relatif), sehingga dialog Finder / file
    manager dibuka oleh backend (server lokal, satu user).

    Response:
        200 {"ok": true,  "path": "/abs/path"}   -> user memilih folder
        200 {"ok": false, "reason": "cancelled"} -> user membatalkan dialog
        4xx {"error": {...}}                     -> dialog gagal (terstruktur)
    """
    return _json_response(service.pick_folder())


# ---------------------------------------------------------------------------
# Project Policy / Permission (PROJECT-LOCAL: `<root>/.aegis/permissions.json`).
#
# Satu sumber policy per project. Mode/scope di-enforce oleh PermissionManager
# EXISTING; TIDAK ada sistem permission kedua. Kelola dari Sidebar -> Projects
# (Project Settings / Policy), bukan dari Settings global.
# ---------------------------------------------------------------------------
@csrf_exempt
@require_http_methods(["GET", "POST"])
@_handle
def project_policy(
    request: HttpRequest, service: GatewayService, project_id: str
) -> JsonResponse:
    """GET/POST /api/projects/<project_id>/policy -> Project Policy (per project).

    GET  -> nilai policy AKTUAL project (`<root>/.aegis/permissions.json`).
    POST -> simpan policy (body: {mode, scope}); hanya project ini terpengaruh.
    """
    if request.method == "GET":
        return _json_response(service.get_project_policy(project_id))

    body = _parse_json_body(request)
    return _json_response(service.save_project_policy(project_id, body))


# ---------------------------------------------------------------------------
# GitHub Backup (OPTIONAL per project). Satu sumber konfigurasi dipakai
# bersama oleh halaman Backup (sidebar, project aktif) dan Projects.
# Credential (token) TIDAK pernah dikembalikan ke klien.
# ---------------------------------------------------------------------------
@csrf_exempt
@require_http_methods(["GET", "POST"])
@_handle
def project_github(
    request: HttpRequest, service: GatewayService, project_id: str
) -> JsonResponse:
    """GET/POST /api/projects/<project_id>/github -> konfigurasi GitHub Backup.

    GET  -> status konfigurasi (tanpa token).
    POST -> simpan konfigurasi (body: repository, branch, exclude, token?).
    """
    if request.method == "GET":
        return _json_response(service.github_backup_status(project_id))

    body = _parse_json_body(request)
    return _json_response(service.save_github_backup_config(project_id, body))


@csrf_exempt
@require_http_methods(["POST"])
@_handle
def project_github_test(
    request: HttpRequest, service: GatewayService, project_id: str
) -> JsonResponse:
    """POST /api/projects/<project_id>/github/test -> uji token/repo/branch."""
    body = _parse_json_body(request)
    return _json_response(service.test_github_backup_connection(project_id, body))


@csrf_exempt
@require_http_methods(["GET", "POST"])
@_handle
def project_github_checkpoints(
    request: HttpRequest, service: GatewayService, project_id: str
) -> JsonResponse:
    """GET/POST /api/projects/<project_id>/github/checkpoints.

    GET  -> daftar checkpoint (Git history).
    POST -> buat checkpoint (body: description) -> add/commit/push.
    """
    if request.method == "GET":
        return _json_response(service.list_github_checkpoints(project_id))

    body = _parse_json_body(request)
    record = service.create_github_checkpoint(project_id, body.get("description"))
    return _json_response(record, status=201)


@csrf_exempt
@require_http_methods(["POST"])
@_handle
def project_github_restore(
    request: HttpRequest, service: GatewayService, project_id: str
) -> JsonResponse:
    """POST /api/projects/<project_id>/github/restore -> recovery ke checkpoint.

    Body: { commit: <hash>, force?: bool }.
    """
    body = _parse_json_body(request)
    return _json_response(
        service.restore_github_checkpoint(
            project_id, body.get("commit"), force=bool(body.get("force", False))
        )
    )


@require_http_methods(["GET"])
@_handle
def project_git_status(
    request: HttpRequest, service: GatewayService, project_id: str
) -> JsonResponse:
    """GET /api/projects/<project_id>/git/status -> status Git local."""
    return _json_response(service.git_status(project_id))


@require_http_methods(["GET"])
@_handle
def project_git_diff(
    request: HttpRequest, service: GatewayService, project_id: str
) -> JsonResponse:
    """GET /api/projects/<project_id>/git/diff -> per-file diff atau summary."""
    file_path = request.GET.get("path")
    return _json_response(service.git_diff(project_id, file_path=file_path))


@require_http_methods(["GET"])
@_handle
def project_git_commits(
    request: HttpRequest, service: GatewayService, project_id: str
) -> JsonResponse:
    """GET /api/projects/<project_id>/git/commits -> riwayat commit Git."""
    limit_str = request.GET.get("limit", "10")
    try:
        limit = int(limit_str)
    except ValueError:
        limit = 10
    return _json_response(service.git_commits(project_id, limit=limit))


@require_http_methods(["GET"])
@_handle
def project_git_branches(
    request: HttpRequest, service: GatewayService, project_id: str
) -> JsonResponse:
    """GET /api/projects/<project_id>/git/branches -> detail branches & sync."""
    return _json_response(service.git_branches(project_id))


@csrf_exempt
@require_http_methods(["POST"])
@_handle
def project_git_discard(
    request: HttpRequest, service: GatewayService, project_id: str
) -> JsonResponse:
    """POST /api/projects/<project_id>/git/discard -> revert/discard uncommitted changes."""
    payload = _parse_json_body(request)
    file_path = payload.get("file_path") or request.GET.get("path")
    return _json_response(service.git_discard(project_id, file_path=file_path))


@csrf_exempt
@require_http_methods(["POST"])
@_handle
def open_in_explorer(request: HttpRequest, service: GatewayService) -> JsonResponse:
    """POST /api/open-in-explorer -> buka Windows Explorer pada ACTIVE PROJECT.

    Path TIDAK diterima dari frontend (anti arbitrary path): backend memakai
    active project yang tersimpan. Frontend hanya memicu aksi.
    """
    return _json_response(service.open_active_project_in_explorer())


@csrf_exempt
@require_http_methods(["POST"])
@_handle
def reveal_in_explorer(request: HttpRequest, service: GatewayService) -> JsonResponse:
    """POST /api/reveal-in-explorer -> buka Windows Explorer highlight file.

    Body: { path: absolute filesystem path }.
    Backend memvalidasi path berada di dalam active project root.
    """
    body = _parse_json_body(request)
    file_path = body.get("path")
    if not file_path:
        from api.services import ValidationError
        raise ValidationError("Field 'path' wajib diisi.")
    return _json_response(service.reveal_file_in_explorer(file_path))


@csrf_exempt
@require_http_methods(["POST"])
@_handle
def delete_entry(request: HttpRequest, service: GatewayService) -> JsonResponse:
    """POST /api/delete-entry -> hapus file atau folder dari project.

    Body: { path: relative path from project root, type: "file"|"dir" }.
    Backend memvalidasi path berada di dalam active project root.
    """
    body = _parse_json_body(request)
    rel_path = body.get("path")
    entry_type = body.get("type", "file")
    if not rel_path:
        from api.services import ValidationError
        raise ValidationError("Field 'path' wajib diisi.")
    return _json_response(service.delete_project_entry(rel_path, entry_type))


@csrf_exempt
@require_http_methods(["POST"])
@_handle
def rename_entry(request: HttpRequest, service: GatewayService) -> JsonResponse:
    """POST /api/files/rename -> ubah nama file atau folder di dalam project.

    Body: { old_path, new_path, project_id? }.
    """
    body = _parse_json_body(request)
    old_path = body.get("old_path") or body.get("oldPath")
    new_path = body.get("new_path") or body.get("newPath")
    project_id = body.get("project_id")
    if not old_path or not new_path:
        from api.services import ValidationError
        raise ValidationError("Field 'old_path' dan 'new_path' wajib diisi.")
    return _json_response(service.rename_project_file(str(old_path), str(new_path), project_id=project_id))


@require_http_methods(["GET"])
@require_auth
@_handle
def files(request: HttpRequest, service: GatewayService) -> JsonResponse:
    """GET /api/files?path=... -> daftar file project aktif (read-only).

    Memakai ListFilesTool Aegis (bukan abstraksi filesystem baru).
    """
    path = request.GET.get("path") or "."
    recursive = request.GET.get("recursive", "").lower() in ("1", "true", "yes")
    return _json_response(service.list_project_files(path, recursive=recursive))


@csrf_exempt
@require_http_methods(["GET", "POST"])
@require_auth
@_handle
def file_content(request: HttpRequest, service: GatewayService) -> JsonResponse:
    """Isi file project aktif untuk Code Editor (Workbench).

    GET  /api/files/content?path=...  -> baca isi file (ReadFileTool Aegis).
    POST /api/files/content           -> simpan isi file (WriteFileTool Aegis),
                                         body: {path, content}.

    Backend tetap satu-satunya yang menyentuh filesystem: frontend TIDAK
    menulis file dari browser. Path divalidasi terhadap active project root
    oleh tool Aegis existing (workspace boundary sama dengan Explorer).
    """
    project_id = request.GET.get("project_id") or None
    if request.method == "GET":
        path = request.GET.get("path")
        return _json_response(service.read_project_file(path, project_id=project_id))

    body = _parse_json_body(request)
    path = body.get("path")
    content = body.get("content")
    project_id = body.get("project_id") or project_id
    return _json_response(service.write_project_file(path, content, project_id=project_id))


@csrf_exempt
@require_http_methods(["GET", "POST", "DELETE"])
@_handle
def active_project(request: HttpRequest, service: GatewayService) -> JsonResponse:
    """Active project state (single-user local app; bukan login/session user).

    GET    -> active project saat ini (null bila tidak ada).
    POST   -> set active project (body: {project_id}).
    DELETE -> Close Project (clear active project; project tetap tersimpan).
    """
    if request.method == "GET":
        return _json_response({"active_project": service.get_active_project()})
    if request.method == "DELETE":
        return _json_response(service.clear_active_project())

    body = _parse_json_body(request)
    project_id = body.get("project_id")
    if not project_id:
        from api.services import ValidationError

        raise ValidationError("Field 'project_id' wajib diisi.")
    return _json_response({"active_project": service.set_active_project(project_id)})


@csrf_exempt
@require_http_methods(["GET", "POST"])
@require_auth
@_handle
def tasks(request: HttpRequest, service: GatewayService) -> JsonResponse:
    """GET /api/tasks -> daftar task (history); POST /api/tasks -> buat task.

    GET hanya membaca task yang sudah ada (in-memory, tanpa database).
    POST memvalidasi + menyiapkan task via Aegis (TaskPreparation).
    """
    if request.method == "GET":
        project_id = request.GET.get("project_id") or None
        return _json_response({"tasks": service.list_tasks(project_id=project_id)})

    body = _parse_json_body(request)
    task = body.get("task")
    project_id = body.get("project_id")
    metadata = body.get("metadata")
    execution_mode = body.get("execution_mode")
    # Attachment gambar (multimodal, opsional). Daftar {data, mime_type,
    # filename?}; divalidasi/dinormalisasi service (batas sama Consultant).
    images = body.get("images")
    active_file = body.get("active_file")
    if execution_mode is None and metadata and isinstance(metadata, dict):
        execution_mode = metadata.get("execution_mode")
    if metadata is not None and not isinstance(metadata, dict):
        from api.services import ValidationError

        raise ValidationError("Field 'metadata' harus berupa object bila diisi.")
    record = service.create_task(
        task=task,
        project_id=project_id,
        metadata=metadata,
        execution_mode=execution_mode,
        images=images,
        active_file=active_file,
    )
    return _json_response(record, status=201)


# ---------------------------------------------------------------------------
# Approval (ASK) — keputusan user untuk action yang ditahan policy.
#
# BUKAN sistem permission kedua: keputusan tetap dibuat PermissionManager
# existing. Endpoint ini hanya menyampaikan Allow/Deny user ke action yang
# DITAHAN, terikat ke task/session agar tidak tertukar antar task.
# ---------------------------------------------------------------------------
@require_http_methods(["GET"])
@_handle
def task_approvals(request: HttpRequest, service: GatewayService) -> JsonResponse:
    """GET /api/tasks/approvals -> approval yang masih PENDING (opsional filter).

    Query param: ?task_id=<id> (opsional).
    """
    task_id = request.GET.get("task_id") or None
    return _json_response({"approvals": service.list_approvals(task_id=task_id)})


@csrf_exempt
@require_http_methods(["POST"])
@_handle
def task_approval_resolve(request: HttpRequest, service: GatewayService) -> JsonResponse:
    """POST /api/tasks/approvals/resolve -> Allow/Deny sebuah approval.

    Body: { request_id: str, allow: bool }.
    """
    body = _parse_json_body(request)
    allow = body.get("allow")
    if isinstance(allow, str):
        allow = allow.strip().lower() in ("1", "true", "yes", "allow", "on")
    return _json_response(
        service.resolve_approval(body.get("request_id"), bool(allow))
    )


@require_http_methods(["GET"])
@_handle
def get_task(request: HttpRequest, service: GatewayService, task_id: str) -> JsonResponse:
    """GET /api/tasks/<task_id> -> detail task."""
    return _json_response(service.get_task(task_id))


@csrf_exempt
@require_http_methods(["POST"])
@_handle
def cancel_task(request: HttpRequest, service: GatewayService, task_id: str) -> JsonResponse:
    """POST /api/tasks/<task_id>/cancel -> minta penghentian task.

    Menandai task CANCELLED dan MEMICU cooperative cancellation pada eksekusi
    yang sedang berjalan (Agent loop berhenti di safe boundary, bukan
    thread.kill). Bukan stop engine kedua: memakai token cancellation tunggal
    yang dibagikan ke runtime/orchestrator Aegis yang sudah ada.
    """
    return _json_response(service.cancel_task(task_id))


# ---------------------------------------------------------------------------
# Task Queue API (TAMPILAN/kontrol UI antrian — belum ada scheduler serial)
# ---------------------------------------------------------------------------
@require_http_methods(["GET"])
@_handle
def task_queue(request: HttpRequest, service: GatewayService) -> JsonResponse:
    """GET /api/tasks/queue -> daftar antrian task (pending/running/disabled).

    Satu queue GLOBAL AEGIS: sumber data tetap TaskRecord in-memory yang sama
    dengan GET /api/tasks. Endpoint ini hanya memproyeksikan status antrian.
    """
    project_id = request.GET.get("project_id") or None
    return _json_response({"tasks": service.list_queue(project_id=project_id)})


@csrf_exempt
@require_http_methods(["POST"])
@_handle
def task_queue_disable(request: HttpRequest, service: GatewayService, task_id: str) -> JsonResponse:
    """POST /api/tasks/queue/<task_id>/disable -> tandai task jangan dieksekusi.

    Disable != cancel: task tetap ada di antrian (queue_state="disabled") dan
    tidak dihapus. Hanya berlaku untuk task yang belum running.
    """
    return _json_response(service.set_queue_state(task_id, "disabled"))


@csrf_exempt
@require_http_methods(["POST"])
@_handle
def task_queue_enable(request: HttpRequest, service: GatewayService, task_id: str) -> JsonResponse:
    """POST /api/tasks/queue/<task_id>/enable -> kembalikan task ke pending."""
    return _json_response(service.set_queue_state(task_id, "pending"))


@csrf_exempt
@require_http_methods(["POST"])
@_handle
def task_queue_move(request: HttpRequest, service: GatewayService, task_id: str) -> JsonResponse:
    """POST /api/tasks/queue/<task_id>/move -> geser posisi task di antrian.

    Body JSON: {"direction": "up"|"down"}. Hanya task non-running.
    """
    body = _parse_json_body(request)
    direction = body.get("direction")
    return _json_response({"tasks": service.move_task(task_id, direction)})


@csrf_exempt
@require_http_methods(["POST"])
@_handle
def task_queue_remove(request: HttpRequest, service: GatewayService, task_id: str) -> JsonResponse:
    """POST /api/tasks/queue/<task_id>/remove -> hapus task dari antrian.

    HANYA task non-running (running harus di-Stop/cancel). Ini bukan cancel.
    """
    return _json_response(service.remove_task(task_id))


@csrf_exempt
@require_http_methods(["POST"])
@_handle
def task_queue_clear(request: HttpRequest, service: GatewayService) -> JsonResponse:
    """POST /api/tasks/queue/clear -> bersihkan task non-running dari antrian."""
    body = _parse_json_body(request)
    project_id = request.GET.get("project_id") or body.get("project_id") or None
    return _json_response(service.clear_queue(project_id=project_id))


# ---------------------------------------------------------------------------
# Task History API (reads .aegis/log/ persistent store)
# ---------------------------------------------------------------------------
@require_http_methods(["GET"])
@_handle
def task_history(request: HttpRequest, service: GatewayService) -> JsonResponse:
    """GET /api/tasks/history -> daftar semua task dari .aegis/log/.

    Query params (opsional):
        project_id: filter berdasarkan project (bila ada).

    Mengembalikan daftar task terurut terbaru ke terlama.
    Setiap task berisi: task_id, first_timestamp, last_timestamp, status, task.
    """
    project_id = request.GET.get("project_id") or None
    return _json_response({"tasks": service.list_task_history(project_id=project_id)})


@csrf_exempt
@require_http_methods(["POST"])
@_handle
def task_history_clear(request: HttpRequest, service: GatewayService) -> JsonResponse:
    """POST /api/tasks/history/clear -> bersihkan seluruh task history untuk sebuah project."""
    body = _parse_json_body(request)
    project_id = request.GET.get("project_id") or body.get("project_id") or None
    return _json_response(service.clear_task_history(project_id=project_id))


@csrf_exempt
@require_http_methods(["GET", "DELETE"])
@_handle
def task_history_detail(request: HttpRequest, service: GatewayService, task_id: str) -> JsonResponse:
    """GET /api/tasks/history/<task_id> -> ringkasan task dari .aegis/log/.
    DELETE /api/tasks/history/<task_id> -> hapus log dan history task.
    """
    project_id = request.GET.get("project_id") or None
    if request.method == "DELETE":
        return _json_response(service.delete_task_history(task_id, project_id=project_id))
    return _json_response(service.get_task_history(task_id, project_id=project_id))

# ---------------------------------------------------------------------------
# Activity API (chronological events per task)
# ---------------------------------------------------------------------------
@require_http_methods(["GET"])
@_handle
def task_activity(request: HttpRequest, service: GatewayService, task_id: str) -> JsonResponse:
    """GET /api/tasks/<task_id>/activity -> chronological activity satu task.

    Query params (opsional):
        event_types: daftar tipe event dipisah koma (opsional).
            Bila tidak diisi, semua event diambil (termasuk tool activity).
        project_id: project terkait (opsional).

    Mengembalikan daftar event terurut chronological berdasarkan timestamp.
    Event yang relevan: task_requested, task_started, agent_commentary,
    tool_called, tool_completed, observation_received, task_completed,
    task_failed, task_cancelled, task_finished, bible_update, dan lainnya.
    """
    project_id = request.GET.get("project_id") or None
    event_types_param = request.GET.get("event_types") or None
    event_types = (
        [e.strip() for e in event_types_param.split(",") if e.strip()]
        if event_types_param
        else None
    )
    return _json_response(
        {"task_id": task_id, "events": service.get_task_activity(task_id, project_id=project_id, event_types=event_types)}
    )


# ---------------------------------------------------------------------------
# Report API (final Agent Report per task)
# ---------------------------------------------------------------------------
@require_http_methods(["GET"])
@_handle
def task_report(request: HttpRequest, service: GatewayService, task_id: str) -> JsonResponse:
    """GET /api/tasks/<task_id>/report -> final Agent Report dari .aegis/log/.

    Source utama: task_completed.data.result.
    Fallback: task_finished.data.result.

    Query params (opsional):
        project_id: project terkait (opsional).
    """
    project_id = request.GET.get("project_id") or None
    return _json_response(service.get_task_report(task_id, project_id=project_id))


# ---------------------------------------------------------------------------
# Extension UI System (Task 05) - generic contract
# ---------------------------------------------------------------------------
@require_http_methods(["GET"])
@_handle
def extensions_ui(request: HttpRequest, service: GatewayService) -> JsonResponse:
    """GET /api/extensions/ui -> list UI contributions (generic).

    Query params (optional):
        extension_id: filter by extension
        type: filter by UI type (modal|form|panel|table|chart|viewer|wizard|result_renderer|action|custom_view)
        enabled_only: 1/0 (default 1)
    """
    from agent_ai.extensions.ui import UICatalog

    manager = service._get_extension_manager()
    cap_reg = manager.capabilities
    ext_reg = manager.registry

    extension_id = request.GET.get("extension_id") or None
    ui_type = request.GET.get("type") or None
    enabled_raw = request.GET.get("enabled_only", "1")
    enabled_only = str(enabled_raw).lower() not in ("0", "false", "no")
    catalog = UICatalog(cap_reg, ext_reg)
    items = catalog.list_contributions(extension_id=extension_id, ui_type=ui_type, enabled_only=enabled_only)
    return _json_response({"count": len(items), "contributions": [c.to_dict() for c in items]})


@require_http_methods(["GET"])
@_handle
def extension_config(request: HttpRequest, service: GatewayService, extension_id: str) -> JsonResponse:
    """GET /api/extensions/config/<extension_id> -> form schema for extension config.

    Returns declarative form schema derived from capability metadata (secret-safe).
    """
    from agent_ai.extensions.ui import build_form_schema_for_extension
    from agent_ai.extensions.config import get_config_store

    manager = service._get_extension_manager()
    cap_reg = manager.capabilities
    ext_reg = manager.registry
    # Verify extension exists
    if not cap_reg.list_by_extension(extension_id) and (ext_reg is None or not ext_reg.exists(extension_id)):
        # Not a hard fail: if no config, return empty form schema
        pass
    try:
        store = get_config_store()
    except Exception:
        store = None
    project_id = request.GET.get("project_id") or None
    schema = build_form_schema_for_extension(extension_id, cap_reg, config_store=store, project_id=project_id)
    # Also include raw definitions for debugging (without secret values)
    return _json_response({"extension_id": extension_id, "schema": schema})


@csrf_exempt
@require_http_methods(["GET", "POST", "PUT"])
@_handle
def extension_config_key(request: HttpRequest, service: GatewayService, extension_id: str, key: str) -> JsonResponse:
    """GET/POST/PUT /api/extensions/config/<extension_id>/<key> -> get/set config value.

    GET  -> returns value (for non-secret) or configured flag (for secret)
    POST/PUT -> sets value (validated via existing ConfigFacade/config store)
    """
    import json as _json

    from agent_ai.extensions.context import ExtensionContext
    from agent_ai.extensions.manifest import Manifest
    from agent_ai.extensions.config import get_config_store, ConfigValidationError
    from agent_ai.extensions.capabilities import CapabilityValidationError as _CVE

    manager = service._get_extension_manager()
    cap_reg = manager.capabilities
    ext_reg = manager.registry
    store = get_config_store()
    manifest = Manifest(id=extension_id, name=extension_id, version="1", description="", api_version="1", raw={}, source_path="")
    ctx = ExtensionContext(manifest=manifest, capability_registry=cap_reg, config_store=store)

    if request.method == "GET":
        try:
            # Determine if secret
            rec = cap_reg.get("config", f"{extension_id}.{key}")
            is_secret = False
            if rec is not None:
                is_secret = bool(rec.metadata.get("secret") or rec.metadata.get("type") == "secret")
            if is_secret:
                # Never return value, just configured flag
                has = ctx.config.has(key)
                return _json_response({"key": key, "extension_id": extension_id, "configured": bool(has), "secret": True})
            else:
                val = ctx.config.get(key)
                return _json_response({"key": key, "extension_id": extension_id, "value": val})
        except Exception as exc:
            # Map to validation/not found
            raise
    else:
        # POST/PUT set value
        body = _parse_json_body(request)
        value = body.get("value")
        scope = body.get("scope") or None
        project_id = body.get("project_id") or request.GET.get("project_id") or None
        try:
            ctx.config.set(key, value, scope=scope, project_id=project_id)
        except (ConfigValidationError, _CVE) as exc:
            from api.services import ValidationError
            raise ValidationError(str(exc)) from exc
        return _json_response({"key": key, "extension_id": extension_id, "value": value if not ctx.config.is_secret(key) else "[redacted]", "saved": True})


# ---------------------------------------------------------------------------
# Extension Management (Task 07) — generic management API (thin over ExtensionManager)
# ---------------------------------------------------------------------------
@require_http_methods(["GET"])
@_handle
def extensions_list(request: HttpRequest, service: GatewayService) -> JsonResponse:
    """GET /api/extensions -> list installed extensions (generic, UI-friendly)."""
    data = service.list_extensions()
    return _json_response(data)


@require_http_methods(["GET", "DELETE"])
@_handle
def extensions_detail(request: HttpRequest, service: GatewayService, extension_id: str) -> JsonResponse:
    """GET /api/extensions/<id> -> detail; DELETE -> uninstall."""
    if request.method == "DELETE":
        result = service.uninstall_extension(extension_id)
        return _json_response(result)
    data = service.get_extension(extension_id)
    return _json_response(data)


@csrf_exempt
@require_http_methods(["POST"])
@_handle
def extensions_install(request: HttpRequest, service: GatewayService) -> JsonResponse:
    """POST /api/extensions/install -> install from Git URL (generic). Body: {repository_url, ref?}"""
    body = _parse_json_body(request)
    # Accept both repository_url and repository for flexibility
    repo = body.get("repository_url") or body.get("repository") or body.get("url") or ""
    ref = body.get("ref") or body.get("branch") or None
    # Light frontend-style validation: empty check; backend is authoritative for git/manifest/etc.
    if not repo or not str(repo).strip():
        from api.services import ValidationError

        raise ValidationError("Field 'repository_url' wajib diisi.")
    result = service.install_extension(str(repo).strip(), ref=str(ref).strip() if ref and str(ref).strip() else None)
    return _json_response(result, status=201)


@csrf_exempt
@require_http_methods(["POST"])
@_handle
def extensions_enable(request: HttpRequest, service: GatewayService, extension_id: str) -> JsonResponse:
    """POST /api/extensions/<id>/enable -> enable extension."""
    result = service.enable_extension(extension_id)
    return _json_response(result)


@csrf_exempt
@require_http_methods(["POST"])
@_handle
def extensions_disable(request: HttpRequest, service: GatewayService, extension_id: str) -> JsonResponse:
    """POST /api/extensions/<id>/disable -> disable extension."""
    result = service.disable_extension(extension_id)
    return _json_response(result)


@csrf_exempt
@require_http_methods(["POST"])
@_handle
def extensions_update(request: HttpRequest, service: GatewayService, extension_id: str) -> JsonResponse:
    """POST /api/extensions/<id>/update -> update extension (generic). Body: {repository_url?, ref?}"""
    body = _parse_json_body(request)
    # Optional: repository_url may be omitted to use stored source; Task 07 prioritizes existing source
    repo = body.get("repository_url") or body.get("repository") or body.get("url") or None
    ref = body.get("ref") or body.get("branch") or None
    result = service.update_extension(extension_id, repository_url=str(repo).strip() if repo and str(repo).strip() else None, ref=str(ref).strip() if ref and str(ref).strip() else None)
    return _json_response(result)


@csrf_exempt
@require_http_methods(["POST"])
@_handle
def extensions_result(request: HttpRequest, service: GatewayService) -> JsonResponse:
    """POST /api/extensions/result -> validate/resolve a structured result payload.

    Body: {renderer?, type?, data?, artifact?, metadata?}
    Returns: {renderer, type, data, artifact, metadata} with resolved renderer.
    Generic, no hardcode extension.
    """
    from agent_ai.extensions.ui import resolve_renderer_for_result

    body = _parse_json_body(request)
    renderer = body.get("renderer") or body.get("type") or resolve_renderer_for_result(body)
    result: Dict[str, Any] = {
        "renderer": renderer,
        "type": body.get("type") or renderer,
        "data": body.get("data"),
        "metadata": body.get("metadata") or {},
    }
    if body.get("artifact") is not None:
        result["artifact"] = body["artifact"]
    return _json_response({"result": result, "resolved_renderer": renderer})


# ---------------------------------------------------------------------------
# Consultant API (Aegis reasoning layer — read-only terhadap CODE PROJECT)
# ---------------------------------------------------------------------------
@csrf_exempt
@require_http_methods(["POST"])
@_handle
def consultant_consult(request: HttpRequest, service: GatewayService) -> JsonResponse:
    """POST /api/consultant/consult -> satu giliran konsultasi Consultant.

    Body JSON:
        message (wajib)         : pertanyaan/permintaan user.
        mode (opsional)         : "quick" | "investigate" (default "quick").
        session_id (opsional)   : id sesi untuk konteks lintas giliran.
        provider_instance_id    : pilihan provider dari konfigurasi LLM (SQLite).
        model_id (opsional)     : pilihan model.
        project_id (opsional)   : project terkait (default active project).
        images (opsional)       : daftar gambar multimodal. Setiap item:
            {"data": "<base64>", "mime_type": "image/png", "filename": opsional}.
            Diteruskan ke Consultant untuk diproses modul vision existing.

    Consultant memakai loop & tool Aegis yang sudah ada (read-only terhadap
    CODE PROJECT, read+update terhadap Project Bible). Response memuat reply,
    tool_events, dan task_proposal (bila Consultant menghasilkan Task Proposal).
    """
    body = _parse_json_body(request)
    return _json_response(
        service.consult(
            message=body.get("message"),
            session_id=body.get("session_id") or None,
            provider_instance_id=body.get("provider_instance_id") or None,
            model_id=body.get("model_id") or None,
            project_id=body.get("project_id") or None,
            mode=body.get("mode") or None,
            images=body.get("images") or None,
            active_file=body.get("active_file") or None,
        )
    )


# ---------------------------------------------------------------------------
# Consultant Session API (list / get / create / rename / delete / reset)
# ---------------------------------------------------------------------------
@csrf_exempt
@require_http_methods(["GET", "POST"])
@_handle
def consultant_sessions(
    request: HttpRequest, service: GatewayService
) -> JsonResponse:
    """GET /api/consultant/sessions -> list consultant sessions (newest first).

    Query params:
        project_id (opsional): filter sessions by project.

    POST /api/consultant/sessions -> create a new consultant session.

    Body JSON (opsional):
        project_id: project terkait (default active project).
        title: judul sesi (default auto dari pesan user pertama).
    """
    if request.method == "GET":
        project_id = request.GET.get("project_id") or None
        sessions = service.list_consultant_sessions(project_id=project_id)
        # Light metadata for the list (UI hanya butuh judul/waktu/turn count).
        items = []
        for s in sessions:
            turns = s.get("turns") or []
            items.append(
                {
                    "session_id": s.get("session_id"),
                    "project_id": s.get("project_id"),
                    "title": s.get("title"),
                    "created_at": s.get("created_at"),
                    "updated_at": s.get("updated_at"),
                    "turn_count": len(turns),
                }
            )
        return _json_response({"sessions": items})

    body = _parse_json_body(request)
    project_id = body.get("project_id") or None
    title = body.get("title") or None
    if not project_id:
        try:
            project_id = service.project_store.get_active_project_id() or None
        except Exception:  # noqa: BLE001
            project_id = None
    session = service.create_consultant_session(project_id=project_id, title=title)
    return _json_response(session, status=201)


@csrf_exempt
@require_http_methods(["GET", "PATCH", "DELETE"])
@_handle
def consultant_session_detail(
    request: HttpRequest, service: GatewayService, session_id: str
) -> JsonResponse:
    """GET /api/consultant/sessions/<id> -> get full session (incl. turns).

    PATCH /api/consultant/sessions/<id> -> rename (body: {\"title\": \"...\"}).

    DELETE /api/consultant/sessions/<id> -> delete session.
    """
    # project_id filter (opsional, agar scope per-project konsisten)
    project_id = request.GET.get("project_id") or None
    if not project_id:
        try:
            project_id = service.project_store.get_active_project_id() or None
        except Exception:  # noqa: BLE001
            project_id = None

    if request.method == "GET":
        session = service.get_consultant_session(session_id, project_id=project_id)
        if session is None:
            from api.services import NotFoundError

            raise NotFoundError("Session not found")
        return _json_response(session)

    if request.method == "PATCH":
        body = _parse_json_body(request)
        title = body.get("title")
        if not title or not str(title).strip():
            from api.services import ValidationError

            raise ValidationError("Field 'title' wajib diisi.")
        updated = service.rename_consultant_session(
            session_id, str(title).strip(), project_id=project_id
        )
        if updated is None:
            from api.services import NotFoundError

            raise NotFoundError("Session not found")
        return _json_response(updated)

    # DELETE
    if project_id:
        deleted = service.delete_consultant_session(session_id, project_id=project_id)
    else:
        deleted = service.delete_consultant_session(session_id)
    if not deleted:
        from api.services import NotFoundError

        raise NotFoundError("Session not found")
    return _json_response({"deleted": True, "session_id": session_id})


@require_http_methods(["GET"])
def events(request: HttpRequest) -> StreamingHttpResponse:
    """GET /api/events -> SSE stream event Aegis (server -> client).

    Query params (opsional):
        session_id: filter event berdasarkan session.
        task_id: filter event berdasarkan task.

    Django HANYA transport: event berasal dari SessionStore Aegis. Tidak ada
    event model kedua / broker / database.
    """
    service = get_service()
    session_id = request.GET.get("session_id") or None
    task_id = request.GET.get("task_id") or None
    last_event_id = (
        request.headers.get("Last-Event-ID")
        or request.META.get("HTTP_LAST_EVENT_ID")
        or request.GET.get("last_event_id")
        or None
    )

    subscription = EventSubscription(
        service.sessions,
        session_id=session_id,
        task_id=task_id,
        last_event_id=last_event_id,
    )
    subscription.start()

    def is_disconnected() -> bool:
        # Django menyediakan request.is_disconnected() pada versi modern.
        checker = getattr(request, "is_disconnected", None)
        return bool(checker()) if callable(checker) else False

    stream = sse_stream(subscription, is_disconnected=is_disconnected)

    async def sse_event_stream():
        try:
            # Kirim comment frame inisial agar Daphne/reverse proxy langsung flush status HTTP 200 dan headers ke client
            yield ": connected\n\n"
            async for chunk in stream:
                yield chunk
        finally:
            if hasattr(stream, "close"):
                import inspect
                if inspect.iscoroutinefunction(stream.close):
                    await stream.close()
                else:
                    stream.close()
            if hasattr(subscription, "close"):
                subscription.close()
    response = StreamingHttpResponse(
        sse_event_stream(),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


# ---------------------------------------------------------------------------
# Terminal: POST /api/terminal/run — stream command output as SSE
# ---------------------------------------------------------------------------
@csrf_exempt
@require_http_methods(["POST"])
@require_auth
def terminal_run(request: HttpRequest) -> StreamingHttpResponse:
    """POST /api/terminal/run → stream command output line-by-line as SSE.

    Body JSON:
        command     (str, required)   : shell command to execute.
        project_id  (str, optional)   : project whose root is the working dir.

    SSE events emitted:
        terminal_output  {text, stream}    : one line of stdout or stderr.
        terminal_done    {exit_code, success} : final result after process ends.
        terminal_error   {error}           : spawn / permission failure.
    """
    import subprocess
    from pathlib import Path

    from agent_ai.tools.terminal import _command_needs_shell, _split_command
    from api.services import GatewayError, ValidationError, get_service

    service = get_service()

    try:
        data = _parse_json_body(request)
    except GatewayError as exc:
        return _error_response(exc)

    command = str(data.get("command") or "").strip()
    project_id = str(data.get("project_id") or "").strip()

    if not command:
        return _json_response(
            {"error": {"code": "validation_error", "message": "Field 'command' wajib diisi."}},
            status=400,
        )

    # Resolve working directory from project root (fallback: server cwd).
    cwd: Path = Path.cwd()
    if project_id:
        try:
            cwd = service._project_root_by_id(project_id)
        except GatewayError as exc:
            return _error_response(exc)

    use_shell = _command_needs_shell(command)

    def _sse(event_type: str, payload: dict) -> str:
        return f"event: {event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def stream_output():
        proc = None
        try:
            if use_shell:
                target = command
            else:
                try:
                    from agent_ai.tools.terminal import ToolValidationError
                    target = _split_command(command)
                except Exception:
                    target = command.split()

            proc = subprocess.Popen(
                target,
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                shell=use_shell,
            )
            for raw_line in iter(proc.stdout.readline, ""):
                yield _sse("terminal_output", {"text": raw_line.rstrip("\n"), "stream": "stdout"})
            proc.wait()
            yield _sse("terminal_done", {"exit_code": proc.returncode, "success": proc.returncode == 0})
        except GeneratorExit:
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
        except FileNotFoundError:
            prog = command.split()[0] if command else command
            yield _sse("terminal_error", {"error": f"Command tidak ditemukan: {prog}"})
        except Exception as exc:  # noqa: BLE001
            yield _sse("terminal_error", {"error": str(exc)})
        finally:
            if proc and proc.poll() is None:
                proc.kill()
    response = StreamingHttpResponse(stream_output(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


# ---------------------------------------------------------------------------
# Google OAuth & Identity Views (docs/Oauth-Google.md, Phase 0)
# ---------------------------------------------------------------------------
@require_http_methods(["GET"])
def google_auth_url(request: HttpRequest) -> JsonResponse:
    """Generate Google OAuth consent URL with signed anti-CSRF state token."""
    from urllib.parse import urlencode
    from api.auth import generate_signed_state

    client_id = getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "")
    if not client_id:
        return _json_response(
            {
                "error": {
                    "code": "GOOGLE_OAUTH_NOT_CONFIGURED",
                    "message": "GOOGLE_OAUTH_CLIENT_ID is not configured in .env. Please set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET or use Quick Dev Login.",
                },
                "configured": False,
            },
            status=400,
        )

    redirect_uri = request.GET.get("redirect_uri") or getattr(
        settings, "GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8478/auth/callback"
    )

    state = generate_signed_state(redirect_uri=redirect_uri)
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "state": state,
        "prompt": "select_account",
    }
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return _json_response({"auth_url": auth_url, "state": state, "client_id": client_id, "configured": True})


@csrf_exempt
@require_http_methods(["POST"])
def auth_dev_login(request: HttpRequest) -> JsonResponse:
    """Dev-only login bypass for local manual testing when Google credentials are not yet configured."""
    if not getattr(settings, "DEBUG", False):
        return _json_response(
            {"error": {"code": "dev_login_disabled", "message": "dev-login hanya diizinkan saat DEBUG=True"}},
            status=403,
        )
    from api.auth import create_aegis_session_token

    try:
        body = _parse_json_body(request)
    except Exception:
        body = {}

    email = body.get("email") or "developer@aegis.local"
    name = body.get("name") or "Local Developer"

    user_info = {
        "sub": "dev-user-001",
        "email": email,
        "name": name,
        "picture": "",
    }
    token = create_aegis_session_token(user_info)
    return _json_response({"token": token, "user": user_info})



@csrf_exempt
@require_http_methods(["POST"])
def google_auth_callback(request: HttpRequest) -> JsonResponse:
    """Handle authorization code exchange and issue AegisCode session token."""
    from api.auth import (
        create_aegis_session_token,
        exchange_google_code,
        verify_google_id_token,
        verify_signed_state,
    )

    try:
        body = _parse_json_body(request)
    except Exception as exc:
        return _json_response({"error": {"code": "INVALID_BODY", "message": str(exc)}}, status=400)

    code = body.get("code")
    state = body.get("state")
    redirect_uri = body.get("redirect_uri") or getattr(
        settings, "GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8478/auth/callback"
    )

    if not code or not state:
        return _json_response(
            {"error": {"code": "MISSING_PARAM", "message": "'code' and 'state' are required"}},
            status=400,
        )

    # Validate state signature and expiration
    verified_state = verify_signed_state(state)
    if not verified_state:
        return _json_response(
            {"error": {"code": "INVALID_STATE", "message": "OAuth state is invalid or expired (>5 mins)"}},
            status=400,
        )

    # Server-to-server code exchange with Google Token API
    try:
        token_data = exchange_google_code(code, redirect_uri)
    except Exception as exc:
        return _json_response(
            {"error": {"code": "TOKEN_EXCHANGE_FAILED", "message": str(exc)}},
            status=400,
        )

    id_token_str = token_data.get("id_token")
    if not id_token_str:
        return _json_response(
            {"error": {"code": "NO_ID_TOKEN", "message": "Google did not return an id_token"}},
            status=400,
        )

    # Verify ID token cryptographic signature
    try:
        user_info = verify_google_id_token(id_token_str)
    except Exception as exc:
        return _json_response(
            {"error": {"code": "INVALID_ID_TOKEN", "message": f"Google id_token verification failed: {exc}"}},
            status=400,
        )

    # Issue AegisCode session JWT
    session_token = create_aegis_session_token(user_info)
    user_profile = {
        "sub": user_info.get("sub"),
        "email": user_info.get("email"),
        "name": user_info.get("name"),
        "picture": user_info.get("picture", ""),
    }

    return _json_response({"token": session_token, "user": user_profile})


@require_http_methods(["GET"])
def auth_me(request: HttpRequest) -> JsonResponse:
    """Return identity of authenticated user based on Bearer token."""
    from api.auth import get_authenticated_user

    user = get_authenticated_user(request)
    if not user:
        return _json_response(
            {"error": {"code": "UNAUTHORIZED", "message": "Not authenticated"}},
            status=401,
        )
    return _json_response({"authenticated": True, "user": user})


@csrf_exempt
@require_http_methods(["POST"])
def auth_logout(request: HttpRequest) -> JsonResponse:
    """Stateless logout endpoint."""
    return _json_response({"success": True})


@csrf_exempt
@require_http_methods(["POST"])
@_handle
def server_terminate(request: HttpRequest, service: GatewayService) -> JsonResponse:
    """POST /api/server/terminate -> inisiasi penghentian aman server AegisCode (zero-zombie)."""
    import os
    from api.lifecycle import get_lifecycle_manager

    body = _parse_json_body(request) if request.body else {}
    force = bool(body.get("force", False))
    delay = float(body.get("delay", 0.3))

    lifecycle = get_lifecycle_manager()
    pid = os.getpid()
    lifecycle.trigger_server_shutdown(delay=delay)

    return _json_response({
        "status": "terminating",
        "message": "Penghentian server AegisCode telah diinisiasi.",
        "pid": pid,
        "force": force,
    })

