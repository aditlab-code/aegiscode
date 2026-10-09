# Spec: Telegram LLM Configuration (Provider & Model Selection)

## Objective
Menyediakan antarmuka konfigurasi LLM (Large Language Model) yang komprehensif, intuitif, dan tangguh pada Telegram Remote Companion AegisCode. Fitur ini memungkinkan pengguna memeriksa provider & model aktif, melihat daftar provider yang terdaftar, memilih/mengganti provider aktif, melihat daftar model yang didukung, memilih/mengganti model aktif, serta menguji latensi/konektivitas LLM (ping).

Sistem harus mendukung **dual-mode**:
1. **1-Alur Linier Berbasis Teks (Text-First / Zero-Callback)**: Pengguna dapat mengeksekusi konfigurasi penuh melalui sub-perintah teks langsung tanpa perlu menekan tombol inline keyboard (`/config_llm provider <id>`, `/config_llm model <id>`, dll).
2. **Interaktif Inline Keyboard (Button-Friendly)**: Pengguna yang lebih menyukai antarmuka visual tetap dapat menekan inline buttons (`[🔌 List Provider]`, `[🧠 Pilih Model]`, `[⚡ Test Ping LLM]`) dengan callback query yang aman dan idempotent.

## Tech Stack
- **Bahasa**: Python 3.12 (AegisCode Backend)
- **Komponen**:
  - `agent_ai.runtime.telegram.handler.TelegramUpdateHandler` (Command routing & callback dispatch)
  - `agent_ai.runtime.telegram.views` (Message & inline keyboard rendering)
  - `agent_ai.runtime.telegram.bot_client.TelegramBotClient` (Telegram API communication & setMyCommands)
  - `apps.django_app.api.services.GatewayService` & `agent_ai.llm_config.service.LLMConfigService` (Backend LLM state management)
- **Framework Pengujian**: `pytest`

## Commands
- Run Companion Tests: `./venv/bin/pytest tests/test_telegram_companion`
- Run Full Backend Test Suite: `./venv/bin/pytest tests/`
- Start Django Dev Server: `./venv/bin/python manage.py runserver 127.0.0.1:8478`

## Perintah Telegram yang Didukung

| Perintah Teks | Alias | Deskripsi |
| :--- | :--- | :--- |
| `/config_llm` | `/config`, `/llm` | Menampilkan ringkasan konfigurasi LLM aktif (provider, model, status) beserta panduan subperintah dan tombol interaktif. |
| `/config_llm providers` | `/config_llm provider` | Menampilkan daftar seluruh instance LLM provider dengan tanda ⭐ pada yang aktif dan petunjuk perintah pemilihan. |
| `/config_llm provider <id>` | - | Mengalihkan provider aktif ke instance `<id>`. Memperbarui state backend secara real-time. |
| `/config_llm models` | `/config_llm model` | Menampilkan daftar model yang tersedia untuk provider aktif saat ini dengan tanda ⭐ pada model terpilih. |
| `/config_llm model <nama>` | - | Mengalihkan model aktif ke `<nama>`. Memperbarui state backend secara real-time. |
| `/config_llm ping` | `/config_llm test` | Menjalankan uji ping konektivitas ke provider aktif dan melaporkan status serta latensi (ms). |
| `/help` | - | Menampilkan panduan perintah resmi yang memuat `/config_llm`. |

## Project Structure
- `src/agent_ai/runtime/telegram/`
  - `handler.py` — Logika pemrosesan perintah `/config_llm`, sub-perintah teks, dan callback query.
  - `views.py` — Generator format pesan HTML dan struktur markup inline keyboard.
  - `bot_client.py` — Pendaftaran command menu di Telegram Bot API via `setMyCommands`.
- `tests/test_telegram_companion/`
  - `test_telegram_gate.py` — Pengujian command dispatcher, routing legacy vs aktif, dan callback query.
  - `test_duplicate_prevention.py` — Pengujian stabilitas poller, deduplikasi, dan isolasi gate.

## Code Style & Conventions
- Type annotations lengkap pada seluruh fungsi (`Optional[str]`, `List[Dict[str, Any]]`, `Tuple[str, Dict[str, Any]]`).
- Formatting pesan menggunakan Telegram HTML tags resmi: `<b>`, `<code>`, `<i>`.
- Selalu sediakan fallback yang anggun jika service backend (`get_providers`, `set_provider`, dll) bernilai `None`.
- Penanganan error eksplisit: Jangan pernah menelan kegagalan secara diam-diam (*Zero Silent Mechanism*).

## Testing Strategy
- Unit Tests:
  1. `test_config_llm_overview_text_and_markup`: Memastikan `/config_llm` tanpa argumen merender ringkasan status provider dan model aktif.
  2. `test_config_llm_list_providers_and_switch`: Memastikan `/config_llm providers` menampilkan list dan `/config_llm provider <id>` memanggil `set_provider(id)`.
  3. `test_config_llm_list_models_and_switch`: Memastikan `/config_llm models` menampilkan list model dan `/config_llm model <id>` memanggil `set_active_model(id)`.
  4. `test_config_llm_ping`: Memastikan `/config_llm ping` memanggil `test_provider()` dan mengembalikan latensi.
  5. `test_config_llm_aliases`: Memastikan `/config` dan `/llm` dieksekusi identik dengan `/config_llm`.
  6. `test_help_view_includes_config_llm`: Memastikan output `/help` mencakup panduan `/config_llm`.

## Boundaries
- **Always do:**
  - Jaga agar UI status bar IDE frontend tetap bersih tanpa modifikasi panel/provider.
  - Pertahankan idempotensi dan deduplikasi update pada Telegram handler.
  - Verifikasi seluruh test suite Telegram (100% green).
- **Ask first:**
  - Menghapus atau mengubah schema data provider di backend storage.
- **Never do:**
  - Mengembalikan mekanisme silent swallow saat terjadi galat penggantian model/provider.
  - Menghilangkan dukungan tombol inline keyboard yang sudah berfungsi dengan baik.

## Success Criteria
- [x] Spesifikasi terdokumentasi rapi di `docs/specs/`.
- [ ] `/help` di Telegram menampilkan `/config_llm` secara jelas.
- [ ] Perintah `/config_llm` dan alias `/config`, `/llm` berfungsi baik dengan atau tanpa argumen.
- [ ] Pengguna dapat mengganti provider dan model via teks langsung atau via tombol inline keyboard.
- [ ] Semua pengujian pada `tests/test_telegram_companion` lulus 100%.
