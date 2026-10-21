"""Configured USD estimates; never silently pretend an unknown price is zero."""

import math

from app.config import get_settings


def estimate_cost(input_tokens: int, output_tokens: int) -> float | None:
    settings = get_settings()
    if (
        settings.parser_input_usd_per_million is None
        or settings.parser_output_usd_per_million is None
        or not math.isfinite(settings.parser_input_usd_per_million)
        or not math.isfinite(settings.parser_output_usd_per_million)
    ):
        return None
    return round(
        (
            input_tokens * settings.parser_input_usd_per_million
            + output_tokens * settings.parser_output_usd_per_million
        )
        / 1_000_000,
        8,
    )
