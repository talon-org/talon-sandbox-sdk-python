"""Client-side size and duration parsers for v2 API normalization."""
from __future__ import annotations

import re

# IEC binary units
_IEC_UNITS: dict[str, int] = {
    "b": 1,
    "kib": 1024,
    "mib": 1024**2,
    "gib": 1024**3,
    "tib": 1024**4,
}

# SI decimal units
_SI_UNITS: dict[str, int] = {
    "kb": 1000,
    "mb": 1_000_000,
    "gb": 1_000_000_000,
    "tb": 1_000_000_000_000,
}

_SIZE_RE = re.compile(r"^([+-]?\d+(?:\.\d+)?)\s*([a-zA-Z]*)$")

# Duration multipliers (to seconds)
_DURATION_UNITS: dict[str, float] = {
    "ms": 0.001,
    "s": 1.0,
    "m": 60.0,
    "h": 3600.0,
    "d": 86400.0,
    "w": 604800.0,
}

_DURATION_RE = re.compile(r"^([+-]?\d+(?:\.\d+)?)\s*(ms|[smhdw])?$")


def parse_size(value: int | float | str) -> int:
    """Parse a size value to bytes.

    Accepts:
    - int/float: treated as bytes
    - "1024": bare integer string, treated as bytes
    - "4GiB": IEC binary (Ki/Mi/Gi/Ti)
    - "1GB": SI decimal (K/M/G/T)

    Returns bytes as int. Raises ValueError for invalid input.
    """
    if isinstance(value, (int, float)):
        if value < 0:
            raise ValueError(f"Cannot parse size: negative value {value!r}")
        return int(value)

    s = str(value).strip()
    if not s:
        raise ValueError("Cannot parse size: empty string")

    m = _SIZE_RE.match(s)
    if not m:
        raise ValueError(f"Cannot parse size: {value!r}")

    num_str, unit = m.group(1), m.group(2).lower()
    num = float(num_str)
    if num < 0:
        raise ValueError(f"Cannot parse size: negative value {value!r}")

    if unit == "" or unit == "b":
        return int(num)

    if unit in _IEC_UNITS:
        return int(num * _IEC_UNITS[unit])

    if unit in _SI_UNITS:
        return int(num * _SI_UNITS[unit])

    raise ValueError(
        f"Cannot parse size: unknown unit {unit!r} in {value!r}. "
        f"Valid units: B, KiB, MiB, GiB, TiB, KB, MB, GB, TB"
    )


def parse_duration(value: int | float | str) -> int:
    """Parse a duration value to whole seconds.

    Accepts:
    - int/float: treated as seconds
    - "30": bare integer string, treated as seconds
    - "30s", "5m", "2h", "1d", "1w": with unit suffix
    - "500ms": milliseconds (rounds down)

    Returns whole seconds as int. Raises ValueError for invalid input.
    """
    if isinstance(value, (int, float)):
        if value < 0:
            raise ValueError(f"Cannot parse duration: negative value {value!r}")
        return int(value)

    s = str(value).strip()
    if not s:
        raise ValueError("Cannot parse duration: empty string")

    m = _DURATION_RE.match(s)
    if not m:
        raise ValueError(
            f"Cannot parse duration: {value!r}. "
            f"Valid units: ms, s, m, h, d, w"
        )

    num_str, unit = m.group(1), (m.group(2) or "s")
    num = float(num_str)
    if num < 0:
        raise ValueError(f"Cannot parse duration: negative value {value!r}")

    multiplier = _DURATION_UNITS[unit]
    return int(num * multiplier)
