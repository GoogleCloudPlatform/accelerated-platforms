# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Shared timestamp, JSON, number/duration formatting, and Markdown table helpers."""

from __future__ import annotations

import json
import math
import os
import re
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

RFC3339_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d+)?(Z|[+-]\d{2}:\d{2})?$"
)
_MISSING = object()


def parse_rfc3339(value: str | datetime) -> datetime:
    """Parses an RFC 3339 timestamp (with arbitrary fractional digits) or datetime to UTC."""
    if isinstance(value, datetime):
        aware = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return aware.astimezone(timezone.utc)
    m = RFC3339_RE.match(value.strip())
    if not m:
        raise ValueError(f"invalid RFC 3339 timestamp: {value!r}")
    base, frac, tz = m.groups()
    tz_str = (tz or "Z").replace("Z", "+00:00")
    dt = datetime.fromisoformat(base + tz_str).astimezone(timezone.utc)
    if frac:
        dt += timedelta(seconds=float(frac))
    return dt


def epoch_seconds(value: Any, *, strict: bool = True) -> float | None:
    """Converts epoch seconds, an RFC 3339 string, or a datetime to UTC epoch seconds."""
    if value is None or value == "" or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, datetime):
        return parse_rfc3339(value).timestamp()
    if isinstance(value, str):
        m = RFC3339_RE.match(value.strip())
        if not m:
            if strict:
                raise ValueError(f"invalid RFC 3339 timestamp: {value!r}")
            return None
        base, frac, tz = m.groups()
        tz_str = (tz or "Z").replace("Z", "+00:00")
        dt = datetime.fromisoformat(base + tz_str).astimezone(timezone.utc)
        return dt.timestamp() + (float(frac) if frac else 0.0)
    return None


def load_json(path: str | os.PathLike[str], default: Any = _MISSING) -> Any:
    """Loads a UTF-8 JSON file, returning `default` if provided and the path is absent."""
    if default is not _MISSING and not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fmt_num(v: Any, digits: int = 1, *, bool_yn: bool = False) -> str:
    """Formats scalars for Markdown tables, rendering None/NaN/Inf as '-'."""
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return "-"
    if bool_yn and isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return f"{v:.{digits}f}"
    return str(v)


def fmt_duration(
    seconds: float | int | None,
    *,
    split_hours: bool = False,
    empty: str = "–",
) -> str:
    """Formats seconds as m:ss (or h:mm:ss when split_hours=True and >= 1h)."""
    if seconds is None:
        return empty
    rounded = int(round(float(seconds)))
    sign = "-" if rounded < 0 else ""
    minutes, secs = divmod(abs(rounded), 60)
    if split_hours:
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{sign}{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{sign}{minutes:d}:{secs:02d}"


def md_table(
    headers: list[str],
    rows: list[list[Any]],
    *,
    cell_fmt: Callable[[Any], str] = str,
) -> str:
    """Renders a GitHub-flavored Markdown table."""
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    lines += ["| " + " | ".join(cell_fmt(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)
