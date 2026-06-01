"""Workout detail modal public facade."""

from __future__ import annotations

from ui import helpers as _helpers
from ui.workout_detail_modal import builder as _builder
from ui.workout_detail_modal import routes as _routes

ui = _builder.ui
background_tasks = _builder.background_tasks
t = _builder.t

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
_ensure_row_heart_rate_enriched = _builder._ensure_row_heart_rate_enriched
_get_row_routes = _builder._get_row_routes
_row_has_activity_data = _builder._row_has_activity_data
_row_has_swim_laps = _builder._row_has_swim_laps
_fit_route_bounds_after_init = _routes._fit_route_bounds_after_init
_build_route_profile_chart_config = _routes._build_route_profile_chart_config
_do_refresh_route_tab = _routes._do_refresh_route_tab
_do_refresh_route_profile_tab = _routes._do_refresh_route_profile_tab
