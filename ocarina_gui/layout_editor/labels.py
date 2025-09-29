"""Shared helpers for layout editor UI components."""


def friendly_label(identifier: str, fallback: str) -> str:
    """Return a user-friendly label for a hole or outline identifier."""

    text = str(identifier).strip().replace("_", " ")
    if not text:
        return fallback
    return " ".join(part.capitalize() for part in text.split())


__all__ = ["friendly_label"]
