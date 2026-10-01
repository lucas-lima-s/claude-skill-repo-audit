from __future__ import annotations

import base64
import re

_CHAR_CLASS_SLASHES = re.compile(r"\[/+\]\+")
_PLUS_CONCAT = re.compile(r"""(['\"])([^'\"]{1,80})\1(?:\s*\+\s*(['\"])([^'\"]{1,80})\3)+""")
_PATTERN_CALL = re.compile(r"""_pattern\(\s*((?:r?(['\"])([^'\"]*)\2\s*,\s*)+r?(['\"])([^'\"]*)\4)\s*\)""")
_PS_CHAR_ARRAY = re.compile(r"@\(\s*((?:'[^']*'\s*,\s*)+'[^']*')\s*\)")
_B64_LITERAL = re.compile(r"""['\"]([A-Za-z0-9+/]{24,}={0,2})['\"]""")
_QUOTED_STRINGS = re.compile(r"""r?(['\"])([^'\"]+)\1""")


def collapse_encoded_paths(line: str) -> str:
    collapsed = line.replace("\\", "/").lower()
    return _CHAR_CLASS_SLASHES.sub("/", collapsed)


def concatenated_strings(line: str) -> list[str]:
    blobs: list[str] = []
    for match in _PLUS_CONCAT.finditer(line):
        parts = [part[1] for part in _QUOTED_STRINGS.findall(match.group(0))]
        if len(parts) >= 2:
            blobs.append("".join(parts))
    for match in _PATTERN_CALL.finditer(line):
        parts = [part[1] for part in _QUOTED_STRINGS.findall(match.group(1))]
        if len(parts) >= 2:
            blobs.append("".join(parts))
    return blobs


def joined_char_arrays(line: str) -> list[str]:
    blobs: list[str] = []
    for match in _PS_CHAR_ARRAY.finditer(line):
        chars = re.findall(r"'([^']*)'", match.group(1))
        if len(chars) >= 4:
            blobs.append("".join(chars))
    return blobs


def decoded_base64_blobs(line: str) -> list[str]:
    blobs: list[str] = []
    for match in _B64_LITERAL.finditer(line):
        token = match.group(1)
        pad = (-len(token)) % 4
        try:
            decoded = base64.b64decode(token + ("=" * pad)).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            continue
        if decoded and decoded.isprintable():
            blobs.append(decoded)
    return blobs


def identity_blobs(line: str) -> list[str]:
    """Strings a denylist should also be matched against, beyond the raw line."""
    return concatenated_strings(line) + joined_char_arrays(line) + decoded_base64_blobs(line)
