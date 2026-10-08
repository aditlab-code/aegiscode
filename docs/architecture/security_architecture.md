# Arsitektur Keamanan & Otentikasi Sovereign AegisCode

Dokumen ini mendefinisikan arsitektur keamanan, batas perimeter (*security boundaries*), dan model otentikasi lokal (*Sovereign Local Authentication*) untuk **AegisCode Studio** dan **Aegis Agent**.

---

## 1. Filosofi & Prinsip Keamanan

AegisCode didesain dengan prinsip **Local-First, Sovereign, dan Zero-Trust**:

1. **Eliminasi Telemetri Pihak Ketiga (No Vendor Lock-in)**:
   Otentikasi Google OAuth dihapus menyeluruh (PR-SEC-2). Seluruh kredensial dan sesi diverifikasi 100% secara lokal pada mesin operator tanpa panggilan jaringan keluar ke server otentikasi eksternal.
2. **Zero-Trust Perimeter (Tanpa Loopback Bypass)**:
   Sebagai mitigasi terhadap serangan *Drive-by Web Exploits*, bypass otentikasi berbasis alamat IP loopback (`127.0.0.1` / `localhost`) ditiadakan (PR-SEC-1). Semua permintaan HTTP dan WebSocket wajib menyertakan token otentikasi yang sah.
3. **Penyimpanan Kredensial Terenkripsi**:
   Kata sandi operator tidak disimpan dalam bentuk teks polos (*plaintext*). Sistem menggunakan algoritma derivasi kunci standar industri **PBKDF2-HMAC-SHA256** dengan 100.000 iterasi dan salt acak 16-byte kriptografis.
4. **Isolasi Berkas Kredensial POSIX**:
   Berkas kredensial (`.aegis/auth.json`) ditulis secara atomik dan dikunci dengan izin akses ketat `0o600` (hanya dapat dibaca dan ditulis oleh pemilik proses).

---

## 2. Model Otentikasi & Token

Sistem mengimplementasikan dua jenis token yang sah:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        MODEL TOKEN AEGISCODE                           │
├──────────────────────────────────┬─────────────────────────────────────┤
│ 1. Ephemeral Handshake Token     │ 2. Session JWT Token                │
├──────────────────────────────────┼─────────────────────────────────────┤
│ • Dibuat otomatis saat startup   │ • Diterbitkan saat login password   │
│ • Disimpan di .aegis/run/gateway │ • Berbasis standar HS256            │
│ • Izin berkas: 0600              │ • Masa berlaku: 7 hari              │
│ • Untuk CLI -> Browser bootstrap │ • Untuk sesi Web UI operator        │
└──────────────────────────────────┴─────────────────────────────────────┘
```

```mermaid
graph TD
    CLI["CLI Launcher (agy)"] -->|Generate 32-byte secret| EPH[".aegis/run/gateway.token (0600)"]
    EPH -->|Inject via URL/Meta| UI["AegisCode Web UI"]
    UI -->|Bearer Ephemeral Token| GW["Django Gateway API"]
    
    OP["Operator (Pengguna)"] -->|Input Password (min 6 char)| LOGIN["POST /api/auth/login"]
    LOGIN -->|PBKDF2 Verify| STORE[".aegis/auth.json"]
    LOGIN -->|Issue JWT HS256| JWT["Session JWT Token"]
    JWT -->|Bearer Session Token| GW
```

### A. Ephemeral Handshake Token (PR-SEC-1)
* **Tujuan**: Memungkinkan peluncuran otomatis browser dari CLI (`agy studio`) tanpa memaksa operator mengetik kata sandi berulang kali setiap kali terminal baru dibuka.
* **Penyimpanan**: `.aegis/run/gateway.token` (permissions `0600`).
* **Masa Hidup**: Seumur hidup proses server Django Gateway; dihapus saat server dimatikan secara aman (*zero-zombie*).

### B. Session JWT Token (PR-SEC-2)
* **Tujuan**: Sesi operator lokal yang terverifikasi melalui kata sandi.
* **Payload**:
  ```json
  {
    "sub": "local-operator",
    "email": "operator@aegis.local",
    "name": "Local Operator",
    "iat": 1728384000,
    "exp": 1728988800
  }
  ```
* **Masa Berlaku**: Default 7 hari (`AEGIS_AUTH_TOKEN_EXPIRY = 604800` detik), dapat dikonfigurasi melalui `.env`.

---

## 3. Alur Verifikasi & Manajemen Kata Sandi

### Kebijakan Kata Sandi:
* **Panjang Minimal**: 6 karakter.
* **Panjang Maksimal**: 128 karakter.
* **Karakter yang Diizinkan**: Teks bebas alfanumerik dan simbol (misal `admin123`, `sandiRahasia!`).

### Spesifikasi Kriptografi (`web/django_app/api/auth.py`):
1. **Derivasi Hash**:
   $$\text{Hash} = \text{PBKDF2-HMAC-SHA256}(\text{Password}, \text{Salt}, \text{iterations}=100\,000)$$
2. **Salt**: 16-byte acak via `secrets.token_bytes(16)`.
3. **Verifikasi Waktu-Konstan**:
   Menggunakan `hmac.compare_digest(computed_hash, stored_hash)` untuk memitigasi serangan analisis waktu (*timing attack*).

### Penulisan Atomik Berkas:
Untuk mencegah kerusakan data (*partial writes*) saat disk crash:
1. Data ditulis ke berkas temporer `.aegis/.auth_<random>.tmp`.
2. Izin berkas disetel ke `0o600`.
3. Berkas diganti secara atomik (`replace`) ke `.aegis/auth.json`.

---

## 4. Batas Keamanan Terminal & Peramban (PR-SEC-2b Track)

### Ancaman: Drive-by Cross-Origin RCE via Dev Runner
Ketika operator menjalankan server pengembangan (misal `npm run dev` atau `uvicorn`) di terminal AegisCode, runner dapat mencetak URL seperti `http://localhost:5173`. Jika proyek memuat dependensi pihak ketiga yang mengeksploitasi celah browser, peramban dapat diarahkan ke situs penyerang yang mencoba mengirimkan *drive-by request* balik ke Gateway internal AegisCode (`http://localhost:8478`).

