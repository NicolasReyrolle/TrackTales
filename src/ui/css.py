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

#: Full-width row for warning badges; wraps on narrow screens.
ROW_WARNING_CLASSES = "w-full items-center justify-center gap-2 flex-wrap"

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

#: Column wrapping a single range selector (takes equal share of available width).
RANGE_SELECTOR_COLUMN_CLASSES = "flex-col w-full gap-1 flex-1"

#: Row that holds the two side-by-side range selectors with spacing.
RANGE_SELECTORS_ROW_CLASSES = "w-full gap-8 q-pb-sm"

#: Label shown above a range slider.
RANGE_LABEL_CLASSES = "text-sm text-gray-500"

# ---------------------------------------------------------------------------
# Labels / typography
# ---------------------------------------------------------------------------

#: Muted small label (status text, helper text).
LABEL_MUTED_CLASSES = "text-sm text-gray-500"

#: Warning badge used to flag non-physical model outputs.
WARNING_BADGE_CLASSES = "font-medium"

#: Quasar badge props for warning emphasis.
WARNING_BADGE_PROPS = "color=orange-8 text-color=white"

#: Muted small label used as a section heading (uppercase + self-centred).
LABEL_SECTION_CLASSES = "text-sm text-gray-500 uppercase self-center"

#: Small muted uppercase label used inside menus/dialogs as a section heading.
PREF_SECTION_LABEL_CLASSES = "text-sm text-gray-500 uppercase px-4 py-1"

#: Preference menu item — prevents the checkmark prefix from wrapping onto a separate line.
PREF_MENU_ITEM_CLASSES = "whitespace-nowrap"

#: Uppercase label used inside cards and chart headers.
LABEL_UPPERCASE_CLASSES = "text-sm text-gray-500 uppercase"

# ---------------------------------------------------------------------------
# Stat cards (KPI tiles)
# ---------------------------------------------------------------------------

#: Stat-card container dimensions and centring.
STAT_CARD_CLASSES = "w-40 h-24 items-center justify-center shadow-sm"

#: Additional classes for stat cards that are clickable actions.
STAT_CARD_CLICKABLE_CLASSES = "cursor-pointer hover:shadow-md transition-shadow"

#: Keyboard/ARIA props for clickable stat cards.
STAT_CARD_CLICKABLE_PROPS = "tabindex=0 role=button"

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

#: Row inside a chart card: title label on the left, action button on the right.
CHART_HEADER_ROW_CLASSES = "w-full justify-between items-center"

#: Dense flat round button for compact icon actions inside chart cards.
BUTTON_DENSE_PROPS = "flat round dense"

#: Dense flat table props for compact read-only tables (e.g. the splits table in the modal).
TABLE_DENSE_FLAT_PROPS = "dense flat"

#: Card inside the fullscreen dialog: fills the dialog area as a flex column so
#: the header keeps its natural height and the chart can grow to fill the rest.
CHART_FULLSCREEN_CARD_CLASSES = "w-screen h-screen flex flex-col chart-fullscreen-card"

#: ECharts element inside the fullscreen dialog: grows to fill remaining height.
ECHART_FULLSCREEN_CLASSES = "w-full flex-1 min-h-0"

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

# ---------------------------------------------------------------------------
# Workout detail modal
# ---------------------------------------------------------------------------

#: Modal card: fixed width (≈ 56 rem / 896 px) with viewport cap for smaller screens.
#: Does not set an explicit height because the tab panels area uses a fixed
#: height (see MODAL_TAB_PANELS_CLASSES), keeping the overall modal size stable
#: when switching tabs.
MODAL_CARD_CLASSES = "w-[56rem] max-w-[95vw]"

#: Tab panels container inside the modal: fixed height so the modal does not
#: resize when switching between Overview, Activity, and Splits tabs.
#: Overflow-y scrolling is enabled so long content (e.g. many splits) can still
#: be reached within the fixed area.
MODAL_TAB_PANELS_CLASSES = "w-full h-[30rem] overflow-y-auto"

#: Centered content column for text-heavy tabs (Overview/Activity) in wide modal.
#: Uses a fixed target width (capped on small screens) so ``mx-auto`` can center it.
MODAL_CENTERED_CONTENT_CLASSES = "w-[42rem] max-w-full mx-auto"

#: Full-width row wrapper that enforces horizontal centering in tab panels.
MODAL_CENTERED_ROW_CLASSES = "w-full justify-center"

#: Modal header row: title on the left, close button on the right.
MODAL_HEADER_ROW_CLASSES = "w-full justify-between items-center"

#: Each field row inside the modal rendered as a centered 2-column grid.
#: ``10rem`` keeps label lengths aligned without truncating common translated labels.
#: ``32rem`` keeps the overall label/value block compact and centered in wide modals.
MODAL_FIELD_ROW_CLASSES = (
    "w-full max-w-[32rem] mx-auto grid grid-cols-[10rem_minmax(0,1fr)] items-baseline gap-x-4"
)

#: Muted label for a field inside the modal (reuses LABEL_MUTED_CLASSES for the base style).
MODAL_FIELD_LABEL_CLASSES = LABEL_MUTED_CLASSES

#: Value text for a field inside the modal.
MODAL_FIELD_VALUE_CLASSES = "text-sm font-medium"

#: Footer row inside the modal: prev button, counter, next button.
MODAL_NAV_ROW_CLASSES = "w-full justify-between items-center q-mt-sm"

#: Navigation counter label ("1 / 42") in the modal footer – same style as LABEL_MUTED_CLASSES.
MODAL_NAV_COUNTER_CLASSES = LABEL_MUTED_CLASSES

#: Compact ``ui.table`` used for the GPS splits in the modal Intervals tab.
MODAL_SPLITS_TABLE_CLASSES = "w-full"

#: Compact ``ui.table`` used for the swimming interval laps in the modal Intervals tab.
MODAL_SWIM_TABLE_CLASSES = "w-full"

#: Fixed-height container for the Leaflet workout-route map in the modal Route tab.
MODAL_ROUTE_MAP_CONTAINER_CLASSES = "w-full workout-route-map-container"

#: Inner HTML map node for Leaflet to mount into (fills the container dimensions).
MODAL_ROUTE_MAP_HTML_CLASSES = "w-full h-full workout-route-map"

#: Fixed-height container for the route profile chart in the modal Profile tab.
MODAL_ROUTE_PROFILE_CONTAINER_CLASSES = "w-full workout-route-profile-container"

#: ECharts node for the route profile chart (fills its container).
MODAL_ROUTE_PROFILE_CLASSES = "w-full h-full workout-route-profile"

#: Compact table for the route-comparison ranking in the modal Comparisons tab.
MODAL_COMPARISON_TABLE_CLASSES = "w-full"

#: Status label showing the user's rank in the Comparisons tab.
MODAL_COMPARISON_RANK_CLASSES = "text-sm font-medium"
