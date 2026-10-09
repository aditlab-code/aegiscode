# Atomic Tasks: Telegram Companion Refinement

- [x] Task 1: Single-Poller Lock & Notification State in telegramService.js
  - Acceptance: telegramService.js memiliki guard isToggling/inFlightAction untuk mencegah concurrent poller execution, mengembalikan state secara prediktif, dan mengekspor notifikasi feedback.
  - Verify: rtk node --test apps/frontend/tests/*.test.mjs
  - Files: apps/frontend/src/services/telegramService.js

- [x] Task 2: 1-Click Toggle & Toast Banner in AppStatusBar.vue
  - Acceptance: Klik badge Telegram di AppStatusBar berfungsi sebagai toggle On/Off poller tunggal. Jika aktif -> matikan poller + tampilkan toast tanpa modal. Jika standby & paired -> hidupkan poller + tampilkan toast tanpa modal. Jika unpaired -> hidupkan poller + buka modal QR. Jika unconfigured -> buka modal instruksi.
  - Verify: rtk npm --prefix apps/frontend run build
  - Files: apps/frontend/src/components/layout/AppStatusBar.vue

- [x] Task 3: Informational Modal & BotFather Guide in TelegramPairingPopover.vue
  - Acceptance: TelegramPairingPopover menampilkan instruksi step-by-step BotFather & warning .env jika unconfigured, QR code & opsi Telegram Web jika pairing, status poller reaktif, dan 0 hardcoded HEX codes.
  - Verify: rtk grep -rn "#[0-9a-fA-F]\{3,8\}" apps/frontend/src/ | grep "\.vue"
  - Files: apps/frontend/src/components/layout/TelegramPairingPopover.vue

- [x] Task 4: Unit Test & Verification Gates
  - Acceptance: Unit test telegramService.test.mjs menguji lock poller dan transisi state, lolos build npm run build, lolos 100% test suites, dan lolos semua 6 frontend verification gates.
  - Verify: rtk node --test apps/frontend/tests/*.test.mjs && rtk npm --prefix apps/frontend run build
  - Files: apps/frontend/tests/telegramService.test.mjs
