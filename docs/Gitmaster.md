# AegisCode Git Master Architecture & Multi-Remote Operational Guide

Dokumen ini adalah panduan resmi pengelolaan arsitektur Git, topologi multi-remote, alur kerja tri-branch (*master*, *main*, *release*), protokol kerahasiaan (*privacy boundaries*), serta prosedur sinkronisasi kode pada ekosistem **AegisCode** (AegisCode Studio & Aegis Agent).

---

## 1. Topologi Multi-Remote & Isolasi Privasi

Untuk melindungi kekayaan intelektual (prompt agen otonom, strategi internal, dan dokumentasi arsitektur) tanpa menghambat kontribusi komunitas sumber terbuka, repositori beroperasi di bawah arsitektur **Dual-Remote**:

```
                              ┌────────────────────────────────────────────────────────┐
                              │                    Lokal Workstation                   │
                              │  Branch: master (Aktif) | main | release               │
                              └───────────────┬────────────────────────┬───────────────┘
                                              │                        │
                         git push dev master  │                        │  git push origin main
                         git push dev release │                        │
                                              ▼                        ▼
┌───────────────────────────────────────────────────────┐    ┌───────────────────────────────────────────────────────┐
│     Remote 'dev' (GitHub Private Repository)          │    │     Remote 'origin' (GitHub Public Repository)        │
│     aditlab-code/aegiscode-dev                        │    │     aditlab-code/aegiscode                            │
├───────────────────────────────────────────────────────┤    ├───────────────────────────────────────────────────────┤
│ • Branch 'master': Pusat pengembangan fitur harian    │    │ • Branch 'main': Rilis komunitas sumber terbuka       │
│ • Branch 'release': Kerangka bundel desktop native    │    │ • Akses: Publik (siapa saja dapat melihat/clone)      │
│ • Berkas: Memuat docs/, AGENTS.md, Roadmap.md         │    │ • Berkas: DILARANG ada docs/, AGENTS.md, Roadmap.md   │
│ • Akses: Privat (Hanya pengembang internal)           │    │ • Filosofi: Bring Your Own Key (BYOK)                 │
└───────────────────────────────────────────────────────┘    └───────────────────────────────────────────────────────┘
```

### 1.1. Konfigurasi Remote Resmi

| Nama Remote | URL Repositori | Status Privasi | Branch yang Dikelola |
| :--- | :--- | :---: | :--- |
| **`origin`** | `https://github.com/aditlab-code/aegiscode.git` | **Publik** | HANYA `main` (Edisi Komunitas) |
| **`dev`** | `https://github.com/aditlab-code/aegiscode-dev.git` | **Privat** | `master` (Fitur & Docs) dan `release` (Bundel) |
| **`fork`** | `https://github.com/aditlab-code/aether-agent.git` | Privat | Cadangan arsip lawas upstream |

---

## 2. Arsitektur Tri-Branch & Pemisahan Tugas

### 2.1. Branch `master` (Development Hub)
- **Status Akses**: Privat (Tersinkronisasi ke `dev/master`).
- **Tujuan**: Pusat integrasi seluruh fitur baru, eksperimen model, perbaikan bug, dan dokumentasi mendalam.
- **Cakupan Berkas**: Seluruh ekosistem dokumen (`docs/`, `AGENTS.md`, `Roadmap.md`) wajib dikelola di branch ini.
- **Alur Kerja**: Bekerja sebagai simpul pusat dua arah yang mengalirkan kode bersih ke edisi komunitas (`main`) dan edisi enterprise (`release`).

### 2.2. Branch `main` (Community Publish Edition)
- **Status Akses**: Publik (Tersinkronisasi ke `origin/main`).
- **Tujuan**: Rilis terbuka bagi komunitas pengembang dengan filosofi **Bring Your Own Key (BYOK)**.
- **Larangan Ketat**: Dilarang keras memuat folder `docs/`, `AGENTS.md`, maupun `Roadmap.md` di tingkat root.
- **Berkas yang Diizinkan di Root**: Hanya berkas `README.md` versi komunitas (berisi panduan instalasi lokal, penggunaan API key sendiri, dan aturan kontribusi).
- **Prosedur Kontribusi**: Seluruh kontribusi komunitas dari luar wajib melalui pembukaan Issue dan Pull Request (PR) terisolasi.
- **Mekanisme Filtrasi**: Menggunakan konfigurasi `.gitattributes` (`export-ignore`) agar dokumen internal tidak pernah terekspos dalam arsip rilis.

