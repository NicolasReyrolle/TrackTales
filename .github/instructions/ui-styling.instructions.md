---
description: "Use when styling UI components, adding CSS/Tailwind/Quasar classes, or editing src/ui/. Covers the css.py single source of truth and ECharts requirements."
applyTo: "src/ui/**"
excludeAgent: "code-review"
---

# CSS and Styling

- All Tailwind/Quasar class strings and NiceGUI `.props()` strings live in `src/ui/css.py` as named constants (`*_CLASSES` / `*_PROPS`). Import and use them instead of writing inline string literals.
- `resources/style.css` is the single global stylesheet. Add new custom CSS class selectors to `resources/style.css`. Add new Tailwind/Quasar class strings and NiceGUI props as `*_CLASSES` / `*_PROPS` constants in `src/ui/css.py`. Every class added must be documented with a comment explaining its purpose.
- Inline styles are forbidden. The only exception is a value computed at runtime (for example, chart or drag coordinates) that cannot be expressed as a class in `resources/style.css`. For each surviving inline style, add a comment in the template or Python file explaining why it is required. Also add a comment-only entry in `resources/style.css` that names the file and component where the inline style is used. Do not create a CSS class for it.
- ECharts (`ui.echart`) must include `"backgroundColor": "transparent"` in every chart config so the card background (which adapts to dark mode via CSS) shows through correctly.
