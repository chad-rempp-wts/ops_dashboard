"""Number formatting that does not depend on the process locale."""

from __future__ import annotations

from typing import Optional


def format_number(value: Optional[float], fmt: str) -> str:
    if value is None or fmt == "text":
        return "No sample" if fmt != "text" else ""
    if fmt == "int":
        return f"{int(round(float(value))):,}"
    if fmt == "pct1":
        return f"{float(value):.1f}%"
    if fmt == "pct2":
        return f"{float(value):.2f}%"
    if fmt == "pct3":
        return f"{float(value):.3f}%"
    if fmt == "ms":
        return f"{int(round(float(value))):,} ms"
    return f"{float(value):.4f}"


def json_number(value: Optional[float]):
    if value is None:
        return None
    rounded = round(float(value), 4)
    if rounded.is_integer():
        return int(rounded)
    return rounded


def nice_ceil(value: float) -> float:
    if value <= 0:
        return 1
    import math

    magnitude = 10 ** math.floor(math.log10(value))
    for step in (1, 2, 2.5, 5, 10):
        candidate = step * magnitude
        if candidate + (magnitude * 1e-9) >= value:
            return float(candidate if candidate != int(candidate) else int(candidate))
    return float(10 * magnitude)


def chart_ymax(peaks: list, limits: list, scale: str) -> float:
    if scale == "percent100":
        return 100
    top = 0.0
    for value in list(peaks) + list(limits):
        if value is not None and float(value) > top:
            top = float(value)
    if top <= 0:
        return 1
    return nice_ceil(top * 1.2)


def chart_ticks(y_max: float) -> list:
    return [round(y_max * index / 4, 6) for index in range(5)]
