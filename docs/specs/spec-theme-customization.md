# Spec: IDE AEGIS Theme & Appearance Customization System

## Objective
Membangun sistem kustomisasi tema visual dan penampilan antarmuka IDE AEGIS yang fleksibel, terkurasi, dan berorientasi pada ergonomi pengguna. Sistem ini memungkinkan pengguna memilih preset tema populer terkurasi atau membuat palet kustom melalui slider interaktif dengan live preview seketika pada seluruh UI shell IDE, dengan tetap menjamin keterbacaan kode (syntax highlighting) pada Monaco Editor.

### User Stories
1. **Curated Presets**: Sebagai pengguna, saya dapat memilih salah satu dari preset tema populer (*Tokyo Night*, *Nordic/Nord*, *Atom One*, dan *High Contrast*) dalam varian *Dark* atau *Light*, sehingga saya mendapatkan estetika yang konsisten dan teruji secara instan.
2. **Custom Palette Generator**: Sebagai pengguna, saya dapat beralih ke mode *Custom* dan memilih base foundation (*Dark* atau *Light*), lalu mengatur slider untuk *Primary*, *Secondary*, dan *Accent* warna, sehingga antarmuka IDE mencerminkan preferensi warna personal saya.
3. **Live Preview**: Sebagai pengguna, setiap perubahan preset atau pergeseran slider langsung diterapkan secara reaktif ke UI shell (sidebar, panel, drawer, status bar, tabs, buttons, dialogs) tanpa reload halaman.
4. **Code Readability Protection**: Sebagai pengembang, saya ingin sintaks kode di Monaco Editor tetap terbaca jelas dengan kontras yang aman, di mana background/border editor tersinkronisasi dengan tema, tetapi aturan pewarnaan token sintaks tetap mengacu pada preset aman (*Dark*, *Light*, atau *High Contrast*).
5. **Persistence & Reset**: Preferensi tema tersimpan otomatis di `localStorage` per peramban dan dapat dikembalikan ke setelan awal kapan saja melalui tombol *Reset to Default*.

---

## Tech Stack
- **Framework UI**: Vue 3 (Composition API, `<script setup>`)
- **Bundler**: Vite 5
- **Editor**: Monaco Editor (`monaco-editor` ^0.52.2)
- **Styling Architecture**: Vanilla CSS Custom Properties / CSS Variables (`apps/frontend/src/styles/`)
- **Storage**: Browser `localStorage` (SSR-safe wrapper)
- **Test Runner**: Node.js native test runner (`node --test`)

---

## Commands
- **Dev Server**: `npm --prefix apps/frontend run dev`
- **Build Frontend**: `npm --prefix apps/frontend run build`
- **Run Unit Tests**: `npm --prefix apps/frontend test`
- **Targeted Test**: `node --test apps/frontend/tests/themeService.test.mjs`
- **ESM Syntax Verification**: `node --check apps/frontend/src/services/themeService.js`

---

## Project Structure
```
apps/frontend/
├── src/
│   ├── services/
│   │   └── themeService.js             # Core theme registry, presets, palette generation & persistence
│   ├── components/
│   │   └── settings/
│   │       ├── AppearanceSettingsPanel.vue  # Dedicated settings tab UI (presets, sliders, preview, reset)
│   │       └── SettingsView.vue             # Registration of 'appearance' tab & navigation
│   └── styles/
│       ├── base/
│       │   └── variables.css                # Base CSS variables definition
│       └── themes/
│           ├── theme-light.css              # Light foundation variables
│           ├── theme-high-contrast.css      # High contrast dark/light variables
│           └── theme-presets.css            # Preset specific overrides (TokyoNight, Nord, Atom)
└── tests/
    └── themeService.test.mjs                # Unit tests for theme logic, presets, and validation
```

---

## Code Style & Conventions

### 1. Theme Configuration Schema (`themeService.js`)
```javascript
export const THEME_MODES = Object.freeze({
  PRESET: "preset",
  CUSTOM: "custom",
});

export const BASE_FOUNDATIONS = Object.freeze({
  DARK: "dark",
  LIGHT: "light",
});

export const CURATED_PRESETS = Object.freeze({
  TOKYO_NIGHT_DARK: "tokyo-night-dark",
  TOKYO_NIGHT_LIGHT: "tokyo-night-light",
  NORD_DARK: "nord-dark",
  NORD_LIGHT: "nord-light",
  ATOM_DARK: "atom-dark",
  ATOM_LIGHT: "atom-light",
  HIGH_CONTRAST_DARK: "high-contrast-dark",
  HIGH_CONTRAST_LIGHT: "high-contrast-light",
});
```

