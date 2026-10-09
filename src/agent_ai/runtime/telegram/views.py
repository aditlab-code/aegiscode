from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

DEFAULT_SKILLS = [
    {
        "id": "spec-driven-development",
        "name": "Spec-Driven Development",
        "description": "Susun spesifikasi sebelum menulis kode",
        "template": "Bantu saya menyusun spesifikasi teknis dan kriteria penerimaan untuk: <tulis fitur>",
    },
    {
        "id": "planning-and-task-breakdown",
        "name": "Plan & Breakdown",
        "description": "Pecah pekerjaan kompleks menjadi task-task terurut",
        "template": "Bantu saya membuat task breakdown dan rencana bertahap untuk: <tulis tugas>",
    },
    {
        "id": "test-driven-development",
        "name": "Test-Driven Development (TDD)",
        "description": "Siklus red-green-refactor untuk fitur baru",
        "template": "Tuliskan test case terlebih dahulu sebelum implementasi untuk modul: <tulis modul>",
    },
    {
        "id": "code-review-and-quality",
        "name": "Code Review & Quality",
        "description": "Tinjau kualitas kode, performa, dan keamanan",
        "template": "Tinjau kode pada file berikut untuk potensi bug dan keamanan: <path/file>",
    },
    {
        "id": "interview-me",
        "name": "Interview Me",
        "description": "Gali kebutuhan mendalam dengan tanya jawab",
        "template": "Saya ingin membangun fitur: <ide>. Tolong wawancarai saya untuk merumuskan kebutuhan.",
    },
    {
        "id": "code-simplification",
        "name": "Code Simplifier",
        "description": "Sederhanakan kode tanpa mengubah fungsionalitas",
        "template": "Sederhanakan dan refaktor kode berikut agar lebih jelas dan bersih: <path/file>",
    },
    {
        "id": "incremental-implementation",
        "name": "Incremental Build",
        "description": "Implementasi dalam irisan tipis yang terverifikasi",
        "template": "Implementasikan irisan berikutnya secara bertahap dan terverifikasi untuk: <tugas>",
    },
    {
        "id": "shipping-and-launch",
        "name": "Ship & Launch",
        "description": "Checklist kesiapan rilis dan deployment",
        "template": "Jalankan evaluasi kesiapan rilis dan smoke testing untuk: <versi/fitur>",
    },
]


