"""Magnet URI parsing."""

import base64
import re
from urllib.parse import parse_qs, urlparse

_HEX = re.compile(r"^[0-9a-fA-F]{40}$")
_BASE32 = re.compile(r"^[A-Za-z2-7]{32}$")


class InvalidMagnet(ValueError):
    pass


def parse_magnet(uri: str) -> tuple[str, str | None]:
    """Return (infohash as lowercase hex, display name or None)."""
    uri = uri.strip()
    parsed = urlparse(uri)
    if parsed.scheme != "magnet":
        raise InvalidMagnet("not a magnet: URI")
    params = parse_qs(parsed.query)
    for xt in params.get("xt", []):
        prefix = "urn:btih:"
        if not xt.lower().startswith(prefix):
            continue
        h = xt[len(prefix):]
        if _HEX.match(h):
            return h.lower(), _first(params.get("dn"))
        if _BASE32.match(h):
            return base64.b32decode(h.upper()).hex(), _first(params.get("dn"))
    raise InvalidMagnet("magnet has no valid urn:btih infohash")


def _first(values: list[str] | None) -> str | None:
    return values[0] if values else None
