# AegisCode Community Edition

AegisCode adalah platform *Autonomous AI Coding Workbench* yang mengutamakan privasi pengguna (*local-first*), deterministik, hemat token, dan aman digunakan pada basis kode produksi melalui perlindungan *guardrails* ketat.

Branch **`main`** ini merupakan repositori resmi untuk rilis publik komunitas sumber terbuka (*open source*).

---

## 1. Filosofi Bring Your Own Key (BYOK)

AegisCode Community Edition beroperasi sepenuhnya dengan prinsip **Bring Your Own Key (BYOK)**:
- **Tanpa Biaya Langganan Platform**: Anda memegang kendali penuh atas infrastruktur komputasi dan pembiayaan model AI.
- **Dukungan Provider AI Fleksibel**:
  - **Google Antigravity**: Model frontier reasoning (`gemini-3.8-flash`, `gemini-3.1-pro`, `claude-sonnet-4-6`) via jembatan CLI `agy` atau token akun Google Anda.
  - **Model Lokal Bebas Biaya (Ollama / Llama.cpp)**: Jalankan model open-weights (DeepSeek Coder, Qwen, Llama 3) langsung di mesin lokal tanpa koneksi internet.
  - **Provider API Cloud**: Dukungan langsung untuk DeepSeek, OpenAI, Anthropic, dan OpenRouter.
- **Privasi Kode Terjaga**: Seluruh pemrosesan penelusuran repositori berjalan secara lokal. Hanya potongan kode terkurasi yang dikirimkan ke model saat pembuatan diff.

---

## 2. Prasyarat Sistem & Instalasi

### Prasyarat
- **Python**: Versi 3.10, 3.11, atau 3.12
- **Node.js**: Versi 18.x atau 20.x LTS dengan npm
- **Git**: Versi 2.30+
- **Sistem Operasi**: macOS, Linux, atau Windows (disarankan menggunakan WSL2 untuk Windows)

### Langkah Pemasangan Mandiri

1. **Clone Repositori**:
   ```bash
   git clone https://github.com/aditlab-code/aegiscode.git
   cd aegiscode
   ```

2. **Siapkan Virtual Environment Python**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Di Windows: venv\Scripts\activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Siapkan Frontend Workbench**:
   ```bash
   cd web/frontend
   npm install
   cd ../..
   ```

4. **Konfigurasi Lingkungan (`.env`)**:
   Salin berkas contoh konfigurasi:
   ```bash
   cp .env.example .env
   ```
   Isi kunci API Anda sesuai penyedia model yang ingin digunakan (misal: `OPENROUTER_API_KEY`, `OPENAI_API_KEY`, dsb.).

---

## 3. Menjalankan AegisCode

Gunakan skrip eksekusi satu langkah:

- **macOS / Linux**:
  ```bash
  ./run.sh
  ```
- **Windows**:
  ```cmd
  run.bat
  ```

Layanan akan berjalan pada:
- **AegisCode Studio Workbench**: `http://localhost:5173`
- **Django API Gateway**: `http://localhost:8000`

---

## 4. Panduan Kontribusi Komunitas

Komunitas dipersilakan mengembangkan dan menyempurnakan fitur AegisCode secara mandiri dengan mematuhi protokol kontribusi berikut:

### Alur Issue & Pull Request (PR)
1. **Buka Issue Terlebih Dahulu**: Setiap penambahan fitur, perubahan arsitektur, atau perbaikan bug wajib diawali dengan pembuatan issue di GitHub untuk mendiskusikan latar belakang dan solusi teknis.
2. **Cabang Fitur Terisolasi**: Buat branch baru dari `main` dengan format penamaan deskriptif:
   ```bash
   git checkout -b feature/nama-fitur
   # atau
   git checkout -b fix/deskripsi-perbaikan
   ```
3. **Standar Pengujian Sebelum Push**:
   Sebelum mengajukan Pull Request, seluruh pengujian wajib lulus tanpa galat:
   ```bash
   # Jalankan pengujian backend
   pytest

   # Jalankan pengujian frontend
   cd web/frontend && npm test
   ```
4. **Pengajuan PR**: Ajukan Pull Request ke branch `main`. Tim maintainer akan meninjau perubahan Anda melalui proses code review sebelum digabungkan.

---

## 5. Lisensi

AegisCode Community Edition didistribusikan di bawah lisensi sumber terbuka. Lihat berkas [LICENSE](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/LICENSE) untuk ketentuan selengkapnya.
