"""Utilities for normalising screenshot filenames in Linux E2E runs."""

from __future__ import annotations

import re
from datetime import UTC, datetime


def normalise_slug(slug: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-") or "screenshot"


def timestamped_filename(slug: str) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{slug}.png"


__all__ = ["normalise_slug", "timestamped_filename"]

