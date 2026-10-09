# Implementation Plan: Refinement Telegram Companion & AppStatusBar Toggle UX

## Context & Objectives
Mengubah interaksi Telegram Companion pada `apps/frontend` menjadi arsitektur **toggle sakelar 1-klik** yang efisien dan deterministik:
- Tombol Companion di `AppStatusBar.vue` dapat langsung menyalakan/mematikan bot poller dengan notifikasi toast tanpa membuka modal saat akun sudah terhubung atau aktif.
- Single-poller lock pada `telegramService.js` untuk mencegah benturan race-condition atau pembuatan instansi poller berlebih.
- Modal `TelegramPairingPopover.vue` diperkaya sebagai pusat informasi: panduan langkah `@BotFather`, warning konfigurasi `.env`, QR Code, dan tautan langsung ke Telegram Web.
- Menjamin alur kerja komunikasi 2 arah LLM yang sudah berjalan tetap terlindungi tanpa fallback/callback yang menyimpang.

---

## Dependency Graph & Architecture

```
telegramService.js (Single-Poller Lock, Reactive Status, Toast Hook)
      ▲
      │
      ├── AppStatusBar.vue (1-Click Toggle Coordinator, Status Badge, Toast Notification)
      │
      └── TelegramPairingPopover.vue (BotFather Guide, .env Warning Banner, QR Code, Web Link)
```

---

## Detailed Task Breakdown

### Task 1: Single-Poller Lock & Notification State in `telegramService.js`
- Tambahkan proteksi penguncian aksi *in-flight* (`isToggling` / request lock) pada `startTelegramPoller` dan `stopTelegramPoller` agar tidak ada pemanggilan ganda jika tombol diklik berulang kali.
- Sediakan state reactive `statusNotification` (message, type) untuk menampung feedback feedback operasional.
- Pastikan method `startTelegramPoller` dan `stopTelegramPoller` memperbarui status secara sinkron.
- Files: `apps/frontend/src/services/telegramService.js`

### Task 2: 1-Click Toggle & Toast Banner in `AppStatusBar.vue`
- Refactor handler `@click` pada badge Telegram Companion:
  - Jika `!telegramStatus.configured`: tampilkan modal instruksi (`showTelegramPopover = true`).
  - Jika `telegramStatus.is_running`: hentikan poller (`stopTelegramPoller()`), tampilkan notifikasi toast di status bar bahwa bot standby, jangan buka modal.
  - Jika `!telegramStatus.is_running`:
    - Jika `telegramStatus.is_paired`: aktifkan poller (`startTelegramPoller()`), tampilkan notifikasi toast bahwa bot aktif mendengarkan, jangan buka modal.
    - Jika `!telegramStatus.is_paired`: aktifkan poller (`startTelegramPoller()`), set status menjadi pairing (*idle on pairing*), dan buka modal (`showTelegramPopover = true`) untuk scan QR / link web.
- Tambahkan elemen floating toast feedback non-intrusif di atas status bar untuk memberi konfirmasi visual saat status poller berubah.
- Perbarui tooltip badge agar informatif dan jelas.
- Files: `apps/frontend/src/components/layout/AppStatusBar.vue`

### Task 3: Informational Modal & BotFather Guide in `TelegramPairingPopover.vue`
- Perbarui tampilan modal saat status `!status.configured`:
  - Tampilkan banner peringatan (*warning*) jelas bahwa bot belum dapat diaktifkan sebelum `TELEGRAM_BOT_TOKEN` dan ID terdaftar (`TELEGRAM_ALLOWED_USER_IDS`) disetel di `.env`.
  - Berikan panduan bertahap pembuatan bot via `@BotFather` (`/newbot`, nama bot, token API).
- Perbarui tampilan QR & link:
  - Pastikan tidak perlu klik pemicu aplikasi desktop; berikan opsi "Buka di Telegram Web" langsung ke peramban.
  - Tampilkan status poller reactively.
- Patuhi standar token CSS: tidak ada hardcoded HEX di `<style>` atau template `.vue`.
- Files: `apps/frontend/src/components/layout/TelegramPairingPopover.vue`

### Task 4: Unit Test & Verification Gates
- Tulis unit test untuk `telegramService.js` dan alur single-poller di `apps/frontend/tests/telegramCompanion.test.mjs`.
- Jalankan static analysis pemeriksaan HEX code, data-theme, dan inline color.
- Jalankan build `npm run build` dan test suite `node --test`.
- Files: `apps/frontend/tests/telegramCompanion.test.mjs`
