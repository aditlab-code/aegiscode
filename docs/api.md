# AegisCode API Gateway Specification

Dokumen ini mendefinisikan spesifikasi antarmuka pemrograman aplikasi (API) pada **Django API Gateway** (`apps/django_app/api`) yang menghubungkan antarmuka pengguna AegisCode Studio (`apps/frontend`) dengan mesin Aegis Agent (`src/agent_ai`).

---

## 1. Arsitektur Otentikasi & Sesi (Stateless Identity)

AegisCode menggunakan mekanisme token JWT bertanda tangan (*Stateless Signed JWT*) tanpa ketergantungan pada tabel database Django session.

### 1.1. Inisialisasi Otentikasi Google
- **Endpoint**: `GET /api/auth/google/url`
- **Deskripsi**: Menghasilkan URL otentikasi Google OAuth2 resmi dengan token *anti-CSRF state*.
- **Response**:
  ```json
  {
    "url": "https://accounts.google.com/o/oauth2/v2/auth?...",
    "state": "eyJhbGciOi..."
  }
  ```

### 1.2. Callback Otentikasi Google
- **Endpoint**: `GET /api/auth/google/callback?code=...&state=...`
- **Deskripsi**: Memvalidasi token state, menukarkan authorization code dengan profil pengguna Google, dan menerbitkan token otentikasi stateless cookie/header.

### 1.3. Status Sesi Pengguna Aktif
- **Endpoint**: `GET /api/auth/me`
- **Deskripsi**: Mengembalikan informasi identitas pengguna aktif (email, nama, avatar).
- **Endpoint Terkait**: `POST /api/auth/logout`, `POST /api/auth/dev-login` (khusus bypass pengujian unit/dev).

---

## 2. API Pengelolaan Proyek & Filesystem

### 2.1. Daftar Proyek & Pemilihan Folder Native
- **Endpoint**: `GET /api/projects`, `POST /api/projects`
- **Endpoint Folder Picker**: `POST /api/projects/pick-folder`
  - Membuka dialog pemilih folder native sistem operasi dan mendaftarkan direktori kerja terpilih.
- **Endpoint Proyek Aktif**: `GET /api/active-project`, `POST /api/active-project`

### 2.2. Penjelajahan Berkas & Konten
- **Endpoint**: `GET /api/files?path=<relative_path>`
  - Mengembalikan struktur pohon direktori workspace.
- **Endpoint**: `GET /api/files/content?path=<relative_path>`
  - Mengembalikan isi konten teks berkas untuk ditampilkan pada editor Monaco. Batas pembacaan aman maksimum 64KB per permintaan.

---

## 3. Git Local Repository Facade API

API ini mengabstraksikan operasi version control Git lokal tanpa mengeksekusi shell escape berbahaya:

### 3.1. Status Perubahan Berkas
- **Endpoint**: `GET /api/projects/<project_id>/git/status`
- **Deskripsi**: Mendeteksi perubahan working tree (`modified`, `untracked`, `deleted`, `staged`).
- **Response**:
  ```json
  {
    "branch": "master",
    "clean": false,
    "files": [
      {"path": "src/main.py", "status": "M", "staged": false}
    ]
  }
  ```

### 3.2. Unified Diff Inspeksi
- **Endpoint**: `GET /api/projects/<project_id>/git/diff?path=<file_path>`
- **Deskripsi**: Menghasilkan representasi diff baris dan karakter untuk dirender oleh Monaco Diff Editor.

### 3.3. Riwayat Commit & Cabang
- **Endpoint**: `GET /api/projects/<project_id>/git/commits?limit=20`
- **Endpoint**: `GET /api/projects/<project_id>/git/branches`

### 3.4. Pembatalan Perubahan Berkas
- **Endpoint**: `POST /api/projects/<project_id>/git/discard`
- **Payload**: `{"path": "src/main.py"}`
- **Deskripsi**: Mengembalikan berkas ke kondisi commit terakhir secara deterministik.

---

## 4. API Runtime Task Agen & Antrian

### 4.1. Pembuatan & Status Task
- **Endpoint**: `POST /api/tasks`
  - **Payload**:
    ```json
    {
      "prompt": "Refactor router to support async",
      "project_id": "proj_123",
      "mode": "orchestrator"
    }
    ```