### 2. Live Dynamic CSS Variables Injection
```javascript
/**
 * Terapkan variabel CSS palet secara langsung ke root document
 * @param {ThemeConfig} config
 */
export function applyThemeConfig(config) {
  if (typeof document === "undefined" || !document.documentElement) return;
  const root = document.documentElement;

  // Set dataset attributes for layout and Monaco synchronization
  root.dataset.theme = config.foundation; // 'dark' | 'light'
  root.dataset.themePreset = config.preset || "";
  root.dataset.themeMode = config.mode; // 'preset' | 'custom'

  if (config.mode === THEME_MODES.CUSTOM && config.customColors) {
    root.style.setProperty("--accent", config.customColors.accent);
    root.style.setProperty("--accent-dim", config.customColors.primary);
    root.style.setProperty("--secondary", config.customColors.secondary);
    // Dynamic derivations for soft highlights
    root.style.setProperty("--accent-soft", hexToRgba(config.customColors.accent, 0.16));
    root.style.setProperty("--border-hover", hexToRgba(config.customColors.accent, 0.4));
  } else {
    // Clear custom override inline styles to allow preset stylesheet rules
    root.style.removeProperty("--accent");
    root.style.removeProperty("--accent-dim");
    root.style.removeProperty("--secondary");
    root.style.removeProperty("--accent-soft");
    root.style.removeProperty("--border-hover");
  }
}
```

---

## Testing Strategy
1. **Unit Testing (`apps/frontend/tests/themeService.test.mjs`)**:
   - Validasi pemuatan nilai awal dari `localStorage` dan fallback default (`aegis-dark`).
   - Verifikasi pemilihan seluruh curated preset (Tokyo Night, Nord, Atom, High Contrast).
   - Validasi struktur mode custom: setting warna primary, secondary, dan accent dengan validasi hex/rgb.
   - Verifikasi fungsi reset to default.
   - Pengujian keamanan SSR (Node.js runtime di mana `window` dan `document` tidak ada atau di-mock).
2. **Build & Bundler Verification**:
   - `npm --prefix apps/frontend run build` harus lulus tanpa bundle error atau unresolvable imports.

---

## Boundaries (Three-Tier System)

### Always Do
- Selalu sediakan fallback yang aman jika `localStorage` kosong, korup, atau tidak dapat diakses.
- Pastikan perubahan tema aman terhadap SSR (selalu periksa `typeof document !== 'undefined'`).
- Jaga kontras teks dengan membatasi kustomisasi slider pada warna aksen/elemen interaktif di atas base foundation yang stabil (Dark/Light).
- Sinkronkan tema Monaco Editor (`aegis-dark`, `aegis-light`, atau `hc-black`) agar background editor cocok dengan tema shell yang dipilih.

### Ask First
- Menambahkan library NPM eksternal baru untuk manipulasi warna (disarankan menggunakan helper utility ringan tanpa bloating bundle).
- Mengubah arsitektur file CSS utama yang mempengaruhi komponen selain theming.

### Never Do
- Memodifikasi token syntax highlighter Monaco secara dinamis per geseran slider warna pengguna (akan memicu kerusakan kontras dan lag performa).
- Menyimpan konfigurasi tema tanpa fallback defensif.

---

## Success Criteria
1. Pengguna dapat memilih 8 preset terkurasi (TokyoNight D/L, Nord D/L, Atom D/L, High Contrast D/L) dari tab Settings > Appearance/Theme dan UI shell langsung berubah seketika.
2. Pengguna dapat memilih mode Custom, memilih base Dark/Light, dan mengatur slider warna Primary, Secondary, dan Accent dengan pembaruan visual langsung (live preview).
3. Monaco Editor menyesuaikan background dan border dengan tema yang dipilih, sementara sintaks kode tetap tajam dan kontras.
4. Preferensi tema tersimpan di `localStorage` dan tetap bertahan setelah halaman direfresh.
5. Tombol "Reset to Default" mengembalikan tampilan ke tema default AEGIS Dark secara mulus.

---

## Open Questions
1. Apakah slider custom lebih disukai menggunakan format Hue slider (0–360° HSL) yang otomatis menghasilkan gradasi harmonis, atau input Color Picker standar HTML5 (`<input type="color">`) yang dilengkapi slider brightness/saturation?
