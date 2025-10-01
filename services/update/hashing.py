"""Hashing helpers for installer verification."""

from __future__ import annotations

import hashlib
from pathlib import Path

from services.update.models import UpdateError


def calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_hash_text(text: str) -> str:
    for token in text.split():
        if token:
            return token.strip()
    raise UpdateError("Hash file did not contain a digest")
