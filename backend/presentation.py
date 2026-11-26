"""User-facing presentation labels.

Technical identifiers remain available in the internal payloads and API
schemas. This module only provides the labels shown in reports and screens.
"""

from __future__ import annotations

ENGINE_DISPLAY_NAME = "SEGYRCALC \u2013 Moteur de calcul \u00e9lectrique"


def engine_display_name(technical_facade: str | None = None) -> str:
    """Return the user-facing engine name, keeping the technical id internal."""
    return ENGINE_DISPLAY_NAME


__all__ = ["ENGINE_DISPLAY_NAME", "engine_display_name"]
