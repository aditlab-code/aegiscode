# Rencana Arsitektur & Implementasi: Kustomisasi Tema IDE AEGIS

## Ringkasan Fitur
Menambahkan sistem kustomisasi tema visual terpadu pada IDE AEGIS yang mencakup:
1. **Curated Presets**: Tokyo Night (Dark/Light), Nordic/Nord (Dark/Light), Atom One (Dark/Light), dan High Contrast (Dark/Light).
2. **Custom Palette Generator**: Pilihan base foundation (*Dark* atau *Light*) dengan slider interaktif kanal RGB (Red 0–255, Green 0–255, Blue 0–255) untuk *Primary*, *Secondary*, dan *Accent*.
3. **Live Preview**: Reaktivitas instan pada variabel CSS yang mempengaruhi seluruh UI shell IDE (sidebar, drawer, panel, status bar, tabs, buttons).
4. **Monaco Editor Guardrail**: Menyelaraskan background/border editor ke tema terpilih, sementara token pewarnaan sintaks kode tetap berpegang pada preset aman (*Dark*, *Light*, *High Contrast*).
5. **UI & Settings Integration**: Panel baru `AppearanceSettingsPanel.vue` di tab `appearance` pada modal `SettingsView.vue` dengan persistensi `localStorage` dan tombol `Reset to Default`.

---

## Dependency Graph (Bottom-Up)
```
1. Base Styles & CSS Variables (apps/frontend/src/styles/themes/theme-presets.css)
       │ - Definisi token warna preset (TokyoNight, Nord, Atom, High Contrast)
       │ - Integrasi ke apps/frontend/src/styles.css
       ▼
2. Theme Service Layer (apps/frontend/src/services/themeService.js)
       │ - Konstanta THEME_MODES, BASE_FOUNDATIONS, CURATED_PRESETS, DEFAULT_CUSTOM_COLORS
       │ - Utility RGB math (rgbToHex, hexToRgb, hexToRgba)
       │ - Evaluasi & penerapan CSS custom properties secara dinamis ke :root
       │ - Sinkronisasi dataset Monaco editor ([data-theme], [data-theme-preset])
       │ - Backward-compatible wrapper untuk createThemeState()
       │ - Persistensi & migrasi localStorage aman SSR
       ▼
3. Unit Testing Layer (apps/frontend/tests/themeService.test.mjs)
       │ - Test suite pengujian preset, kalkulasi slider RGB, persistensi, & SSR safety
       ▼
4. UI Settings Component (apps/frontend/src/components/settings/AppearanceSettingsPanel.vue)
       │ - Grid kartu Curated Presets dengan visual badges
       │ - Kontrol mode Custom: toggle base Dark/Light & 3 slider RGB (R, G, B: 0–255)
       │ - Mini Live Preview mockup (sidebar slice, button, active tab, status bar)
       │ - Tombol Reset to Default
       ▼
5. Settings Modal Integration (apps/frontend/src/components/settings/SettingsView.vue)
       │ - Penambahan tab navigasi "Appearance / Theme"
       │ - Mount AppearanceSettingsPanel pada activeTab === 'appearance'
       ▼
6. E2E & Build Verification
       │ - Eksekusi seluruh node --test suite (126+ tests)
       │ - Eksekusi npm run build (verifikasi bundler Vite)
```

---

## Vertical Slices

### Slice 1: Core Theme Engine, Presets CSS, & Unit Tests
- Memperluas `themeService.js` dengan dukungan preset dan custom RGB slider math.
- Membuat `theme-presets.css` berisi definisi palet Tokyo Night, Nord, Atom, High Contrast Dark/Light.
- Menulis unit test lengkap di `apps/frontend/tests/themeService.test.mjs` untuk memverifikasi logika sebelum UI dibuat.

### Slice 2: Appearance Settings Panel UI
- Membangun `AppearanceSettingsPanel.vue` dengan preset selector, kontrol slider RGB 3-channel, swatch visual, live preview mockup, dan aksi reset.

### Slice 3: Integration ke SettingsView & Verifikasi Menyeluruh
- Mendaftarkan tab `appearance` pada `SettingsView.vue`.
- Menghubungkan reactivity state tema dengan `App.vue` dan Monaco editor dataset.
- Menjalankan build Vite dan seluruh suite regression tests.
