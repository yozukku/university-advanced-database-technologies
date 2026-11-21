import json
from datetime import datetime
from decimal import Decimal
from hashlib import sha256

from bench.check.verify.canonical import NORMALISE, milliseconds

APPROX = "approx"


def value(kind, item):
    if item is None or kind == APPROX:
        return None
    if hasattr(item, "to_native"):
        item = item.to_native()
    return NORMALISE[kind](item)


def row(kinds, values):
    return [value(kind, item) for kind, item in zip(kinds, values, strict=True)]


def default(item):
    if isinstance(item, datetime):
        return milliseconds(item)
    if isinstance(item, Decimal):
        return str(item)
    if isinstance(item, (bytes, bytearray)):
        return bytes(item).hex()
    if isinstance(item, (set, frozenset)):
        return sorted(item)
    raise TypeError(f"Cannot encode {type(item).__name__}")


def encode(item):
    return json.dumps(item, ensure_ascii=False, separators=(",", ":"), sort_keys=True, default=default)


def digest(item):
    return sha256(encode(item).encode()).hexdigest()


def result(kinds, rows, ordered):
    found = [row(kinds, values) for values in rows]
    return found if ordered else sorted(found, key=encode)
