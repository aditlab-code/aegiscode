# Daftar Tugas Atomik (Todo): Kustomisasi Tema IDE AEGIS

- [x] Task 1: Buat stylesheet `theme-presets.css` dan daftarkan di `styles.css`
  - Acceptance: Variabel CSS terdefinisi untuk seluruh curated preset: Tokyo Night (Dark/Light), Nord (Dark/Light), Atom (Dark/Light), dan High Contrast (Dark/Light).
  - Verify: `npm --prefix apps/frontend run build`.
  - Files: `apps/frontend/src/styles/themes/theme-presets.css`, `apps/frontend/src/styles.css`.

- [x] Task 2: Perluas `themeService.js` dengan engine preset, slider RGB kustom, dan sinkronisasi Monaco
  - Acceptance: Fungsi `setPreset()`, `setCustomColors()`, `applyThemeConfig()`, `resetTheme()`, dan `createThemeState()` mendukung preset dan custom RGB slider dengan reaktivitas instan dan backward-compatibility penuh.
  - Verify: `node --check apps/frontend/src/services/themeService.js`.
  - Files: `apps/frontend/src/services/themeService.js`.

- [x] Task 3: Tulis unit test suite di `apps/frontend/tests/themeService.test.mjs`
  - Acceptance: Menguji inisialisasi default, pemilihan curated preset, kalkulasi slider RGB, persistensi storage, reset default, dan backward compatibility dengan suite `services.test.mjs`.
  - Verify: `node --test apps/frontend/tests/themeService.test.mjs apps/frontend/tests/services.test.mjs`.
  - Files: `apps/frontend/tests/themeService.test.mjs`.

- [x] Task 4: Bangun komponen UI `AppearanceSettingsPanel.vue`
  - Acceptance: Merender kartu curated presets, selector base Dark/Light, 3-channel slider RGB (Red, Green, Blue: 0–255) per warna (Primary, Secondary, Accent), live swatch preview, dan tombol reset.
  - Verify: `npm --prefix apps/frontend run build`.
  - Files: `apps/frontend/src/components/settings/AppearanceSettingsPanel.vue`.

- [x] Task 5: Integrasikan tab Appearance / Theme ke dalam `SettingsView.vue`
  - Acceptance: Tab "Appearance" muncul di navigasi SettingsView, me-render `AppearanceSettingsPanel`, dan perubahan warna langsung memantulkan live preview ke seluruh UI shell.
  - Verify: `npm --prefix apps/frontend run build`.
  - Files: `apps/frontend/src/components/settings/SettingsView.vue`.

- [x] Task 6: Verifikasi menyeluruh end-to-end dan regression testing
  - Acceptance: Seluruh 130 unit tests frontend lulus tanpa error, build bundle Vite bersih, transisi tema lancar.
  - Verify: `npm --prefix apps/frontend test && npm --prefix apps/frontend run build`.
  - Files: Seluruh berkas terkait.

- [x] Task 7: Koreksi Pemetaan CSS Variables & Desain Unified Panel
  - Acceptance: Primary color terhubung ke `--accent`, `--primary`, `--border-hover`, `--selection`; Secondary color terhubung ke `--secondary`, `--text-dim`, `--muted`, `--btn-outline-muted`; struktur komponen `AppearanceSettingsPanel.vue` diselaraskan ke `<AppCard variant="panel" class="settings-panel">` dengan header action dan zero emoji (100% inline SVG).
  - Verify: `npm --prefix apps/frontend test && npm --prefix apps/frontend run build`.
  - Files: `apps/frontend/src/services/themeService.js`, `apps/frontend/src/components/settings/AppearanceSettingsPanel.vue`.