- **Endpoint**: `GET /api/tasks/<task_id>`
- **Endpoint Pembatalan**: `POST /api/tasks/<task_id>/cancel`

### 4.2. Gerbang Persetujuan Kebijakan (Human-in-the-Loop Gating)
- **Endpoint**: `GET /api/tasks/approvals`
  - Mengambil daftar aksi destruktif yang sedang ditahan oleh `SupervisedModePolicy`.
- **Endpoint**: `POST /api/tasks/approvals/resolve`
  - **Payload**: `{"approval_id": "appr_123", "decision": "approve" | "reject"}`

### 4.3. Antrian Task (Queue Management)
- **Endpoint**: `GET /api/tasks/queue`, `POST /api/tasks/queue/clear`
- **Endpoint Operasi**:
  - `POST /api/tasks/queue/<task_id>/move`
  - `POST /api/tasks/queue/<task_id>/disable`
  - `POST /api/tasks/queue/<task_id>/enable`
  - `POST /api/tasks/queue/<task_id>/remove`

### 4.4. Aktivitas & Laporan Akhir
- **Endpoint**: `GET /api/tasks/<task_id>/activity` (kronologi panggilan tool).
- **Endpoint**: `GET /api/tasks/<task_id>/report` (ringkasan penyelesaian tugas).

---

## 5. API Konsultan & Penalaran (Read-Only)

- **Endpoint**: `GET /api/consultant/sessions`
- **Endpoint**: `POST /api/consultant/consult`
  - Mengirim kueri diskusi ke modul konsultan tanpa memberikan hak modifikasi sistem berkas.

---

## 6. API Konfigurasi Model Provider & Kredensial

- **Endpoint**: `GET /api/llm/providers`
  - Menampilkan daftar provider yang didukung (Google Antigravity, Ollama, DeepSeek, OpenAI-compatible).
- **Endpoint**: `GET /api/llm/models`
- **Endpoint**: `POST /api/llm/credentials`
- **Endpoint Uji Koneksi**: `POST /api/llm/providers/test`

---

## 7. Streaming & Terminal PTY Bridge

### 7.1. Server-Sent Events (SSE)
- **Endpoint**: `GET /api/events`
  - Saluran streaming real-time untuk status task, indikator kemajuan, dan notifikasi latar belakang.

### 7.2. WebSocket ANSI PTY Bridge
- **Endpoint**: `ws://localhost:8000/ws/terminal/`
  - Terkoneksi ke sesi interactive pseudo-terminal dengan dukungan input karakter raw, penanganan signal `Ctrl+C`, dan pembersihan proses saat terminal ditutup.

---

## 8. API Siklus Hidup Server & Terminasi (Zero-Zombie Lifecycle)

Endpoint ini mengelola penghentian server AegisCode secara deterministik sesuai spesifikasi [docs/PRD.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/PRD.md) dan [docs/ruleset.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/ruleset.md):

### 8.1. Terminasi Server
- **Endpoint**: `POST /api/server/terminate`
- **Payload (Opsional)**:
  ```json
  {
    "force": false,
    "delay": 0.3
  }
  ```
- **Deskripsi**:
  1. Menerima permintaan dan merespons segera dengan HTTP 200 agar klien antarmuka pengguna tidak terputus secara mendadak.
  2. Membatalkan seluruh task agen yang sedang berjalan secara kooperatif (`CancellationToken`).
  3. Menutup dan membersihkan seluruh sesi terminal PTY aktif (`pty.terminate()`) serta melepaskan file descriptor master/slave.
  4. Menjadwalkan penghentian proses server dalam thread asinkron (mengirim sinyal `SIGTERM` ke pohon proses server, disusul eskalasi `SIGKILL` jika belum berhenti dalam batas waktu 3 detik) untuk memastikan port dilepas dan tingkat proses orphan/zombie adalah 0%.
- **Response**:
  ```json
  {
    "status": "terminating",
    "message": "Penghentian server AegisCode telah diinisiasi.",
    "pid": 12345,
    "force": false
  }
  ```
