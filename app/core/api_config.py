"""Dependency-free URL policy shared by the client and Android build tooling."""

import ipaddress
import os
import re
import sys
from urllib.parse import urlsplit, urlunsplit


def is_android_runtime() -> bool:
    return (
        hasattr(sys, "getandroidapilevel")
        or sys.platform == "android"
        or os.getenv("FLET_PLATFORM", "").casefold() == "android"
    )


def normalize_api_url(value: str, *, android: bool = False, require_https: bool = False) -> str:
    """Return a backend root, accepting an optional proxy prefix and /api/v1 suffix.

    Errors deliberately omit the supplied URL, which may contain credentials.
    """
    invalid = "Use an absolute HTTP(S) backend URL without credentials, query parameters or fragments."
    try:
        if not isinstance(value, str) or not value.strip():
            raise ValueError
        value = value.strip()
        if re.search(r"[\s\\\x00-\x1f\x7f]", value) or "?" in value or "#" in value:
            raise ValueError
        parsed = urlsplit(value)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username is not None or parsed.password is not None):
            raise ValueError
        if parsed.port is not None and not 1 <= parsed.port <= 65535:
            raise ValueError
        if parsed.netloc.endswith(":"):
            raise ValueError
        host = parsed.hostname.rstrip(".").casefold()
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            labels = host.encode("idna").decode("ascii").split(".")
            if (len(host) > 253 or re.fullmatch(r"[0-9.]+", host)
                    or not all(re.fullmatch(r"(?!-)[A-Za-z0-9-]{1,63}(?<!-)", label) for label in labels)):
                raise ValueError
            loopback = host == "localhost" or host.endswith(".localhost")
        else:
            address = getattr(address, "ipv4_mapped", None) or address
            loopback = address.is_loopback or address.is_unspecified
    except (ValueError, UnicodeError):
        raise ValueError(invalid) from None
    if android and loopback:
        raise ValueError("Android requires a LAN address or a hosted HTTPS backend; loopback points to the phone.")
    if require_https and parsed.scheme != "https":
        raise ValueError("This configuration requires an HTTPS backend.")
    path = parsed.path.rstrip("/")
    if path.endswith("/api/v1"):
        path = path[:-7].rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))
