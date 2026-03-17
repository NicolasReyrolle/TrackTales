"""Protocol for UI state assertion functions."""

from typing import Any, Protocol

from nicegui.testing import UserInteraction


class StateAssertion(Protocol):
    """Protocol for UI state assertion functions."""

    def __call__(
        self,
        interaction: UserInteraction[Any],
        enabled: bool | None = None,
        visible: bool | None = None,
    ) -> None: ...