### Mitigasi Sisi Klien (Terminal Link Sandbox):
Pada [web/frontend/src/components/terminal/TerminalView.vue](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/web/frontend/src/components/terminal/TerminalView.vue):
1. **Filter Protokol Ketat**: Hanya protokol `http:` dan `https:` yang diizinkan untuk dibuka. Protokol berbahaya (`javascript:`, `data:`, `file:`, `blob:`) otomatis diblokir.
2. **Isolasi Referensi DOM**:
   Tautan dibuka di tab baru dengan proteksi:
   ```javascript
   const newWindow = window.open(parsed.href, "_blank", "noopener,noreferrer");
   if (newWindow) {
     newWindow.opener = null;
   }
   ```
   Hal ini memutus hubungan referensi `window.opener` sehingga tab dev server yang dibuka tidak memiliki hak akses balik ke memori, DOM, atau `localStorage` AegisCode Studio.

### Mitigasi Sisi Server (Boundary Guard):
1. **Pemeriksaan Header Mutatif**:
   Endpoint mutatif (`POST`, `PUT`, `DELETE`) memeriksa header `Origin` dan `Sec-Fetch-Site`. Permintaan berlabel `Sec-Fetch-Site: cross-site` ditolak HTTP 403 Forbidden.
2. **Pencabutan `@csrf_exempt` Blanket**:
   Endpoint eksekusi terminal dan perintah sistem dilindungi otentikasi wajib.

---

## 5. Prosedur Darurat & Reset Kata Sandi

Jika operator lupa kata sandi atau mengalami penguncian sesi lokal:

### Opsi 1: Override via Variabel Lingkungan (Prioritas Tertinggi)
Tambahkan variabel `AEGIS_PASSWORD` pada berkas `.env` di root repositori:
```env
AEGIS_PASSWORD=sandiBaruAnda123
```
*Efek*: Gateway langsung memprioritaskan nilai variabel lingkungan ini di atas berkas `.aegis/auth.json`. Anda dapat langsung masuk menggunakan sandi baru tersebut.

### Opsi 2: Reset Berkas Kredensial Lokal
Jalankan perintah penghapusan berkas otentikasi dari terminal host:
```bash
rm .aegis/auth.json
```
*Efek*: Status konfigurasi kembali ke `has_password: false` (First-Run Fresh State). Muat ulang halaman web studio, dan antarmuka akan langsung menyajikan formulir **Buat Kata Sandi Baru**.

---

## 6. Struktur Titik Akhir (Endpoints) Otentikasi

| Metode | Jalur | Deskripsi | Status Respon |
|---|---|---|---|
| `GET` | `/api/auth/status` | Pengecekan status konfigurasi sandi & sesi | `200 OK` |
| `POST` | `/api/auth/login` | Verifikasi kata sandi & penerbitan JWT | `200 OK` / `401 Unauthorized` |
| `POST` | `/api/auth/setup` | Inisialisasi kata sandi pertama kali | `200 OK` / `403 Forbidden` (jika sudah ada) |
| `GET` | `/api/auth/me` | Membaca profil operator terotentikasi | `200 OK` / `401 Unauthorized` |
| `POST` | `/api/auth/logout` | Pembersihan sesi di sisi klien/server | `200 OK` |
| `WS` | `/ws/terminal/` | PTY WebSocket dengan guard token & origin | `Close 4001` (tanpa token) / `Close 4003` (origin asing) |

---

## 7. Rujukan Pengujian & Verifikasi

Suite pengujian keamanan terpusat pada:
* **`tests/test_pin_auth.py`**: Uji unit kriptografi hash PBKDF2, aturan minimal 6 karakter, endpoint setup, login, status, dan isolasi izin berkas `0o600`.
* **`tests/test_auth_boundary.py`**: Uji batas perimeter HTTP dan WebSocket Channels (menolak request tanpa token meski dari IP loopback, menolak origin asing).
* **`web/frontend/src/authService.test.mjs`**: Uji unit client auth frontend (penyimpanan token, login password, verifikasi sesi).
