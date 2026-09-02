---
description: "Use when styling UI components, adding CSS/Tailwind/Quasar classes, or editing src/ui/. Covers the css.py single source of truth and ECharts requirements."
applyTo: "src/ui/**"
---

# CSS and Styling

- All Tailwind/Quasar class strings and NiceGUI `.props()` strings live in `src/ui/css.py` as named constants (`*_CLASSES` / `*_PROPS`). Import and use them instead of writing inline string literals.
- `resources/style.css` is the single global stylesheet. Add new CSS classes there rather than using `.style(...)` inline styles. Every class added must be documented with a comment explaining its purpose.
- Inline styles (`style="..."` in Vue templates or `.style(...)` in Python) are forbidden unless strictly unavoidable; document any surviving inline styles with a comment in both the template and `style.css`.
- ECharts (`ui.echart`) must include `"backgroundColor": "transparent"` in every chart config so the card background (which adapts to dark mode via CSS) shows through correctly.