### 2.3. Branch `release` (Enterprise MVP Bundle)
- **Status Akses**: Privat (Tersinkronisasi ke `dev/release`).
- **Tujuan**: Jalur rilis enterprise untuk mengemas aplikasi desktop native minimal MVP dalam format `.dmg` (macOS) secara lokal via Tauri v2.
- **Konfigurasi Produksi**: Seluruh modul debug dinonaktifkan (`debug = false`, strip symbol aktif, opt-level 3, devtools off).
- **Status Operasional**: Disiapkan sebagai kerangka siaga (*standby bundle*).

---

## 3. Matriks Perintah Operasional Git Harian

### 3.1. Bekerja pada Branch `master` (Pengembangan Internal)
```bash
# Memastikan berada di branch master
git checkout master

# Mengambil pembaruan terbaru dari remote privat
git pull dev master

# Menyimpan perubahan harian
git add .
git commit -m "feat(subsystem): deskripsi perubahan kode"

# Mencadangkan ke remote privat (aman 100% dari publik)
git push dev master
```

### 3.2. Merilis Pembaruan ke Branch `main` (Komunitas Publik)
Saat fitur pada `master` telah siap untuk dipublikasikan ke komunitas:
```bash
# 1. Beralih ke branch main
git checkout main

# 2. Ambil perubahan kode dari master (tanpa dokumen terlarang)
# Perubahan kode digabungkan secara selektif atau rebase
git merge master --no-commit

# 3. Pastikan berkas terlarang tetap terhapus dari working tree main
git rm -rf docs AGENTS.md Roadmap.md 2>/dev/null || true

# 4. Pastikan README.md komunitas tetap utuh
git checkout HEAD -- README.md

# 5. Commit dan push ke remote origin publik
git commit -m "chore: rilis sinkronisasi edisi komunitas"
git push origin main

# 6. Kembali ke branch master
git checkout master
```

### 3.3. Mengelola Branch `release` (Bundel Enterprise)
```bash
# Beralih ke branch release
git checkout release

# Menggabungkan pembaruan fungsional dari master
git merge master

# Memastikan konfigurasi Tauri v2 tetap dalam mode release (debug = false)
# Jalankan verifikasi build lokal
cd web/frontend && npm run build && cd ../..

# Commit dan push ke remote privat dev
git push dev release

# Kembali ke branch master
git checkout master
```

---

## 4. Mekanisme Menerima Kontribusi Komunitas (Inbound PR)

Jika kontributor komunitas mengajukan Pull Request di repositori publik `origin`:

1. **Review di GitHub**: Periksa perubahan kode pada antarmuka PR GitHub `aditlab-code/aegiscode`.
2. **Uji Lokal di Mesin**:
   ```bash
   git fetch origin pull/<ID_PR>/head:pr-<ID_PR>
   git checkout pr-<ID_PR>
   pytest
   cd web/frontend && npm run build && cd ../..
   ```
3. **Merge ke `main`**: Gabungkan PR tersebut ke branch `main` publik setelah lolos uji verifikasi.
4. **Tarik Balik ke `master`**:
   ```bash
   git checkout master
   git merge origin/main -m "merge: integrasi kontribusi komunitas PR #<ID_PR>"
   git push dev master
   ```

---

## 5. Ringkasan Status Branch Tracking Saat Ini

```text
Local Branch   Tracking Remote   Visibilitas   Fungsi
────────────   ───────────────   ───────────   ────────────────────────────────────────
main           origin/main       Publik        Edisi Komunitas Sumber Terbuka (BYOK)
master         dev/master        Privat        Pusat Fitur, Aturan Agen, & Dokumen Inti
release        dev/release       Privat        Kerangka Pemaketan Desktop Native Tauri
```
