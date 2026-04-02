"""Centralized CSS class and props constants for Apple Health Analyzer UI.

All Tailwind/Quasar class strings and NiceGUI props strings used across UI
modules are defined here as named constants.  Keeping them in one place makes
it easy to spot inconsistencies, rename a class globally, and prevents magic
strings from spreading across multiple files.

Convention
----------
- ``*_CLASSES``  – value passed to ``.classes(...)`` on a NiceGUI element.
- ``*_PROPS``    – value passed to ``.props(...)`` on a NiceGUI element.
  The value is a space-separated list of Quasar property names/values
  exactly as NiceGUI's ``.props()`` expects them (e.g. ``"flat round"``).
"""

# ---------------------------------------------------------------------------
# Layout / structural
# ---------------------------------------------------------------------------

#: Full-width row with vertically-centred children.
ROW_FULL_ITEMS_CLASSES = "w-full items-center"

#: Full-width row with children centred both axes and a horizontal gap.
ROW_CENTERED_CLASSES = "w-full justify-center gap-4"

#: Full-width row with centred children and Quasar spacing (used for loaders).
ROW_LOADING_CLASSES = "w-full items-center justify-center q-gutter-sm"

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

#: Header bar: space-between layout with a bottom border.
HEADER_CLASSES = "items-center justify-between border-b"

#: App logo image size.
APP_LOGO_CLASSES = "w-16 h-16"

#: App title label.
APP_TITLE_CLASSES = "font-bold text-xl"

# ---------------------------------------------------------------------------
# Buttons
# ---------------------------------------------------------------------------

#: Flat + round button style (dark-mode toggle, language selector, etc.).
BUTTON_FLAT_ROUND_PROPS = "flat round"

# ---------------------------------------------------------------------------
# Form / inputs
# ---------------------------------------------------------------------------

#: Input field that stretches to fill available row space.
INPUT_GROW_CLASSES = "flex-grow"

#: Medium-width input (e.g. date-range text input).
INPUT_MEDIUM_CLASSES = "w-50"

#: Small-width input (e.g. activity-type select).
INPUT_SMALL_CLASSES = "w-40"

#: Row containing a date range input and its popup picker.
DATE_ROW_CLASSES = "items-center gap-2"

#: Row containing a range slider and its label.
RANGE_ROW_CLASSES = "flex-col w-full gap-1"

#: Label shown above a range slider.
RANGE_LABEL_CLASSES = "text-sm text-gray-500"

# ---------------------------------------------------------------------------
# Labels / typography
# ---------------------------------------------------------------------------

#: Muted small label (status text, helper text).
LABEL_MUTED_CLASSES = "text-sm text-gray-500"

#: Muted small label used as a section heading (uppercase + self-centred).
LABEL_SECTION_CLASSES = "text-sm text-gray-500 uppercase self-center"

#: Uppercase label used inside cards and chart headers.
LABEL_UPPERCASE_CLASSES = "text-sm text-gray-500 uppercase"

# ---------------------------------------------------------------------------
# Stat cards (KPI tiles)
# ---------------------------------------------------------------------------

#: Stat-card container dimensions and centring.
STAT_CARD_CLASSES = "w-40 h-24 items-center justify-center shadow-sm"

#: Small muted uppercase label inside a stat card.
STAT_CARD_LABEL_CLASSES = "text-xs text-gray-500 uppercase"

#: Row that aligns the value and unit on the baseline.
STAT_CARD_VALUE_ROW_CLASSES = "items-baseline gap-1"

#: Large bold numeric value inside a stat card.
STAT_CARD_VALUE_CLASSES = "text-xl font-bold"

#: Tiny muted unit suffix inside a stat card.
STAT_CARD_UNIT_CLASSES = "text-xs text-gray-400"

# ---------------------------------------------------------------------------
# Chart cards
# ---------------------------------------------------------------------------

#: Chart card container dimensions and centring.
CHART_CARD_CLASSES = "w-100 h-80 items-center justify-center shadow-sm"

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

#: Full-width tab bar or tab-panel container.
TABS_FULL_CLASSES = "w-full"

# ---------------------------------------------------------------------------
# Tables / best segments
# ---------------------------------------------------------------------------

#: Muted label when content is not yet available.
LABEL_EMPTY_STATE_CLASSES = "text-gray-500"

#: Full-width table.
TABLE_FULL_CLASSES = "w-full"
