# Panduan Pengguna Komunitas AegisCode Studio

Panduan ini ditujukan bagi pengguna dan kontributor komunitas sumber terbuka untuk memulai dan mengoperasikan **AegisCode Studio v0.2.05**.

---

## 1. Persiapan & Menjalankan Aplikasi

### Prasyarat Sistem
- **Node.js**: v18.0.0 atau lebih baru (npm v9+)
- **Python**: v3.10 atau lebih baru (dengan pip & virtualenv)
- **Git**: Terpasang di sistem operasi Anda

### Langkah Menjalankan

1. **Jalankan Backend (Django API & Agent Runtime):**
   ```bash
   cd apps/django_app
   python -m venv .venv
   source .venv/bin/activate  # Di Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   python manage.py runserver 0.0.0.0:8000
   ```

2. **Jalankan Frontend (Studio Vite):**
   ```bash
   cd apps/frontend
   npm install
   npm run dev
   ```

3. Buka browser Anda di `http://localhost:5173`.

---

## 2. Login & Autentikasi Pengembang Lokal

AegisCode mengedepankan kedaulatan data lokal (*Sovereign Local Authentication*). Kredensial tidak dikirim ke server cloud mana pun:

1. **Inisialisasi Pertama Kali (First-Run):**
   - Saat membuka Studio pertama kali, modal setup kata sandi akan tampil otomatis.
   - Buat kata sandi pengembang lokal (minimal 6 karakter).
   - Simpan kata sandi. Kredensial di-hash menggunakan PBKDF2-HMAC-SHA256 dan disimpan secara lokal di `.aegis/auth.json`.
2. **Login Harian:**
   - Masukkan kata sandi yang telah dibuat pada layar login untuk membuka akses ke Workbench IDE.
3. **Opsi Environment Variable (Otomasi):**
   - Anda juga dapat mengatur kata sandi secara deklaratif melalui variabel lingkungan:
     ```bash
     export AEGIS_PASSWORD="sandi_pilihan_anda"
     ```

---

## 3. Menghubungkan Telegram Remote Companion

Fitur Telegram Remote Companion memungkinkan Anda memantau status agen dan menyetujui perubahan kode dari ponsel pintar saat tidak berada di depan komputer:

1. **Buat Bot di `@BotFather`:**
   - Buka Telegram dan cari `@BotFather`.
   - Kirimkan perintah `/newbot` dan ikuti petunjuk hingga mendapatkan HTTP Bot Token.
2. **Atur Variabel Lingkungan:**
   - Tambahkan token bot ke file `.env` di direktori utama:
     ```env
     TELEGRAM_BOT_TOKEN="token_dari_botfather_disini"
     ```
   - Muat ulang (*restart*) backend Django.
3. **Pairing Akun via IDE:**
   - Buka menu **Settings** (`Ctrl+,` atau `Cmd+,`) -> **Remote Companion**, atau klik badge Telegram di status bar kanan bawah.
   - Klik tombol **"Pindai QR Code Pairing"**.
   - Pindai QR code menggunakan kamera ponsel atau klik tautan **"Buka di Telegram"** (`t.me/<bot>?start=<token>`).
   - Tekan **Start** di Telegram. Status pairing akan otomatis aktif dan terhubung.
4. **Memberi Persetujuan dari Ponsel (HITL):**
   - Saat agen mengajukan perubahan berkas (*diff*), ponsel Anda akan menerima notifikasi ringkasan.
   - Tekan tombol inline `[Approve]` untuk mengizinkan perubahan atau `[Reject]` untuk menolak.
   - Balas pesan bot (*reply*) untuk memberikan instruksi tambahan langsung ke agen.

---

## 4. Menggunakan Agents Aegis (Olympus Framework)

AegisCode mengoperasikan tim multi-agent otonom berbasis **Olympus Framework** dengan pembagian tanggung jawab spesialis:

### Peran Utama Persona Olympus:
- **Zeus Orchestrator**: Koordinator utama alur kerja dan penegak standar kualitas lintas fase.
- **Athena Planner**: Menganalisis kebutuhan dan menyusun rencana pemecahan tugas yang rapi.
- **Hermes Scout**: Menjelajahi basis kode dan memetakan struktur file dan simbol.
- **Hephaestus Coder**: Menulis kode secara bertahap dan rapi (*incremental implementation*).
- **Heracles Tester**: Memvalidasi fungsionalitas dengan pengujian otomatis (*test-driven verification*).
- **Themis Reviewer**: Menilai kualitas, keamanan, performa, dan arsitektur kode sebelum digabungkan.

### Alur Kerja di Workbench IDE:
1. Buka drawer asisten di sisi kanan layar dan pilih tab **Agents**.
2. Masukkan instruksi tugas yang diinginkan, misalnya:
   ```text
   Tambahkan validasi email pada formulir kontak dan buatkan unit test-nya.
   ```
3. Agent akan memetakan kode, merancang rencana, dan menyajikan pratinjau perubahan (*diff review*).
4. Tinjau perubahan pada editor visual, lalu klik **Approve** di IDE (atau konfirmasi via Telegram).

---

## 5. Bantuan & FAQ Singkat

- **Lupa Kata Sandi IDE Lokal?**  
  Hapus file konfigurasi lokal dengan perintah `rm .aegis/auth.json`, lalu muat ulang halaman browser untuk membuat sandi baru.
- **Bot Telegram Tidak Merespons?**  
  Periksa apakah `TELEGRAM_BOT_TOKEN` di `.env` sudah benar dan komputer terhubung ke internet.
- **Mereset Pairing Telegram?**  
  Buka Settings -> Remote Companion lalu klik "Putuskan Hubungan Akun", atau hapus berkas `.aegis/telegram_paired.json`.
