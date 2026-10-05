# Arsip Fitur yang Telah Diimplementasikan (Completed Milestones)

Dokumen ini memuat catatan historis dan dokumentasi teknis dari seluruh fase, modul, dan fitur yang telah berhasil diselesaikan dan lolos uji verifikasi pada basis kode **AegisCode** (AegisCode Studio & Aegis Agent).

---

## 1. Phase 0: Google Antigravity Provider & Stateless OAuth

*Status*: **Selesai & Terverifikasi (Exit Code 0)**

### Rincian Implementasi:
- **Provider Core**: Mengimplementasikan `AntigravityProvider` pada `src/agent_ai/providers/antigravity.py` dengan dukungan jembatan CLI native (`agy`) serta panggilan langsung ke endpoint frontier reasoning.
- **Stateless Google OAuth**: Mengimplementasikan alur otentikasi Google berbasis stateless signed JWT dengan validasi token anti-CSRF pada `web/django_app/api/auth.py`.
- **Sistem Pembacaan Kredensial Otomatis**: Membaca kredensial OAuth lokal pengguna secara otomatis dari `~/.gemini/oauth_creds.json`.
- **Registri Model Frontier**: Mendukung keluarga model penalaran terkini:
  - Gemini: `gemini-3.8-flash-high`, `gemini-3.8-flash-medium`, `gemini-3.8-flash-low`, `gemini-3.7-flash-high`, `gemini-3.1-pro-high`, `gemini-3.1-pro-low`.
  - Thinking Models: `claude-sonnet-4-6`, `claude-opus-4-6-thinking`.
  - Open Weights: `gpt-oss-120b-medium`.
- **Integrasi Database Ganda**: Pendaftaran otomatis Google Antigravity pada `LLMConfigService` dengan discovery database `.aegis/` (`data/aegis.db`) dan fallback otomatis ke `.aether/` (`data/aether.db`).

### Berkas Terkait:
- `src/agent_ai/providers/antigravity.py`
- `src/agent_ai/config/settings.py`
- `src/agent_ai/providers/factory.py`
- `src/agent_ai/llm_config/provider_service.py`
- `web/django_app/api/auth.py`

### Pengujian & Verifikasi:
- `tests/test_antigravity_provider.py`
- `tests/test_oauth_state.py`

---

## 2. Phase 1: Interaksi UI & Fondasi Version Control

*Status*: **Selesai & Terverifikasi (Exit Code 0)**

### Rincian Implementasi:
- **Pencarian Sebutan Cepat (@file)**: Implementasi resolver sebutan file berbasis fuzzy search pada `src/agent_ai/contextbuilder/mention.py` dengan batas atas aman 64KB per pembacaan file.
- **Template Perintah Cepat (*Slash Commands*)**: Penyediaan template perintah terstandarisasi (`/fix`, `/test`, `/audit`, `/refactor`) pada prompt input.
- **Git Local Repository Facade**: Menghubungkan abstraksi `GitRepositoryFacade` (`src/agent_ai/git/repository.py`) ke API Gateway REST:
  - `/api/git/status`: Mendeteksi perubahan file secara real-time.
  - `/api/git/diff`: Menghasilkan representasi unified diff baris dan karakter.
  - `/api/git/commits`: Menampilkan riwayat commit repositori lokal.
  - `/api/git/branches`: Menampilkan daftar branch lokal dan remote.
  - `/api/git/discard`: Membatalkan perubahan lokal file yang belum di-commit.
- **Indikator Status Berkas Real-Time**: Lencana status berkas (`M` Modified, `U` Untracked, `D` Deleted, `A` Added) pada `web/frontend/src/components/FileExplorer.vue`.
- **Monaco Diff Editor Terintegrasi**: Visualisasi perbandingan berkas dua arah (*side-by-side*) dan satu arah (*inline*) di dalam AegisCode Studio via `web/frontend/src/components/MonacoDiffEditor.vue` dan `ChangesPanel.vue`.

### Berkas Terkait:
- `src/agent_ai/contextbuilder/mention.py`
- `src/agent_ai/git/repository.py`
- `web/django_app/api/views.py`
- `web/frontend/src/components/ChangesPanel.vue`
- `web/frontend/src/components/MonacoDiffEditor.vue`
- `web/frontend/src/components/FileExplorer.vue`
- `web/frontend/src/components/CommandPalette.vue`

### Pengujian & Verifikasi:
- `tests/test_mention_resolver.py`
- `tests/test_git_facade.py`
- `web/frontend/tests/MonacoDiffEditor.test.ts`

---

## 3. Eksekusi Latar Belakang & Retensi Tampilan Assistant

*Status*: **Selesai & Terverifikasi**

### Rincian Implementasi:
- **Retensi Komponen DOM (`v-show`)**: Kolom AI Assistant pada `web/frontend/src/pages/WorkbenchView.vue` dipertahankan menggunakan `v-show="assistantVisible"`, menjaga proses eksekusi task, posisi scroll, riwayat obrolan, dan panggilan tool tetap aktif meskipun drawer ditutup.
- **Indikator Navbar Aktif**: Komponen `AppNavbar.vue` menampilkan pil status `.nav-assistant-pill` dengan denyut warna saat AI sedang memproses task di latar belakang.
- **Notifikasi Penyelesaian Mengambang (*Completion Toast*)**: Komponen `.wb-bg-toast` muncul saat task latar belakang selesai, memberikan pratinjau hasil dan tombol pintas untuk langsung membuka panel asisten terkait.