def render_project_selector_view(projects: List[Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
    """Menampilkan menu pemilihan project aktif dari database Aegis IDE."""
    if not projects:
        text = (
            "📁 <b>Project di Aegis IDE:</b>\n\n"
            "⚠️ Belum ada project yang tersimpan di Aegis IDE Workstation.\n"
            "Silakan buat atau buka project terlebih dahulu melalui antarmuka IDE Aegis."
        )
        return text, {"inline_keyboard": []}

    text = (
        "📁 <b>Pilih Project Aktif di Aegis IDE:</b>\n\n"
        "Silakan pilih salah satu project di bawah untuk ditinjau status repositori dan perubahannya:"
    )
    buttons = []
    for p in projects:
        pid = p.get("id") or p.get("project_id", "")
        name = p.get("name") or "Unnamed Project"
        buttons.append([{"text": f"📁 {name}", "callback_data": f"project:select:{pid}"}])

    return text, {"inline_keyboard": buttons}


def render_repo_view(
    info: Dict[str, Any],
    changed_files: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Menampilkan nama proyek, root path, branch git, last commit, status perubahan, serta tombol aksi."""
    if not info.get("has_active_project", True):
        text = (
            "📁 <b>Informasi Repositori Aegis IDE:</b>\n\n"
            "⚠️ <i>Belum ada project yang aktif di Aegis IDE.</i>\n\n"
            "Tekan tombol di bawah untuk memilih project yang ingin ditinjau:"
        )
        keyboard = {
            "inline_keyboard": [
                [{"text": "📁 Pilih Project", "callback_data": "repo:switch_project"}]
            ]
        }
        return text, keyboard

    name = info.get("name", "AegisCode")
    root = info.get("root", "-")

    if not info.get("is_repo", True):
        text = (
            "📁 <b>Informasi Repositori Aktif:</b>\n\n"
            f"• <b>Nama Proyek:</b> <code>{name}</code>\n"
            f"• <b>Root Path:</b> <code>{root}</code>\n"
            "• <b>Status Git:</b> ⚠️ <i>Belum diinisialisasi sebagai repositori Git (.git belum ada).</i>\n\n"
            "Tekan tombol di bawah untuk menginisialisasi Git atau ganti project (atau ketik <code>/repo init</code>):"
        )
        keyboard = {
            "inline_keyboard": [
                [{"text": "⚙️ Inisialisasi Git", "callback_data": "repo:init"}],
                [{"text": "🔄 Ganti Project", "callback_data": "repo:switch_project"}],
            ]
        }
        return text, keyboard

    branch = info.get("branch", "-")
    last_commit = info.get("last_commit", "-")
    uncommitted = info.get("uncommitted_changes", 0)
    is_dirty = info.get("is_dirty", False) or uncommitted > 0 or bool(changed_files)

    files = changed_files if changed_files is not None else info.get("changed_files", [])

    dirty_str = (
        f"⚠️ {uncommitted or len(files)} perubahan belum di-commit"
        if is_dirty
        else "Clean (tidak ada perubahan berkas)"
    )

    lines = [
        "📁 <b>Informasi Repositori Aktif:</b>\n",
        f"• <b>Nama Proyek:</b> <code>{name}</code>",
        f"• <b>Root Path:</b> <code>{root}</code>",
        f"• <b>Branch Git:</b> <code>{branch}</code>",
        f"• <b>Commit Terakhir:</b> <code>{last_commit}</code>",
        f"• <b>Status Perubahan:</b> {dirty_str}",
    ]

    buttons = []
    if files:
        lines.append("\n<b>Daftar Berkas Berubah:</b>")
        for f in files:
            path = f.get("path", "")
            file_lines = f.get("lines", 0)
            status = f.get("status", "M")
            lines.append(f"• <code>{path} {file_lines} line {status}</code>")

        lines.append("\nPilih aksi untuk seluruh perubahan (atau ketik <code>/repo accept</code> / <code>/repo discard</code>):")
        buttons.append([
            {"text": "✅ Accept Perubahan", "callback_data": "repo:accept"},
            {"text": "🗑️ Discard Perubahan", "callback_data": "repo:discard"},
        ])

    buttons.append([
        {"text": "🔄 Ganti Project", "callback_data": "repo:switch_project"}
    ])

    return "\n".join(lines), {"inline_keyboard": buttons}


def render_mode_view(current_mode: str) -> Tuple[str, Dict[str, Any]]:
    """Menampilkan status mode aktif (Ask ⏸️ vs Agents ⚡) dan tombol pemilih."""
    mode_normalized = current_mode.lower().strip()
    is_ask = mode_normalized == "ask"
    mode_label = "Ask ⏸️ (Perlu Konfirmasi)" if is_ask else "Agents ⚡ (Otonom Penuh)"

    text = (
        "⚙️ <b>Kontrol Mode Operasional AegisCode:</b>\n\n"
        f"Mode saat ini: <b>{mode_label}</b>\n\n"
        "• <b>Ask Mode ⏸️:</b> Agen berkonsultasi dan meminta konfirmasi sebelum eksekusi kritis.\n"
        "• <b>Agents Mode ⚡:</b> Agen mengeksekusi tugas secara otonom mandiri dengan audit streaming.\n\n"
        "Pilih mode di bawah atau ketik langsung <code>/aegis_mode ask</code> / <code>/aegis_mode agents</code>:"
    )

    keyboard = {
        "inline_keyboard": [
            [
                {"text": f"{'⭐ ' if is_ask else ''}Ask Mode ⏸️", "callback_data": "mode:set:ask"},
                {"text": f"{'⭐ ' if not is_ask else ''}Agents Mode ⚡", "callback_data": "mode:set:agents"},
            ]
        ]
    }
    return text, keyboard


def render_config_llm_view(
    active_provider: str,
    active_model: str,
    is_ready: bool = True,
) -> Tuple[str, Dict[str, Any]]:
    """Menampilkan ringkasan LLM aktif dengan tombol list provider, pilih model, dan test ping."""
    status_icon = "🟢" if is_ready else "🔴"
    status_text = "Siap Digunakan" if is_ready else "Perlu Konfigurasi"

    text = (
        "🛠️ <b>Konfigurasi LLM AegisCode:</b>\n\n"
        f"• <b>Provider Aktif:</b> <code>{active_provider or 'Belum dipilih'}</code>\n"
        f"• <b>Model Aktif:</b> <code>{active_model or 'Default'}</code>\n"
        f"• <b>Status Gateway:</b> {status_icon} {status_text}\n\n"
        "<b>Perintah Teks 1-Alur:</b>\n"
        "• <code>/config_llm providers</code> - Daftar seluruh provider\n"
        "• <code>/config_llm provider &lt;id&gt;</code> - Pilih/ganti provider\n"
        "• <code>/config_llm models</code> - Daftar model provider aktif\n"
        "• <code>/config_llm model &lt;nama&gt;</code> - Pilih/ganti model aktif\n"
        "• <code>/config_llm ping</code> - Uji latensi koneksi\n\n"
        "Atau gunakan tombol interaktif di bawah:"
    )

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🔌 List Provider", "callback_data": "config:providers"},
                {"text": "🧠 Pilih Model", "callback_data": "config:models"},
            ],
            [
                {"text": "⚡ Test Ping LLM", "callback_data": "config:ping"},
            ],
        ]
    }
    return text, keyboard


def render_provider_list_view(providers: List[Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
    """Daftar provider dengan tanda ⭐ pada yang aktif dan tombol kembali ke config."""
    lines = []
    buttons = []

    if not providers:
        lines.append("<i>Belum ada provider yang terdaftar di sistem.</i>")
    else:
        for p in providers:
            is_active = p.get("is_active", False)
            p_id = str(p.get("id", ""))
            p_name = p.get("name") or p_id
            active_mark = "⭐ (Aktif)" if is_active else ""
            lines.append(
                f"• <b>{p_name}</b> {active_mark}\n"
                f"  <i>ID:</i> <code>{p_id}</code> | <i>Model:</i> <code>{p.get('model', 'default')}</code>"
            )
            btn_text = f"{'⭐ ' if is_active else ''}{p_name}"
            buttons.append([{"text": btn_text, "callback_data": f"provider:set:{p_id}"}])

    buttons.append([{"text": "🔙 Kembali ke Config", "callback_data": "config:main"}])

    text = (
        "🔌 <b>Daftar LLM Provider:</b>\n\n"
        + "\n".join(lines)
        + "\n\nPilih provider di bawah atau ketik <code>/config_llm provider &lt;id&gt;</code>:"
    )
    return text, {"inline_keyboard": buttons}


def render_model_list_view(
    models: List[Dict[str, Any]],
    provider_id: Optional[str] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Daftar model untuk provider aktif dengan tanda ⭐ dan tombol kembali ke config."""
    lines = []
    buttons = []

    header = f"untuk provider <code>{provider_id}</code>" if provider_id else "aktif"

    if not models:
        lines.append(f"<i>Tidak ada model terdaftar untuk provider {header}.</i>")
    else:
        for m in models:
            is_active = m.get("is_active", False)
            m_name = m.get("name") or m.get("id") or "Unknown"
            active_mark = "⭐ (Aktif)" if is_active else ""
            lines.append(f"• <code>{m_name}</code> {active_mark}")
            btn_text = f"{'⭐ ' if is_active else ''}{m_name}"
            buttons.append([{"text": btn_text, "callback_data": f"model:set:{m_name}"}])

    buttons.append([{"text": "🔙 Kembali ke Config", "callback_data": "config:main"}])

    text = (
        f"🧠 <b>Daftar Model {header}:</b>\n\n"
        + "\n".join(lines)
        + f"\n\nPilih model di bawah atau ketik <code>/config_llm model &lt;nama&gt;</code>:"
    )
    return text, {"inline_keyboard": buttons}


def render_ping_result_view(res: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """Hasil tes latensi/konektivitas LLM dengan tombol kembali ke config."""
    status = res.get("status", "ok")
    provider = res.get("provider", "Unknown")
    model = res.get("model", "default")
    latency = float(res.get("latency_ms", 0.0))

    if status == "ok":
        text = (
            "✅ <b>Uji Konektivitas LLM Berhasil!</b>\n\n"
            f"• <b>Provider:</b> <code>{provider}</code>\n"
            f"• <b>Model:</b> <code>{model}</code>\n"
            f"• <b>Status:</b> OK (200)\n"
            f"• <b>Latensi Respons:</b> <b>{latency:.1f} ms</b>"
        )
    else:
        detail = res.get("detail") or res.get("message", "Unknown error")
        text = (
            "❌ <b>Uji Konektivitas LLM Gagal!</b>\n\n"
            f"• <b>Provider:</b> <code>{provider}</code>\n"
            f"• <b>Model:</b> <code>{model}</code>\n"
            f"• <b>Status:</b> ERROR\n"
            f"• <b>Latensi:</b> {latency:.1f} ms\n"
            f"• <b>Detail:</b> <i>{detail}</i>"
        )

    keyboard = {
        "inline_keyboard": [
            [{"text": "🔙 Kembali ke Config", "callback_data": "config:main"}]
        ]
    }
    return text, keyboard


def render_chat_templates_view(
    active_skill: Optional[str] = None,
    skills: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Antarmuka /aegis_chat yang menampilkan template pemandu dengan tombol pilihan."""
    skill_list = skills or DEFAULT_SKILLS
    lines = []
    buttons = []

    for s in skill_list:
        s_id = s.get("id", "")
        s_name = s.get("name") or s_id
        desc = s.get("description", "")
        is_active = (active_skill == s_id) or bool(s.get("is_active"))
        mark = " ⭐ (Aktif)" if is_active else ""
        lines.append(f"• <b>{s_name}</b>{mark}\n  <i>{desc}</i>")

        btn_text = f"{'⭐ ' if is_active else ''}{s_name}"
        buttons.append([{"text": btn_text, "callback_data": f"skill:set:{s_id}"}])

    active_info = f"<b>Skill Aktif:</b> <code>{active_skill}</code>\n\n" if active_skill else ""
    text = (
        "💬 <b>Aegis Chat & Template Skills Pemandu:</b>\n\n"
        f"{active_info}"
        "Kirim instruksi langsung atau pilih template skill di bawah untuk memandu AI:\n\n"
        + "\n\n".join(lines)
    )
    return text, {"inline_keyboard": buttons}


def render_skill_selected_view(
    skill_id: str,
    skill_name: str,
    template_prompt: str,
) -> Tuple[str, Dict[str, Any]]:
    """Notifikasi skill terpilih beserta contoh draft prompt siap pakai."""
    text = (
        f"🎯 <b>Skill Diaktifkan: {skill_name}</b>\n\n"
        f"ID: <code>{skill_id}</code>\n\n"
        "💡 <b>Contoh Draft Prompt Siap Pakai:</b>\n"
        f"<code>{template_prompt}</code>\n\n"
        "<i>Silakan salin teks di atas, sesuaikan isinya, lalu kirimkan langsung di chat ini.</i>"
    )
    keyboard = {
        "inline_keyboard": [
            [{"text": "📋 Kembali ke Daftar Template", "callback_data": "config:skills"}]
        ]
    }
    return text, keyboard


def render_help_view() -> str:
    """Teks panduan resmi perintah teks linier AegisCode Companion (Zero-Callback)."""
    return (
        "🛡️ <b>AegisCode Mobile Companion Bot (1 Alur Linier):</b>\n\n"
        "<b>Perintah Operasional Utama:</b>\n"
        "• <code>/repo</code> - Status repositori, branch aktif, commit, & status perubahan.\n"
        "• <code>/repo accept</code> - Commit seluruh perubahan dengan pesan LLM.\n"
        "• <code>/repo discard</code> - Batalkan seluruh perubahan berkas.\n"
        "• <code>/repo init</code> - Inisialisasi Git pada proyek aktif.\n"
        "• <code>/mode</code> [ask|agents] - Beralih antara mode Ask (konfirmasi) vs Agents (otonom).\n"
        "• <code>/config_llm</code> - Konfigurasi LLM (pilih provider, model, & uji ping latensi).\n"
        "• <code>/allow &lt;req_id&gt;</code> - Setujui permintaan tindakan kritis HITL.\n"
        "• <code>/deny &lt;req_id&gt;</code> - Tolak permintaan tindakan kritis HITL.\n"
        "• <code>/status</code> - Status gateway runtime dan branch git.\n"
        "• <code>/agents</code> - Pantau status armada subagen Olympus Fleet.\n"
        "• <code>/help</code> - Menampilkan panduan ringkas ini.\n\n"
        "<i>Tips: Anda dapat langsung mengetik instruksi coding apa pun tanpa awalan '/' untuk berkonsultasi atau mengeksekusi tugas.</i>"
    )
