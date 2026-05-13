"""Workout detail modal public facade.

This package-level module intentionally keeps logic minimal and re-exports the
modal setup API plus test-referenced helpers from dedicated implementation modules.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from ui import helpers as _helpers
from ui.workout_detail_modal import builder as _builder
from ui.workout_detail_modal import routes as _routes

ui = _builder.ui
background_tasks = _builder.background_tasks
t = _builder.t


def _translate_func() -> Callable[..., str]:
    """Return the current translation callable with a narrow return type."""
    return cast(Callable[..., str], t)

_format_split_pace = _helpers._format_split_pace
_format_split_speed = _helpers._format_split_speed
_format_elevation_change = _helpers._format_elevation_change

create_workout_detail_modal = _builder.create_workout_detail_modal
_FIELD_DISPLAY = _builder._FIELD_DISPLAY
_RUNNING_FIELD_DISPLAY = _builder._RUNNING_FIELD_DISPLAY
_WALKING_FIELD_DISPLAY = _builder._WALKING_FIELD_DISPLAY
_HIKING_FIELD_DISPLAY = _builder._HIKING_FIELD_DISPLAY
_CYCLING_FIELD_DISPLAY = _builder._CYCLING_FIELD_DISPLAY
_ACTIVITY_FIELD_KEYS = _builder._ACTIVITY_FIELD_KEYS
_build_swim_display_rows = _builder._build_swim_display_rows
_format_split_rows = _builder._format_split_rows
_compute_splits_lazy = _builder._compute_splits_lazy
_get_row_routes = _builder._get_row_routes
_row_has_activity_data = _builder._row_has_activity_data
_row_has_swim_laps = _builder._row_has_swim_laps
_fit_route_bounds_after_init = _routes._fit_route_bounds_after_init


def _build_route_profile_chart_config(routes: list[Any]) -> dict[str, Any]:
    """Build route profile chart config using the current translation context."""
    return _routes._build_route_profile_chart_config_with_translate(
        routes, translate=_translate_func()
    )


def _do_refresh_route_tab(
    no_route_label: Any,
    route_map: Any,
    row: dict[str, Any],
) -> None:
    """Update the Route tab map with plain route polylines."""
    _routes._do_refresh_route_tab(
        no_route_label,
        route_map,
        row,
        fit_bounds_scheduler=background_tasks.create,
        translate=_translate_func(),
    )


def _do_refresh_route_profile_tab(
    no_route_label: Any,
    route_profile_chart: Any,
    row: dict[str, Any],
) -> None:
    """Update the Profile tab chart with altitude and pace series."""
    _routes._do_refresh_route_profile_tab(
        no_route_label,
        route_profile_chart,
        row,
        translate=_translate_func(),
    )
