# AegisCode Rule-Set Development & Engineering Standards

Dokumen ini mendefinisikan aturan rekayasa perangkat lunak, standar kode, protokol eksekusi alat, dan pedoman kualitas wajib bagi seluruh pengembang dan agen otonom pada repositori **AegisCode**.

---

## 1. Kebijakan Kode Ringkas (Lean Code Policy / YAGNI)

*You Aren't Gonna Need It*. Jangan pernah membuat abstraksi atau menambahkan pustaka pihak ketiga tanpa kebutuhan langsung yang nyata:
1. **Zero-Orphan Code**: Dilarang membuat fungsi, kelas, variabel, atau modul yang tidak memiliki referensi pemanggil aktif.
2. **Ketergantungan Minimal**: Utamakan pustaka bawaan standar (Python Standard Library, Node.js Native Runner) sebelum mempertimbangkan paket eksternal baru.
3. **Pembersihan Berkelanjutan**: Setiap refaktorisasi wajib menghapus kode usang (*dead code*) alih-alih mengomentarinya.

---

## 2. Protokol Rust Token Killer (RTK Protocol)

Seluruh agen dan pengembang diwajibkan menggunakan utilitas `rtk` untuk operasi CLI guna menghemat beban token konteks LLM:

| Operasi | Perintah RTK | Perintah Fallback (Jika RTK Tidak Tersedia) |
|---|---|---|
| Pencarian Kode (Grep) | `rtk rg <pola>` | `rg <pola>` / `grep -rn <pola>` |
| Pencarian Berkas | `rtk find <jalur> <bendera>` | `find <jalur> <bendera>` |
| Pembacaan Berkas | `rtk read <jalur>` | Pembacaan berkas langsung |
| Version Control Git | `rtk git status/diff/log` | `git status/diff/log` |
| Eksekusi Pengujian | `rtk test` | `pytest` / `node --test` / `npm test` |
| Inspeksi JSON | `rtk json --keys-only` | `jq` |
| Analisis Galat Cerdas | `rtk smart` / `rtk err <cmd>` | Pembacaan log manual |

---

## 3. Protokol Pengujian Dual-Stack & Strict Stop-Gate

1. **Dual-Stack Runner**:
   - Backend Python Engine: `pytest` pada direktori `tests/`.
   - Frontend Workbench: `vitest` / `node --test` pada `web/frontend/`.
2. **Strict Stop-Gate**:
   - Tugas atau commit TIDAK boleh dinyatakan selesai sebelum seluruh pengujian lulus dengan kode keluar 0 (*exit code 0*).
   - Dilarang mematikan *assertion*, menambahkan dekorator `@pytest.mark.skip` tanpa persetujuan, atau menyembunyikan galat uji.
3. **Cakupan Pengujian Wajib**:
   - Integritas berkas metadata agen dan frontmatter YAML skill.
   - Validitas sintaksis skrip bash dan hook JSON.
   - Deteksi kompatibilitas mundur jalur `.aegis/` dan `.aether/`.
   - Verifikasi kebersihan proses (*zero-zombie process verification*).

---

## 4. Siklus Hidup Proses & Penanganan Zombie (Zero-Zombie Process)

1. **Terminasi Tree-Kill**:
   - Seluruh proses latar belakang (server Django, Vite, daemon agen, shell terminal) wajib terdaftar dalam pohon proses yang terlacak.
   - Saat aplikasi desktop ditutup atau sesi dihentikan, supervisor wajib mengirimkan sinyal `SIGTERM` ke seluruh sub-proses anak (`process tree-kill`), disusul `SIGKILL` jika proses tidak berhenti dalam tenggat waktu aman (3 detik).
2. **Pembersihan Resource PTY**:
   - Terminal PTY harus segera melepaskan file descriptor saat socket ditutup oleh pengguna.

---

## 5. Kompatibilitas Mundur & State Discovery

Repositori menerapkan strategi penemuan status dua arah:
1. **Penyimpanan State Ruang Kerja**:
   - Prioritas Utama: `.aegis/` (misal: `.aegis/vectors.db`, `.aegis/map/`).
   - Fallback Transparan: `.aether/`.
2. **Database Konfigurasi**:
   - Prioritas Utama: `data/aegis.db`.
   - Fallback Transparan: `data/aether.db`.
3. Seluruh pembacaan konfigurasi harus memeriksa keberadaan berkas `.aegis` terlebih dahulu sebelum mengakses `.aether`.

---

## 6. Regulasi Cabang Git (Branch Regulations)

1. **Branch `master`**:
   - Branch pengembangan utama yang memuat dokumentasi arsitektur lengkap (`docs/`, `AGENTS.md`, `Roadmap.md`).
2. **Branch `main`**:
   - Branch rilis komunitas publik dengan konsep **Bring Your Own Key (BYOK)**.
   - Bebas dari folder `docs/`, `AGENTS.md`, dan `Roadmap.md`. Hanya menyertakan `README.md` komunitas.
   - Pembaruan dari komunitas wajib melalui Pull Request (PR) dan issue.
   - Sinkronisasi menggunakan `.gitattributes` (`export-ignore`) dan `git sparse-checkout`.
3. **Branch `release`**:
   - Branch rilis enterprise untuk bundel aplikasi native macOS Tauri v2 (`.dmg`) secara lokal.
   - Seluruh pengaturan debug wajib dinonaktifkan (`debug = false`).

---

## 7. Standar Komunikasi & Pelaporan

1. **Bahasa Internal**: Bahasa Inggris digunakan murni untuk penulisan logika pemikiran (*reasoning* internal), pencarian simbol, dan kode program.
2. **Bahasa Output**: Bahasa Indonesia baku wajib digunakan untuk semua respons kepada pengguna, komentar kode, pesan commit Git, dan dokumen resmi.
3. **Larangan Bahasa Daerah**: Dilarang keras menggunakan kosakata bahasa Jawa dalam teks output.
4. **Larangan Emoji**: Dilarang menyertakan simbol emoji atau emotikon pada seluruh pesan output, komentar kode, commit Git, maupun dokumentasi teknis.
