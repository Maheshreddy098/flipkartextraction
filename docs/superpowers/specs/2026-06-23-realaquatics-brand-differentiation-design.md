# Real Aquatics Brand Differentiation

**Date:** 2026-06-23  
**Scope:** `realaquatics-frontend` only — WowPets untouched  
**Goal:** Make Real Aquatics portal visually distinct from WowPets so users cannot confuse the two

---

## Problem

Both portals are Vue 3 + Tailwind SPAs built from the same codebase. Current RA portal uses identical colors (blue primary, gray-900 sidebar) and layout as WowPets. Only the title text differs.

---

## Design Decisions

| Decision | Choice |
|----------|--------|
| Color theme | Teal/cyan (aquatics) |
| Sidebar style | Deep teal (`teal-900`) |
| Login page | Ocean gradient (`teal-600 → cyan-400`) |
| Sidebar logo | SVG wave icon + "Real Aquatics 3PL" text |

---

## Changes — 3 Files

### 1. `realaquatics-frontend/tailwind.config.js`

Replace `primary` palette (currently blue) with full teal scale:

```js
primary: {
  50:  '#f0fdfa',
  100: '#ccfbf1',
  200: '#99f6e4',
  300: '#5eead4',
  400: '#2dd4bf',
  500: '#14b8a6',
  600: '#0d9488',
  700: '#0f766e',
  800: '#115e59',
  900: '#134e4a',
}
```

Effect: all `primary-*` Tailwind classes across components auto-switch to teal — buttons, focus rings, status badges, active states.

### 2. `realaquatics-frontend/src/layouts/AppLayout.vue`

Three targeted changes:

- **Sidebar bg:** `bg-gray-900` → `bg-teal-900`
- **Active nav item:** `bg-gray-800 text-white border-r-2 border-blue-500` → `bg-teal-800 text-white border-r-2 border-teal-400`
- **Sidebar header:** Add SVG wave icon before "Real Aquatics 3PL" title text

SVG wave icon (inline, white, ~20px):
```html
<svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-teal-300 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
    d="M3 15c1.5-2 3-2 4.5 0S11 17 12.5 15 15 13 16.5 15 19 17 20.5 15 22 13 23 13" />
</svg>
```

### 3. `realaquatics-frontend/src/pages/Login.vue`

Two targeted changes:

- **Page background:** `bg-gradient-to-br from-blue-50 to-indigo-100` → `bg-gradient-to-br from-teal-600 to-cyan-400`
- **Button + focus rings:** all `blue-*` → `teal-*` (button `bg-blue-600 hover:bg-blue-700`, input `focus:ring-blue-500 focus:border-blue-500`)

---

## What Does NOT Change

- All component logic, API calls, routing
- WowPets frontend — zero files touched
- Page structure, layout, nav items
- Font, spacing, shadows

---

## After Implementation

Run `npm run build` in `realaquatics-frontend/` to rebuild assets and update `www/realaquatics.html`.
